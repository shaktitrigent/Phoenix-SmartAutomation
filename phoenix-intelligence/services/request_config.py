"""Request-local project environment parsing; never changes process settings."""

import os
import stat
from dataclasses import dataclass, field
from pathlib import Path, PureWindowsPath
from types import MappingProxyType
from typing import Mapping, Optional, Tuple

from dotenv.parser import parse_stream
from phoenix_shared.contracts.project_context import ProjectContext


@dataclass(frozen=True)
class ConfigDiagnostics:
    project_context_received: bool = True
    project_root_accessible: bool = False
    env_file_found: bool = False
    env_local_file_found: bool = False
    anthropic_key_available: bool = False
    sources: Tuple[str, ...] = ("process_environment",)
    reason: Optional[str] = None


@dataclass(frozen=True)
class RequestConfig:
    # Suppress values from repr as well as all diagnostics and logging.
    values: Mapping[str, str] = field(repr=False)
    diagnostics: ConfigDiagnostics

    def __post_init__(self):
        object.__setattr__(self, "values", MappingProxyType(dict(self.values)))


class _InvalidPath(Exception):
    """Only fixed, non-sensitive reason codes may be passed to this exception."""


def _native_path(value: str) -> Path:
    windows = PureWindowsPath(value)
    if os.name != "nt" and (windows.drive or "\\" in value):
        raise _InvalidPath("client_path_platform_unavailable")
    if os.name == "nt" and (windows.root or windows.drive) and not windows.is_absolute():
        raise _InvalidPath("client_path_platform_unavailable")
    path = Path(value)
    if not value or "\x00" in value:
        raise _InvalidPath("invalid_path")
    if ".." in path.parts:
        raise _InvalidPath("path_traversal_rejected")
    return path


def _inside_root(root: Path, path: Path) -> Path:
    candidate = path if path.is_absolute() else root / path
    resolved = candidate.resolve()
    try:
        resolved.relative_to(root)
    except ValueError:
        raise _InvalidPath("environment_path_outside_project") from None
    return resolved


def _read_file(path: Path):
    try:
        metadata = path.stat()
    except FileNotFoundError:
        return {}, False, False
    if not stat.S_ISREG(metadata.st_mode):
        raise _InvalidPath("environment_path_not_file")
    values = {}
    malformed = False
    # parse_stream handles quoting/escapes/= without printing malformed content
    # or interpolating against ambient os.environ. Bare keys are not overrides.
    with path.open("r", encoding="utf-8-sig") as stream:
        for binding in parse_stream(stream):
            malformed |= binding.error
            if not binding.error and binding.key is not None and binding.value is not None:
                values[binding.key] = binding.value
    return values, True, malformed


def load_request_config(context: Optional[ProjectContext]) -> Optional[RequestConfig]:
    """Merge .env < process snapshot < local file, with no global side effects.

    Absent context preserves the legacy call path. Invalid/unavailable paths
    yield a process-only snapshot and a fixed reason, never raw exception text.
    No variable interpolation is performed; values are parsed literally.
    """
    if context is None:
        return None
    process = dict(os.environ)
    accessible = False
    try:
        root = _native_path(context.project_root)
        if not root.is_absolute():
            raise _InvalidPath("project_root_not_absolute")
        root = root.resolve(strict=True)
        if not root.is_dir():
            raise _InvalidPath("project_root_not_directory")
        accessible = True
        # Validate BOTH paths before reading either file. Absolute local paths
        # emitted by Phase 1 are supported only when contained in this root.
        base_path = _inside_root(root, Path(".env"))
        local_path = _inside_root(root, _native_path(context.environment_file))
        if local_path == base_path:
            raise _InvalidPath("environment_file_duplicates_base")
        base, base_found, base_malformed = _read_file(base_path)
        local, local_found, local_malformed = _read_file(local_path)
    except _InvalidPath as exc:
        reason = str(exc)
    except (OSError, ValueError, RuntimeError, UnicodeError):
        reason = "environment_file_unavailable" if accessible else "project_root_unavailable"
    else:
        merged = {**base, **process, **local}
        sources = (("project_env",) if base_found else ()) + ("process_environment",)
        if local_found:
            sources += ("project_env_local",)
        return RequestConfig(merged, ConfigDiagnostics(
            project_root_accessible=True,
            env_file_found=base_found,
            env_local_file_found=local_found,
            anthropic_key_available=bool(merged.get("ANTHROPIC_API_KEY")),
            sources=sources,
            reason="malformed_environment_lines_ignored" if base_malformed or local_malformed else None,
        ))
    return RequestConfig(process, ConfigDiagnostics(
        project_root_accessible=accessible,
        anthropic_key_available=bool(process.get("ANTHROPIC_API_KEY")),
        reason=reason,
    ))

"""PackageAdapter — runs phoenix from pre-built wheels and the bundled exe."""
from __future__ import annotations

import glob
import shutil
import subprocess
import sys
import time
from pathlib import Path
from typing import List, Optional

from preflight.adapters.base import CliResult, TargetAdapter


def _venv_python(venv_dir: Path) -> Path:
    """Return the Python executable path inside a venv (cross-platform)."""
    if sys.platform == "win32":
        return venv_dir / "Scripts" / "python.exe"
    return venv_dir / "bin" / "python"


def _latest_wheel(wheel_dir: Path, name_glob: str) -> Path:
    """Return the newest wheel matching *name_glob* in wheel_dir."""
    matches = sorted(wheel_dir.glob(name_glob), key=lambda p: p.stat().st_mtime, reverse=True)
    if not matches:
        raise FileNotFoundError(
            f"No wheel matching '{name_glob}' found in {wheel_dir}"
        )
    return matches[0]


class PackageAdapter(TargetAdapter):
    """Install from pre-built wheels; launch the bundled exe as the server."""

    def __init__(
        self,
        config: dict,
        repo_root: Path,
        wheel_dir: Optional[Path] = None,
    ) -> None:
        self._config = config
        self._repo_root = repo_root
        self._port: int = int(config.get("intelligence_server_port", 8001))
        self._wheel_dir: Path = wheel_dir or (repo_root / config["paths"]["dist_dir"])
        # Resolve relative dist path
        if not self._wheel_dir.is_absolute():
            self._wheel_dir = (repo_root / self._wheel_dir).resolve()

        self._preflight_dir: Path = repo_root / "preflight"
        self._venv_dir: Path = self._preflight_dir / "_venvs" / "package"
        self._python: Path = _venv_python(self._venv_dir)
        self._proc: subprocess.Popen | None = None

    # ------------------------------------------------------------------
    # TargetAdapter implementation
    # ------------------------------------------------------------------

    def setup(self) -> None:
        """Create a fresh venv and install packaged wheels."""
        if self._venv_dir.exists():
            shutil.rmtree(self._venv_dir)

        self._venv_dir.mkdir(parents=True, exist_ok=True)

        subprocess.run(
            [sys.executable, "-m", "venv", str(self._venv_dir)],
            check=True,
        )

        pip = self._python.parent / ("pip.exe" if sys.platform == "win32" else "pip")

        subprocess.run(
            [str(self._python), "-m", "pip", "install", "--upgrade", "pip"],
            check=True,
        )

        # Install the shared and core wheels (latest versions in dist/)
        shared_wheel = _latest_wheel(self._wheel_dir, "phoenix_shared-*.whl")
        core_wheel = _latest_wheel(self._wheel_dir, "phoenix_core-*.whl")

        subprocess.run(
            [str(pip), "install", str(shared_wheel), str(core_wheel)],
            check=True,
        )

        # Extra test/runtime dependencies
        extras = [
            "playwright",
            "pytest-playwright",
            "pytest",
        ]
        subprocess.run(
            [str(pip), "install"] + extras,
            check=True,
        )

        # Install Playwright browsers
        subprocess.run(
            [str(self._python), "-m", "playwright", "install", "--with-deps", "chromium"],
            check=True,
        )

    def start_server(self) -> None:
        """Launch the bundled phoenix-intelligence executable."""
        exe_candidates = list(self._wheel_dir.glob("phoenix-intelligence*.exe"))
        if not exe_candidates:
            # Fallback: look for an exe without extension (Linux/macOS bundle)
            exe_candidates = list(self._wheel_dir.glob("phoenix-intelligence*"))
            exe_candidates = [p for p in exe_candidates if not p.suffix or p.suffix not in (".whl", ".tar", ".gz")]

        if not exe_candidates:
            raise FileNotFoundError(
                f"phoenix-intelligence executable not found in {self._wheel_dir}"
            )

        exe = sorted(exe_candidates, key=lambda p: p.stat().st_mtime, reverse=True)[0]
        self._proc = subprocess.Popen(
            [str(exe), "--port", str(self._port)],
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
        )

    def stop_server(self) -> None:
        """Terminate the server process, waiting up to 5 s before killing."""
        if self._proc is None:
            return
        self._proc.terminate()
        try:
            self._proc.wait(timeout=5)
        except subprocess.TimeoutExpired:
            self._proc.kill()
            self._proc.wait()
        self._proc = None

    def health_url(self) -> str:
        return f"http://localhost:{self._port}/health"

    def api_base_url(self) -> str:
        return f"http://localhost:{self._port}/api/v1"

    def run_cli(self, args: List[str], cwd: str) -> CliResult:
        """Run phoenix CLI via the venv's python -m phoenix.cli.main."""
        cmd = [str(self._python), "-m", "phoenix.cli.main"] + args
        t0 = time.perf_counter()
        result = subprocess.run(
            cmd,
            cwd=cwd,
            capture_output=True,
            text=True,
        )
        duration = time.perf_counter() - t0
        return CliResult(
            exit_code=result.returncode,
            stdout=result.stdout,
            stderr=result.stderr,
            duration_s=duration,
        )

    def teardown(self) -> None:
        """Stop server and remove the venv."""
        self.stop_server()
        if self._venv_dir.exists():
            shutil.rmtree(self._venv_dir, ignore_errors=True)

    # ------------------------------------------------------------------
    # Helpers accessible from stages
    # ------------------------------------------------------------------

    @property
    def python_exe(self) -> str:
        return str(self._python)

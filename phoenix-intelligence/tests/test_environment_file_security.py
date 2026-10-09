"""Deterministic filesystem races, handle ownership, and request isolation."""

from concurrent.futures import ThreadPoolExecutor
import ctypes
import hashlib
import json
import logging
import os
from pathlib import Path
import sys
from threading import Barrier
from unittest.mock import Mock

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from phoenix_shared.contracts.project_context import ProjectContext
from services import environment_files as ef, request_config as rc


def context(root):
    return ProjectContext(project_root=str(root), environment_file=".env.local",
                          page_name="login", locator_directory=str(root / "locators"))


def directory_link(link, target):
    if os.name == "nt":
        import _winapi
        _winapi.CreateJunction(str(target), str(link))
    else:
        link.symlink_to(target, target_is_directory=True)


def file_link(link, target):
    try:
        link.symlink_to(target)
    except OSError as exc:
        if os.name == "nt" and exc.winerror == 1314:
            pytest.skip("Windows file symlinks require Developer Mode or symlink privilege")
        raise


def assert_fallback(result):
    assert result.diagnostics.project_root_accessible
    assert not result.diagnostics.project_environment_loaded
    assert result.diagnostics.fallback_to_process_only
    assert result.diagnostics.reason is not None
    assert result.diagnostics.sources == ("process_environment",)
    assert dict(result.values) == dict(os.environ)


@pytest.mark.parametrize("replacement", ["file_symlink", "directory_reparse", "ancestor"])
@pytest.mark.parametrize("race", [False, True])
def test_escape_rejected_before_content_read(tmp_path, monkeypatch, capfd, caplog, replacement, race):
    if replacement == "ancestor" and not race:
        # This case tests component rejection directly; initial root aliases
        # are otherwise intentionally canonicalized by the project resolver.
        replacement = "directory_reparse"
    root, outside = tmp_path / "project", tmp_path / "outside"
    root.mkdir()
    outside.mkdir()
    secret = "unique-outside-race-secret-93751"
    target = outside / ".env"
    target.write_text(f"ESCAPE_SENTINEL={secret}\n")
    (root / ".env").write_text("LOCAL_VALUE=original\n")
    original_read = rc._read_file
    parser = Mock(wraps=rc.parse_stream)
    monkeypatch.setattr(rc, "parse_stream", parser)
    caplog.set_level(logging.DEBUG)

    def replace():
        if replacement == "ancestor":
            root.rename(tmp_path / "original-project")
            directory_link(root, outside)
        else:
            (root / ".env").unlink()
            if replacement == "file_symlink":
                file_link(root / ".env", target)
            else:
                directory_link(root / ".env", outside)

    if race:
        # The loader has completed preliminary root/containment checks. The
        # actual handle opener has not run yet. Replace the target right here.
        def raced_read(project, name):
            replace()
            return original_read(project, name)
        monkeypatch.setattr(rc, "_read_file", raced_read)
    else:
        replace()
    result = rc.load_request_config(context(root))
    assert_fallback(result)
    parser.assert_not_called()
    assert "ESCAPE_SENTINEL" not in result.values
    output = capfd.readouterr()
    assert secret not in output.out + output.err + caplog.text + repr(result)


def test_existing_ancestor_link_rejected_by_handle_opener(tmp_path):
    outside = tmp_path / "outside"
    outside.mkdir()
    (outside / ".env").write_text("KEY=outside-secret")
    alias = tmp_path / "alias"
    directory_link(alias, outside)
    with pytest.raises(ef.UnsafeEnvironmentFile):
        with ef.open_environment(alias, ".env"):
            pytest.fail("must not expose a stream through a reparse/symlink ancestor")


@pytest.mark.parametrize("fail_parser", [False, True])
def test_parse_uses_validated_descriptor_and_closes_it(tmp_path, monkeypatch, fail_parser):
    (tmp_path / ".env").write_text("BASE_ONLY=base\n")
    (tmp_path / ".env.local").write_text("LOCAL_ONLY=local\n")
    original_parse = rc.parse_stream
    streams, descriptors = [], []
    handles = []
    validated = []
    if os.name == "nt":
        import msvcrt
        original_open = ef._windows_open
        original_validate = ef._windows_validate

        def opened(*args):
            handle = original_open(*args)
            handles.append(handle)
            return handle

        def validate(api, handle, expected, directory):
            original_validate(api, handle, expected, directory)
            if not directory:
                validated.append(handle)

        monkeypatch.setattr(ef, "_windows_open", opened)
        monkeypatch.setattr(ef, "_windows_validate", validate)
    else:
        original_open = os.open
        original_validate = ef._validate_posix

        def opened(*args, **kwargs):
            fd = original_open(*args, **kwargs)
            handles.append(fd)
            return fd

        def validate(chain, root_fd, fd, name):
            original_validate(chain, root_fd, fd, name)
            validated.append(fd)

        monkeypatch.setattr(os, "open", opened)
        monkeypatch.setattr(ef, "_validate_posix", validate)

    def parse(stream):
        streams.append(stream)
        descriptors.append(stream.fileno())
        identity = msvcrt.get_osfhandle(stream.fileno()) if os.name == "nt" else stream.fileno()
        assert identity == validated[-1]
        os.fstat(stream.fileno())
        if fail_parser:
            raise UnicodeError("synthetic-private-parser-message")
        return original_parse(stream)

    monkeypatch.setattr(rc, "parse_stream", parse)
    # Neither validation nor parsing may reopen a pathname with Path.open.
    monkeypatch.setattr(Path, "open", Mock(side_effect=AssertionError("pathname reopened")))
    result = rc.load_request_config(context(tmp_path))
    assert streams
    assert all(stream.closed for stream in streams)
    for fd in descriptors:
        with pytest.raises(OSError):
            os.fstat(fd)
    assert handles
    for handle in handles:
        if os.name == "nt":
            ctypes.set_last_error(0)
            assert ef._windows_api().GetFileType(handle) == 0
            assert ctypes.get_last_error() == 6
        else:
            with pytest.raises(OSError):
                os.fstat(handle)
    if fail_parser:
        assert_fallback(result)
        assert "synthetic-private" not in repr(result)
    else:
        assert result.values["BASE_ONLY"] == "base"
        assert result.values["LOCAL_ONLY"] == "local"
        assert result.diagnostics.project_environment_loaded
        assert not result.diagnostics.fallback_to_process_only


def test_handles_closed_on_validation_failure(tmp_path, monkeypatch):
    (tmp_path / ".env").write_text("KEY=never-read")
    handles = []
    if os.name == "nt":
        original_open = ef._windows_open
        original_validate = ef._windows_validate

        def opened(*args):
            handle = original_open(*args)
            handles.append(handle)
            return handle

        def validate(api, handle, expected, directory):
            if not directory:
                raise ef.UnsafeEnvironmentFile("environment_target_changed")
            return original_validate(api, handle, expected, directory)

        monkeypatch.setattr(ef, "_windows_open", opened)
        monkeypatch.setattr(ef, "_windows_validate", validate)
    else:
        original_open = os.open

        def opened(*args, **kwargs):
            fd = original_open(*args, **kwargs)
            handles.append(fd)
            return fd

        monkeypatch.setattr(os, "open", opened)
        monkeypatch.setattr(ef, "_validate_posix", Mock(side_effect=ef.UnsafeEnvironmentFile("environment_target_changed")))
    assert_fallback(rc.load_request_config(context(tmp_path)))
    assert handles
    for handle in handles:
        if os.name == "nt":
            # Native GetFileType returns FILE_TYPE_UNKNOWN + INVALID_HANDLE.
            ctypes.set_last_error(0)
            assert ef._windows_api().GetFileType(handle) == 0
            assert ctypes.get_last_error() == 6
        else:
            with pytest.raises(OSError):
                os.fstat(handle)


def test_generator_does_not_log_manual_step_values(caplog):
    from services.agents.test_generator import (
        _apply_explicit_locator_fixes,
        _extract_fill_target_and_value,
    )

    secret = "manual-step-secret-sentinel-51827"
    step = {"action": f"Enter '{secret}' in the Username field (id='user-name')"}
    caplog.set_level(logging.DEBUG, logger="services.agents.test_generator")
    _extract_fill_target_and_value(step["action"])
    _apply_explicit_locator_fixes("def test_login():\n    pass\n", {"steps": [step]})

    assert secret not in caplog.text


@pytest.mark.skipif(os.name == "nt", reason="POSIX descriptor-relative race")
def test_posix_ancestor_replaced_after_open(tmp_path, monkeypatch):
    root, outside = tmp_path / "project", tmp_path / "outside"
    root.mkdir()
    outside.mkdir()
    (root / ".env").write_text("ORIGINAL=inside")
    (outside / ".env").write_text("ESCAPE_SENTINEL=posix-race-secret")
    original_validate = ef._validate_posix

    def validate(*args):
        root.rename(tmp_path / "moved")
        root.symlink_to(outside, target_is_directory=True)
        original_validate(*args)

    monkeypatch.setattr(ef, "_validate_posix", validate)
    parser = Mock(side_effect=AssertionError("must reject before parsing"))
    monkeypatch.setattr(rc, "parse_stream", parser)
    assert_fallback(rc.load_request_config(context(root)))
    parser.assert_not_called()


@pytest.mark.parametrize("process_has_key", [False, True])
def test_sequential_exclusive_keys(tmp_path, monkeypatch, process_has_key):
    monkeypatch.delenv("A_ONLY_KEY", raising=False)
    if process_has_key:
        monkeypatch.setenv("A_ONLY_KEY", "independent-process-value")
    a, b = tmp_path / "a", tmp_path / "b"
    a.mkdir()
    b.mkdir()
    (a / ".env.local").write_text("A_ONLY_KEY=project-a-value")
    first = rc.load_request_config(context(a))
    second = rc.load_request_config(context(b))
    assert first.values["A_ONLY_KEY"] == "project-a-value"
    if process_has_key:
        assert second.values["A_ONLY_KEY"] == "independent-process-value"
    else:
        assert "A_ONLY_KEY" not in second.values


def test_synchronized_requests_do_not_leak(tmp_path, monkeypatch):
    from api import server
    settings = (server._llm_settings, server._mcp_settings)
    before_settings = [vars(item).copy() for item in settings]
    before_clients = (server._llm_client, server._mcp_client)
    for key in ("A_ONLY_KEY", "B_ONLY_KEY", "REQUEST_VALUE"):
        monkeypatch.delenv(key, raising=False)
    monkeypatch.setenv("COMMON_PROCESS", "common")
    before_env = hashlib.sha256(json.dumps(dict(os.environ), sort_keys=True).encode()).digest()
    roots = [tmp_path / "a", tmp_path / "b"]
    for root, key in zip(roots, ("A_ONLY_KEY", "B_ONLY_KEY")):
        root.mkdir()
        (root / ".env.local").write_text(f"REQUEST_VALUE={root.name}\n{key}={root.name}")
    barrier = Barrier(2)
    original_read = rc._read_file

    def read(root, name):
        if name == ".env.local":
            barrier.wait(timeout=10)
        return original_read(root, name)

    monkeypatch.setattr(rc, "_read_file", read)
    with ThreadPoolExecutor(max_workers=2) as pool:
        a, b = list(pool.map(rc.load_request_config, map(context, roots)))
    assert a.values["REQUEST_VALUE"] == a.values["A_ONLY_KEY"] == "a"
    assert b.values["REQUEST_VALUE"] == b.values["B_ONLY_KEY"] == "b"
    assert "B_ONLY_KEY" not in a.values
    assert "A_ONLY_KEY" not in b.values
    assert a.values["COMMON_PROCESS"] == b.values["COMMON_PROCESS"] == "common"
    assert hashlib.sha256(json.dumps(dict(os.environ), sort_keys=True).encode()).digest() == before_env
    assert [vars(item) for item in settings] == before_settings
    assert (server._llm_client, server._mcp_client) == before_clients


@pytest.mark.skipif(os.name != "nt", reason="Windows directory sharing semantics")
def test_windows_ancestors_cannot_be_renamed_while_parsing(tmp_path):
    (tmp_path / ".env").write_text("NORMAL=inside")
    with ef.open_environment(tmp_path, ".env") as stream:
        with pytest.raises(PermissionError):
            tmp_path.rename(tmp_path.parent / "renamed-project")
        with pytest.raises(PermissionError):
            (tmp_path / ".env").unlink()
        assert stream.read() == "NORMAL=inside"


@pytest.mark.skipif(os.name == "nt", reason="POSIX permits renaming an open file")
def test_posix_parser_keeps_original_handle_after_name_replacement(tmp_path, monkeypatch):
    (tmp_path / ".env").write_text("NORMAL=original")
    original_parse = rc.parse_stream

    def parse(stream):
        if not (tmp_path / "saved").exists():
            (tmp_path / ".env").rename(tmp_path / "saved")
            (tmp_path / ".env").write_text("ESCAPE_SENTINEL=replacement-secret")
        return original_parse(stream)

    monkeypatch.setattr(rc, "parse_stream", parse)
    result = rc.load_request_config(context(tmp_path))
    assert result.values["NORMAL"] == "original"
    assert "ESCAPE_SENTINEL" not in result.values

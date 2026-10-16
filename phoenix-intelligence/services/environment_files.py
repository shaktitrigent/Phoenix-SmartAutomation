"""Handle-based environment reads. No path or OS error details escape this module."""

from contextlib import contextmanager, ExitStack
import os
from pathlib import Path
import stat


class UnsafeEnvironmentFile(Exception):
    pass


def _identity(metadata):
    return metadata.st_dev, metadata.st_ino


def _validate_posix(chain, root_fd, fd, name):
    if not stat.S_ISREG(os.fstat(fd).st_mode):
        raise UnsafeEnvironmentFile("environment_path_not_file")
    # Validate each opened directory against its retained parent, not a fresh
    # absolute-path traversal. This detects ancestor replacement/renaming.
    for parent, child, component in chain:
        current = os.stat(component, dir_fd=parent, follow_symlinks=False)
        if not stat.S_ISDIR(current.st_mode) or _identity(current) != _identity(os.fstat(child)):
            raise UnsafeEnvironmentFile("environment_target_changed")
    current = os.stat(name, dir_fd=root_fd, follow_symlinks=False)
    if not stat.S_ISREG(current.st_mode) or _identity(current) != _identity(os.fstat(fd)):
        raise UnsafeEnvironmentFile("environment_target_changed")


@contextmanager
def _posix_stream(root, name):
    flags = os.O_RDONLY | os.O_DIRECTORY | os.O_NOFOLLOW
    with ExitStack() as stack:
        parent = os.open(root.anchor, flags)
        stack.callback(os.close, parent)
        chain = []
        for component in root.parts[1:]:
            child = os.open(component, flags, dir_fd=parent)
            stack.callback(os.close, child)
            chain.append((parent, child, component))
            parent = child
        # NONBLOCK prevents an attacker-controlled FIFO from blocking open.
        try:
            fd = os.open(name, os.O_RDONLY | os.O_NOFOLLOW | os.O_NONBLOCK, dir_fd=parent)
        except FileNotFoundError:
            yield None
            return
        stack.callback(os.close, fd)
        _validate_posix(chain, parent, fd, name)
        with os.fdopen(fd, "r", encoding="utf-8-sig", closefd=False) as stream:
            yield stream


def _windows_api():
    import ctypes
    from ctypes import wintypes

    api = ctypes.WinDLL("kernel32", use_last_error=True)
    api.CreateFileW.argtypes = [wintypes.LPCWSTR, wintypes.DWORD, wintypes.DWORD,
                               wintypes.LPVOID, wintypes.DWORD, wintypes.DWORD, wintypes.HANDLE]
    api.CreateFileW.restype = wintypes.HANDLE
    api.CloseHandle.argtypes = [wintypes.HANDLE]
    api.CloseHandle.restype = wintypes.BOOL
    api.GetFinalPathNameByHandleW.argtypes = [wintypes.HANDLE, wintypes.LPWSTR, wintypes.DWORD, wintypes.DWORD]
    api.GetFinalPathNameByHandleW.restype = wintypes.DWORD
    api.GetFileInformationByHandleEx.argtypes = [wintypes.HANDLE, ctypes.c_int, wintypes.LPVOID, wintypes.DWORD]
    api.GetFileInformationByHandleEx.restype = wintypes.BOOL
    api.GetFileType.argtypes = [wintypes.HANDLE]
    api.GetFileType.restype = wintypes.DWORD
    return api


def _windows_open(api, path, directory):
    import ctypes

    # OPEN_REPARSE_POINT applies to the final component; callers separately
    # open/check/retain EVERY ancestor. No FILE_SHARE_DELETE on any handle.
    handle = api.CreateFileW(str(path), 0x80 if directory else 0x80000000,
                             3 if directory else 1, None, 3, 0x02200000, None)
    if handle == ctypes.c_void_p(-1).value:
        error = ctypes.get_last_error()
        if error == 2:
            raise FileNotFoundError()
        raise UnsafeEnvironmentFile("environment_handle_unavailable")
    return handle


def _windows_path(api, handle):
    import ctypes

    size = api.GetFinalPathNameByHandleW(handle, None, 0, 0)
    if not size:
        raise UnsafeEnvironmentFile("environment_handle_validation_failed")
    buffer = ctypes.create_unicode_buffer(size + 1)
    actual = api.GetFinalPathNameByHandleW(handle, buffer, len(buffer), 0)
    if not actual or actual >= len(buffer):
        raise UnsafeEnvironmentFile("environment_handle_validation_failed")
    value = buffer.value
    if value.startswith("\\\\?\\UNC\\"):
        value = "\\\\" + value[8:]
    elif value.startswith("\\\\?\\"):
        value = value[4:]
    return Path(value)


def _windows_validate(api, handle, expected, directory):
    import ctypes
    from ctypes import wintypes

    class AttributeTagInfo(ctypes.Structure):
        _fields_ = [("attributes", wintypes.DWORD), ("tag", wintypes.DWORD)]

    info = AttributeTagInfo()
    if not api.GetFileInformationByHandleEx(handle, 9, ctypes.byref(info), ctypes.sizeof(info)):
        raise UnsafeEnvironmentFile("environment_handle_validation_failed")
    if info.attributes & 0x400:  # FILE_ATTRIBUTE_REPARSE_POINT
        raise UnsafeEnvironmentFile("environment_reparse_point_rejected")
    if bool(info.attributes & 0x10) != directory or api.GetFileType(handle) != 1:
        raise UnsafeEnvironmentFile("environment_path_not_file")
    # Equality is stricter than containment because only direct approved files
    # are permitted. The result comes from the opened handle, not Path.resolve.
    if _windows_path(api, handle) != expected:
        raise UnsafeEnvironmentFile("environment_target_changed")


@contextmanager
def _windows_stream(root, name):
    import msvcrt

    api = _windows_api()
    with ExitStack() as stack:
        path = Path(root.anchor)
        for component in (None, *root.parts[1:]):
            if component is not None:
                path /= component
            handle = _windows_open(api, path, True)
            stack.callback(api.CloseHandle, handle)
            _windows_validate(api, handle, path, True)
        try:
            handle = _windows_open(api, root / name, False)
        except FileNotFoundError:
            yield None
            return
        # Transfer ownership to a CRT descriptor only AFTER validation.
        try:
            _windows_validate(api, handle, root / name, False)
            fd = msvcrt.open_osfhandle(handle, os.O_RDONLY)
        except BaseException:
            api.CloseHandle(handle)
            raise
        stack.callback(os.close, fd)
        if not stat.S_ISREG(os.fstat(fd).st_mode):
            raise UnsafeEnvironmentFile("environment_path_not_file")
        with os.fdopen(fd, "r", encoding="utf-8-sig", closefd=False) as stream:
            yield stream


@contextmanager
def open_environment(root, name):
    """Yield a validated stream or None for a missing approved file."""
    if name not in (".env", ".env.local"):
        raise UnsafeEnvironmentFile("environment_filename_not_allowed")
    implementation = _windows_stream if os.name == "nt" else _posix_stream
    try:
        with implementation(root, name) as stream:
            yield stream
    except (OSError, ValueError):
        raise UnsafeEnvironmentFile("environment_handle_unavailable") from None

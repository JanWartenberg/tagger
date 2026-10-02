"""A real Windows sharing lock: allow reads, deny writes and deletion."""

from collections.abc import Iterator
from contextlib import contextmanager
import ctypes
from ctypes import wintypes
import os
from pathlib import Path


@contextmanager
def read_only_sharing_lock(path: Path) -> Iterator[None]:
    if os.name != "nt":
        raise RuntimeError("Sharing-lock acceptance requires Windows")
    api = ctypes.WinDLL("kernel32", use_last_error=True)
    api.CreateFileW.argtypes = [
        wintypes.LPCWSTR,
        wintypes.DWORD,
        wintypes.DWORD,
        ctypes.c_void_p,
        wintypes.DWORD,
        wintypes.DWORD,
        wintypes.HANDLE,
    ]
    api.CreateFileW.restype = wintypes.HANDLE
    api.CloseHandle.argtypes = [wintypes.HANDLE]
    api.CloseHandle.restype = wintypes.BOOL
    invalid = ctypes.c_void_p(-1).value
    # GENERIC_READ, FILE_SHARE_READ, OPEN_EXISTING, FILE_ATTRIBUTE_NORMAL.
    handle = api.CreateFileW(str(path), 0x80000000, 1, None, 3, 0x80, None)
    if handle == invalid:
        raise ctypes.WinError(ctypes.get_last_error())
    try:
        # Prove an actual sharing violation rather than relying on permissions.
        writer = api.CreateFileW(str(path), 0x40000000, 7, None, 3, 0x80, None)
        error = ctypes.get_last_error()
        if writer != invalid:
            api.CloseHandle(writer)
            raise AssertionError("Sharing lock unexpectedly permits writes")
        if error != 32:  # ERROR_SHARING_VIOLATION
            raise ctypes.WinError(error)
        yield
    finally:
        if not api.CloseHandle(handle):
            raise ctypes.WinError(ctypes.get_last_error())

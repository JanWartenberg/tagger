"""Windows Job Object containment for acceptance children and descendants."""

import ctypes
from ctypes import wintypes
import os
import signal
import subprocess
import sys
import time


class _BasicLimits(ctypes.Structure):
    _fields_ = [
        ("PerProcessUserTimeLimit", ctypes.c_longlong),
        ("PerJobUserTimeLimit", ctypes.c_longlong),
        ("LimitFlags", wintypes.DWORD),
        ("MinimumWorkingSetSize", ctypes.c_size_t),
        ("MaximumWorkingSetSize", ctypes.c_size_t),
        ("ActiveProcessLimit", wintypes.DWORD),
        ("Affinity", ctypes.c_size_t),
        ("PriorityClass", wintypes.DWORD),
        ("SchedulingClass", wintypes.DWORD),
    ]


class _IoCounters(ctypes.Structure):
    _fields_ = [
        (name, ctypes.c_ulonglong)
        for name in (
            "ReadOperationCount",
            "WriteOperationCount",
            "OtherOperationCount",
            "ReadTransferCount",
            "WriteTransferCount",
            "OtherTransferCount",
        )
    ]


class _ExtendedLimits(ctypes.Structure):
    _fields_ = [
        ("BasicLimitInformation", _BasicLimits),
        ("IoInfo", _IoCounters),
        ("ProcessMemoryLimit", ctypes.c_size_t),
        ("JobMemoryLimit", ctypes.c_size_t),
        ("PeakProcessMemoryUsed", ctypes.c_size_t),
        ("PeakJobMemoryUsed", ctypes.c_size_t),
    ]


class _Accounting(ctypes.Structure):
    _fields_ = [
        ("TotalUserTime", ctypes.c_longlong),
        ("TotalKernelTime", ctypes.c_longlong),
        ("ThisPeriodTotalUserTime", ctypes.c_longlong),
        ("ThisPeriodTotalKernelTime", ctypes.c_longlong),
        ("TotalPageFaultCount", wintypes.DWORD),
        ("TotalProcesses", wintypes.DWORD),
        ("ActiveProcesses", wintypes.DWORD),
        ("TotalTerminatedProcesses", wintypes.DWORD),
    ]


class WindowsJob:
    """Own a non-inheritable kill-on-close job; fail closed if assignment fails."""

    def __init__(self):
        if os.name != "nt":
            raise RuntimeError("Windows Job Objects require Windows")
        self.api = ctypes.WinDLL("kernel32", use_last_error=True)
        signatures = {
            "CreateJobObjectW": ([ctypes.c_void_p, wintypes.LPCWSTR], wintypes.HANDLE),
            "SetInformationJobObject": (
                [wintypes.HANDLE, ctypes.c_int, ctypes.c_void_p, wintypes.DWORD],
                wintypes.BOOL,
            ),
            "QueryInformationJobObject": (
                [
                    wintypes.HANDLE,
                    ctypes.c_int,
                    ctypes.c_void_p,
                    wintypes.DWORD,
                    ctypes.c_void_p,
                ],
                wintypes.BOOL,
            ),
            "AssignProcessToJobObject": (
                [wintypes.HANDLE, wintypes.HANDLE],
                wintypes.BOOL,
            ),
            "OpenProcess": (
                [wintypes.DWORD, wintypes.BOOL, wintypes.DWORD],
                wintypes.HANDLE,
            ),
            "TerminateJobObject": ([wintypes.HANDLE, wintypes.UINT], wintypes.BOOL),
            "CloseHandle": ([wintypes.HANDLE], wintypes.BOOL),
        }
        for name, (args, result) in signatures.items():
            function = getattr(self.api, name)
            function.argtypes = args
            function.restype = result
        self.handle = self.api.CreateJobObjectW(None, None)
        self._check(self.handle)
        limits = _ExtendedLimits()
        limits.BasicLimitInformation.LimitFlags = 0x2000  # KILL_ON_JOB_CLOSE
        try:
            self._check(
                self.api.SetInformationJobObject(
                    self.handle, 9, ctypes.byref(limits), ctypes.sizeof(limits)
                )
            )
        except BaseException:
            self.close()
            raise

    @staticmethod
    def _check(result):
        if not result:
            raise ctypes.WinError(ctypes.get_last_error())

    def assign(self, pid):
        # SET_QUOTA | TERMINATE, the documented assignment access requirements.
        process = self.api.OpenProcess(0x0100 | 0x0001, False, pid)
        self._check(process)
        try:
            self._check(self.api.AssignProcessToJobObject(self.handle, process))
        finally:
            self._check(self.api.CloseHandle(process))

    def active_processes(self):
        accounting = _Accounting()
        self._check(
            self.api.QueryInformationJobObject(
                self.handle,
                1,
                ctypes.byref(accounting),
                ctypes.sizeof(accounting),
                None,
            )
        )
        return accounting.ActiveProcesses

    def terminate(self):
        self._check(self.api.TerminateJobObject(self.handle, 1))
        deadline = time.monotonic() + 15
        while self.active_processes():
            if time.monotonic() >= deadline:
                raise TimeoutError("Windows job still contains live processes")
            time.sleep(0.02)

    def close(self):
        if self.handle:
            self._check(self.api.CloseHandle(self.handle))
            self.handle = None


def start_child(script, **kwargs):
    """Gate Windows script execution until its job assignment succeeds.

    If the runner dies before assignment, its pipe closes and the gated child
    exits without running the scenario or starting any descendants.
    """
    job = WindowsJob() if os.name == "nt" else None
    child = None
    try:
        if job:
            gate = (
                "import sys, runpy, pathlib; "
                "token = sys.stdin.buffer.read(1); "
                "sys.exit(125) if token != b'G' else None; "
                "sys.argv = sys.argv[1:]; "
                "sys.path.insert(0, str(pathlib.Path(sys.argv[0]).resolve().parent)); "
                "runpy.run_path(sys.argv[0], run_name='__main__')"
            )
            child = subprocess.Popen(
                [sys.executable, "-c", gate, str(script)],
                stdin=subprocess.PIPE,
                **kwargs,
            )
            job.assign(child.pid)
            assert child.stdin is not None  # Popen was constructed with stdin=PIPE.
            child.stdin.write(b"G")
            child.stdin.close()
            child.stdin = None
        else:
            child = subprocess.Popen(
                [sys.executable, str(script)], start_new_session=True, **kwargs
            )
        return child, job
    except BaseException:
        if child is not None:
            child.kill()
            child.wait(timeout=15)
        raise
    finally:
        if job and (child is None or child.stdin is not None):
            job.close()


def stop_child(child, job):
    """Terminate descendants even if their immediate parent has already exited."""
    try:
        if sys.platform == "win32":
            if job is None:
                raise RuntimeError("Windows child has no containment job")
            job.terminate()
        else:
            try:
                os.killpg(child.pid, signal.SIGKILL)
            except ProcessLookupError:
                pass
        child.wait(timeout=15)
    finally:
        if job:
            job.close()

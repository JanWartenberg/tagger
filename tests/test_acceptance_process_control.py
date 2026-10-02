"""Native cleanup fault probes; Windows-only cases never silently claim a pass."""

import ctypes
from ctypes import wintypes
import os
from pathlib import Path
import subprocess
import tempfile
import time
import unittest
from unittest.mock import patch

from acceptance.process_control import start_child, stop_child, WindowsJob


class ProcessLifecycleTests(unittest.TestCase):
    def test_timeout_child_is_terminated(self):
        with tempfile.TemporaryDirectory() as temporary:
            script = Path(temporary) / "probe.py"
            script.write_text("import time; time.sleep(120)", encoding="utf-8")
            child, job = start_child(script)
            try:
                with self.assertRaises(subprocess.TimeoutExpired):
                    child.wait(timeout=0.1)
            finally:
                stop_child(child, job)
            self.assertIsNotNone(child.poll())


@unittest.skipUnless(os.name == "nt", "requires native Windows Job Objects")
class WindowsProcessContainmentTests(unittest.TestCase):
    def probe(self, abrupt, close_only=False):
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            marker = root / "descendant.pid"
            script = root / "probe.py"
            descendant = (
                "import os, pathlib, time; "
                f"pathlib.Path({str(marker)!r}).write_text(str(os.getpid())); "
                "time.sleep(120)"
            )
            script.write_text(
                "import os, subprocess, sys, time\n"
                f"subprocess.Popen([sys.executable, '-c', {descendant!r}])\n"
                + ("os._exit(23)\n" if abrupt else "time.sleep(120)\n"),
                encoding="utf-8",
            )
            child, job = start_child(script)
            process = None
            try:
                deadline = time.monotonic() + 10
                while not marker.exists() or not marker.read_text():
                    if time.monotonic() >= deadline:
                        self.fail("Descendant did not start")
                    time.sleep(0.02)
                pid = int(marker.read_text())
                api = job.api
                api.OpenProcess.argtypes = [
                    wintypes.DWORD,
                    wintypes.BOOL,
                    wintypes.DWORD,
                ]
                process = api.OpenProcess(0x00100000, False, pid)  # SYNCHRONIZE
                self.assertTrue(process, ctypes.get_last_error())
                api.WaitForSingleObject.argtypes = [wintypes.HANDLE, wintypes.DWORD]
                api.WaitForSingleObject.restype = wintypes.DWORD
                if abrupt:
                    self.assertEqual(child.wait(timeout=10), 23)
                else:
                    with self.assertRaises(subprocess.TimeoutExpired):
                        child.wait(timeout=0.1)
                self.assertGreaterEqual(job.active_processes(), 1)
                if close_only:
                    job.close()
                    child.wait(timeout=15)
                else:
                    stop_child(child, job)
                self.assertEqual(api.WaitForSingleObject(process, 15000), 0)
            finally:
                if job.handle:
                    stop_child(child, job)
                if process:
                    job._check(job.api.CloseHandle(process))

    def test_timeout_kills_descendants(self):
        self.probe(abrupt=False)

    def test_abrupt_child_exit_kills_descendants(self):
        self.probe(abrupt=True)

    def test_job_handle_close_kills_descendants(self):
        self.probe(abrupt=False, close_only=True)

    def test_assignment_failure_never_runs_script(self):
        with tempfile.TemporaryDirectory() as temporary:
            marker = Path(temporary) / "ran"
            script = Path(temporary) / "probe.py"
            script.write_text(
                f"from pathlib import Path; Path({str(marker)!r}).touch()",
                encoding="utf-8",
            )
            with patch.object(WindowsJob, "assign", side_effect=OSError("refused")):
                with self.assertRaisesRegex(OSError, "refused"):
                    start_child(script)
            self.assertFalse(marker.exists())


if __name__ == "__main__":
    unittest.main()

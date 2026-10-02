"""Explicit integration command. Takes no photo-directory input."""

from datetime import datetime, timezone
import hashlib
import json
import os
from pathlib import Path
import platform
import shutil
import signal
import subprocess
import sys
import tempfile
import traceback

HERE = Path(__file__).resolve().parent
REPO = HERE.parents[1]
REQUIRED_CASES = {
    "copy": {"cancel_copy", "confirmed_subset", "backup_policy"},
    "reopen": {"fresh_application_persistence"},
}


def command(*args):
    return subprocess.check_output(
        args, text=True, stderr=subprocess.STDOUT, timeout=15
    ).strip()


def stop_tree(child):
    if os.name == "nt":
        if child.poll() is None:
            subprocess.run(
                ["taskkill", "/PID", str(child.pid), "/T", "/F"],
                capture_output=True,
                timeout=15,
                check=True,
            )
    else:
        try:
            os.killpg(child.pid, signal.SIGKILL)
        except ProcessLookupError:
            pass
    child.wait(timeout=15)


def isolated_environment(root):
    env = os.environ.copy()
    env.update(
        {
            "APPDATA": str(root / "appdata"),
            "LOCALAPPDATA": str(root / "localappdata"),
            "HOME": str(root / "home"),
            "USERPROFILE": str(root / "home"),
            "XDG_CONFIG_HOME": str(root / "config"),
            "XDG_CACHE_HOME": str(root / "cache"),
            "QT_QPA_PLATFORM": "offscreen",
            "TAGGER_ACCEPTANCE_ROOT": str(root),
            "PYTHONUNBUFFERED": "1",
            "PYTHONDONTWRITEBYTECODE": "1",
            "PYTHONIOENCODING": "utf-8",
        }
    )
    for name in ("appdata", "localappdata", "home", "config", "cache"):
        (root / name).mkdir()
    return env


def run_phase(root, env, phase, backup, report_dir, report):
    name = f"backup-{backup}-{phase}"
    result = {"phase": phase, "backup": backup, "status": "failed"}
    report["phases"].append(result)
    env = {**env, "TAGGER_ACCEPTANCE_PHASE": phase, "TAGGER_ACCEPTANCE_BACKUP": backup}
    stdout = report_dir / f"{name}-stdout.txt"
    stderr = report_dir / f"{name}-stderr.txt"
    result.update({"stdout": stdout.name, "stderr": stderr.name})
    # File-backed logs survive a crash or hard timeout; do not buffer them in RAM.
    with (
        stdout.open("w", encoding="utf-8") as out,
        stderr.open("w", encoding="utf-8") as err,
    ):
        child = subprocess.Popen(
            [sys.executable, str(HERE / "confirmed_copy.py")],
            cwd=root,
            env=env,
            stdout=out,
            stderr=err,
            start_new_session=os.name != "nt",
        )
        result["pid"] = child.pid
        try:
            code = child.wait(timeout=120)
        finally:
            stop_tree(child)
    result["returncode"] = code
    observations = [
        json.loads(line)
        for line in stdout.read_text(encoding="utf-8").splitlines()
        if line.startswith("{")
    ]
    result["observations"] = observations
    if code:
        raise RuntimeError(f"{name} exited {code}; see {stderr.name}")
    passed = {
        item.get("case") for item in observations if item.get("status") == "passed"
    }
    if passed != REQUIRED_CASES[phase]:
        raise RuntimeError(f"{name}: expected {REQUIRED_CASES[phase]}, got {passed}")
    result["status"] = "passed"


def main():
    if len(sys.argv) != 1:
        raise SystemExit("Usage: python run.py (no photo-directory arguments accepted)")
    report_dir = (
        HERE / "reports" / datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%S.%fZ")
    )
    report_dir.mkdir(parents=True)
    report = {
        "command": [sys.executable, *sys.argv],
        "platform": platform.platform(),
        "python": sys.version,
        "status": "failed",
        "phases": [],
        "workspaces": [],
        "windows_sharing_lock": "not implemented; Windows validation still required",
        "visual_acceptance": "not run",
        "harness_sha256": {
            name: hashlib.sha256((HERE / name).read_bytes()).hexdigest()
            for name in ("run.py", "confirmed_copy.py")
        },
    }
    try:
        if not __debug__ or os.environ.get("PYTHONOPTIMIZE", "0") != "0":
            raise RuntimeError(
                "Run without Python optimization; assertions are required"
            )
        if not shutil.which("exiftool"):
            raise RuntimeError("Required dependency missing: exiftool on PATH")
        report["exiftool"] = command("exiftool", "-ver")
        report["commit"] = command("git", "-C", str(REPO), "rev-parse", "HEAD")
        report["working_tree"] = command("git", "-C", str(REPO), "status", "--short")
        for backup in ("off", "on"):
            workspace = {"backup": backup}
            report["workspaces"].append(workspace)
            root = None
            try:
                with tempfile.TemporaryDirectory(
                    prefix="tagger-acceptance-"
                ) as temporary:
                    root = Path(temporary)
                    workspace["path"] = temporary
                    env = isolated_environment(root)
                    # The writer must exit successfully before starting a fresh reader.
                    for phase in ("copy", "reopen"):
                        run_phase(root, env, phase, backup, report_dir, report)
            finally:
                if root is not None:
                    workspace["removed"] = not root.exists()
        report["status"] = "passed"
    except BaseException:
        report["error"] = traceback.format_exc()
    finally:
        (report_dir / "report.json").write_text(
            json.dumps(report, indent=2), encoding="utf-8"
        )
    print(f"{report['status'].upper()}: {report_dir / 'report.json'}")
    return 0 if report["status"] == "passed" else 1


if __name__ == "__main__":
    sys.exit(main())

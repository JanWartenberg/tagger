"""Explicit integration command. Takes no photo-directory input."""

from datetime import datetime, timezone
import hashlib
import json
import os
from pathlib import Path
import platform
import shutil
import subprocess
import sys
import tempfile
import traceback
from typing import Any

from process_control import start_child, stop_child

HERE = Path(__file__).resolve().parent
REPO = HERE.parents[1]
REQUIRED_CASES = {
    "ignore": {"ignore_remembered_without_photo_writes"},
    "ignored-reopen": {
        "fresh_process_ignore_and_read_only_inspection",
        "explicit_restore_persists_without_photo_writes",
        "clear_all_ignores_without_photo_writes",
        "changed_capture_evidence_returns_without_photo_writes",
        "ignored_list_keyboard_navigation_and_close",
    },
    "copy": {"cancel_copy", "confirmed_subset", "backup_policy"},
    "reopen": {"fresh_application_persistence"},
    **{
        f"safety-{stage}": {
            f"{stage}_{change}_{role}_refused"
            for role in ("source", "target")
            for change in ("changed", "missing")
        }
        for stage in ("preview", "confirm")
    },
    "write-guard": {"write_changed_target_refused", "write_missing_target_refused"},
    "windows-lock": {"sharing_lock_partial_failure", "sharing_lock_failed_only_retry"},
}


def command(*args):
    return subprocess.check_output(
        args, text=True, stderr=subprocess.STDOUT, timeout=15
    ).strip()


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
    if phase == "windows-lock":
        root = root / "locked-ui"
        root.mkdir()
        env = isolated_environment(root)
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
        child, job = start_child(
            HERE
            / (
                "confirmed_copy.py"
                if phase in ("copy", "reopen")
                else "ignored_candidates.py"
                if phase in ("ignore", "ignored-reopen")
                else "locked_copy.py"
                if phase == "windows-lock"
                else "safety_cases.py"
            ),
            cwd=root,
            env=env,
            stdout=out,
            stderr=err,
        )
        result["pid"] = child.pid
        try:
            code = child.wait(timeout=120)
        finally:
            stop_child(child, job)
            result["process_tree_cleanup"] = "verified"
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


def run_cleanup_checks(report_dir, report):
    if os.name != "nt":
        report["windows_process_cleanup"] = {
            "status": "not run",
            "reason": "Windows only",
        }
        return
    result = {
        "status": "failed",
        "stdout": "cleanup-stdout.txt",
        "stderr": "cleanup-stderr.txt",
    }
    report["windows_process_cleanup"] = result
    with (
        (report_dir / result["stdout"]).open("w", encoding="utf-8") as out,
        (report_dir / result["stderr"]).open("w", encoding="utf-8") as err,
    ):
        child, job = start_child(
            REPO / "tests" / "test_acceptance_process_control.py",
            cwd=REPO,
            stdout=out,
            stderr=err,
        )
        try:
            code = child.wait(timeout=120)
        finally:
            stop_child(child, job)
    result["returncode"] = code
    if code:
        raise RuntimeError("Windows cleanup probes failed; see cleanup-stderr.txt")
    result["status"] = "passed"


def main():
    if len(sys.argv) != 1:
        raise SystemExit("Usage: python run.py (no photo-directory arguments accepted)")
    report_dir = (
        HERE / "reports" / datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%S.%fZ")
    )
    report_dir.mkdir(parents=True)
    report: dict[str, Any] = {
        "command": [sys.executable, *sys.argv],
        "platform": platform.platform(),
        "python": sys.version,
        "status": "failed",
        "phases": [],
        "workspaces": [],
        "windows_sharing_lock": {
            "status": "not run",
            "reason": "not reached" if os.name == "nt" else "Windows only",
        },
        "visual_acceptance": "not run",
        "harness_sha256": {
            name: hashlib.sha256((HERE / name).read_bytes()).hexdigest()
            for name in (
                "run.py",
                "confirmed_copy.py",
                "ignored_candidates.py",
                "process_control.py",
                "safety_cases.py",
                "locked_copy.py",
                "windows_lock.py",
                "../test_acceptance_process_control.py",
            )
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
        run_cleanup_checks(report_dir, report)
        for backup in ("off", "on"):
            workspace: dict[str, Any] = {"backup": backup}
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
                    phases = [
                        "copy",
                        "reopen",
                        "safety-preview",
                        "safety-confirm",
                        "write-guard",
                        "ignore",
                        "ignored-reopen",
                    ]
                    if os.name == "nt":
                        phases.append("windows-lock")
                    for phase in phases:
                        if phase == "windows-lock":
                            report["windows_sharing_lock"] = {"status": "failed"}
                        run_phase(root, env, phase, backup, report_dir, report)
            finally:
                if root is not None:
                    workspace["removed"] = not root.exists()
        if os.name == "nt":
            report["windows_sharing_lock"] = {
                "status": "passed",
                "backup_settings": ["off", "on"],
            }
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

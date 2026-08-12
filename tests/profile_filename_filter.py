"""Deterministic regression harness for final filename-filter application.

Run with: ``python3 tests/profile_filename_filter.py``.

It seeds the same loaded normal Photo Workspace state that the Qt adapter holds
immediately before applying a filename condition.  The call-count assertion is
intentional: timing is reported for diagnosis, while derived-membership calls
are deterministic across machines.
"""

from __future__ import annotations

from pathlib import Path
import sys
import time

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from photo_workspace import PhotoWorkspace

PATH_COUNT = 3_000
MAX_DERIVED_MEMBERSHIP_CALLS = 2


def loaded_workspace(path_count: int = PATH_COUNT) -> PhotoWorkspace:
    """Return a normal workspace immediately before a final filter application."""
    paths = [f"/photos/photo-{number:05}.jpg" for number in range(path_count)]
    workspace = PhotoWorkspace()
    # Setup deliberately avoids measuring the initial folder render. The
    # diagnostic target is set_filename_filter() against an already loaded view.
    workspace._paths = paths
    workspace._visible = set(paths)
    workspace._selected = {paths[0]}
    workspace._active_path = paths[0]
    return workspace


def main() -> int:
    workspace = loaded_workspace()
    derived_membership_calls = 0
    original = workspace._filtered_visible

    def count_derived_membership() -> set[str]:
        nonlocal derived_membership_calls
        derived_membership_calls += 1
        return original()

    workspace._filtered_visible = count_derived_membership  # type: ignore[method-assign]
    started = time.perf_counter()
    snapshot = workspace.set_filename_filter("photo-02999")
    elapsed = time.perf_counter() - started
    print(
        "filename filter: "
        f"{PATH_COUNT} paths, {elapsed:.3f}s, "
        f"{derived_membership_calls} derived-membership calls, "
        f"{len(snapshot.visible_paths)} visible path(s)"
    )
    if derived_membership_calls > MAX_DERIVED_MEMBERSHIP_CALLS:
        print(
            "FAIL: deriving visible membership more than twice makes snapshot "
            "construction quadratic.",
            file=sys.stderr,
        )
        return 1
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

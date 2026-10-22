"""Keep the GUI application alive across independently cleaned-up Qt fixtures."""

import os
from pathlib import Path
import subprocess
import sys
import textwrap

import pytest


def test_application_survives_ui_fixture_cleanup(tmp_path):
    pytest.importorskip("PyQt6")
    script = textwrap.dedent(
        """
        import gc
        from pathlib import Path
        import sys
        import weakref

        import pytest
        from PyQt6 import QtWidgets

        sys.path.insert(0, str(Path.cwd() / "tests"))
        from test_default_index_root import windows
        from test_ignored_candidates_ui import workspace
        from test_main_window_characterization import MainWindowCharacterizationTests

        def exercise_fixture(factory, directory):
            with pytest.MonkeyPatch.context() as patches:
                fixture = factory.__wrapped__(directory, patches)
                value = next(fixture)
                create = value[0] if isinstance(value, tuple) else value
                created = create()
                application = QtWidgets.QApplication.instance()
                reference = weakref.ref(application)
                assert application is not None
                del application, created, create, value
                with pytest.raises(StopIteration):
                    next(fixture)
                del fixture
            gc.collect()
            assert reference() is not None, "QApplication destroyed between UI fixtures"
            return reference

        root = Path(sys.argv[1])
        first = exercise_fixture(workspace, root / "ignored")
        second = exercise_fixture(windows, root / "index-root")
        assert first() is second()
        MainWindowCharacterizationTests.setUpClass()
        assert MainWindowCharacterizationTests.app is first()
        """
    )
    result = subprocess.run(
        [sys.executable, "-X", "faulthandler", "-c", script, str(tmp_path)],
        cwd=Path(__file__).resolve().parents[1],
        env={**os.environ, "QT_QPA_PLATFORM": "offscreen"},
        capture_output=True,
        text=True,
        timeout=15,
    )
    assert result.returncode == 0, result.stdout + result.stderr

"""The acceptance harness waits for real Qt outcome controls to become visible."""

import importlib.util
import os
from pathlib import Path
import subprocess
import sys
import textwrap
import unittest


@unittest.skipUnless(importlib.util.find_spec("PyQt6"), "requires PyQt6 widgets")
class AcceptanceOutcomeWaitTests(unittest.TestCase):
    def test_new_outcome_widgets_are_awaited_before_retry(self):
        scenario = textwrap.dedent("""
            from pathlib import Path
            from PyQt6 import QtWidgets
            from locked_copy import retry_control

            app = QtWidgets.QApplication([])
            window = QtWidgets.QWidget()
            layout = QtWidgets.QVBoxLayout(window)
            window.show()
            app.processEvents()
            successful, locked = Path('successful.jpg'), Path('locked.jpg')
            labels = [QtWidgets.QLabel(f'{successful}: successful'),
                      QtWidgets.QLabel(f'{locked}: failed')]
            for label in labels:
                layout.addWidget(label)
            button = QtWidgets.QPushButton('Retry failed targets')
            layout.addWidget(button)
            # As in the Windows trace: correct text exists before Qt shows it.
            assert all(not label.isVisible() for label in labels)
            assert not button.isVisible()
            assert retry_control(app, window, successful, locked) is button
            assert all(label.isVisible() for label in labels)
            assert button.isVisible() and button.isEnabled()
            window.close()
        """)
        result = subprocess.run(
            [sys.executable, "-c", scenario],
            cwd=Path(__file__).resolve().parent / "acceptance",
            env={**os.environ, "QT_QPA_PLATFORM": "offscreen"},
            capture_output=True,
            text=True,
            timeout=30,
        )
        self.assertEqual(result.returncode, 0, result.stdout + result.stderr)

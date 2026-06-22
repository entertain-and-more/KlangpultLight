"""Tests für den Headless-Selftest in main.py.

Ruft main.py als Subprozess mit nur PODCAST_RECORDER_SELFTEST=1 auf.
main.py setzt offscreen + Mock-Audio + Mock-Video selbst.
Erwartet Exit-Code 0. Prüft bei Video-Selftest zusätzlich auf program.mp4.
"""
import os
import subprocess
import sys

import pytest


# sys.executable statt hartkodiertem venv-Pfad (M-5)
PYTHON = sys.executable
RECORDER_DIR = os.path.join(
    os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
)


def test_selftest_exit_code_0():
    """main.py im Selftest-Modus muss mit Exit-Code 0 beenden."""
    umgebung = os.environ.copy()
    umgebung["PODCAST_RECORDER_SELFTEST"] = "1"
    umgebung.pop("QT_QPA_PLATFORM", None)
    umgebung.pop("PODCAST_RECORDER_MOCK_AUDIO", None)
    umgebung.pop("PODCAST_RECORDER_MOCK_VIDEO", None)
    umgebung["PYTHONIOENCODING"] = "utf-8"

    ergebnis = subprocess.run(
        [PYTHON, "main.py"],
        cwd=RECORDER_DIR,
        env=umgebung,
        capture_output=True,
        text=True,
        timeout=60,
    )

    stdout = ergebnis.stdout.strip()
    stderr = ergebnis.stderr.strip()

    if ergebnis.returncode != 0:
        pytest.fail(
            f"Selftest Exit-Code {ergebnis.returncode}\n"
            f"stdout: {stdout}\n"
            f"stderr: {stderr}"
        )

    assert "SELFTEST OK" in stdout, (
        f"Erwartete 'SELFTEST OK' in stdout, bekam: {stdout}\nstderr: {stderr}"
    )

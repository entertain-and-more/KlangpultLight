"""Tests für den Headless-Selftest in main.py.

Ruft main.py als Subprozess auf mit SELFTEST + offscreen + mock-Audio.
Erwartet Exit-Code 0.
"""
import os
import subprocess
import sys

import pytest


PYTHON = r"C:\_Local_DEV\venvs\podcast_packages\Scripts\python.exe"
RECORDER_DIR = os.path.join(
    os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
)


@pytest.mark.skipif(
    not os.path.isfile(PYTHON),
    reason="Podcast-venv nicht gefunden — Selftest übersprungen.",
)
def test_selftest_exit_code_0():
    """main.py im Selftest-Modus muss mit Exit-Code 0 beenden."""
    umgebung = os.environ.copy()
    umgebung["PODCAST_RECORDER_SELFTEST"] = "1"
    umgebung["QT_QPA_PLATFORM"] = "offscreen"
    umgebung["PODCAST_RECORDER_MOCK_AUDIO"] = "1"
    umgebung["PYTHONIOENCODING"] = "utf-8"

    ergebnis = subprocess.run(
        [PYTHON, "main.py"],
        cwd=RECORDER_DIR,
        env=umgebung,
        capture_output=True,
        text=True,
        timeout=30,
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

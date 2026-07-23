"""Tests für Laufzeitpfade des Recorders im Source- und Frozen-Betrieb."""

from pathlib import Path

import main


def test_runtime_base_dir_ist_recorder_ordner_im_source_betrieb(monkeypatch):
    """Source-Betrieb schreibt weiter relativ zum Recorder-Ordner."""
    monkeypatch.delattr(main.sys, "frozen", raising=False)
    monkeypatch.setattr(main.sys, "executable", str(Path(main.__file__).with_name("dummy.exe")), raising=False)

    assert main._runtime_base_dir() == str(Path(main.__file__).resolve().parent)


def test_runtime_base_dir_ist_exe_ordner_im_frozen_betrieb(monkeypatch, tmp_path):
    """Frozen-Betrieb muss den EXE-Ordner statt _MEIPASS/Temp nutzen."""
    fake_exe = tmp_path / "KlangpultLightRecorder.exe"
    monkeypatch.setattr(main.sys, "frozen", True, raising=False)
    monkeypatch.setattr(main.sys, "executable", str(fake_exe), raising=False)

    assert main._runtime_base_dir() == str(tmp_path.resolve())

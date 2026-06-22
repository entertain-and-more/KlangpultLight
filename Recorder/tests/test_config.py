"""Tests für core.config — AppConfig Defaults und save/load Roundtrip."""
import json
import os
import pytest
from pathlib import Path


def test_defaults():
    """AppConfig liefert korrekte Standardwerte ohne Datei."""
    from core.config import AppConfig
    cfg = AppConfig()
    assert cfg.samplerate == 48000
    assert cfg.block_size == 1024
    assert cfg.channels == 2
    assert cfg.workspace_dir == "./workspace"
    assert cfg.mock_audio is False


def test_load_missing_file_returns_defaults(tmp_path):
    """load_config mit nicht-existenter Datei → Defaults."""
    from core.config import load_config
    cfg = load_config(str(tmp_path / "nicht_vorhanden.json"))
    assert cfg.samplerate == 48000
    assert cfg.channels == 2


def test_save_and_load_roundtrip(tmp_path):
    """save_config schreibt JSON, load_config liest es korrekt zurück."""
    from core.config import AppConfig, save_config, load_config
    cfg = AppConfig(samplerate=44100, channels=1, workspace_dir="./mein_workspace", mock_audio=True)
    pfad = str(tmp_path / "config.json")
    save_config(cfg, pfad)

    # Datei existiert und ist valides JSON
    assert Path(pfad).exists()
    with open(pfad, encoding="utf-8") as f:
        data = json.load(f)
    assert data["samplerate"] == 44100

    # Roundtrip: geladene Config entspricht gespeicherter
    cfg2 = load_config(pfad)
    assert cfg2.samplerate == 44100
    assert cfg2.channels == 1
    assert cfg2.workspace_dir == "./mein_workspace"
    assert cfg2.mock_audio is True


def test_save_utf8_ohne_bom(tmp_path):
    """JSON-Datei wird UTF-8 ohne BOM geschrieben."""
    from core.config import AppConfig, save_config
    pfad = str(tmp_path / "config.json")
    save_config(AppConfig(), pfad)
    raw = Path(pfad).read_bytes()
    # Kein BOM (EF BB BF am Anfang)
    assert not raw.startswith(b"\xef\xbb\xbf")


def test_save_atomic_keine_tmp_datei(tmp_path):
    """Nach save_config() darf keine .json.tmp-Datei übrig bleiben.

    Belegt Bugsweep-Fix: save_config() nutzt jetzt Temp-Datei + os.replace().
    """
    from core.config import AppConfig, save_config
    pfad = str(tmp_path / "config.json")
    save_config(AppConfig(), pfad)

    tmp_datei = pfad + ".tmp"
    assert not os.path.exists(tmp_datei), (
        f".json.tmp darf nach save_config() nicht existieren: {tmp_datei}"
    )
    assert os.path.isfile(pfad), "config.json muss existieren"

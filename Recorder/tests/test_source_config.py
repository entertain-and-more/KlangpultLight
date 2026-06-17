"""Tests für sources.source_config — SourceEntry, SourcesConfig, load/save.

Headless, kein GUI-Import, kein Hardware-Zugriff.
"""
import json
from pathlib import Path


# ---------------------------------------------------------------------------
# Defaults
# ---------------------------------------------------------------------------

def test_defaults_mic_entries():
    """load_sources_config ohne Datei → mic_1 + mic_2 vorhanden, capture=True."""
    from sources.source_config import load_sources_config
    cfg = load_sources_config(None)
    quellen = {e.source_id: e for e in cfg.sources}
    assert "mic_1" in quellen, "mic_1 fehlt in Defaults"
    assert "mic_2" in quellen, "mic_2 fehlt in Defaults"
    assert quellen["mic_1"].capture is True
    assert quellen["mic_2"].capture is True


def test_defaults_system_capture_false():
    """load_sources_config ohne Datei → system-Quelle capture=False (bis Loopback bestätigt)."""
    from sources.source_config import load_sources_config
    cfg = load_sources_config(None)
    quellen = {e.source_id: e for e in cfg.sources}
    assert "system" in quellen, "system fehlt in Defaults"
    assert quellen["system"].capture is False


def test_defaults_mic_enabled():
    """Standardquellen sind enabled."""
    from sources.source_config import load_sources_config
    cfg = load_sources_config(None)
    for eintrag in cfg.sources:
        assert eintrag.enabled is True, f"{eintrag.source_id}.enabled sollte True sein"


# ---------------------------------------------------------------------------
# set_capture
# ---------------------------------------------------------------------------

def test_set_capture_true():
    """set_capture(system, True) ändert system.capture auf True."""
    from sources.source_config import load_sources_config
    cfg = load_sources_config(None)
    cfg.set_capture("system", True)
    eintrag = cfg.get("system")
    assert eintrag is not None
    assert eintrag.capture is True


def test_set_capture_false():
    """set_capture(mic_1, False) ändert mic_1.capture auf False."""
    from sources.source_config import load_sources_config
    cfg = load_sources_config(None)
    cfg.set_capture("mic_1", False)
    eintrag = cfg.get("mic_1")
    assert eintrag is not None
    assert eintrag.capture is False


def test_set_capture_unbekannte_id():
    """set_capture mit unbekannter ID löst keinen Fehler aus."""
    from sources.source_config import load_sources_config
    cfg = load_sources_config(None)
    cfg.set_capture("nicht_vorhanden", True)  # kein Exception


# ---------------------------------------------------------------------------
# capture_sources / enabled_sources
# ---------------------------------------------------------------------------

def test_capture_sources_nur_enabled_und_capture():
    """capture_sources() liefert nur Quellen, die enabled=True UND capture=True sind."""
    from sources.source_config import load_sources_config
    cfg = load_sources_config(None)
    # system hat capture=False → fehlt in capture_sources
    ids = {e.source_id for e in cfg.capture_sources()}
    assert "system" not in ids
    assert "mic_1" in ids
    assert "mic_2" in ids


def test_capture_sources_beruecksichtigt_disabled():
    """capture_sources() schließt disabled Quellen aus."""
    from sources.source_config import load_sources_config, SourceEntry
    cfg = load_sources_config(None)
    # mic_1 deaktivieren
    eintrag = cfg.get("mic_1")
    assert eintrag is not None
    eintrag.enabled = False
    ids = {e.source_id for e in cfg.capture_sources()}
    assert "mic_1" not in ids


def test_enabled_sources_alle_standards():
    """enabled_sources() liefert alle Standard-Quellen (alle enabled=True per Default)."""
    from sources.source_config import load_sources_config
    cfg = load_sources_config(None)
    enabled_ids = {e.source_id for e in cfg.enabled_sources()}
    for eintrag in cfg.sources:
        assert eintrag.source_id in enabled_ids


def test_enabled_sources_nach_disable():
    """enabled_sources() beachtet manuell deaktivierte Quelle."""
    from sources.source_config import load_sources_config
    cfg = load_sources_config(None)
    eintrag = cfg.get("mic_2")
    assert eintrag is not None
    eintrag.enabled = False
    ids = {e.source_id for e in cfg.enabled_sources()}
    assert "mic_2" not in ids


# ---------------------------------------------------------------------------
# get
# ---------------------------------------------------------------------------

def test_get_bekannte_id():
    """get() mit gültiger ID liefert SourceEntry."""
    from sources.source_config import load_sources_config
    cfg = load_sources_config(None)
    eintrag = cfg.get("mic_1")
    assert eintrag is not None
    assert eintrag.source_id == "mic_1"


def test_get_unbekannte_id():
    """get() mit unbekannter ID liefert None."""
    from sources.source_config import load_sources_config
    cfg = load_sources_config(None)
    assert cfg.get("phantom") is None


# ---------------------------------------------------------------------------
# save → load Roundtrip
# ---------------------------------------------------------------------------

def test_roundtrip_vollstaendig(tmp_path):
    """save_sources_config + load_sources_config ist ein vollständiger Roundtrip."""
    from sources.source_config import load_sources_config, save_sources_config
    cfg = load_sources_config(None)
    # system-Quelle aktivieren, gain setzen
    eintrag = cfg.get("system")
    eintrag.capture = True
    eintrag.capture_method = "wasapi_loopback"
    eintrag.gain = 0.8

    pfad = str(tmp_path / "sources.json")
    save_sources_config(cfg, pfad)
    assert Path(pfad).exists()

    cfg2 = load_sources_config(pfad)
    system2 = cfg2.get("system")
    assert system2 is not None
    assert system2.capture is True
    assert system2.capture_method == "wasapi_loopback"
    assert abs(system2.gain - 0.8) < 1e-9


def test_roundtrip_reihenfolge(tmp_path):
    """Quellen-Reihenfolge bleibt nach Roundtrip erhalten."""
    from sources.source_config import load_sources_config, save_sources_config
    cfg = load_sources_config(None)
    ids_vor = [e.source_id for e in cfg.sources]

    pfad = str(tmp_path / "sources.json")
    save_sources_config(cfg, pfad)
    cfg2 = load_sources_config(pfad)
    ids_nach = [e.source_id for e in cfg2.sources]
    assert ids_vor == ids_nach


def test_utf8_ohne_bom(tmp_path):
    """JSON-Datei wird UTF-8 ohne BOM geschrieben (Umlaute im notes-Feld)."""
    from sources.source_config import load_sources_config, save_sources_config
    cfg = load_sources_config(None)
    eintrag = cfg.get("mic_1")
    eintrag.notes = "Aufnahme mit Umlauten: ä ö ü"

    pfad = str(tmp_path / "sources.json")
    save_sources_config(cfg, pfad)

    roh = Path(pfad).read_bytes()
    # Kein BOM
    assert not roh.startswith(b"\xef\xbb\xbf")
    # Umlaute korrekt codiert
    text = roh.decode("utf-8")
    assert "ä ö ü" in text


def test_fehlende_datei_liefert_defaults(tmp_path):
    """load_sources_config mit nicht-existentem Pfad → sinnvolle Defaults."""
    from sources.source_config import load_sources_config
    cfg = load_sources_config(str(tmp_path / "nicht_da.json"))
    assert len(cfg.sources) > 0


def test_from_dict_unbekannte_felder_ignoriert():
    """from_dict ignoriert unbekannte Felder (Vorwärts-Kompatibilität)."""
    from sources.source_config import SourcesConfig
    daten = {
        "sources": [
            {
                "source_id": "mic_1",
                "name": "Mikrofon 1",
                "kind": "mic",
                "enabled": True,
                "capture": True,
                "device_index": None,
                "gain": 1.0,
                "capture_method": None,
                "notes": "",
                "zukuenftiges_feld": "ignoriert",
            }
        ]
    }
    cfg = SourcesConfig.from_dict(daten)
    assert cfg.get("mic_1") is not None

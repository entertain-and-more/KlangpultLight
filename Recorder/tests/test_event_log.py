"""Tests für core.event_log — JSON-Lines-Protokoll."""
import json
from pathlib import Path


def test_log_schreibt_valide_zeile(tmp_path):
    """log() schreibt eine Zeile mit 't', 'type' und übergebenen Feldern."""
    from core.event_log import EventLog
    pfad = str(tmp_path / "events.jsonl")
    log = EventLog(pfad)
    log.log("aufnahme_gestartet", quelle="Mikrofon 1", kanal=0)
    log.close()

    zeilen = Path(pfad).read_text(encoding="utf-8").strip().splitlines()
    assert len(zeilen) == 1
    obj = json.loads(zeilen[0])
    assert "t" in obj
    assert obj["type"] == "aufnahme_gestartet"
    assert obj["quelle"] == "Mikrofon 1"
    assert obj["kanal"] == 0


def test_log_mehrere_zeilen_append(tmp_path):
    """Mehrere log()-Aufrufe erzeugen mehrere Zeilen (append, keine Überschreibung)."""
    from core.event_log import EventLog
    pfad = str(tmp_path / "events.jsonl")
    log = EventLog(pfad)
    log.log("start", schritt=1)
    log.log("stop", schritt=2)
    log.log("fehler", meldung="Gerät nicht verfügbar")
    log.close()

    zeilen = Path(pfad).read_text(encoding="utf-8").strip().splitlines()
    assert len(zeilen) == 3
    obj = json.loads(zeilen[2])
    assert obj["type"] == "fehler"
    # Echter Umlaut muss im JSON erhalten bleiben
    assert "Gerät" in obj["meldung"]


def test_log_erstellt_verzeichnis(tmp_path):
    """EventLog legt fehlendes Verzeichnis automatisch an."""
    from core.event_log import EventLog
    pfad = str(tmp_path / "tief" / "verschachtelt" / "events.jsonl")
    log = EventLog(pfad)
    log.log("test")
    log.close()
    assert Path(pfad).exists()


def test_log_utf8_ohne_bom(tmp_path):
    """Logdatei ist UTF-8 ohne BOM."""
    from core.event_log import EventLog
    pfad = str(tmp_path / "events.jsonl")
    log = EventLog(pfad)
    log.log("ü_test", text="Äpfel über Öfen")
    log.close()
    raw = Path(pfad).read_bytes()
    assert not raw.startswith(b"\xef\xbb\xbf")
    # Umlaute korrekt kodiert (keine \uXXXX-Escapes erforderlich, direkte UTF-8-Bytes)
    decoded = raw.decode("utf-8")
    assert "Äpfel" in decoded


def test_log_zeitstempel_utc_aware(tmp_path):
    """Zeitstempel in EventLog-Einträgen muss UTC-aware sein (enthält '+00:00' oder 'Z').

    Belegt Bugsweep-Fix: EventLog nutzte datetime.now() (Lokalzeit, kein Timezone-Info)
    statt datetime.now(timezone.utc) — inkonsistent mit library.py und projects_api.py.
    """
    from core.event_log import EventLog
    pfad = str(tmp_path / "events.jsonl")
    log = EventLog(pfad)
    log.log("timezone_test")
    log.close()

    zeilen = Path(pfad).read_text(encoding="utf-8").strip().splitlines()
    obj = json.loads(zeilen[0])
    t = obj["t"]
    # UTC-aware ISO-8601: endet auf +00:00 oder Z
    assert "+" in t or t.endswith("Z"), (
        f"Zeitstempel '{t}' ist nicht UTC-aware — muss '+00:00' oder 'Z' enthalten"
    )

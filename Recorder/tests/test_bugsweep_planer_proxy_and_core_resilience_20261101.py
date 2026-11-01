"""tests.test_bugsweep_planer_proxy_and_core_resilience_20261101 — Regressionstests für Bugsweep 2026-11-01.

Prüft die funktionale Resilienz von:
1. planer.server.planer_server (PlanerHandler Proxy & Health Probe):
   - Malformed Content-Length Header Guard
   - http.client.HTTPException & RemoteDisconnected Handling (502 statt Crash)
   - Connection-Close in finally (Socket-Leak Schutz)
   - _probe_health Failsafe bei http.client.HTTPException
2. Recorder.core.config (AppConfig load/save):
   - load_config Resilienz bei Non-Dict JSON (Listen, Zahlen, Strings, None)
   - load_config Resilienz bei Verzeichnispfad (kein PermissionError / IsADirectoryError)
   - save_config Verzeichnisschutz (IsADirectoryError vor Temp-Datei)
   - save_config Windows ReadOnly-Overwrite (stat.S_IWRITE Härtung)
   - save_config Prozess-isolierte Temp-Datei (PID-Suffix & Cleanup bei Fehler)
3. Recorder.core.event_log (EventLog):
   - Non-serializable Objects (Path, set, Exceptions via default=str)
   - Context Manager Support & Idempotent Close
"""
from __future__ import annotations

import http.client
import json
import os
import stat
import sys
from pathlib import Path
from unittest.mock import MagicMock, patch

import pytest

# Pfade für planer_server und Recorder einbinden
_ROOT = Path(__file__).resolve().parent.parent.parent
_PLANER_SERVER_DIR = _ROOT / "planer" / "server"
if str(_PLANER_SERVER_DIR) not in sys.path:
    sys.path.insert(0, str(_PLANER_SERVER_DIR))
_RECORDER_DIR = _ROOT / "Recorder"
if str(_RECORDER_DIR) not in sys.path:
    sys.path.insert(0, str(_RECORDER_DIR))

from core.config import AppConfig, load_config, save_config  # noqa: E402
from core.event_log import EventLog  # noqa: E402
from planer_server import PlanerHandler  # noqa: E402


# =============================================================================
# 1. PlanerServer Proxy & Health Resilienz
# =============================================================================

def test_proxy_malformed_content_length():
    """Ein ungültiger Content-Length Header (z. B. 'invalid', leer oder negativ)
    darf keinen unhandled ValueError werfen."""
    handler = MagicMock(spec=PlanerHandler)
    handler.command = "POST"
    handler.path = "/api/projects"
    handler.headers = {"Content-Length": "invalid"}
    handler.rfile = MagicMock()
    handler._fehler = MagicMock()

    # Ungepatchter Code wirft ValueError: invalid literal for int() with base 10: 'invalid'
    PlanerHandler._proxy(handler, backend_port=19999, is_head=False)
    handler._fehler.assert_called_once()
    assert handler._fehler.call_args[0][0] == 502


def test_proxy_http_client_exception_handling():
    """Wenn der Backend-Dienst die Verbindung unerwartet abbricht (RemoteDisconnected /
    BadStatusLine), muss _proxy mit 502 antworten statt mit unhandled Exception abzustürzen."""
    handler = MagicMock(spec=PlanerHandler)
    handler.command = "GET"
    handler.path = "/api/projects/123"
    handler.headers = {}
    handler.rfile = MagicMock()
    handler._fehler = MagicMock()

    mock_conn = MagicMock()
    # Simuliere RemoteDisconnected (erbt von BadStatusLine -> HTTPException, NICHT OSError)
    mock_conn.getresponse.side_effect = http.client.RemoteDisconnected("Remote end closed connection without response")

    with patch("http.client.HTTPConnection", return_value=mock_conn):
        PlanerHandler._proxy(handler, backend_port=19999, is_head=False)

    handler._fehler.assert_called_once()
    assert handler._fehler.call_args[0][0] == 502
    assert "Backend-Dienst nicht erreichbar" in handler._fehler.call_args[0][1]
    # Verbindung muss in finally geschlossen worden sein
    assert mock_conn.close.called


def test_proxy_connection_closed_on_stream_failure():
    """Wenn beim Schreiben an den Client eine Exception auftritt, muss die
    Backend-Verbindung dennoch in finally geschlossen werden (Socket-Leak Schutz)."""
    handler = MagicMock(spec=PlanerHandler)
    handler.command = "GET"
    handler.path = "/api/library"
    handler.headers = {}
    handler.rfile = MagicMock()
    handler.send_response = MagicMock()
    handler.send_header = MagicMock()
    handler.end_headers = MagicMock()
    handler._set_cors_headers = MagicMock()
    handler._fehler = MagicMock()

    mock_conn = MagicMock()
    mock_resp = MagicMock()
    mock_resp.status = 200
    mock_resp.getheader.return_value = None
    mock_resp.read.side_effect = [b"chunk1", BrokenPipeError("Client disconnected")]
    mock_conn.getresponse.return_value = mock_resp

    with patch("http.client.HTTPConnection", return_value=mock_conn):
        try:
            PlanerHandler._proxy(handler, backend_port=19999, is_head=False)
        except Exception:
            pass

    assert mock_conn.close.called, "Backend-Verbindung muss auch bei Stream-Fehler geschlossen werden"


def test_probe_health_http_client_exception_handling():
    """Wenn beim Health-Probe ein http.client.RemoteDisconnected auftritt,
    muss _probe_health False zurückgeben statt abzustürzen."""
    mock_conn = MagicMock()
    mock_conn.getresponse.side_effect = http.client.BadStatusLine("Bad status")

    with patch("http.client.HTTPConnection", return_value=mock_conn):
        ok = PlanerHandler._probe_health(19999)
    assert ok is False
    assert mock_conn.close.called


# =============================================================================
# 2. AppConfig Resilienz & Windows-I/O Härtung
# =============================================================================

def test_load_config_non_dict_json(tmp_path):
    """Wenn config.json gültiges JSON aber kein Dict enthält (z. B. Liste oder Zahl),
    muss load_config Standardwerte liefern statt mit AttributeError abzustürzen."""
    config_file = tmp_path / "config.json"
    config_file.write_text("[1, 2, 3]", encoding="utf-8")

    # Ungepatcht stürzt ab mit AttributeError: 'list' object has no attribute 'items'
    cfg = load_config(str(config_file))
    assert isinstance(cfg, AppConfig)
    assert cfg.samplerate == 48000
    assert cfg.channels == 2


def test_load_config_directory_path(tmp_path):
    """Wenn der Pfad zu einem Verzeichnis zeigt, darf load_config keinen
    PermissionError oder IsADirectoryError werfen, sondern Defaults liefern."""
    cfg = load_config(str(tmp_path))
    assert isinstance(cfg, AppConfig)
    assert cfg.samplerate == 48000


def test_save_config_target_is_directory(tmp_path):
    """Wenn save_config auf ein bestehendes Verzeichnis aufgerufen wird,
    muss deterministisch IsADirectoryError ausgelöst werden."""
    cfg = AppConfig()
    with pytest.raises(IsADirectoryError):
        save_config(cfg, str(tmp_path))


def test_save_config_readonly_overwrite(tmp_path):
    """Wenn die Zieldatei bereits existiert und schreibgeschützt ist (stat.S_IREAD),
    muss save_config sie unter Windows erfolgreich überschreiben können."""
    target_file = tmp_path / "sub" / "readonly_config.json"
    target_file.parent.mkdir(parents=True, exist_ok=True)
    target_file.write_text('{"samplerate": 44100}', encoding="utf-8")

    # Schreibschutz setzen
    os.chmod(target_file, stat.S_IREAD)
    try:
        cfg = AppConfig(samplerate=48000, channels=2)
        save_config(cfg, str(target_file))

        # Prüfen, dass Datei aktualisiert wurde
        reloaded = load_config(str(target_file))
        assert reloaded.samplerate == 48000
    finally:
        # Sicherstellen, dass Aufräumen möglich ist
        if target_file.exists():
            os.chmod(target_file, stat.S_IWRITE)


def test_save_config_pid_temp_file_cleanup_on_error(tmp_path):
    """save_config muss PID-spezifische Temp-Dateien nutzen und diese bei
    einem Fehler rückstandsfrei aufräumen."""
    target_file = tmp_path / "config.json"
    cfg = AppConfig()

    with patch("os.replace", side_effect=RuntimeError("Simulated disk error")):
        with pytest.raises(RuntimeError):
            save_config(cfg, str(target_file))

    # Keine verwaisten .tmp-Dateien im Verzeichnis
    tmp_files = list(tmp_path.glob("*.tmp*"))
    assert len(tmp_files) == 0, f"Verwaiste Temp-Dateien gefunden: {tmp_files}"


# =============================================================================
# 3. EventLog Resilienz & Serialization
# =============================================================================

def test_event_log_non_serializable_objects(tmp_path):
    """EventLog.log darf nicht mit TypeError abstürzen, wenn nicht-JSON-serialisierbare
    Objekte übergeben werden (z. B. Path, set, Exception)."""
    log_file = tmp_path / "events.jsonl"
    logger = EventLog(str(log_file))

    class CustomObject:
        def __str__(self):
            return "CustomObj(id=42)"

    logger.log(
        "test_event",
        path_obj=Path("C:/test/path"),
        set_obj={1, 2, 3},
        err=ValueError("Simulated error"),
        custom=CustomObject(),
    )
    logger.close()

    assert log_file.is_file()
    lines = log_file.read_text(encoding="utf-8").strip().splitlines()
    assert len(lines) == 1
    data = json.loads(lines[0])
    assert data["type"] == "test_event"
    assert "C:/test/path" in data["path_obj"] or "test" in data["path_obj"]
    assert "CustomObj(id=42)" in data["custom"]


def test_event_log_context_manager_and_idempotent_close(tmp_path):
    """EventLog unterstützt with-Statement (Context Manager) und idempotentes close()."""
    log_file = tmp_path / "events.jsonl"
    with EventLog(str(log_file)) as logger:
        logger.log("event_in_context", value=123)
        # Mehrfaches close() darf keinen Fehler werfen
        logger.close()
        logger.close()

    lines = log_file.read_text(encoding="utf-8").strip().splitlines()
    assert len(lines) == 1
    data = json.loads(lines[0])
    assert data["type"] == "event_in_context"
    assert data["value"] == 123

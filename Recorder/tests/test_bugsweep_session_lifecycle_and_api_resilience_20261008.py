"""test_bugsweep_session_lifecycle_and_api_resilience_20261008.py — Bugsweep Regression Tests.

Belegt Mängel in KlangpultLight vor dem Fix:
1. RecordingSession.stop(): Fehler beim Metadaten-Update oder Video-Mux hinterließen
   den Aufnahmezustand unbereinigt (self._aktuelle_meta != None, priority nicht restored,
   self._state.recording blieb True), wodurch nachfolgende Aufnahmen blockiert wurden.
2. VideoRecorder.close(): Timeout bei ffmpeg.wait() warf TimeoutExpired ohne den Prozess
   zu terminieren oder das Stderr-Tempfile zu schließen (Zombie-Prozess & Handle-Leak).
3. ProjectsApiServer: Unhandled ValueError in _handle_line_put, _handle_asset_post/put,
   _handle_episode_post/put, _handle_monitor_put bei Validierungsfehlern.
4. WavRecorder.close(): Fehler beim Flush/Close leckten die offene SoundFile-Instanz.
5. RemoteWsServer._toggle_mute(): Direkte Manipulation von kanal.mute aktualisierte
   den AppState.active_source_ids nicht.
6. MainWindow.closeEvent(): Abgelöste schwebende Float-Panels wurden beim Schließen des
   Hauptfensters nicht geschlossen.
"""
from __future__ import annotations

import subprocess
import urllib.error
import urllib.request
import json
from unittest.mock import MagicMock, patch

import pytest


@pytest.fixture(autouse=True)
def mock_umgebung(monkeypatch):
    """Deaktiviert automatische Hintergrunddienste für Testisolation."""
    monkeypatch.setenv("PODCAST_RECORDER_MOCK_AUDIO", "1")
    monkeypatch.setenv("PODCAST_RECORDER_MOCK_VIDEO", "1")
    monkeypatch.setenv("PODCAST_RECORDER_BRIDGE", "0")


# ---------------------------------------------------------------------------
# Test 1: RecordingSession.stop() Cleanup-Garantie bei Exceptions
# ---------------------------------------------------------------------------

def test_recording_session_stop_cleanup_on_exception(tmp_path):
    from recordings.library import RecordingLibrary
    from recordings.recording_session import RecordingSession
    from core.app_state import AppState

    lib = RecordingLibrary(str(tmp_path))
    engine = MagicMock()
    engine.stop_recording.return_value = {"duration": 2.5, "mix": str(tmp_path / "mix.wav")}
    engine.capture_metrics.return_value = {}

    state = AppState()
    session = RecordingSession(library=lib, engine=engine, state=state)

    session.start("Test-Take", audio_enabled=True)
    assert session._aktuelle_meta is not None
    assert state.recording is True

    # Simuliere Exception bei update_metadata
    with patch.object(lib, "update_metadata", side_effect=OSError("Disk write error")):
        with pytest.raises(OSError):
            session.stop()

    # Nach dem Fehler MUSS die Session bereinigt sein
    assert session._aktuelle_meta is None, "self._aktuelle_meta muss im Fehlerfall None sein"
    assert state.recording is False, "state.recording muss im Fehlerfall False sein"
    assert session._event_log is None, "self._event_log muss geschlossen und None sein"


# ---------------------------------------------------------------------------
# Test 2: VideoRecorder.close() Zombie- und Handle-Schutz bei Wait-Timeout
# ---------------------------------------------------------------------------

def test_video_recorder_close_terminates_process_on_wait_timeout():
    from video.video_recorder import VideoRecorder

    rec = VideoRecorder(width=640, height=480, fps=30, writer_join_timeout=0.1)
    mock_proc = MagicMock()
    mock_proc.stdin = MagicMock()
    # Erster Aufruf wait() wirft TimeoutExpired
    mock_proc.wait.side_effect = [subprocess.TimeoutExpired(cmd="ffmpeg", timeout=0.1), 0]
    rec._prozess = mock_proc
    rec._stderr_datei = MagicMock()

    with pytest.raises(RuntimeError) as exc_info:
        rec.close()

    assert "Timeout" in str(exc_info.value) or "beendet" in str(exc_info.value)
    # mock_proc MUSS terminiert/gekillt worden sein
    assert mock_proc.terminate.called or mock_proc.kill.called
    assert rec._prozess is None
    assert rec._stderr_datei is None


# ---------------------------------------------------------------------------
# Test 3: ProjectsApiServer fängt ValueError bei ungültigen / Traversal-IDs ab
# ---------------------------------------------------------------------------

def test_projects_api_value_error_handling_in_handlers(tmp_path):
    from bridge.projects_api import ProjectsApiServer

    server = ProjectsApiServer(data_dir=str(tmp_path / "projects"))
    server.start(host="127.0.0.1", port=0)
    port = server.port

    try:
        # PUT /api/projects/{id}/line mit id=".." oder ungültiger ID
        url = f"http://127.0.0.1:{port}/api/projects/invalid..id/line"
        body = json.dumps({"line": ["pad1"]}).encode("utf-8")
        req_put = urllib.request.Request(
            url,
            data=body,
            headers={"Content-Type": "application/json"},
            method="PUT",
        )
        with pytest.raises(urllib.error.HTTPError) as exc_put:
            urllib.request.urlopen(req_put, timeout=5)
        # Server MUSS mit 400 oder 404 antworten, NIEMALS mit unhandled 500
        assert exc_put.value.code in (400, 404), f"Erwartet 400/404, erhalten: {exc_put.value.code}"

    finally:
        server.stop()


# ---------------------------------------------------------------------------
# Test 4: WavRecorder.close() setzt _datei=None selbst bei Exception
# ---------------------------------------------------------------------------

def test_wav_recorder_close_finally_cleans_handle():
    from audio.wav_recorder import WavRecorder

    rec = WavRecorder(samplerate=48000, channels=2)
    mock_sf = MagicMock()
    mock_sf.flush.side_effect = OSError("I/O Flush Error")
    rec._datei = mock_sf

    with pytest.raises(OSError):
        rec.close()

    assert rec._datei is None, "rec._datei muss auch nach Flush-Exception None sein"


# ---------------------------------------------------------------------------
# Test 5: RemoteWsServer._toggle_mute synchronisiert Engine und AppState
# ---------------------------------------------------------------------------

def test_remote_ws_toggle_mute_calls_engine_method():
    from bridge.remote_ws import RemoteWsServer
    from core.app_state import AppState

    engine = MagicMock()
    kanal = MagicMock()
    kanal.source_id = "mic_1"
    kanal.mute = False
    engine._channels = [kanal]
    state = AppState()

    ws = RemoteWsServer(engine=engine, state=state)
    ws._toggle_mute("mic_1")

    # set_channel_capture_enabled MUSS aufgerufen werden um kanal.mute und state synchron zu halten
    assert engine.set_channel_capture_enabled.called, "engine.set_channel_capture_enabled muss gerufen werden"


# ---------------------------------------------------------------------------
# Test 6: MainWindow.closeEvent schließt schwebende Float-Panels
# ---------------------------------------------------------------------------

def test_main_window_close_event_closes_floating_panels(qtbot):
    from ui.main_window import MainWindow
    from core.config import AppConfig
    from core.app_state import AppState
    from PySide6.QtWidgets import QWidget

    config = MagicMock(spec=AppConfig)
    config.mock_audio = True
    config.workspace_dir = "./workspace"
    dev_mgr = MagicMock()
    dev_mgr.verified_input_devices.return_value = []
    engine = MagicMock()
    engine.is_running.return_value = False
    engine.channel_count.return_value = 2
    library = MagicMock()
    library.list_recordings.return_value = []
    state = AppState()

    win = MainWindow(
        config=config,
        device_manager=dev_mgr,
        engine=engine,
        library=library,
        state=state,
    )
    qtbot.addWidget(win)

    # Simuliere ein abgelöstes Fenster in _float_panels
    mock_float_win = MagicMock(spec=QWidget)
    win._float_panels[12345] = (mock_float_win, 0, 1)

    win.close()
    assert mock_float_win.close.called, "Floating window muss bei MainWindow.close() geschlossen werden"

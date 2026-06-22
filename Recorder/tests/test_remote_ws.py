"""tests.test_remote_ws — Tests für den RemoteWsServer.

Belegt:
  - Verbindungsaufbau + Empfang von state_update (channel_peaks/recording/active_pad_ids)
  - trigger_pad → board_player.trigger() wird aufgerufen
  - toggle_mute → Engine-Kanal mute wird umgeschaltet
  - push_transcript_chunk → transcript_chunk-Nachricht empfangen
  - Sauberer Stop — kein Orphan-Thread, keine offenen Sockets

Verwendet websockets.sync.client (websockets >= 11) für synchronen Testclient.
"""
import json
import threading
import time

import pytest
import websockets.sync.client as ws_sync


@pytest.fixture(autouse=True)
def mock_umgebung(monkeypatch):
    """Alle Tests laufen mit Mock-Audio und Mock-Video."""
    monkeypatch.setenv("PODCAST_RECORDER_MOCK_AUDIO", "1")
    monkeypatch.setenv("PODCAST_RECORDER_MOCK_VIDEO", "1")
    monkeypatch.setenv("PODCAST_RECORDER_BRIDGE", "0")


# ---------------------------------------------------------------------------
# Mock-Objekte (headless, kein GUI, kein sounddevice)
# ---------------------------------------------------------------------------

class MockEngine:
    """Mock für AudioEngine — liefert statische Peaks."""
    def __init__(self, peaks=None):
        self._peaks = peaks or [0.1, 0.2]
        # MixerChannel-ähnliche Struktur für toggle_mute
        class _Kanal:
            def __init__(self, sid):
                self.source_id = sid
                self.mute = False
        self._channels = [_Kanal("mic_1"), _Kanal("system")]

    def latest_peaks(self):
        return list(self._peaks)


class MockState:
    """Mock für AppState."""
    def __init__(self, recording=False):
        self.recording = recording


class MockBoardPlayer:
    """Mock für BoardPlayer — protokolliert trigger()-Aufrufe."""
    def __init__(self):
        self.triggered = []
        self._pads = []

    def trigger(self, pad_id: str):
        self.triggered.append(pad_id)

    def active_pad_ids(self):
        return list(self._pads)


# ---------------------------------------------------------------------------
# Hilfsfunktion: Server starten und bereinigen
# ---------------------------------------------------------------------------

def _starte_server(engine=None, state=None, board_player=None, interval=0.02):
    """Startet RemoteWsServer auf Port 0 und gibt (server, port) zurück."""
    from bridge.remote_ws import RemoteWsServer
    server = RemoteWsServer(
        engine=engine or MockEngine(),
        state=state or MockState(),
        board_player=board_player or MockBoardPlayer(),
        state_update_interval=interval,
    )
    server.start(host="127.0.0.1", port=0)
    port = server.port
    assert port is not None and port > 0, f"Port nicht gesetzt: {port}"
    return server, port


# ---------------------------------------------------------------------------
# Test: Verbindungsaufbau + state_update empfangen
# ---------------------------------------------------------------------------

def test_state_update_empfangen(tmp_path):
    """Client verbindet sich und empfängt mindestens ein state_update."""
    engine = MockEngine(peaks=[0.3, 0.7])
    state = MockState(recording=True)
    board_player = MockBoardPlayer()

    server, port = _starte_server(engine=engine, state=state, board_player=board_player, interval=0.05)
    try:
        url = f"ws://127.0.0.1:{port}"
        with ws_sync.connect(url) as ws:
            # state_update sollte innerhalb ~100ms ankommen (interval=0.05)
            raw = ws.recv(timeout=2.0)
            msg = json.loads(raw)

        assert msg["type"] == "state_update", f"Erwartet state_update, bekam: {msg}"
        assert "channel_peaks" in msg, "channel_peaks fehlt"
        assert "recording" in msg, "recording fehlt"
        assert "active_pad_ids" in msg, "active_pad_ids fehlt"
        assert "prompter_line" in msg, "prompter_line fehlt"

        assert msg["channel_peaks"] == [0.3, 0.7], f"Unerwartete Peaks: {msg['channel_peaks']}"
        assert msg["recording"] is True, "recording sollte True sein"
        assert isinstance(msg["active_pad_ids"], list)
        assert msg["prompter_line"] == 0
    finally:
        server.stop()


# ---------------------------------------------------------------------------
# Test: trigger_pad → board_player.trigger() aufgerufen
# ---------------------------------------------------------------------------

def test_trigger_pad_ruft_board_player_trigger(tmp_path):
    """trigger_pad-Nachricht ruft board_player.trigger(pad_id) auf."""
    board_player = MockBoardPlayer()
    server, port = _starte_server(board_player=board_player, interval=10.0)  # kein state_update-Spam

    try:
        url = f"ws://127.0.0.1:{port}"
        with ws_sync.connect(url) as ws:
            nachricht = json.dumps({"type": "trigger_pad", "pad_id": "demo1"})
            ws.send(nachricht)
            time.sleep(0.1)  # kurz warten, bis Nachricht verarbeitet
    finally:
        server.stop()

    assert "demo1" in board_player.triggered, (
        f"board_player.trigger('demo1') wurde nicht aufgerufen. Triggered: {board_player.triggered}"
    )


# ---------------------------------------------------------------------------
# Test: toggle_mute → Engine-Kanal mute wird umgeschaltet
# ---------------------------------------------------------------------------

def test_toggle_mute_schaltet_kanal_um(tmp_path):
    """toggle_mute-Nachricht schaltet den mute-Status des Kanals um."""
    engine = MockEngine()
    assert engine._channels[0].mute is False, "Kanal sollte initial nicht gemutet sein"

    server, port = _starte_server(engine=engine, interval=10.0)

    try:
        url = f"ws://127.0.0.1:{port}"
        with ws_sync.connect(url) as ws:
            nachricht = json.dumps({"type": "toggle_mute", "source_id": "mic_1"})
            ws.send(nachricht)
            time.sleep(0.1)
    finally:
        server.stop()

    assert engine._channels[0].mute is True, (
        f"Kanal 'mic_1' sollte nach toggle_mute gemutet sein, ist aber mute={engine._channels[0].mute}"
    )


# ---------------------------------------------------------------------------
# Test: push_transcript_chunk → transcript_chunk empfangen
# ---------------------------------------------------------------------------

def test_push_transcript_chunk_gesendet(tmp_path):
    """push_transcript_chunk() sendet transcript_chunk an verbundene Clients."""
    server, port = _starte_server(interval=10.0)

    empfangen = []
    fehler = []
    bereit = threading.Event()

    def _client_thread():
        url = f"ws://127.0.0.1:{port}"
        try:
            with ws_sync.connect(url) as ws:
                bereit.set()  # Signalisieren: Client ist verbunden
                # Warten auf transcript_chunk (timeout 3 s)
                raw = ws.recv(timeout=3.0)
                empfangen.append(json.loads(raw))
        except Exception as exc:
            fehler.append(exc)

    t = threading.Thread(target=_client_thread, daemon=True)
    t.start()

    # Warten bis Client wirklich verbunden ist (max. 2 s)
    bereit.wait(timeout=2.0)
    # Kurze Pause, damit _clients-Set im asyncio-Thread aktualisiert ist
    time.sleep(0.1)

    try:
        server.push_transcript_chunk(
            text="Hallo Podcast-Welt!",
            is_final=True,
            t_start=1.5,
            engine="whisper",
        )
        t.join(timeout=3.0)
    finally:
        server.stop()

    assert len(empfangen) >= 1, "Kein transcript_chunk empfangen"
    msg = empfangen[0]
    assert msg["type"] == "transcript_chunk", f"Unerwarteter Typ: {msg}"
    assert msg["text"] == "Hallo Podcast-Welt!"
    assert msg["is_final"] is True
    assert msg["t_start"] == 1.5
    assert msg["engine"] == "whisper"


# ---------------------------------------------------------------------------
# Test: Sauberer Stop — kein Orphan-Thread
# ---------------------------------------------------------------------------

def test_kein_orphan_thread_nach_stop(tmp_path):
    """Nach stop() läuft kein RemoteWsServer-Thread mehr."""
    server, port = _starte_server(interval=10.0)

    threads_nach_start = {t.name for t in threading.enumerate()}
    assert "RemoteWsServer" in threads_nach_start, "RemoteWsServer-Thread sollte aktiv sein"

    server.stop()
    time.sleep(0.2)

    threads_nach_stop = {t.name for t in threading.enumerate()}
    assert "RemoteWsServer" not in threads_nach_stop, (
        "RemoteWsServer-Thread läuft noch nach stop() — Orphan-Thread!"
    )


# ---------------------------------------------------------------------------
# Test: Client-Disconnect löst keinen Server-Absturz aus
# ---------------------------------------------------------------------------

def test_stop_setzt_thread_auf_none():
    """Nach stop() ist _thread auf None gesetzt (kein verwaister Thread-Verweis).

    Belegt Bugsweep-Fix: stop() setzt _thread = None VOR dem join() statt danach.
    Das verhindert ein Fenster wo _thread gesetzt ist aber der Thread bereits
    heruntergefahren wird.
    """
    server, port = _starte_server(interval=10.0)

    # Vor stop(): _thread ist gesetzt
    assert server._thread is not None, "_thread muss nach start() gesetzt sein"
    server.stop()

    # Nach stop(): _thread = None
    assert server._thread is None, "_thread muss nach stop() None sein"


def test_thread_start_fehler_blockiert_nicht_naechsten_start():
    """Thread-Start-Fehler hinterlässt _thread = None, so dass start() nochmals funktioniert.

    Belegt Bugsweep-Fix Lauf 35: Früher wurde self._thread gesetzt, bevor thread.start()
    aufgerufen wurde. Bei einem Fehler in start() blieb _thread non-None → nächster
    start()-Aufruf gab sofort zurück ohne zu starten.
    """
    import unittest.mock as mock
    from bridge.remote_ws import RemoteWsServer

    server = RemoteWsServer()

    original_start = threading.Thread.start
    call_count = [0]

    def mock_start(self_thread):
        call_count[0] += 1
        if call_count[0] == 1:
            raise RuntimeError("Thread-Start sabotiert")
        return original_start(self_thread)

    with mock.patch.object(threading.Thread, "start", mock_start):
        with pytest.raises(RuntimeError, match="Thread-Start sabotiert"):
            server.start(host="127.0.0.1", port=0)

    # Nach fehlgeschlagenem start(): _thread muss None sein
    assert server._thread is None, "_thread muss None sein nach fehlgeschlagenem start()"

    # Zweiter start()-Aufruf muss erfolgreich sein
    server.start(host="127.0.0.1", port=0)
    try:
        assert server._thread is not None, "_thread muss nach erfolgreichem start() gesetzt sein"
        assert server.port is not None and server.port > 0, "Port muss nach start() gesetzt sein"
    finally:
        server.stop()


def test_client_disconnect_kein_absturz(tmp_path):
    """Wenn ein Client die Verbindung trennt, läuft der Server weiter."""
    server, port = _starte_server(interval=0.05)

    try:
        # Client verbinden und sofort trennen
        url = f"ws://127.0.0.1:{port}"
        with ws_sync.connect(url) as ws:
            pass  # Verbindung wird beim Exit sauber getrennt

        time.sleep(0.1)

        # Zweiter Client kann sich noch verbinden
        with ws_sync.connect(url) as ws2:
            raw = ws2.recv(timeout=1.0)
            msg = json.loads(raw)
        assert msg["type"] == "state_update"
    finally:
        server.stop()

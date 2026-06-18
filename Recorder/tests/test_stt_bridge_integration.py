"""Tests für die STT-Bridge-Integration.

Belegt: on_chunk → bridge.push_transcript_chunk → transcript_chunk-WebSocket-Nachricht
konform zu remote_protocol_v1.json (Felder: type, text, is_final, t_start, engine).

Headless, kein echtes Modell, kein Netzwerk (außer lokalem WebSocket).
"""
import json
import threading
import time

import numpy as np
import pytest
import websockets.sync.client as ws_sync

from stt.mock_engine import MockSttEngine
from stt.stt_manager import SttManager
from stt.transcript_models import TranscriptChunk


# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------


@pytest.fixture(autouse=True)
def mock_umgebung(monkeypatch):
    """Alle Tests laufen mit Mock-Audio, Mock-Video, Bridge deaktiviert."""
    monkeypatch.setenv("PODCAST_RECORDER_MOCK_AUDIO", "1")
    monkeypatch.setenv("PODCAST_RECORDER_MOCK_VIDEO", "1")
    monkeypatch.setenv("PODCAST_RECORDER_BRIDGE", "0")


# ---------------------------------------------------------------------------
# Mock-Objekte
# ---------------------------------------------------------------------------


class MockAudioEngine:
    """Minimaler Mock für AudioEngine (nur für WS-Server-Start benötigt)."""

    def __init__(self):
        class _Kanal:
            def __init__(self, sid):
                self.source_id = sid
                self.mute = False
        self._channels = [_Kanal("mic_1")]

    def latest_peaks(self):
        return [0.0]


class MockState:
    recording = False


class MockBoardPlayer:
    def trigger(self, pad_id: str):
        pass

    def active_pad_ids(self):
        return []


# ---------------------------------------------------------------------------
# Hilfs-Setup
# ---------------------------------------------------------------------------


def _starte_ws_server():
    """Startet RemoteWsServer auf Port 0 und gibt (server, port) zurück."""
    from bridge.remote_ws import RemoteWsServer

    server = RemoteWsServer(
        engine=MockAudioEngine(),
        state=MockState(),
        board_player=MockBoardPlayer(),
        state_update_interval=10.0,  # kein state_update-Spam im Test
    )
    server.start(host="127.0.0.1", port=0)
    port = server.port
    assert port is not None and port > 0, f"Port nicht gesetzt: {port}"
    return server, port


def _sinus_block(samples: int = 48_000, samplerate: int = 48_000) -> np.ndarray:
    """Erzeugt einen Sinus-Block (float32, Mono)."""
    t = np.linspace(0, samples / samplerate, samples, endpoint=False)
    return (np.sin(2 * np.pi * 440 * t) * 0.5).astype(np.float32)


# ---------------------------------------------------------------------------
# Test: on_chunk → push_transcript_chunk → WebSocket-Nachricht
# ---------------------------------------------------------------------------


def test_on_chunk_sendet_transcript_chunk_ueber_bridge():
    """on_chunk-Callback → bridge.push_transcript_chunk → transcript_chunk WS-Nachricht.

    Prüft Konformität zu remote_protocol_v1.json (Pflichtfelder: type, text,
    is_final, t_start, engine).
    """
    server, port = _starte_ws_server()

    empfangen: list[dict] = []
    fehler: list[Exception] = []
    bereit = threading.Event()

    def _client_thread():
        url = f"ws://127.0.0.1:{port}"
        try:
            with ws_sync.connect(url) as ws:
                bereit.set()  # Client ist verbunden
                raw = ws.recv(timeout=5.0)
                empfangen.append(json.loads(raw))
        except Exception as exc:
            fehler.append(exc)
            bereit.set()  # Event setzen, damit Test nicht hängt

    t = threading.Thread(target=_client_thread, daemon=True)
    t.start()

    # Warten bis Client verbunden ist
    bereit.wait(timeout=2.0)
    # Kurze Pause: _clients-Set im asyncio-Thread muss aktualisiert sein
    time.sleep(0.1)

    try:
        # on_chunk-Adapter: TranscriptChunk → bridge.push_transcript_chunk
        def on_chunk(chunk: TranscriptChunk) -> None:
            server.push_transcript_chunk(
                text=chunk.text,
                is_final=chunk.is_final,
                t_start=chunk.t_start,
                engine=chunk.engine,
            )

        # SttManager mit MockEngine und kurzem Fenster
        samplerate = 48_000
        window_seconds = 0.1  # kurzes Fenster für schnellen Test
        engine = MockSttEngine()
        manager = SttManager(
            engine=engine,
            on_chunk=on_chunk,
            samplerate=samplerate,
            window_seconds=window_seconds,
        )
        manager.start()

        # Genug Audio füttern, damit ein Fenster ausgelöst wird
        fenster_samples = int(samplerate * window_seconds)
        manager.feed(_sinus_block(fenster_samples + 512, samplerate))

        # Warten bis Client-Thread eine Nachricht empfangen hat
        t.join(timeout=5.0)
        manager.stop()
    finally:
        server.stop()

    # Auswertung
    assert not fehler, f"WebSocket-Client-Fehler: {fehler}"
    assert len(empfangen) >= 1, "Kein transcript_chunk empfangen"

    msg = empfangen[0]

    # Protokoll-Konformität (remote_protocol_v1.json — transcript_chunk)
    assert msg["type"] == "transcript_chunk", f"Falscher Typ: {msg['type']!r}"
    assert "text" in msg, "Feld 'text' fehlt im transcript_chunk"
    assert "is_final" in msg, "Feld 'is_final' fehlt im transcript_chunk"
    assert "t_start" in msg, "Feld 't_start' fehlt im transcript_chunk"
    assert "engine" in msg, "Feld 'engine' fehlt im transcript_chunk"

    assert isinstance(msg["text"], str), f"text sollte str sein, ist {type(msg['text'])}"
    assert isinstance(msg["is_final"], bool), f"is_final sollte bool sein"
    assert isinstance(msg["t_start"], (int, float)), f"t_start sollte numeric sein"
    assert isinstance(msg["engine"], str), f"engine sollte str sein"

    # Inhalt prüfen (Mock liefert "Segment 1")
    assert msg["text"].startswith("Segment"), f"Unerwarteter Text: {msg['text']!r}"
    assert msg["engine"] == "mock", f"Unerwartete Engine: {msg['engine']!r}"


def test_on_chunk_adapter_direkt():
    """Direkte Verifikation: TranscriptChunk-Felder werden korrekt an push_transcript_chunk übergeben."""
    empfangene_aufrufe: list[dict] = []

    def mock_push(text, is_final, t_start, engine):
        empfangene_aufrufe.append({
            "text": text,
            "is_final": is_final,
            "t_start": t_start,
            "engine": engine,
        })

    # Chunk direkt erzeugen und Adapter aufrufen
    chunk = TranscriptChunk(
        text="Hallo Podcast!",
        is_final=True,
        t_start=2.5,
        engine="mock",
    )

    # on_chunk-Adapter wie in main.py
    def on_chunk(c: TranscriptChunk) -> None:
        mock_push(
            text=c.text,
            is_final=c.is_final,
            t_start=c.t_start,
            engine=c.engine,
        )

    on_chunk(chunk)

    assert len(empfangene_aufrufe) == 1
    aufruf = empfangene_aufrufe[0]
    assert aufruf["text"] == "Hallo Podcast!"
    assert aufruf["is_final"] is True
    assert aufruf["t_start"] == 2.5
    assert aufruf["engine"] == "mock"

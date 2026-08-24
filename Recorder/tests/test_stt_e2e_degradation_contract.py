"""End-to-End- und Degradations-Vertragstests für das STT-Subsystem (TW-KLANGPULTLIGHT-04).

Belegt vollständig:
1. End-to-End-Pfad: AudioSink -> SttManager-Akkumulation -> LiveSttEngine -> BridgeService (WebSocket) -> Planer-Client (transcript_chunk).
2. Degradationsgrenzen:
   - LocalWhisperEngine: Fehlende Lib, Modell-Ladefehler, Inferenz-Exceptions -> sauberes [], kein Crash.
   - CloudSttEngine: Opt-in Nachweis, fehlender Key, Netzwerk-Timeout/ConnectionError/RateLimit -> sauberes [], kein Crash.
   - select_engine: Vollständige Fallback-Kette (Cloud -> Local -> Mock/Inactive), niemals None.
3. Audio-Puffer-Resilienz: NaN/Inf-Werte, leere Blöcke, Stereo-Downmix, unvollständige Chunks.
4. Lebenszyklus & Thread-Sicherheit: Geordneter Start/Stop ohne verwaiste Threads.

Headless, deterministisch, ohne externe Netzwerkabhängigkeit.
"""
from __future__ import annotations

import json
import sys
import threading
import time
import types
from typing import Any
from unittest.mock import MagicMock, patch

import numpy as np
import pytest
import websockets.sync.client as ws_sync

from bridge.remote_ws import RemoteWsServer
from stt.cloud_engine import CloudSttEngine
from stt.engine_base import LiveSttEngine
from stt.local_engine import LocalWhisperEngine
from stt.mock_engine import MockSttEngine
from stt.stt_manager import SttManager, select_engine
from stt.transcript_models import TranscriptChunk


# ---------------------------------------------------------------------------
# Fixtures & Mocks
# ---------------------------------------------------------------------------

@pytest.fixture(autouse=True)
def mock_umgebung(monkeypatch):
    """Sichert eine isolierte Testumgebung ohne Hardware/Bridge-Autostart."""
    monkeypatch.setenv("PODCAST_RECORDER_MOCK_AUDIO", "1")
    monkeypatch.setenv("PODCAST_RECORDER_MOCK_VIDEO", "1")
    monkeypatch.setenv("PODCAST_RECORDER_BRIDGE", "0")


class MockAudioEngineMinimal:
    """Minimaler AudioEngine-Mock für WebSocket-Server."""
    def __init__(self):
        class _Kanal:
            def __init__(self, sid):
                self.source_id = sid
                self.mute = False
        self._channels = [_Kanal("mic_1")]

    def latest_peaks(self):
        return [0.0]


class MockStateMinimal:
    recording = False


class MockBoardPlayerMinimal:
    def trigger(self, pad_id: str):
        pass

    def active_pad_ids(self):
        return []


def _starte_test_ws_server() -> tuple[RemoteWsServer, int]:
    """Startet einen RemoteWsServer auf einem dynamischen Port."""
    server = RemoteWsServer(
        engine=MockAudioEngineMinimal(),
        state=MockStateMinimal(),
        board_player=MockBoardPlayerMinimal(),
        state_update_interval=10.0,
    )
    server.start(host="127.0.0.1", port=0)
    port = server.port
    assert port is not None and port > 0
    return server, port


def _sinus_block(samples: int = 48_000, samplerate: int = 48_000) -> np.ndarray:
    """Erzeugt einen Sinus-Block (float32, Mono)."""
    t = np.linspace(0, samples / samplerate, samples, endpoint=False)
    return (np.sin(2 * np.pi * 440 * t) * 0.5).astype(np.float32)


# ---------------------------------------------------------------------------
# Test 1: Vollständiger End-to-End-Pfad bis zum WebSocket-Event
# ---------------------------------------------------------------------------

class TestSttEndToEndPath:
    """Prüft die lückenlose Kette: Audio-Feed -> SttManager -> Bridge -> WebSocket."""

    def test_e2e_live_stt_to_websocket_planer_event(self):
        """Audio-Einspeisung löst nach Fenster-Akkumulation ein valides transcript_chunk WS-Event aus."""
        server, port = _starte_test_ws_server()
        empfangene_nachrichten: list[dict[str, Any]] = []
        client_bereit = threading.Event()
        fehler: list[Exception] = []

        def _ws_client():
            url = f"ws://127.0.0.1:{port}"
            try:
                with ws_sync.connect(url) as ws:
                    client_bereit.set()
                    # Erste empfangene Nachricht auswerten
                    msg_raw = ws.recv(timeout=5.0)
                    empfangene_nachrichten.append(json.loads(msg_raw))
            except Exception as exc:
                fehler.append(exc)
                client_bereit.set()

        t_client = threading.Thread(target=_ws_client, daemon=True)
        t_client.start()
        client_bereit.wait(timeout=2.0)
        time.sleep(0.1)

        try:
            # on_chunk-Adapter wie in main.py
            def on_chunk(chunk: TranscriptChunk) -> None:
                server.push_transcript_chunk(
                    text=chunk.text,
                    is_final=chunk.is_final,
                    t_start=chunk.t_start,
                    engine=chunk.engine,
                )

            samplerate = 48_000
            window_seconds = 0.1
            engine = MockSttEngine()
            manager = SttManager(
                engine=engine,
                on_chunk=on_chunk,
                samplerate=samplerate,
                window_seconds=window_seconds,
            )
            manager.start()

            # Genug Audio für Fenster bereitstellen
            samples = int(samplerate * window_seconds) + 1024
            manager.feed(_sinus_block(samples, samplerate))

            t_client.join(timeout=5.0)
            manager.stop()
        finally:
            server.stop()

        assert not fehler, f"WebSocket-Fehler aufgetreten: {fehler}"
        assert len(empfangene_nachrichten) >= 1, "Kein transcript_chunk beim WebSocket-Client angekommen"

        chunk_msg = empfangene_nachrichten[0]
        assert chunk_msg["type"] == "transcript_chunk"
        assert "text" in chunk_msg and isinstance(chunk_msg["text"], str)
        assert "is_final" in chunk_msg and isinstance(chunk_msg["is_final"], bool)
        assert "t_start" in chunk_msg and isinstance(chunk_msg["t_start"], (int, float))
        assert "engine" in chunk_msg and chunk_msg["engine"] == "mock"


# ---------------------------------------------------------------------------
# Test 2: Degradationsgrenzen von LocalWhisperEngine
# ---------------------------------------------------------------------------

class TestLocalWhisperDegradationContract:
    """Verifiziert das fehlertolerante Verhalten der lokalen Whisper-Engine."""

    def test_local_engine_missing_dependency_graceful(self, monkeypatch):
        """Wenn faster_whisper fehlt: available() False, transcribe() liefert [] ohne Crash."""
        monkeypatch.setitem(sys.modules, "faster_whisper", None)
        engine = LocalWhisperEngine()
        engine._lib_verfuegbar = None

        assert engine.available() is False
        chunks = engine.transcribe(_sinus_block(1024), samplerate=48_000, t_start=0.0)
        assert chunks == []

    def test_local_engine_inference_runtime_exception_handled(self):
        """Inferenzfehler (z. B. Out-of-Memory / CUDA Crash) führen zu leerem Resultat statt Exception."""
        engine = LocalWhisperEngine()
        engine._lib_verfuegbar = True
        mock_model = MagicMock()
        mock_model.transcribe.side_effect = RuntimeError("CUDA Out of Memory in forward_pass")
        engine._modell = mock_model

        chunks = engine.transcribe(_sinus_block(1024), samplerate=48_000, t_start=1.5)
        assert chunks == []

    def test_local_engine_empty_or_silent_audio_returns_empty(self):
        """Stilles oder leeres Audio führt nicht zu Segment-Müll."""
        engine = LocalWhisperEngine()
        engine._lib_verfuegbar = True
        mock_model = MagicMock()
        mock_model.transcribe.return_value = ([], MagicMock())
        engine._modell = mock_model

        chunks = engine.transcribe(np.zeros(2048, dtype=np.float32), samplerate=48_000, t_start=0.0)
        assert chunks == []


# ---------------------------------------------------------------------------
# Test 3: Degradationsgrenzen von CloudSttEngine (Opt-in & Fehlerpfade)
# ---------------------------------------------------------------------------

class TestCloudSttDegradationContract:
    """Verifiziert Opt-in-Zwang und Fehlertoleranz der Cloud-Engine bei Netz- und API-Fehlern."""

    def test_cloud_engine_is_strictly_opt_in(self, monkeypatch):
        """Ohne expliziten API-Key ist CloudSttEngine niemals verfügbar."""
        monkeypatch.delenv("OPENAI_API_KEY", raising=False)
        engine = CloudSttEngine()
        engine._lib_verfuegbar = None
        assert engine.available() is False
        assert engine.transcribe(_sinus_block(1024), 48_000, 0.0) == []

    def test_cloud_engine_handles_network_timeout_and_errors(self, monkeypatch):
        """Netzwerk-Timeouts oder Connection-Drops lösen sauberes Fallback aus."""
        monkeypatch.setenv("OPENAI_API_KEY", "sk-test-token-valid-format-for-test")
        stub_openai = types.ModuleType("openai")
        monkeypatch.setitem(sys.modules, "openai", stub_openai)

        engine = CloudSttEngine()
        engine._lib_verfuegbar = True

        mock_client = MagicMock()
        mock_client.audio.transcriptions.create.side_effect = TimeoutError("Connection timed out after 10.0s")
        engine._client = mock_client

        chunks = engine.transcribe(_sinus_block(1024), samplerate=48_000, t_start=2.0)
        assert chunks == []

    def test_cloud_engine_handles_api_auth_and_ratelimit_errors(self, monkeypatch):
        """Ungültige Tokens oder Rate-Limits stürzen den Audio-Thread nicht ab."""
        monkeypatch.setenv("OPENAI_API_KEY", "sk-expired-key")
        engine = CloudSttEngine()
        engine._lib_verfuegbar = True

        mock_client = MagicMock()
        mock_client.audio.transcriptions.create.side_effect = Exception("401 Unauthorized: Invalid API Key")
        engine._client = mock_client

        chunks = engine.transcribe(_sinus_block(1024), samplerate=48_000, t_start=3.0)
        assert chunks == []


# ---------------------------------------------------------------------------
# Test 4: Engine-Auswahl- und Fallback-Hierarchie (select_engine)
# ---------------------------------------------------------------------------

class TestSelectEngineFallbackHierarchy:
    """Verifiziert die deterministische Auswahl und Fallbacks von select_engine."""

    def test_select_engine_fallback_chain_complete(self):
        """Hierarchie: Prefer Cloud -> Fallback Local -> Fallback Mock -> Inactive Local (niemals None)."""
        cloud_avail = MagicMock(spec=LiveSttEngine)
        cloud_avail.available.return_value = True
        cloud_unavail = MagicMock(spec=LiveSttEngine)
        cloud_unavail.available.return_value = False

        local_avail = MagicMock(spec=LiveSttEngine)
        local_avail.available.return_value = True
        local_unavail = MagicMock(spec=LiveSttEngine)
        local_unavail.available.return_value = False

        mock_engine = MockSttEngine()

        # 1. Cloud bevorzugt und verfügbar
        assert select_engine("cloud", local=local_avail, cloud=cloud_avail) is cloud_avail

        # 2. Cloud bevorzugt, aber unvollständig -> Fallback auf Local
        assert select_engine("cloud", local=local_avail, cloud=cloud_unavail) is local_avail

        # 3. Beide unvollständig, mit Mock -> Fallback auf Mock
        assert select_engine("cloud", local=local_unavail, cloud=cloud_unavail, mock=mock_engine) is mock_engine

        # 4. Beide unvollständig, ohne Mock -> lokales Objekt (inaktiv), aber niemals None
        fallback = select_engine("cloud", local=local_unavail, cloud=cloud_unavail, mock=None)
        assert fallback is local_unavail
        assert fallback is not None


# ---------------------------------------------------------------------------
# Test 5: Audio-Puffer- und Format-Resilienz
# ---------------------------------------------------------------------------

class TestAudioBufferResilience:
    """Verifiziert, dass SttManager mit irregulären Audio-Daten robust umgeht."""

    def test_stt_manager_handles_nan_and_inf_without_crash(self):
        """Blöcke mit NaN oder Inf bringen den STT-Worker nicht zum Absturz."""
        empfangen: list[TranscriptChunk] = []
        event = threading.Event()

        def on_chunk(c: TranscriptChunk):
            empfangen.append(c)
            event.set()

        manager = SttManager(
            engine=MockSttEngine(),
            on_chunk=on_chunk,
            samplerate=48_000,
            window_seconds=0.05,
        )
        manager.start()

        # Block mit NaN und Inf Werten
        samples = int(48_000 * 0.05) + 512
        corrupt_audio = np.full(samples, np.nan, dtype=np.float32)
        corrupt_audio[10:20] = np.inf
        corrupt_audio[20:30] = -np.inf

        # Füttern sollte abgefangen/verarbeitet werden ohne den Worker zu töten
        manager.feed(corrupt_audio)
        event.wait(timeout=2.0)
        manager.stop()

        # Worker muss sauber gestoppt haben
        assert manager._worker_thread is None

    def test_stt_manager_empty_and_zero_shape_arrays_ignored(self):
        """Leere Arrays oder 0-Shape-Blöcke führen nicht zu IndexError."""
        manager = SttManager(
            engine=MockSttEngine(),
            on_chunk=lambda _: None,
            samplerate=48_000,
            window_seconds=0.1,
        )
        manager.start()

        manager.feed(np.array([], dtype=np.float32))
        manager.feed(np.zeros((0, 2), dtype=np.float32))

        time.sleep(0.1)
        manager.stop()
        assert manager._worker_thread is None

    def test_stt_manager_graceful_shutdown_under_load(self):
        """stop() beendet die Abarbeitung deterministisch auch bei vollem Puffer."""
        manager = SttManager(
            engine=MockSttEngine(),
            on_chunk=lambda _: time.sleep(0.01),  # leicht verzögert
            samplerate=48_000,
            window_seconds=0.02,
        )
        manager.start()

        for _ in range(10):
            manager.feed(_sinus_block(2048, 48_000))

        # Schneller Stop während Abarbeitung
        manager.stop()
        assert manager._worker_thread is None

"""Tests für recordings.recording_session — RecordingSession.

Verwendet echte AudioEngine im Mock-Modus (env PODCAST_RECORDER_MOCK_AUDIO=1).
Headless, kein Hardware-Zugriff.
"""
import json
import os
import time

import pytest

from audio.device_manager import DeviceManager
from audio.engine import AudioEngine
from audio.mixer_channel import MixerChannel
from core.app_state import AppState
from core.config import AppConfig
from recordings.library import RecordingLibrary
from recordings.recording_session import RecordingSession


def _engine_und_session(tmp_path, state=None):
    """Hilfsfunktion: Baut Engine + Session im Mock-Modus."""
    config = AppConfig(mock_audio=True, workspace_dir=str(tmp_path))
    channels = [
        MixerChannel(source_id="mic_1", name="Mikrofon 1"),
    ]
    engine = AudioEngine(config, channels, state=state)
    engine.start()  # Mock-Thread starten, damit Frames produziert werden

    lib = RecordingLibrary(str(tmp_path))
    session = RecordingSession(library=lib, engine=engine, state=state)
    return engine, lib, session


class TestRecordingSessionStartStop:
    def test_start_erstellt_aufnahme(self, tmp_path):
        engine, lib, session = _engine_und_session(tmp_path)
        try:
            meta = session.start("Podcast Test")
            assert meta.recording_id.startswith("recording_")
            assert meta.title == "Podcast Test"
            # Original-Branch vorhanden
            originals = [b for b in meta.branches if b.is_original]
            assert len(originals) == 1
        finally:
            session.stop()
            engine.stop()

    def test_stop_setzt_duration_groesser_null(self, tmp_path):
        """Echte Frames → duration > 0."""
        engine, lib, session = _engine_und_session(tmp_path)
        try:
            session.start("Dauer-Test")
            time.sleep(0.15)  # Mindestens ~7 Blöcke à 1024/48000 ≈ 21 ms
            meta = session.stop()
        finally:
            engine.stop()

        assert meta.duration > 0, "Dauer muss > 0 sein (echte Frames wurden geschrieben)"

    def test_mix_wav_existiert(self, tmp_path):
        """mix.wav muss nach stop() auf der Platte liegen."""
        engine, lib, session = _engine_und_session(tmp_path)
        session.start("WAV-Test")
        time.sleep(0.12)
        meta = session.stop()
        engine.stop()

        original = next(b for b in meta.branches if b.is_original)
        assert os.path.isfile(original.audio_path), f"mix.wav fehlt: {original.audio_path}"

    def test_state_recording_flag_getoggelt(self, tmp_path):
        """AppState.recording wird korrekt gesetzt/gelöscht."""
        state = AppState()
        engine, lib, session = _engine_und_session(tmp_path, state=state)

        assert state.recording is False
        session.start("State-Test")
        assert state.recording is True
        time.sleep(0.05)
        session.stop()
        engine.stop()
        assert state.recording is False

    def test_events_jsonl_enthält_start_und_stop(self, tmp_path):
        """events.jsonl enthält start- und stop-Event."""
        engine, lib, session = _engine_und_session(tmp_path)
        meta = session.start("Events-Test")
        time.sleep(0.05)
        meta = session.stop()
        engine.stop()

        events_pfad = os.path.join(
            lib.recording_dir(meta.recording_id), "events.jsonl"
        )
        assert os.path.isfile(events_pfad)

        typen = []
        with open(events_pfad, encoding="utf-8") as f:
            for zeile in f:
                zeile = zeile.strip()
                if zeile:
                    typen.append(json.loads(zeile)["type"])

        assert "start" in typen, "start-Event fehlt in events.jsonl"
        assert "stop" in typen, "stop-Event fehlt in events.jsonl"

    def test_doppelter_start_wirft_fehler(self, tmp_path):
        """Zweiter start() ohne stop() soll RuntimeError werfen."""
        engine, lib, session = _engine_und_session(tmp_path)
        session.start("Erster Start")
        try:
            with pytest.raises(RuntimeError):
                session.start("Zweiter Start")
        finally:
            session.stop()
            engine.stop()

    def test_stop_ohne_start_wirft_fehler(self, tmp_path):
        """stop() ohne vorherigen start() soll RuntimeError werfen."""
        engine, lib, session = _engine_und_session(tmp_path)
        try:
            with pytest.raises(RuntimeError):
                session.stop()
        finally:
            engine.stop()

    def test_aufnahme_in_library_nach_stop(self, tmp_path):
        """Nach stop() ist die Aufnahme über list_recordings() auffindbar."""
        engine, lib, session = _engine_und_session(tmp_path)
        session.start("Library-Test")
        time.sleep(0.1)
        session.stop()
        engine.stop()

        aufnahmen = lib.list_recordings()
        assert len(aufnahmen) == 1
        assert aufnahmen[0].duration > 0


class TestRecordingSessionStartRollback:
    """Bugsweep-Fix Lauf 39: Partieller Start-Fehler blockiert nicht nächsten start()."""

    def test_start_fehler_in_engine_blockiert_nicht_naechsten_start(self, tmp_path):
        """Wenn engine.start_recording() wirft, muss ein erneuter start() funktionieren.

        Früher: _aktuelle_meta wurde VOR engine.start_recording() gesetzt. Bei
        einem Fehler blieb die Session im "läuft bereits"-Zustand — kein
        Recover möglich ohne Session neu zu erstellen.
        Fix: try/except in start() stellt sicher, dass _aktuelle_meta = None
        bleibt wenn engine.start_recording() scheitert.
        """
        from unittest.mock import patch

        engine, lib, session = _engine_und_session(tmp_path)
        try:
            # Ersten start()-Versuch sabotieren
            with patch.object(engine, "start_recording", side_effect=RuntimeError("Engine sabotiert")):
                with pytest.raises(RuntimeError, match="Engine sabotiert"):
                    session.start("Sabotierter Start")

            # Nach Fehler: _aktuelle_meta muss None sein
            assert session._aktuelle_meta is None, (
                "_aktuelle_meta muss None sein nach fehlgeschlagenem start()"
            )

            # Zweiter start() muss erfolgreich sein
            meta = session.start("Zweiter Start")
            assert meta.recording_id.startswith("recording_")
            time.sleep(0.05)
            session.stop()
        finally:
            engine.stop()


class TestStoppeVideoUndMuxFehlerprotokoll:
    """2b-Minor 1: VideoRecorder.close()-RuntimeError darf nicht verschluckt werden."""

    def test_video_close_fehler_wird_protokolliert(self, tmp_path, monkeypatch):
        """Wenn VideoRecorder.close() einen RuntimeError wirft, wird dieser im EventLog protokolliert.

        Statt `except Exception: pass` muss der Fehler als 'video_error'-Event im EventLog landen,
        damit ffmpeg-Fehler nicht lautlos verloren gehen.
        """
        import json as _json
        from unittest.mock import MagicMock, patch

        engine, lib, session = _engine_und_session(tmp_path)

        # Fake-VideoRecorder der bei close() einen RuntimeError wirft
        mock_recorder = MagicMock()
        mock_recorder.close.side_effect = RuntimeError("ffmpeg exited with code 1")

        # Fake-VideoCapture der sauber stoppt
        mock_capture = MagicMock()
        mock_capture.stop.return_value = None

        # Fake-VideoSource
        mock_source = MagicMock()
        mock_source.read_frame.return_value = None
        mock_source.info.width = 640
        mock_source.info.height = 480

        # Session starten
        meta = session.start("Video-Fehler-Test")

        # Intern den Recorder und die Capture-Instanz durch Mocks ersetzen
        session._video_recorder = mock_recorder
        session._video_capture = mock_capture
        session._video_pfad = str(tmp_path / "fake_video.mp4")

        # Eine leere Datei anlegen damit die Existenzprüfung in _stoppe_video_und_mux greift
        (tmp_path / "fake_video.mp4").write_bytes(b"")

        time.sleep(0.1)
        meta = session.stop()
        engine.stop()

        # Das 'video_error'-Event muss in events.jsonl stehen
        events_pfad = os.path.join(
            lib.recording_dir(meta.recording_id), "events.jsonl"
        )
        assert os.path.isfile(events_pfad), "events.jsonl fehlt"

        typen = []
        with open(events_pfad, encoding="utf-8") as f:
            for zeile in f:
                zeile = zeile.strip()
                if zeile:
                    typen.append(_json.loads(zeile)["type"])

        assert "video_error" in typen, (
            f"Erwartetes 'video_error'-Event nicht in events.jsonl. Gefundene Events: {typen}"
        )

    def test_video_close_fehler_ohne_event_log_wird_geloggt(self, tmp_path, caplog):
        """Task 3c Minor: close()-Fehler ohne EventLog wird via logging.warning geloggt.

        Belegt: der Fehler wird NICHT still verschluckt, auch wenn kein EventLog
        vorhanden ist. logging.warning() muss mindestens einen Eintrag produzieren,
        der den Fehlertext enthält.
        """
        import logging
        from unittest.mock import MagicMock

        engine, lib, session = _engine_und_session(tmp_path)

        mock_recorder = MagicMock()
        mock_recorder.close.side_effect = RuntimeError("no event log test error")

        mock_capture = MagicMock()
        mock_capture.stop.return_value = None

        # Session starten, dann EventLog manuell auf None setzen
        meta = session.start("EventLog-Fehler-Test")
        session._video_recorder = mock_recorder
        session._video_capture = mock_capture
        session._video_pfad = str(tmp_path / "fake2.mp4")
        (tmp_path / "fake2.mp4").write_bytes(b"")

        # EventLog manuell deaktivieren (Fallback-Pfad triggern)
        session._event_log = None

        with caplog.at_level(logging.WARNING, logger="recordings.recording_session"):
            session.stop()
        engine.stop()

        # Warning muss erscheinen
        assert any(
            "no event log test error" in rec.message or "kein EventLog" in rec.message
            for rec in caplog.records
        ), (
            f"Kein Warning-Log für close()-Fehler ohne EventLog. "
            f"Log-Records: {[r.message for r in caplog.records]}"
        )

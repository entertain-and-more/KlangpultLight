"""Tests für recordings.recording_session — Video-Integration (Task 2b).

Prüft:
  - Session mit Mock-Video erzeugt program.mp4 (existiert, >0 Bytes)
  - Metadaten-Feld video_path gesetzt, Dauer > 0
  - Audio-only-Pfad (ohne Video) bleibt gültig (Rückwärtskompatibilität)
"""
import os
import shutil
import time

import pytest


@pytest.fixture(autouse=True)
def mock_umgebung(monkeypatch):
    """Alle Tests hier laufen mit Mock-Audio und Mock-Video."""
    monkeypatch.setenv("PODCAST_RECORDER_MOCK_AUDIO", "1")
    monkeypatch.setenv("PODCAST_RECORDER_MOCK_VIDEO", "1")


def _ffmpeg_verfuegbar() -> bool:
    return shutil.which("ffmpeg") is not None


def _engine_und_session(tmp_path, state=None):
    """Hilfsfunktion: Baut Engine + Session im Mock-Modus."""
    from core.config import AppConfig
    from audio.mixer_channel import MixerChannel
    from audio.engine import AudioEngine
    from recordings.library import RecordingLibrary
    from recordings.recording_session import RecordingSession

    config = AppConfig(mock_audio=True, workspace_dir=str(tmp_path))
    channels = [MixerChannel(source_id="mic_1", name="Mikrofon 1")]
    engine = AudioEngine(config, channels, state=state)
    engine.start()

    lib = RecordingLibrary(str(tmp_path))
    session = RecordingSession(library=lib, engine=engine)
    return engine, lib, session


def _mock_video_source():
    """Erstellt eine MockVideoSource."""
    from video.video_manager import VideoManager
    manager = VideoManager()
    info = manager.suggest_default_source()
    assert info is not None
    return manager.open_source(info)


class TestSessionVideoIntegration:
    def test_session_mit_video_erzeugt_program_mp4(self, tmp_path):
        """Session mit Mock-Video erzeugt program.mp4 (existiert, >0 Bytes)."""
        if not _ffmpeg_verfuegbar():
            pytest.skip("ffmpeg nicht im PATH — Test übersprungen")

        engine, lib, session = _engine_und_session(tmp_path)
        try:
            video_source = _mock_video_source()
            meta = session.start("Video-Test", video_source=video_source)
            time.sleep(0.3)  # Frames produzieren lassen
            meta = session.stop()
        finally:
            engine.stop()

        # program.mp4 prüfen
        original = next(b for b in meta.branches if b.is_original)
        program_mp4 = original.video_path

        assert program_mp4, "video_path muss nach stop() gesetzt sein"
        assert os.path.isfile(program_mp4), f"program.mp4 muss existieren: {program_mp4}"
        assert os.path.getsize(program_mp4) > 0, "program.mp4 darf nicht leer sein"

    def test_session_mit_video_metadaten_video_path_gesetzt(self, tmp_path):
        """Nach stop() ist video_path im Original-Branch gesetzt."""
        if not _ffmpeg_verfuegbar():
            pytest.skip("ffmpeg nicht im PATH — Test übersprungen")

        engine, lib, session = _engine_und_session(tmp_path)
        try:
            video_source = _mock_video_source()
            session.start("Meta-Test", video_source=video_source)
            time.sleep(0.2)
            meta = session.stop()
        finally:
            engine.stop()

        original = next(b for b in meta.branches if b.is_original)
        assert original.video_path, "video_path muss gesetzt sein"
        assert original.video_path.endswith("program.mp4")

    def test_session_mit_video_dauer_groesser_null(self, tmp_path):
        """Aufnahme-Dauer muss nach stop() > 0 sein (Audio-Frames wurden geschrieben)."""
        if not _ffmpeg_verfuegbar():
            pytest.skip("ffmpeg nicht im PATH — Test übersprungen")

        engine, lib, session = _engine_und_session(tmp_path)
        try:
            video_source = _mock_video_source()
            session.start("Dauer-Test", video_source=video_source)
            time.sleep(0.2)
            meta = session.stop()
        finally:
            engine.stop()

        assert meta.duration > 0, "Dauer muss > 0 sein nach Video-Aufnahme"

    def test_session_audio_only_bleibt_gueltig(self, tmp_path):
        """Audio-only (video_source=None) — rückwärtskompatibel, kein Video-Pfad."""
        engine, lib, session = _engine_und_session(tmp_path)
        try:
            meta = session.start("Audio-Only-Test")  # kein video_source
            time.sleep(0.15)
            meta = session.stop()
        finally:
            engine.stop()

        assert meta.duration > 0, "Dauer muss > 0 sein (Audio-Only)"
        original = next(b for b in meta.branches if b.is_original)
        assert original.audio_path, "audio_path muss gesetzt sein"
        assert not original.video_path, "video_path muss leer sein bei Audio-Only"

    def test_session_audio_only_mix_wav_existiert(self, tmp_path):
        """Audio-only: mix.wav muss auf der Platte liegen."""
        engine, lib, session = _engine_und_session(tmp_path)
        session.start("WAV-Only-Test")
        time.sleep(0.12)
        meta = session.stop()
        engine.stop()

        original = next(b for b in meta.branches if b.is_original)
        assert os.path.isfile(original.audio_path), f"mix.wav fehlt: {original.audio_path}"

    def test_session_video_only_ohne_audio_path(self, tmp_path):
        """Video-only erzeugt program.mp4, aber keine Audio-WAV im Original-Branch."""
        if not _ffmpeg_verfuegbar():
            pytest.skip("ffmpeg nicht im PATH — Test übersprungen")

        engine, lib, session = _engine_und_session(tmp_path)
        try:
            video_source = _mock_video_source()
            session.start(
                "Video-Only-Test",
                video_source=video_source,
                audio_enabled=False,
            )
            time.sleep(0.25)
            meta = session.stop()
        finally:
            engine.stop()

        original = next(b for b in meta.branches if b.is_original)
        assert original.audio_path == ""
        assert original.video_path.endswith("program.mp4")
        assert os.path.isfile(original.video_path)
        assert os.path.getsize(original.video_path) > 0
        assert meta.duration > 0

    def test_session_video_only_ohne_videoquelle_ungueltig(self, tmp_path):
        """audio_enabled=False ohne Videoquelle wird abgelehnt statt leere Aufnahme zu erzeugen."""
        engine, _lib, session = _engine_und_session(tmp_path)
        try:
            with pytest.raises(ValueError, match="Video-only"):
                session.start("Ungültig", audio_enabled=False)
        finally:
            engine.stop()

    def test_session_video_aufnahme_in_library_auffindbar(self, tmp_path):
        """Nach Video-Aufnahme ist die Aufnahme über list_recordings() auffindbar."""
        if not _ffmpeg_verfuegbar():
            pytest.skip("ffmpeg nicht im PATH — Test übersprungen")

        engine, lib, session = _engine_und_session(tmp_path)
        try:
            video_source = _mock_video_source()
            session.start("Library-Video-Test", video_source=video_source)
            time.sleep(0.2)
            session.stop()
        finally:
            engine.stop()

        aufnahmen = lib.list_recordings()
        assert len(aufnahmen) >= 1
        assert aufnahmen[0].duration > 0

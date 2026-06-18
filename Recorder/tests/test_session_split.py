"""Tests für recordings.recording_session — Video-Split-Aufnahme (Task 6b, TDD).

Prüft:
  - Session mit 2 Mock-Video-Quellen → program.mp4 existiert (>0 Bytes)
  - program.mp4 hat die Compositor-Zielauflösung
  - Single-Source-Pfad bleibt grün (Rückwärtskompatibilität)
  - video_sources als Liste mit 1 Element → Single-Source-Pfad
"""
import os
import shutil
import time

import pytest


@pytest.fixture(autouse=True)
def mock_umgebung(monkeypatch):
    monkeypatch.setenv("PODCAST_RECORDER_MOCK_AUDIO", "1")
    monkeypatch.setenv("PODCAST_RECORDER_MOCK_VIDEO", "1")


def _ffmpeg_verfuegbar() -> bool:
    return shutil.which("ffmpeg") is not None


def _engine_und_session(tmp_path):
    from core.config import AppConfig
    from audio.mixer_channel import MixerChannel
    from audio.engine import AudioEngine
    from recordings.library import RecordingLibrary
    from recordings.recording_session import RecordingSession

    config = AppConfig(mock_audio=True, workspace_dir=str(tmp_path))
    channels = [MixerChannel(source_id="mic_1", name="Mikrofon 1")]
    engine = AudioEngine(config, channels)
    engine.start()

    lib = RecordingLibrary(str(tmp_path))
    session = RecordingSession(library=lib, engine=engine)
    return engine, lib, session


def _zwei_mock_quellen():
    """Erstellt 2 MockVideoSource-Instanzen."""
    from video.video_source import MockVideoSource, VideoSourceInfo
    info0 = VideoSourceInfo(
        source_id="mock_0", name="Mock 0", kind="mock",
        verified=True, is_mock=True, width=128, height=72,
    )
    info1 = VideoSourceInfo(
        source_id="mock_1", name="Mock 1", kind="mock",
        verified=True, is_mock=True, width=128, height=72,
    )
    return MockVideoSource(info0), MockVideoSource(info1)


def _eine_mock_quelle():
    from video.video_manager import VideoManager
    manager = VideoManager()
    info = manager.suggest_default_source()
    assert info is not None
    return manager.open_source(info)


class TestSessionSplit:
    def test_zwei_quellen_program_mp4_existiert(self, tmp_path):
        """Session mit 2 Mock-Video-Quellen → program.mp4 existiert und ist >0 Bytes."""
        if not _ffmpeg_verfuegbar():
            pytest.skip("ffmpeg nicht im PATH — Test übersprungen")

        engine, lib, session = _engine_und_session(tmp_path)
        src0, src1 = _zwei_mock_quellen()
        try:
            meta = session.start("Split-Test", video_sources=[src0, src1])
            time.sleep(0.5)  # Frames produzieren lassen
            meta = session.stop()
        finally:
            engine.stop()

        original = next(b for b in meta.branches if b.is_original)
        program_mp4 = original.video_path

        assert program_mp4, "video_path muss nach stop() gesetzt sein"
        assert os.path.isfile(program_mp4), f"program.mp4 muss existieren: {program_mp4}"
        assert os.path.getsize(program_mp4) > 0, "program.mp4 darf nicht leer sein"

    def test_zwei_quellen_compositor_aufloesung(self, tmp_path):
        """program.mp4 aus 2-Quellen-Aufnahme hat die Compositor-Zielauflösung."""
        if not _ffmpeg_verfuegbar():
            pytest.skip("ffmpeg nicht im PATH — Test übersprungen")

        engine, lib, session = _engine_und_session(tmp_path)
        src0, src1 = _zwei_mock_quellen()
        try:
            meta = session.start("Auflösungs-Test", video_sources=[src0, src1])
            time.sleep(0.5)
            meta = session.stop()
        finally:
            engine.stop()

        original = next(b for b in meta.branches if b.is_original)
        program_mp4 = original.video_path
        assert program_mp4 and os.path.isfile(program_mp4)

        # Auflösung per cv2 prüfen
        import cv2
        cap = cv2.VideoCapture(program_mp4)
        try:
            w = int(cap.get(cv2.CAP_PROP_FRAME_WIDTH))
            h = int(cap.get(cv2.CAP_PROP_FRAME_HEIGHT))
        finally:
            cap.release()

        # Zielauflösung des Compositors (Standard: 1280×720)
        from video.compositor import COMPOSITOR_STANDARD_AUFLOESUNG
        erwartet_w, erwartet_h = COMPOSITOR_STANDARD_AUFLOESUNG
        assert w == erwartet_w, f"Breite: erwartet {erwartet_w}, erhalten {w}"
        assert h == erwartet_h, f"Höhe: erwartet {erwartet_h}, erhalten {h}"

    def test_single_source_pfad_weiter_gruen(self, tmp_path):
        """Single-Source (video_source=...) bleibt abwärtskompatibel."""
        if not _ffmpeg_verfuegbar():
            pytest.skip("ffmpeg nicht im PATH — Test übersprungen")

        engine, lib, session = _engine_und_session(tmp_path)
        try:
            src = _eine_mock_quelle()
            meta = session.start("Single-Source-Test", video_source=src)
            time.sleep(0.3)
            meta = session.stop()
        finally:
            engine.stop()

        original = next(b for b in meta.branches if b.is_original)
        assert original.video_path, "video_path muss gesetzt sein"
        assert os.path.isfile(original.video_path), "program.mp4 muss existieren"
        assert os.path.getsize(original.video_path) > 0

    def test_video_sources_liste_mit_einem_element_single_pfad(self, tmp_path):
        """video_sources=[src] (1 Element) → Single-Source-Pfad, kein Compositor."""
        if not _ffmpeg_verfuegbar():
            pytest.skip("ffmpeg nicht im PATH — Test übersprungen")

        engine, lib, session = _engine_und_session(tmp_path)
        src0, _ = _zwei_mock_quellen()
        try:
            meta = session.start("1-Element-Liste-Test", video_sources=[src0])
            time.sleep(0.3)
            meta = session.stop()
        finally:
            engine.stop()

        original = next(b for b in meta.branches if b.is_original)
        assert original.video_path, "video_path muss gesetzt sein"
        assert os.path.isfile(original.video_path)

    def test_audio_only_bleibt_gueltig_nach_split_erweiterung(self, tmp_path):
        """Audio-only (kein video_source/video_sources) bleibt korrekt."""
        engine, lib, session = _engine_und_session(tmp_path)
        try:
            meta = session.start("Audio-Only-Split-Test")
            time.sleep(0.15)
            meta = session.stop()
        finally:
            engine.stop()

        assert meta.duration > 0
        original = next(b for b in meta.branches if b.is_original)
        assert original.audio_path
        assert not original.video_path

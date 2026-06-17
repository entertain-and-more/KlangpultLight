"""Tests für video.video_recorder — VideoRecorder mit echtem ffmpeg."""
import os
import shutil
import numpy as np
import pytest


def _ffmpeg_verfuegbar() -> bool:
    return shutil.which("ffmpeg") is not None


def _synthetischen_frame_erzeugen(width: int, height: int, frame_idx: int) -> np.ndarray:
    """Erzeugt einen synthetischen BGR-Frame (Farbverlauf + Zähler-Muster)."""
    frame = np.zeros((height, width, 3), dtype=np.uint8)
    # Blau-Kanal: Farbverlauf horizontal
    frame[:, :, 0] = np.linspace(0, 255, width, dtype=np.uint8)
    # Grün-Kanal: Farbverlauf vertikal
    frame[:, :, 1] = np.linspace(0, 255, height, dtype=np.uint8).reshape(-1, 1)
    # Rot-Kanal: Frame-Index kodiert (mod 256)
    frame[:, :, 2] = frame_idx % 256
    return frame


def test_video_recorder_erzeugt_nicht_leere_mp4(tmp_path):
    """VideoRecorder schreibt aus synthetischen Frames eine existierende, nicht-leere mp4."""
    if not _ffmpeg_verfuegbar():
        pytest.skip("ffmpeg nicht im PATH — Test übersprungen")

    from video.video_recorder import VideoRecorder

    width, height, fps = 320, 240, 10
    out_pfad = str(tmp_path / "test_out.mp4")

    recorder = VideoRecorder(width=width, height=height, fps=fps)
    recorder.open(out_pfad)

    for i in range(5):
        frame = _synthetischen_frame_erzeugen(width, height, i)
        recorder.write_frame(frame)

    dauer = recorder.close()

    assert os.path.exists(out_pfad), "Ausgabedatei muss existieren"
    assert os.path.getsize(out_pfad) > 0, "Ausgabedatei darf nicht leer sein"
    assert dauer > 0.0, f"Dauer muss > 0 sein, war: {dauer}"


def test_video_recorder_dauer_plausibel(tmp_path):
    """Dauer aus close() entspricht ungefähr frames/fps."""
    if not _ffmpeg_verfuegbar():
        pytest.skip("ffmpeg nicht im PATH — Test übersprungen")

    from video.video_recorder import VideoRecorder

    width, height, fps = 320, 240, 10
    n_frames = 10
    erwartete_dauer = n_frames / fps  # 1.0 Sekunde

    out_pfad = str(tmp_path / "dauer_test.mp4")
    recorder = VideoRecorder(width=width, height=height, fps=fps)
    recorder.open(out_pfad)

    for i in range(n_frames):
        frame = _synthetischen_frame_erzeugen(width, height, i)
        recorder.write_frame(frame)

    dauer = recorder.close()

    # Toleranz ± 20% (ffmpeg-Overhead)
    assert abs(dauer - erwartete_dauer) < erwartete_dauer * 0.5, (
        f"Dauer {dauer:.3f}s weicht zu stark von Erwartung {erwartete_dauer:.3f}s ab"
    )


def test_video_recorder_falsches_ffmpeg_wirft_exception(tmp_path):
    """Bei fehlendem ffmpeg-Binary wirft open() eine klare Exception."""
    from video.video_recorder import VideoRecorder

    recorder = VideoRecorder(width=320, height=240, fps=10, ffmpeg_bin="ffmpeg_gibt_es_nicht_xyz")

    with pytest.raises(Exception, match="ffmpeg"):
        recorder.open(str(tmp_path / "niemals.mp4"))


def test_video_recorder_erstellt_verzeichnis(tmp_path):
    """VideoRecorder legt das Ausgabeverzeichnis an, falls es nicht existiert."""
    if not _ffmpeg_verfuegbar():
        pytest.skip("ffmpeg nicht im PATH — Test übersprungen")

    from video.video_recorder import VideoRecorder

    neues_verzeichnis = tmp_path / "neues_verz" / "tief"
    out_pfad = str(neues_verzeichnis / "video.mp4")

    recorder = VideoRecorder(width=160, height=120, fps=5)
    recorder.open(out_pfad)

    for i in range(3):
        frame = _synthetischen_frame_erzeugen(160, 120, i)
        recorder.write_frame(frame)

    recorder.close()

    assert os.path.exists(out_pfad), "Datei muss im neu erstellten Verzeichnis liegen"

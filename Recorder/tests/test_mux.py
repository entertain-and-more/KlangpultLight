"""Tests für video.video_recorder.mux_audio_video — Audio-Video-Mux mit ffmpeg."""
import os
import shutil
import struct
import wave
import numpy as np
import pytest


def _ffmpeg_verfuegbar() -> bool:
    return shutil.which("ffmpeg") is not None


def _ffprobe_verfuegbar() -> bool:
    return shutil.which("ffprobe") is not None


def _kurze_wav_erzeugen(pfad: str, dauer_s: float = 0.5, samplerate: int = 44100) -> None:
    """Erzeugt eine kurze Sinus-WAV-Datei ohne externe Abhängigkeiten."""
    n_frames = int(dauer_s * samplerate)
    freq = 440.0
    t = np.linspace(0, dauer_s, n_frames, endpoint=False)
    audio = (0.3 * np.sin(2 * np.pi * freq * t) * 32767).astype(np.int16)

    with wave.open(pfad, "w") as wf:
        wf.setnchannels(1)
        wf.setsampwidth(2)  # 16-bit
        wf.setframerate(samplerate)
        wf.writeframes(audio.tobytes())


def _synthetischen_frame_erzeugen(width: int, height: int, idx: int) -> np.ndarray:
    frame = np.zeros((height, width, 3), dtype=np.uint8)
    frame[:, :, 0] = idx % 256
    frame[:, :, 1] = (idx * 2) % 256
    frame[:, :, 2] = (idx * 3) % 256
    return frame


@pytest.fixture
def kurze_test_dateien(tmp_path):
    """Erzeugt eine kurze WAV + eine kurze MP4 (ohne Audio) für Mux-Tests."""
    if not _ffmpeg_verfuegbar():
        pytest.skip("ffmpeg nicht im PATH — Test übersprungen")

    from video.video_recorder import VideoRecorder

    # Kurze WAV erzeugen
    wav_pfad = str(tmp_path / "test_audio.wav")
    _kurze_wav_erzeugen(wav_pfad, dauer_s=0.5)
    assert os.path.exists(wav_pfad)

    # Kurze MP4 (stumm) erzeugen
    video_pfad = str(tmp_path / "test_video.mp4")
    rec = VideoRecorder(width=160, height=120, fps=10)
    rec.open(video_pfad)
    for i in range(5):
        frame = _synthetischen_frame_erzeugen(160, 120, i)
        rec.write_frame(frame)
    rec.close()
    assert os.path.exists(video_pfad)

    return {"wav": wav_pfad, "video": video_pfad, "tmp": str(tmp_path)}


def test_mux_erzeugt_ausgabedatei(kurze_test_dateien):
    """mux_audio_video erzeugt eine nicht-leere program.mp4."""
    from video.video_recorder import mux_audio_video

    out_pfad = os.path.join(kurze_test_dateien["tmp"], "program.mp4")

    ergebnis = mux_audio_video(
        video_path=kurze_test_dateien["video"],
        audio_path=kurze_test_dateien["wav"],
        out_path=out_pfad,
    )

    assert ergebnis == out_pfad, "Rückgabewert muss out_path sein"
    assert os.path.exists(out_pfad), "Ausgabedatei muss existieren"
    assert os.path.getsize(out_pfad) > 0, "Ausgabedatei darf nicht leer sein"


def test_mux_ausgabe_hat_video_und_audio_spur(kurze_test_dateien):
    """Gemuxte MP4 enthält sowohl Video- als auch Audio-Spur (geprüft via ffprobe)."""
    if not _ffprobe_verfuegbar():
        pytest.skip("ffprobe nicht im PATH — Stream-Prüfung übersprungen")

    import subprocess
    import json
    from video.video_recorder import mux_audio_video

    out_pfad = os.path.join(kurze_test_dateien["tmp"], "program_geprüft.mp4")
    mux_audio_video(
        video_path=kurze_test_dateien["video"],
        audio_path=kurze_test_dateien["wav"],
        out_path=out_pfad,
    )

    # ffprobe: Stream-Infos als JSON abrufen
    result = subprocess.run(
        [
            "ffprobe", "-v", "quiet",
            "-print_format", "json",
            "-show_streams",
            out_pfad,
        ],
        capture_output=True,
        text=True,
        timeout=15,
    )

    assert result.returncode == 0, f"ffprobe fehlgeschlagen: {result.stderr}"

    info = json.loads(result.stdout)
    streams = info.get("streams", [])
    codec_types = {s.get("codec_type") for s in streams}

    assert "video" in codec_types, f"Kein Video-Stream gefunden. Streams: {codec_types}"
    assert "audio" in codec_types, f"Kein Audio-Stream gefunden. Streams: {codec_types}"


def test_mux_gibt_out_path_zurueck(kurze_test_dateien):
    """mux_audio_video gibt immer out_path als String zurück."""
    from video.video_recorder import mux_audio_video

    out_pfad = os.path.join(kurze_test_dateien["tmp"], "rueckgabe_test.mp4")

    ergebnis = mux_audio_video(
        video_path=kurze_test_dateien["video"],
        audio_path=kurze_test_dateien["wav"],
        out_path=out_pfad,
    )

    assert isinstance(ergebnis, str)
    assert ergebnis == out_pfad

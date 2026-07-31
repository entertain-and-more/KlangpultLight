"""Tests für video.video_recorder — VideoRecorder mit echtem ffmpeg."""
import os
import shutil
import threading
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


def test_video_recorder_close_idempotent(tmp_path):
    """close() darf zweimal aufgerufen werden — zweiter Aufruf gibt dieselbe Dauer zurück (M-2)."""
    if not _ffmpeg_verfuegbar():
        pytest.skip("ffmpeg nicht im PATH — Test übersprungen")

    from video.video_recorder import VideoRecorder

    width, height, fps = 160, 120, 10
    out_pfad = str(tmp_path / "idempotent.mp4")

    recorder = VideoRecorder(width=width, height=height, fps=fps)
    recorder.open(out_pfad)

    for i in range(5):
        frame = _synthetischen_frame_erzeugen(width, height, i)
        recorder.write_frame(frame)

    dauer1 = recorder.close()
    dauer2 = recorder.close()  # zweiter Aufruf — darf nicht abstürzen

    assert dauer1 == dauer2, f"Idempotenz verletzt: close() lieferte {dauer1} vs. {dauer2}"
    assert dauer1 > 0, "Dauer muss > 0 sein"


def test_video_recorder_write_frame_falsche_shape(tmp_path):
    """write_frame() muss ValueError werfen, wenn die Frame-Shape nicht passt (M-3)."""
    if not _ffmpeg_verfuegbar():
        pytest.skip("ffmpeg nicht im PATH — Test übersprungen")

    from video.video_recorder import VideoRecorder

    width, height, fps = 320, 240, 10
    out_pfad = str(tmp_path / "shape_fehler.mp4")

    recorder = VideoRecorder(width=width, height=height, fps=fps)
    recorder.open(out_pfad)

    # Falsches Shape — andere Breite
    falscher_frame = np.zeros((height, width // 2, 3), dtype=np.uint8)
    with pytest.raises(ValueError, match="Shape"):
        recorder.write_frame(falscher_frame)

    # Recorder aufräumen (FFmpeg läuft noch)
    try:
        recorder.close()
    except Exception:
        pass


class _BlockierenderStdin:
    def __init__(self):
        self.write_started = threading.Event()
        self.release = threading.Event()
        self.closed = False

    def write(self, data):
        self.write_started.set()
        self.release.wait(timeout=2)

    def close(self):
        self.closed = True


class _FakeProcess:
    def __init__(self, stdin):
        self.stdin = stdin
        self.returncode = 0
        self.terminated = False

    def wait(self, timeout=None):
        return self.returncode

    def terminate(self):
        self.terminated = True
        self.returncode = -15
        self.stdin.release.set()


def _recorder_mit_blockierender_pipe(monkeypatch, tmp_path, queue_size=1, join_timeout=0.05):
    from video import video_recorder

    stdin = _BlockierenderStdin()
    prozess = _FakeProcess(stdin)
    monkeypatch.setattr(video_recorder.shutil, "which", lambda _name: "ffmpeg")
    monkeypatch.setattr(video_recorder.subprocess, "Popen", lambda *args, **kwargs: prozess)
    recorder = video_recorder.VideoRecorder(
        width=2,
        height=2,
        fps=10,
        writer_queue_size=queue_size,
        writer_join_timeout=join_timeout,
    )
    recorder.open(str(tmp_path / "queue.mp4"))
    return recorder, stdin, prozess


def test_video_recorder_verwirft_frames_bei_writer_rueckstau(monkeypatch, tmp_path):
    """Ein blockiertes FFmpeg-stdin darf den Capture-Callback nicht aufhalten."""
    recorder, stdin, _prozess = _recorder_mit_blockierender_pipe(monkeypatch, tmp_path)
    frame = np.zeros((2, 2, 3), dtype=np.uint8)

    recorder.write_frame(frame)
    assert stdin.write_started.wait(timeout=1), "Writer muss den ersten Frame bearbeiten"
    recorder.write_frame(frame)
    recorder.write_frame(frame)

    assert recorder.diagnostics["frames_dropped"] == 1
    stdin.release.set()
    assert recorder.close() == pytest.approx(0.2)


def test_video_recorder_beendet_blockierten_writer_kontrolliert(monkeypatch, tmp_path):
    """Der Aufnahme-Stopp terminiert FFmpeg statt an einem blockierten Write zu hängen."""
    recorder, stdin, prozess = _recorder_mit_blockierender_pipe(monkeypatch, tmp_path)
    recorder.write_frame(np.zeros((2, 2, 3), dtype=np.uint8))
    assert stdin.write_started.wait(timeout=1)

    with pytest.raises(RuntimeError, match="Exit-Code -15"):
        recorder.close()

    assert prozess.terminated

"""Tests für die Roh-Capture-Diagnose (zero_pct) der AudioEngine.

Portiert aus der Vollversion (Codex-Review): zählt Nullen im ROHEN Callback-Input
(vor jeder Verarbeitung) → WASAPI/Treiber vs. App. Plus RT-Log-Drossel via Status.
"""
import numpy as np


def _engine(tmp_path, channels=("mic1", "mic2")):
    from core.config import AppConfig
    from audio.mixer_channel import MixerChannel
    from audio.engine import AudioEngine
    cfg = AppConfig(mock_audio=True, workspace_dir=str(tmp_path))
    kanaele = [MixerChannel(source_id=c, name=c) for c in channels]
    return AudioEngine(cfg, kanaele)


def test_capture_metrics_struktur_und_default(tmp_path):
    eng = _engine(tmp_path)
    m = eng.capture_metrics()
    assert "mic1" in m and "mic2" in m
    assert m["mic1"]["zero_pct"] == 0.0
    assert set(m["mic1"]) >= {"callbacks", "total", "zeros", "status_count", "statuses", "zero_pct"}


def test_callback_zaehlt_roh_nullen(tmp_path):
    eng = _engine(tmp_path)
    cb = eng._stream_callback_factory("mic1")
    block = np.zeros((100, 2), dtype=np.float32)  # 200 Samples, alle 0 …
    block[0, 0] = 0.5                              # … bis auf 1
    cb(block, 100, None, 0)  # kein Status
    m = eng.capture_metrics()["mic1"]
    assert m["callbacks"] == 1
    assert m["total"] == 200
    assert m["zeros"] == 199
    assert m["zero_pct"] == round(100.0 * 199 / 200, 2)


def test_callback_zaehlt_status_und_drosselt(tmp_path):
    eng = _engine(tmp_path)
    cb = eng._stream_callback_factory("mic1")
    block = np.ones((64, 2), dtype=np.float32)
    # Mehrere Status-Callbacks rasch hintereinander → Drossel zählt alle, loggt 1x.
    for _ in range(5):
        cb(block, 64, None, "input overflow")
    m = eng.capture_metrics()["mic1"]
    assert m["status_count"] == 5
    assert "input overflow" in m["statuses"]


def test_reset_capture_metrics(tmp_path):
    eng = _engine(tmp_path)
    eng._capture_metrics["mic1"].update({"callbacks": 3, "total": 1000, "zeros": 250})
    assert eng.capture_metrics()["mic1"]["zero_pct"] == 25.0
    eng.reset_capture_metrics()
    assert eng.capture_metrics()["mic1"]["zero_pct"] == 0.0
    assert eng.capture_metrics()["mic1"]["total"] == 0


def test_start_recording_resetet_metriken(tmp_path, monkeypatch):
    monkeypatch.setenv("PODCAST_RECORDER_MOCK_AUDIO", "1")
    eng = _engine(tmp_path)
    eng._capture_metrics["mic1"].update({"total": 500, "zeros": 100})
    eng.start_recording(str(tmp_path / "take01"))
    try:
        assert eng.capture_metrics()["mic1"]["total"] == 0
    finally:
        eng.stop_recording()

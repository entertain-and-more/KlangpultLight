"""Tests für audio.mixer_channel — Gain, Mute, Peak."""
import numpy as np
import pytest


def _block(wert: float, laenge: int = 1024, kanaele: int = 2) -> np.ndarray:
    """Hilfs-Block mit konstantem Wert, Shape (laenge, kanaele)."""
    return np.full((laenge, kanaele), wert, dtype=np.float32)


def test_gain_skaliert():
    """process() mit gain=0.5 halbiert die Amplitude."""
    from audio.mixer_channel import MixerChannel
    kanal = MixerChannel(source_id="mic1", name="Mikrofon 1", gain=0.5)
    block = _block(0.8)
    out = kanal.process(block)
    assert np.allclose(out, block * 0.5, atol=1e-6)


def test_mute_liefert_nullblock():
    """Wenn mute=True, liefert process() einen Nullblock."""
    from audio.mixer_channel import MixerChannel
    kanal = MixerChannel(source_id="mic1", name="Mikrofon 1", mute=True)
    block = _block(0.9)
    out = kanal.process(block)
    assert np.all(out == 0.0)


def test_peak_wird_aktualisiert():
    """Nach process() enthält peak den korrekten Maximalwert."""
    from audio.mixer_channel import MixerChannel
    kanal = MixerChannel(source_id="mic1", name="Mikrofon 1", gain=1.0)
    block = _block(0.6)
    kanal.process(block)
    assert abs(kanal.peak - 0.6) < 1e-6


def test_peak_bei_mute():
    """Auch bei mute=True wird peak auf Basis des Outputs (Nullen) aktualisiert."""
    from audio.mixer_channel import MixerChannel
    kanal = MixerChannel(source_id="mic1", name="Mikrofon 1", mute=True)
    kanal.process(_block(0.9))
    assert kanal.peak == 0.0


def test_gain_standard_ist_eins():
    """Standardmäßiger Gain ist 1.0 (keine Abschwächung)."""
    from audio.mixer_channel import MixerChannel
    kanal = MixerChannel(source_id="mic1", name="Mikrofon 1")
    block = _block(0.5)
    out = kanal.process(block)
    assert np.allclose(out, block, atol=1e-6)

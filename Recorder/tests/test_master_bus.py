"""Tests für audio.master_bus — Summierung, Solo, Clipping."""
import numpy as np


def _block(wert: float, laenge: int = 1024, kanaele: int = 2) -> np.ndarray:
    """Hilfs-Block mit konstantem Wert, Shape (laenge, kanaele)."""
    return np.full((laenge, kanaele), wert, dtype=np.float32)


def test_summierung_zweier_kanaele():
    """MasterBus summiert zwei Kanäle korrekt."""
    from audio.mixer_channel import MixerChannel
    from audio.master_bus import MasterBus
    ch1 = MixerChannel(source_id="a", name="Kanal A", gain=1.0)
    ch2 = MixerChannel(source_id="b", name="Kanal B", gain=1.0)
    bus = MasterBus([ch1, ch2])
    blocks = {"a": _block(0.2), "b": _block(0.3)}
    out = bus.mix(blocks)
    # 0.2 + 0.3 = 0.5, kein Clipping
    assert np.allclose(out, 0.5, atol=1e-5)


def test_solo_blendet_nicht_solo_aus():
    """Wenn ein Kanal solo=True ist, werden Nicht-Solo-Kanäle ausgeblendet."""
    from audio.mixer_channel import MixerChannel
    from audio.master_bus import MasterBus
    ch1 = MixerChannel(source_id="a", name="Solo Kanal", gain=1.0, solo=True)
    ch2 = MixerChannel(source_id="b", name="Normaler Kanal", gain=1.0, solo=False)
    bus = MasterBus([ch1, ch2])
    blocks = {"a": _block(0.4), "b": _block(0.6)}
    out = bus.mix(blocks)
    # Nur ch1 trägt bei: 0.4
    assert np.allclose(out, 0.4, atol=1e-5)


def test_clipping_auf_minus_eins_bis_eins():
    """Summiertes Signal wird auf [-1, 1] geclippt."""
    from audio.mixer_channel import MixerChannel
    from audio.master_bus import MasterBus
    ch1 = MixerChannel(source_id="a", name="Kanal A", gain=1.0)
    ch2 = MixerChannel(source_id="b", name="Kanal B", gain=1.0)
    bus = MasterBus([ch1, ch2])
    # 0.8 + 0.8 = 1.6 > 1.0 → geclippt auf 1.0
    blocks = {"a": _block(0.8), "b": _block(0.8)}
    out = bus.mix(blocks)
    assert np.all(out <= 1.0)
    assert np.all(out >= -1.0)
    assert np.allclose(out, 1.0, atol=1e-5)


def test_peaks_gibt_kanalpeaks():
    """peaks() liefert eine Liste mit der Länge der Kanal-Liste."""
    from audio.mixer_channel import MixerChannel
    from audio.master_bus import MasterBus
    ch1 = MixerChannel(source_id="a", name="Kanal A", gain=1.0)
    ch2 = MixerChannel(source_id="b", name="Kanal B", gain=1.0)
    bus = MasterBus([ch1, ch2])
    bus.mix({"a": _block(0.3), "b": _block(0.5)})
    p = bus.peaks()
    assert len(p) == 2
    assert abs(p[0] - 0.3) < 1e-5
    assert abs(p[1] - 0.5) < 1e-5


def test_peaks_alle_kanaele_auch_nicht_solo():
    """Auch Nicht-Solo-Kanäle bekommen ihren Peak aktualisiert."""
    from audio.mixer_channel import MixerChannel
    from audio.master_bus import MasterBus
    ch1 = MixerChannel(source_id="a", name="Solo", gain=1.0, solo=True)
    ch2 = MixerChannel(source_id="b", name="Normal", gain=1.0, solo=False)
    bus = MasterBus([ch1, ch2])
    bus.mix({"a": _block(0.3), "b": _block(0.7)})
    p = bus.peaks()
    # Beide Peaks sollen gesetzt sein
    assert abs(p[0] - 0.3) < 1e-5
    assert abs(p[1] - 0.7) < 1e-5

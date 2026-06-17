"""Tests für audio.wav_recorder — Datei schreiben, Dauer, Rücklesbarkeit."""
import numpy as np
import soundfile as sf
import pytest


def test_wav_schreiben_und_dauer(tmp_path):
    """WavRecorder schreibt eine WAV-Datei, Dauer > 0, Datei existiert."""
    from audio.wav_recorder import WavRecorder
    samplerate = 48000
    kanaele = 2
    block_laenge = 1024

    pfad = str(tmp_path / "test.wav")
    rec = WavRecorder(samplerate=samplerate, channels=kanaele)
    rec.open(pfad)

    # 4 Blöcke schreiben
    for _ in range(4):
        block = np.zeros((block_laenge, kanaele), dtype=np.float32)
        rec.write(block)

    dauer = rec.close()
    assert dauer > 0.0

    import os
    assert os.path.exists(pfad)


def test_wav_ruecklesen_kanaele_und_samplerate(tmp_path):
    """Geschriebene WAV-Datei hat korrekte Kanalzahl und Samplerate."""
    from audio.wav_recorder import WavRecorder
    samplerate = 48000
    kanaele = 2
    pfad = str(tmp_path / "test2.wav")
    rec = WavRecorder(samplerate=samplerate, channels=kanaele)
    rec.open(pfad)
    rec.write(np.zeros((1024, kanaele), dtype=np.float32))
    rec.close()

    data, sr = sf.read(pfad)
    assert sr == samplerate
    assert data.ndim == 2
    assert data.shape[1] == kanaele


def test_wav_dauer_aus_frames(tmp_path):
    """Dauer wird aus Frames/Samplerate berechnet, nicht aus Wall-Clock."""
    from audio.wav_recorder import WavRecorder
    samplerate = 48000
    kanaele = 2
    block_laenge = 1024
    n_bloecke = 10

    pfad = str(tmp_path / "dauer_test.wav")
    rec = WavRecorder(samplerate=samplerate, channels=kanaele)
    rec.open(pfad)
    for _ in range(n_bloecke):
        rec.write(np.zeros((block_laenge, kanaele), dtype=np.float32))
    dauer = rec.close()

    erwartete_dauer = (block_laenge * n_bloecke) / samplerate
    assert abs(dauer - erwartete_dauer) < 1e-4


def test_wav_erstellt_verzeichnis(tmp_path):
    """WavRecorder legt fehlendes Verzeichnis automatisch an."""
    from audio.wav_recorder import WavRecorder
    pfad = str(tmp_path / "tief" / "ordner" / "aufnahme.wav")
    rec = WavRecorder(samplerate=48000, channels=2)
    rec.open(pfad)
    rec.write(np.zeros((256, 2), dtype=np.float32))
    rec.close()
    import os
    assert os.path.exists(pfad)

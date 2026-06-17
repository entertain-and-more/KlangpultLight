"""Tests für audio.drift_monitor — Drift-Erkennung und Callback."""
import pytest


def test_kein_drift_unter_schwelle():
    """Kein Drift, wenn queue_len dauerhaft unter warn_threshold bleibt."""
    from audio.drift_monitor import DriftMonitor
    dm = DriftMonitor(warn_threshold=10)
    for _ in range(20):
        dm.observe(5)  # unter Schwelle
    assert dm.has_drift() is False


def test_drift_ueber_schwelle():
    """Drift wird erkannt, wenn queue_len dauerhaft über warn_threshold bleibt."""
    from audio.drift_monitor import DriftMonitor
    dm = DriftMonitor(warn_threshold=10)
    # Genug Beobachtungen über Schwelle, um anhaltenden Drift auszulösen
    for _ in range(10):
        dm.observe(15)
    assert dm.has_drift() is True


def test_callback_bei_drift_uebergang():
    """on_warning wird genau einmal beim Übergang in Drift aufgerufen (Flanke)."""
    from audio.drift_monitor import DriftMonitor
    aufrufe = []

    dm = DriftMonitor(warn_threshold=10)
    dm.on_warning = lambda: aufrufe.append(1)

    # Drift auslösen
    for _ in range(10):
        dm.observe(20)

    # Callback genau einmal
    assert len(aufrufe) == 1


def test_callback_nicht_mehrfach_im_drift():
    """on_warning feuert nicht bei jedem observe, wenn Drift schon aktiv ist."""
    from audio.drift_monitor import DriftMonitor
    aufrufe = []
    dm = DriftMonitor(warn_threshold=10)
    dm.on_warning = lambda: aufrufe.append(1)

    for _ in range(30):
        dm.observe(20)

    # Genau 1 Übergang, nicht 30 Callbacks
    assert len(aufrufe) == 1


def test_kein_callback_ohne_drift():
    """on_warning wird nicht aufgerufen, wenn kein Drift auftritt."""
    from audio.drift_monitor import DriftMonitor
    aufrufe = []
    dm = DriftMonitor(warn_threshold=10)
    dm.on_warning = lambda: aufrufe.append(1)

    for _ in range(20):
        dm.observe(3)

    assert len(aufrufe) == 0

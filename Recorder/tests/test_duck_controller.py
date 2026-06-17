"""tests.test_duck_controller — Tests für board.duck_controller.

TDD Task 4a. Headless, vollständig deterministisch (tick-basiert, kein wall-clock).

Belegt:
  - start_duck() rampt Richtung Duck-Faktor
  - stop_duck() rampt zurück auf 1.0
  - Grenzen werden korrekt eingehalten
  - Werte nach vollständiger Rampe exakt am Ziel
"""
import math
import pytest


# ---------------------------------------------------------------------------
# Hilfsfunktion
# ---------------------------------------------------------------------------

def _vollstaendig_ticken(dc, steps: int = 1000, dt: float = 0.01):
    """Führt viele Ticks durch, bis der Faktor konvergiert."""
    for _ in range(steps):
        dc.tick(dt)


# ---------------------------------------------------------------------------
# Standardwerte / Konstruktion
# ---------------------------------------------------------------------------

def test_standard_faktor_ist_eins():
    """Ohne start_duck() ist current_gain_factor() == 1.0."""
    from board.duck_controller import DuckController

    dc = DuckController()
    assert abs(dc.current_gain_factor() - 1.0) < 1e-9


def test_duck_target_factor_korrekt():
    """duck_target_factor() == 10^(duck_db/20)."""
    from board.duck_controller import DuckController

    dc = DuckController(duck_db=-12.0)
    erwartet = 10 ** (-12.0 / 20.0)
    assert abs(dc.duck_target_factor() - erwartet) < 1e-9


# ---------------------------------------------------------------------------
# start_duck — Rampe abwärts
# ---------------------------------------------------------------------------

def test_start_duck_rampt_abwaerts():
    """start_duck() startet Rampe — nach wenigen Ticks sinkt der Faktor."""
    from board.duck_controller import DuckController

    dc = DuckController(duck_db=-12.0, attack=0.05, release=0.3)
    dc.start_duck()

    dc.tick(0.01)  # 1 Tick = 10 ms — attack=50 ms → 20 % des Weges
    assert dc.current_gain_factor() < 1.0, "Faktor sollte nach start_duck + tick sinken"


def test_start_duck_erreicht_ziel():
    """Nach ausreichend vielen Ticks liegt current_gain_factor() am Duck-Faktor."""
    from board.duck_controller import DuckController

    dc = DuckController(duck_db=-12.0, attack=0.05)
    dc.start_duck()
    _vollstaendig_ticken(dc)

    erwartet = 10 ** (-12.0 / 20.0)
    assert abs(dc.current_gain_factor() - erwartet) < 1e-6, (
        f"Duck-Ziel nicht erreicht: {dc.current_gain_factor():.6f} ≠ {erwartet:.6f}"
    )


def test_start_duck_unterschreitet_nicht():
    """current_gain_factor() unterschreitet nie den Duck-Faktor."""
    from board.duck_controller import DuckController

    dc = DuckController(duck_db=-20.0, attack=0.001)
    dc.start_duck()

    minimum = dc.duck_target_factor()
    for _ in range(500):
        dc.tick(0.1)
        assert dc.current_gain_factor() >= minimum - 1e-9, (
            f"Faktor unterschreitet Minimum: {dc.current_gain_factor()}"
        )


# ---------------------------------------------------------------------------
# stop_duck — Rampe aufwärts
# ---------------------------------------------------------------------------

def test_stop_duck_rampt_aufwaerts():
    """stop_duck() startet die Rampe zurück auf 1.0."""
    from board.duck_controller import DuckController

    dc = DuckController(duck_db=-12.0, attack=0.01, release=0.1)
    dc.start_duck()
    _vollstaendig_ticken(dc)  # vollständig absenken

    assert dc.current_gain_factor() < 0.5

    dc.stop_duck()
    dc.tick(0.01)
    assert dc.current_gain_factor() > 10 ** (-12.0 / 20.0), "Faktor sollte nach stop_duck steigen"


def test_stop_duck_erreicht_eins():
    """Nach vollständiger Release-Rampe ist current_gain_factor() == 1.0."""
    from board.duck_controller import DuckController

    dc = DuckController(duck_db=-12.0, attack=0.01, release=0.05)
    dc.start_duck()
    _vollstaendig_ticken(dc)

    dc.stop_duck()
    _vollstaendig_ticken(dc)

    assert abs(dc.current_gain_factor() - 1.0) < 1e-6, (
        f"Faktor nach Release nicht 1.0: {dc.current_gain_factor():.6f}"
    )


def test_stop_duck_ueberschreitet_nicht():
    """current_gain_factor() überschreitet nie 1.0 während der Release-Rampe."""
    from board.duck_controller import DuckController

    dc = DuckController(duck_db=-6.0, attack=0.01, release=0.001)
    dc.start_duck()
    _vollstaendig_ticken(dc, dt=0.1)

    dc.stop_duck()
    for _ in range(200):
        dc.tick(0.1)
        assert dc.current_gain_factor() <= 1.0 + 1e-9, (
            f"Faktor überschreitet 1.0: {dc.current_gain_factor()}"
        )


# ---------------------------------------------------------------------------
# Parametrisierte Grenzwert-Tests
# ---------------------------------------------------------------------------

@pytest.mark.parametrize("duck_db", [-6.0, -12.0, -20.0, -40.0])
def test_duck_faktor_mathematisch_korrekt(duck_db):
    """10^(duck_db/20) ist der exakte Zielwert."""
    from board.duck_controller import DuckController

    dc = DuckController(duck_db=duck_db, attack=0.001)
    dc.start_duck()
    _vollstaendig_ticken(dc, dt=0.1)

    erwartet = 10 ** (duck_db / 20.0)
    assert abs(dc.current_gain_factor() - erwartet) < 1e-6


def test_ohne_tick_kein_faktorwechsel():
    """Ohne tick()-Aufruf ändert sich der Faktor nicht."""
    from board.duck_controller import DuckController

    dc = DuckController()
    dc.start_duck()
    # Kein tick()
    assert abs(dc.current_gain_factor() - 1.0) < 1e-9

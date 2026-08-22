"""board.duck_controller — Mic-Ducking während Board-Audio-Wiedergabe.

Keine GUI-Imports. Rein deterministisch — Zeit ist ein injizierbarer Parameter
(tick-basiert), kein wall-clock-Aufruf in den Tests.

Implementierung:
    Lineare Rampe (attack/release) auf dem Gain-Faktor, gesteuert durch
    tick()-Aufrufe mit explizitem dt (Zeitdelta in Sekunden).
    In der echten Laufzeit ruft der MixWorker tick(block_size / samplerate) pro
    Mix-Tick auf; im Test wird dt direkt übergeben.
"""
from __future__ import annotations



class DuckController:
    """Senkt die effektive Verstärkung definierter Mic-Kanäle.

    Zustand:
        - ``_ziel_faktor``: 1.0 (inaktiv) oder 10**(duck_db/20) (aktiv).
        - ``_aktueller_faktor``: rampt von ``_aktueller_faktor`` zu ``_ziel_faktor``.

    Attack/Release-Rampe:
        Linear in Seconds; tick(dt) schiebt den Faktor um dt/attack bzw.
        dt/release in Richtung des Ziels.

    Args:
        duck_db:  Absenkung in dB (negativ, z. B. -12.0).
        attack:   Rampe-Zeit zum Absenken in Sekunden (Standard: 0.05 s = 50 ms).
        release:  Rampe-Zeit zum Wiederherstellen in Sekunden (Standard: 0.3 s).
    """

    def __init__(
        self,
        duck_db: float = -12.0,
        attack: float = 0.05,
        release: float = 0.3,
    ) -> None:
        self._duck_faktor: float = 10 ** (duck_db / 20.0)
        self._attack: float = max(attack, 1e-9)    # kein Division-durch-Null
        self._release: float = max(release, 1e-9)
        self._aktueller_faktor: float = 1.0
        self._ziel_faktor: float = 1.0

    # -------------------------------------------------------------------------
    # Steuerung
    # -------------------------------------------------------------------------

    def start_duck(self) -> None:
        """Startet das Ducking — Ziel-Faktor auf den Duck-Wert setzen."""
        self._ziel_faktor = self._duck_faktor

    def stop_duck(self) -> None:
        """Beendet das Ducking — Ziel-Faktor auf 1.0 setzen."""
        self._ziel_faktor = 1.0

    # -------------------------------------------------------------------------
    # Tick (deterministisch, kein wall-clock)
    # -------------------------------------------------------------------------

    def tick(self, dt: float) -> None:
        """Schiebt den aktuellen Gain-Faktor eine dt-Sekunde lang in Richtung Ziel.

        Lineare Rampe:
        - Absenken (ducking aktiv):    schrittweite = dt / attack
        - Wiederherstellen (inaktiv):  schrittweite = dt / release

        Args:
            dt: Vergangene Zeit seit letztem Tick in Sekunden.
        """
        if self._aktueller_faktor > self._ziel_faktor:
            # Absenken
            schritt = dt / self._attack
            self._aktueller_faktor = max(
                self._ziel_faktor,
                self._aktueller_faktor - schritt,
            )
        elif self._aktueller_faktor < self._ziel_faktor:
            # Anheben
            schritt = dt / self._release
            self._aktueller_faktor = min(
                self._ziel_faktor,
                self._aktueller_faktor + schritt,
            )

    # -------------------------------------------------------------------------
    # Abfrage
    # -------------------------------------------------------------------------

    def current_gain_factor(self) -> float:
        """Gibt den aktuellen Gain-Faktor zurück (zwischen duck-Faktor und 1.0).

        Returns:
            Float zwischen ``10**(duck_db/20)`` und ``1.0``.
        """
        return self._aktueller_faktor

    def duck_target_factor(self) -> float:
        """Gibt den Ziel-Faktor im voll abgesenkten Zustand zurück.

        Hilfreich für Tests, um den Erwartungswert zu berechnen.

        Returns:
            ``10**(duck_db/20)``
        """
        return self._duck_faktor

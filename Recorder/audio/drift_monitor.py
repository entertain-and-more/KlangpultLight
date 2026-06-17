"""audio.drift_monitor — Erkennung von Audio-Buffer-Drift.

Kein GUI-Import. Nur stdlib.

Buffer-Drift entsteht, wenn die Verarbeitungsrate nicht mit der
Einspeisungsrate Schritt hält und die Warteschlange kontinuierlich wächst.
"""
from typing import Optional, Callable


# Mindestanzahl aufeinanderfolgender Überschreitungen, bevor Drift gemeldet wird.
_DRIFT_KONSEKUTIV_SCHWELLE = 3


class DriftMonitor:
    """Überwacht die Länge einer Audio-Queue und erkennt anhaltenden Drift.

    Drift liegt vor, wenn ``queue_len`` für mindestens
    ``_DRIFT_KONSEKUTIV_SCHWELLE`` aufeinanderfolgende ``observe()``-Aufrufe
    oberhalb von ``warn_threshold`` liegt.

    Der Callback ``on_warning`` wird **flankengetriggert**: Er feuert genau
    einmal beim Übergang von Kein-Drift nach Drift, nicht bei jedem observe().
    """

    def __init__(self, warn_threshold: int = 10) -> None:
        """Erstellt einen DriftMonitor.

        Args:
            warn_threshold: Schwellwert für die Queue-Länge.
        """
        self._schwelle = warn_threshold
        self._konsekutiv: int = 0
        self._drift_aktiv: bool = False
        self.on_warning: Optional[Callable[[], None]] = None
        """Callback, der einmal beim Eintritt in den Drift-Zustand aufgerufen wird."""

    def observe(self, queue_len: int) -> None:
        """Wertet eine aktuelle Queue-Länge aus.

        Args:
            queue_len: Aktuelle Länge der Audio-Puffer-Queue.
        """
        if queue_len > self._schwelle:
            self._konsekutiv += 1
        else:
            # Unter der Schwelle → Zähler zurücksetzen, Drift verlassen
            self._konsekutiv = 0
            self._drift_aktiv = False

        # Übergang in Drift-Zustand: genau einmal Callback feuern
        if self._konsekutiv >= _DRIFT_KONSEKUTIV_SCHWELLE and not self._drift_aktiv:
            self._drift_aktiv = True
            if self.on_warning is not None:
                self.on_warning()

    def has_drift(self) -> bool:
        """Gibt an, ob aktuell ein Drift-Zustand erkannt wurde.

        Returns:
            True, wenn anhaltender Drift vorliegt.
        """
        return self._drift_aktiv

"""core.app_state — Thread-sicherer Anwendungszustand.

Kein GUI-Import. Nutzt threading.RLock statt QMutex,
damit core/ vollständig GUI-frei bleibt.
"""
import threading
from typing import Any


class AppState:
    """Thread-sicherer Zustandscontainer für den Klangpult light – Recorder.

    Alle Getter und Setter sind thread-safe über einen RLock
    (wiedereintrittssicher, damit Komplex-Operationen nicht deadlocken).
    """

    def __init__(self) -> None:
        self._lock = threading.RLock()
        self._recording: bool = False
        self._peaks: list[float] = []
        self._active_source_ids: list[str] = []

    # --- recording -----------------------------------------------------------

    @property
    def recording(self) -> bool:
        """Ob gerade eine Aufnahme läuft."""
        with self._lock:
            return self._recording

    @recording.setter
    def recording(self, wert: bool) -> None:
        with self._lock:
            self._recording = wert

    # --- peaks ---------------------------------------------------------------

    @property
    def peaks(self) -> list[float]:
        """Aktuelle Kanal-Pegel (Kopie, thread-safe)."""
        with self._lock:
            return list(self._peaks)

    @peaks.setter
    def peaks(self, wert: list[float]) -> None:
        with self._lock:
            self._peaks = list(wert)

    # --- active_source_ids ---------------------------------------------------

    @property
    def active_source_ids(self) -> list[str]:
        """Liste der aktiven Quell-IDs (Kopie, thread-safe)."""
        with self._lock:
            return list(self._active_source_ids)

    @active_source_ids.setter
    def active_source_ids(self, wert: list[str]) -> None:
        with self._lock:
            self._active_source_ids = list(wert)

    # --- snapshot ------------------------------------------------------------

    def snapshot(self) -> dict[str, Any]:
        """Gibt einen konsistenten Schnappschuss des gesamten Zustands zurück.

        Da alle Felder unter demselben Lock gelesen werden, ist der
        Schnappschuss atomar.

        Returns:
            dict mit recording, peaks, active_source_ids.
        """
        with self._lock:
            return {
                "recording": self._recording,
                "peaks": list(self._peaks),
                "active_source_ids": list(self._active_source_ids),
            }

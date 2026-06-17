"""audio.mixer_channel — Einzelner Mischer-Kanal mit Gain, Mute, Peak.

Kein GUI-Import. Nur numpy + stdlib.
"""
import numpy as np
from dataclasses import dataclass, field


@dataclass
class MixerChannel:
    """Repräsentiert einen einzelnen Eingangskanal im Mischpult.

    Der Kanal verarbeitet Audio-Blöcke (Shape: ``(block_size, channels)``),
    wendet Gain und Mute an und aktualisiert den Peak-Wert.
    """
    source_id: str
    """Eindeutige Quell-ID (z. B. "mic1", "system")."""
    name: str
    """Anzeigename des Kanals."""
    gain: float = 1.0
    """Linearer Verstärkungsfaktor (1.0 = keine Änderung)."""
    mute: bool = False
    """Wenn True, wird der Ausgang auf Null gesetzt."""
    solo: bool = False
    """Solo-Flag; Auflösung mehrerer Solo-Kanäle im MasterBus."""
    peak: float = 0.0
    """Zuletzt gemessener Spitzenwert (max abs des Ausgangs)."""

    def process(self, block: np.ndarray) -> np.ndarray:
        """Verarbeitet einen Audio-Block.

        Wendet Gain an, erzwingt Nullen bei Mute und aktualisiert
        danach self.peak (max abs des Ausgangs).

        Args:
            block: Eingangs-Array, Shape (block_size, channels), float32.

        Returns:
            Verarbeitetes Array gleicher Shape und dtype.
        """
        out = block.astype(np.float32, copy=True) * self.gain
        if self.mute:
            out[:] = 0.0

        # Peak aus dem tatsächlichen Ausgang berechnen
        self.peak = float(np.max(np.abs(out))) if out.size > 0 else 0.0
        return out

"""ui.level_meter — Einfacher horizontaler Pegelbalken (PySide6).

Nur GUI — kein Audio-Zugriff direkt.
"""
from PySide6.QtCore import Qt
from PySide6.QtGui import QColor, QPainter, QLinearGradient
from PySide6.QtWidgets import QWidget

from ui.styles import (
    FARBE_PEGEL_NIEDRIG,
    FARBE_PEGEL_MITTEL,
    FARBE_PEGEL_HOCH,
    FARBE_PEGEL_HINTERGRUND,
)


class LevelMeter(QWidget):
    """Horizontaler Pegelbalken.

    Pegel 0.0 = kein Signal, 1.0 = Maximum.
    Farbverlauf: grün → gelb → rot.
    """

    def __init__(self, parent=None) -> None:
        super().__init__(parent)
        self._pegel: float = 0.0
        self.setMinimumHeight(14)
        self.setMaximumHeight(18)
        self.setMinimumWidth(60)

    def set_level(self, pegel: float) -> None:
        """Setzt den Pegel und löst einen Neuzeichnungs-Aufruf aus.

        Args:
            pegel: Wert zwischen 0.0 und 1.0.
        """
        # Klemmen auf [0, 1]
        self._pegel = max(0.0, min(1.0, pegel))
        self.update()

    def paintEvent(self, event) -> None:  # noqa: N802
        painter = QPainter(self)
        painter.setRenderHint(QPainter.RenderHint.Antialiasing)

        breite = self.width()
        hoehe = self.height()

        # Hintergrund
        painter.fillRect(0, 0, breite, hoehe, QColor(FARBE_PEGEL_HINTERGRUND))

        if self._pegel > 0:
            füll_breite = int(breite * self._pegel)

            # Farbverlauf: grün → gelb → rot
            verlauf = QLinearGradient(0, 0, breite, 0)
            verlauf.setColorAt(0.0, QColor(FARBE_PEGEL_NIEDRIG))
            verlauf.setColorAt(0.6, QColor(FARBE_PEGEL_MITTEL))
            verlauf.setColorAt(1.0, QColor(FARBE_PEGEL_HOCH))

            painter.fillRect(0, 0, füll_breite, hoehe, verlauf)

        painter.end()

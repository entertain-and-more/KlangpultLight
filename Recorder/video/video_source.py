"""video.video_source — VideoSource-Basisklasse und konkrete Implementierungen.

Kein GUI-Import. Kein PySide6.
Abhängigkeiten: numpy (immer), cv2 und mss optional (lazy-import, Mock-Fallback).
"""
from __future__ import annotations

from abc import ABC, abstractmethod
from dataclasses import dataclass
from typing import Optional

import numpy as np


@dataclass
class VideoSourceInfo:
    """Metadaten einer Video-Quelle."""

    source_id: str
    """Eindeutiger Bezeichner (z. B. 'camera_0', 'screen_0', 'mock_0')."""

    name: str
    """Menschenlesbarer Name."""

    kind: str
    """Quell-Art: 'camera' | 'screen' | 'mock'."""

    verified: bool
    """True, wenn die Quelle testweise geöffnet und 1 Frame gelesen wurde."""

    is_mock: bool = False
    """True, wenn es sich um eine synthetische Mock-Quelle handelt."""

    width: int = 1280
    """Breite in Pixeln."""

    height: int = 720
    """Höhe in Pixeln."""


class VideoSource(ABC):
    """Abstrakte Basisklasse für alle Video-Quellen."""

    @abstractmethod
    def open(self) -> None:
        """Öffnet die Video-Quelle."""

    @abstractmethod
    def read_frame(self) -> Optional[np.ndarray]:
        """Liest einen Frame.

        Returns:
            numpy-Array (H, W, 3), dtype=uint8, BGR — oder None wenn nicht geöffnet.
        """

    @abstractmethod
    def close(self) -> None:
        """Schließt die Video-Quelle."""

    @property
    @abstractmethod
    def info(self) -> VideoSourceInfo:
        """Gibt die Quell-Metadaten zurück."""


class CameraSource(VideoSource):
    """Video-Quelle über OpenCV VideoCapture (Kamera-Index).

    cv2 wird lazy importiert — falls es fehlt, schlägt open() mit klarem Fehler fehl.
    """

    def __init__(self, info: VideoSourceInfo, index: int = 0) -> None:
        self._info = info
        self._index = index
        self._cap = None  # cv2.VideoCapture, nach open()

    @property
    def info(self) -> VideoSourceInfo:
        return self._info

    def open(self) -> None:
        """Öffnet die Kamera via OpenCV."""
        if self._cap is not None:
            return  # bereits geöffnet — idempotent

        try:
            import cv2  # lazy import
        except ImportError as exc:
            raise RuntimeError(
                "OpenCV (cv2) ist nicht installiert — Kamera-Quelle nicht verfügbar."
            ) from exc

        # Auf Windows den DirectShow-Backend erzwingen: schneller und vermeidet
        # den lauten/langsamen obsensor-Backend (cv::obsensor … index out of range),
        # der beim Probing nicht vorhandener Indizes den Start blockiert.
        import sys
        if sys.platform == "win32":
            self._cap = cv2.VideoCapture(self._index, cv2.CAP_DSHOW)
        else:
            self._cap = cv2.VideoCapture(self._index)
        if not self._cap.isOpened():
            self._cap = None
            raise RuntimeError(
                f"Kamera-Index {self._index} konnte nicht geöffnet werden."
            )

    def read_frame(self) -> Optional[np.ndarray]:
        """Liest einen Frame von der Kamera.

        Returns:
            HxWx3 uint8 BGR-Frame oder None bei Fehler/nicht geöffnet.
        """
        if self._cap is None:
            return None
        ret, frame = self._cap.read()
        if not ret or frame is None:
            return None
        return frame

    def close(self) -> None:
        """Schließt die Kamera-Verbindung."""
        if self._cap is not None:
            self._cap.release()
            self._cap = None


class ScreenSource(VideoSource):
    """Video-Quelle über mss (Bildschirm-Capture).

    mss wird lazy importiert — falls es fehlt, schlägt open() mit klarem Fehler fehl.
    """

    def __init__(self, info: VideoSourceInfo, monitor_index: int = 1) -> None:
        """
        Args:
            info: Quell-Metadaten.
            monitor_index: mss-Monitor-Index (1 = erster Monitor, 0 = virtueller Gesamtschirm).
        """
        self._info = info
        self._monitor_index = monitor_index
        self._sct = None  # mss.mss()-Instanz

    @property
    def info(self) -> VideoSourceInfo:
        return self._info

    def open(self) -> None:
        """Öffnet die Bildschirm-Capture-Verbindung."""
        if self._sct is not None:
            return  # idempotent

        try:
            import mss  # lazy import
        except ImportError as exc:
            raise RuntimeError(
                "mss ist nicht installiert — Bildschirm-Quelle nicht verfügbar."
            ) from exc

        self._sct = mss.mss()

    def read_frame(self) -> Optional[np.ndarray]:
        """Liest einen Screenshot als Frame.

        Returns:
            HxWx3 uint8 BGR-Frame oder None bei Fehler/nicht geöffnet.
        """
        if self._sct is None:
            return None

        try:
            monitore = self._sct.monitors
            if self._monitor_index >= len(monitore):
                return None
            monitor = monitore[self._monitor_index]
            screenshot = self._sct.grab(monitor)
            # mss liefert BGRA — letzte Kanal (Alpha) wegschneiden
            frame = np.array(screenshot)[:, :, :3]
            return frame.astype(np.uint8)
        except Exception:
            return None

    def close(self) -> None:
        """Schließt die mss-Verbindung."""
        if self._sct is not None:
            try:
                self._sct.close()
            except Exception:
                pass
            self._sct = None


class MockVideoSource(VideoSource):
    """Synthetische Video-Quelle — immer verfügbar, ohne Hardware.

    Erzeugt deterministisch Farbverlauf-Frames mit eingebettetem Frame-Zähler.
    Frame-Zähler steigt je read_frame()-Aufruf um 1 — aufeinanderfolgende Frames
    unterscheiden sich, gleicher Startzähler liefert gleiches erstes Frame.
    """

    def __init__(self, info: VideoSourceInfo) -> None:
        self._info = info
        self._offen = False
        self._frame_idx = 0

    @property
    def info(self) -> VideoSourceInfo:
        return self._info

    def open(self) -> None:
        """Öffnet die Mock-Quelle (setzt Frame-Zähler zurück)."""
        self._frame_idx = 0
        self._offen = True

    def read_frame(self) -> Optional[np.ndarray]:
        """Gibt einen synthetischen Frame zurück.

        Returns:
            (H, W, 3) uint8 BGR-Frame oder None wenn nicht geöffnet.
        """
        if not self._offen:
            return None

        w = self._info.width
        h = self._info.height
        idx = self._frame_idx

        frame = np.zeros((h, w, 3), dtype=np.uint8)
        # Blau: horizontaler Farbverlauf
        frame[:, :, 0] = np.linspace(0, 200, w, dtype=np.uint8)
        # Grün: vertikaler Farbverlauf
        frame[:, :, 1] = np.linspace(0, 200, h, dtype=np.uint8).reshape(-1, 1)
        # Rot: Frame-Index kodiert (mod 256) — macht aufeinanderfolgende Frames verschieden
        frame[:, :, 2] = idx % 256

        self._frame_idx += 1
        return frame

    def close(self) -> None:
        """Schließt die Mock-Quelle."""
        self._offen = False

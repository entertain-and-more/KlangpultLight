"""video.video_manager — VideoManager: listet und öffnet Video-Quellen.

Kein GUI-Import. Kein PySide6.
Mock-Aktivierung: env PODCAST_RECORDER_MOCK_VIDEO=1 oder fehlende/leere Backends.
"""
from __future__ import annotations

import os
from typing import Optional

from video.video_source import (
    VideoSource,
    VideoSourceInfo,
    CameraSource,
    ScreenSource,
    MockVideoSource,
)


class VideoManager:
    """Verwaltet verfügbare Video-Quellen (Kameras, Bildschirme, Mock-Fallback).

    Aktivierungsregel:
    - Wenn env ``PODCAST_RECORDER_MOCK_VIDEO=1`` gesetzt ist, wird ausschließlich
      die Mock-Quelle geliefert (Hardware-Zugriffe werden übersprungen).
    - Sonst werden Kameras und Bildschirme aufgelistet; liefert kein Backend
      mindestens 1 Quelle, wird automatisch ein Mock hinzugefügt.
    """

    def list_camera_sources(
        self, verify: bool = True, max_index: int = 5
    ) -> list[VideoSourceInfo]:
        """Listet verfügbare Kamera-Quellen.

        Args:
            verify: Wenn True, wird jede Kamera testweise geöffnet (1 Frame),
                    um ``verified=True`` setzen zu können.
            max_index: Maximaler cv2-Capture-Index (0 bis max_index-1).

        Returns:
            Liste von VideoSourceInfo für gefundene Kameras.
        """
        if self._mock_aktiv():
            return []

        try:
            import cv2  # noqa: F401
        except ImportError:
            return []

        quellen: list[VideoSourceInfo] = []
        for idx in range(max_index):
            info = VideoSourceInfo(
                source_id=f"camera_{idx}",
                name=f"Kamera {idx}",
                kind="camera",
                verified=False,
                is_mock=False,
            )
            if verify:
                # Testweise öffnen: 1 Frame lesen
                src = CameraSource(info, index=idx)
                try:
                    src.open()
                    frame = src.read_frame()
                    src.close()
                    if frame is not None:
                        # Tatsächliche Auflösung aus Frame übernehmen
                        h, w = frame.shape[:2]
                        info = VideoSourceInfo(
                            source_id=f"camera_{idx}",
                            name=f"Kamera {idx}",
                            kind="camera",
                            verified=True,
                            is_mock=False,
                            width=w,
                            height=h,
                        )
                        quellen.append(info)
                except Exception:
                    pass  # Kamera nicht erreichbar — überspringen
            else:
                quellen.append(info)

        return quellen

    def list_screen_sources(self) -> list[VideoSourceInfo]:
        """Listet verfügbare Bildschirm-Quellen.

        Returns:
            Liste von VideoSourceInfo für gefundene Bildschirme.
        """
        if self._mock_aktiv():
            return []

        try:
            import mss
        except ImportError:
            return []

        quellen: list[VideoSourceInfo] = []
        try:
            with mss.mss() as sct:
                # monitore[0] = virtueller Gesamtschirm, monitore[1..] = physische Monitore
                for i, monitor in enumerate(sct.monitors):
                    if i == 0:
                        continue  # Gesamtschirm überspringen
                    info = VideoSourceInfo(
                        source_id=f"screen_{i}",
                        name=f"Bildschirm {i}",
                        kind="screen",
                        verified=True,
                        is_mock=False,
                        width=monitor.get("width", 1920),
                        height=monitor.get("height", 1080),
                    )
                    quellen.append(info)
        except Exception:
            pass

        return quellen

    def available_sources(self) -> list[VideoSourceInfo]:
        """Gibt alle verfügbaren Quellen zurück (Kameras + Bildschirme + Mock-Fallback).

        Im Mock-Modus oder wenn keine realen Quellen gefunden wurden, wird
        automatisch mindestens eine Mock-Quelle hinzugefügt.

        Returns:
            Liste von VideoSourceInfo (mindestens 1 Eintrag).
        """
        if self._mock_aktiv():
            return [self._mock_info()]

        quellen: list[VideoSourceInfo] = []
        quellen.extend(self.list_camera_sources(verify=True))
        quellen.extend(self.list_screen_sources())

        if not quellen:
            quellen.append(self._mock_info())

        return quellen

    def open_source(self, info: VideoSourceInfo) -> VideoSource:
        """Erstellt und gibt eine VideoSource-Instanz für die gegebene Info zurück.

        Die Quelle ist noch nicht geöffnet — Aufrufer muss ``src.open()`` rufen.

        Args:
            info: Quell-Metadaten (aus available_sources() oder list_*()).

        Returns:
            Passende VideoSource-Instanz.
        """
        if info.kind == "mock" or info.is_mock:
            return MockVideoSource(info)

        if info.kind == "camera":
            # Index aus source_id extrahieren (z. B. "camera_0" → 0)
            try:
                idx = int(info.source_id.split("_")[-1])
            except (ValueError, IndexError):
                idx = 0
            return CameraSource(info, index=idx)

        if info.kind == "screen":
            try:
                monitor_idx = int(info.source_id.split("_")[-1])
            except (ValueError, IndexError):
                monitor_idx = 1
            return ScreenSource(info, monitor_index=monitor_idx)

        # Fallback: Mock
        return MockVideoSource(info)

    def suggest_default_source(self) -> Optional[VideoSourceInfo]:
        """Schlägt die beste verfügbare Standard-Quelle vor.

        Bevorzugt: echte Kamera → Bildschirm → Mock.

        Returns:
            VideoSourceInfo oder None, falls keine Quelle vorhanden (sollte nicht passieren).
        """
        quellen = self.available_sources()
        if not quellen:
            return None

        # Echte Kamera bevorzugen
        for q in quellen:
            if q.kind == "camera" and q.verified and not q.is_mock:
                return q

        # Bildschirm als zweite Wahl
        for q in quellen:
            if q.kind == "screen" and not q.is_mock:
                return q

        # Mock-Fallback
        return quellen[0]

    # -------------------------------------------------------------------------
    # Interne Hilfsmethoden
    # -------------------------------------------------------------------------

    @staticmethod
    def _mock_aktiv() -> bool:
        """Prüft, ob der Mock-Modus aktiv ist."""
        return os.environ.get("PODCAST_RECORDER_MOCK_VIDEO", "").strip() == "1"

    @staticmethod
    def _mock_info() -> VideoSourceInfo:
        """Erstellt eine Standard-Mock-VideoSourceInfo."""
        return VideoSourceInfo(
            source_id="mock_0",
            name="Mock-Video-Quelle",
            kind="mock",
            verified=True,
            is_mock=True,
            width=1280,
            height=720,
        )

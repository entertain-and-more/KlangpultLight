"""video.compositor — Mehrquellen-Compositing für die Videoaufnahme.

Kein GUI-Import. Kein PySide6.

compose_layout(frames, out_size) → numpy-Canvas (uint8, BGR):
  1 Quelle  → vollbild
  2 Quellen → nebeneinander (side-by-side)
  3–4 Quellen → 2×2-Raster (fehlende Kacheln schwarz)
  None-Frames → schwarze Kachel

Alle Frames werden mit cv2.resize in ihre Kachel skaliert.
Die Ausgabe ist garantiert C-contiguous und hat exakt out_size.
"""
from __future__ import annotations

from typing import Optional

import numpy as np

# Zielauflösung: Standard-Compositor-Auflösung (width, height)
# Wird von test_session_split und main.py selftest als Konstante importiert.
COMPOSITOR_STANDARD_AUFLOESUNG: tuple[int, int] = (1280, 720)


def compose_layout(
    frames: list[Optional[np.ndarray]],
    out_size: tuple[int, int],
) -> np.ndarray:
    """Fügt 1–4 BGR-Frames in ein Ziel-Canvas zusammen.

    Args:
        frames: Liste von BGR-Frames (numpy uint8, shape HxWx3) oder None.
                Leere Liste und alle-None → schwarzes Canvas.
        out_size: Zielgröße als (width, height).

    Returns:
        Canvas als numpy-Array (H, W, 3), dtype=uint8, C-contiguous.
        Die Größe ist garantiert (H, W) unabhängig von den Eingangsframes.
    """
    import cv2  # lazy import — kein Top-Level-Import damit Tests importierbar bleiben

    W, H = out_size
    canvas = np.zeros((H, W, 3), dtype=np.uint8)

    # Maximal 4 Quellen unterstützt
    n = min(len(frames), 4)
    if n == 0:
        return np.ascontiguousarray(canvas)

    if n == 1:
        # 1 Quelle → Vollbild
        kacheln = [(0, 0, W, H)]
    elif n == 2:
        # 2 Quellen → nebeneinander
        halb = W // 2
        kacheln = [
            (0, 0, halb, H),
            (halb, 0, W - halb, H),
        ]
    else:
        # 3–4 Quellen → 2×2-Raster
        halb_w = W // 2
        halb_h = H // 2
        kacheln = [
            (0, 0, halb_w, halb_h),           # oben-links
            (halb_w, 0, W - halb_w, halb_h),   # oben-rechts
            (0, halb_h, halb_w, H - halb_h),   # unten-links
            (halb_w, halb_h, W - halb_w, H - halb_h),  # unten-rechts
        ]

    for i in range(n):
        frame = frames[i] if i < len(frames) else None
        if frame is None:
            continue  # Kachel bleibt schwarz

        x, y, tw, th = kacheln[i]
        if tw <= 0 or th <= 0:
            continue

        # Auf Kachel-Größe skalieren
        try:
            skaliert = cv2.resize(frame, (tw, th), interpolation=cv2.INTER_LINEAR)
        except Exception:
            continue

        # Skaliertes Frame in Canvas schreiben (nur gültigen Bereich)
        canvas[y:y + th, x:x + tw] = skaliert[:th, :tw]

    return np.ascontiguousarray(canvas)

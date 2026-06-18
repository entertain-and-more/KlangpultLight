"""Tests für video.compositor — compose_layout (Task 6b, TDD).

Prüft:
  - 1 Frame → voll auf Canvas
  - 2 Frames → nebeneinander (je halbe Breite)
  - 3 Frames → 2×2-Raster, Kachel 4 schwarz
  - 4 Frames → 2×2-Raster, alle befüllt
  - fehlender Frame (None) → schwarze Kachel
  - Canvas-Größe immer exakt out_size
"""
import numpy as np
import pytest


def _rotes_frame(h=72, w=128):
    """Synthetisches BGR-Frame: rot."""
    f = np.zeros((h, w, 3), dtype=np.uint8)
    f[:, :, 2] = 200  # BGR: Blau=0, Grün=0, Rot=200
    return f


def _gruenes_frame(h=72, w=128):
    f = np.zeros((h, w, 3), dtype=np.uint8)
    f[:, :, 1] = 200
    return f


def _blaues_frame(h=72, w=128):
    f = np.zeros((h, w, 3), dtype=np.uint8)
    f[:, :, 0] = 200
    return f


def _weisses_frame(h=72, w=128):
    f = np.ones((h, w, 3), dtype=np.uint8) * 200
    return f


OUT = (128, 72)  # (width, height)


class TestCompositorLayout:
    def test_1_frame_volle_canvas_groesse(self):
        """1 Frame → Canvas ist genau out_size (W×H)."""
        from video.compositor import compose_layout
        frame = _rotes_frame()
        result = compose_layout([frame], OUT)
        W, H = OUT
        assert result.shape == (H, W, 3)

    def test_1_frame_canvas_nicht_schwarz(self):
        """1 Frame → enthält nicht nur Nullen (Frame wurde hineingeschrieben)."""
        from video.compositor import compose_layout
        frame = _rotes_frame()
        result = compose_layout([frame], OUT)
        assert result.max() > 0, "Canvas sollte den Frame enthalten"

    def test_2_frames_canvas_groesse(self):
        """2 Frames → Canvas-Größe = out_size."""
        from video.compositor import compose_layout
        frames = [_rotes_frame(), _gruenes_frame()]
        result = compose_layout(frames, OUT)
        W, H = OUT
        assert result.shape == (H, W, 3)

    def test_2_frames_beide_haelften_nicht_schwarz(self):
        """2 Frames → linke und rechte Hälfte enthalten Pixel (nicht alles Null)."""
        from video.compositor import compose_layout
        frames = [_rotes_frame(), _gruenes_frame()]
        result = compose_layout(frames, OUT)
        W, H = OUT
        halb = W // 2
        # Linke Hälfte
        linke_haelfte = result[:, :halb, :]
        assert linke_haelfte.max() > 0, "Linke Hälfte darf nicht schwarz sein"
        # Rechte Hälfte
        rechte_haelfte = result[:, halb:, :]
        assert rechte_haelfte.max() > 0, "Rechte Hälfte darf nicht schwarz sein"

    def test_3_frames_canvas_groesse(self):
        """3 Frames → Canvas-Größe = out_size."""
        from video.compositor import compose_layout
        frames = [_rotes_frame(), _gruenes_frame(), _blaues_frame()]
        result = compose_layout(frames, OUT)
        W, H = OUT
        assert result.shape == (H, W, 3)

    def test_3_frames_vierte_kachel_schwarz(self):
        """3 Frames → 4. Kachel (rechts unten) ist schwarz."""
        from video.compositor import compose_layout
        frames = [_rotes_frame(), _gruenes_frame(), _blaues_frame()]
        result = compose_layout(frames, OUT)
        W, H = OUT
        halb_w = W // 2
        halb_h = H // 2
        vierte = result[halb_h:, halb_w:, :]
        assert vierte.max() == 0, "4. Kachel (fehlt) muss schwarz sein"

    def test_4_frames_canvas_groesse(self):
        """4 Frames → Canvas-Größe = out_size."""
        from video.compositor import compose_layout
        frames = [_rotes_frame(), _gruenes_frame(), _blaues_frame(), _weisses_frame()]
        result = compose_layout(frames, OUT)
        W, H = OUT
        assert result.shape == (H, W, 3)

    def test_4_frames_alle_kacheln_nicht_schwarz(self):
        """4 Frames → alle 4 Kacheln enthalten Pixel."""
        from video.compositor import compose_layout
        frames = [_rotes_frame(), _gruenes_frame(), _blaues_frame(), _weisses_frame()]
        result = compose_layout(frames, OUT)
        W, H = OUT
        halb_w = W // 2
        halb_h = H // 2
        assert result[:halb_h, :halb_w, :].max() > 0, "Kachel 1 (oben-links)"
        assert result[:halb_h, halb_w:, :].max() > 0, "Kachel 2 (oben-rechts)"
        assert result[halb_h:, :halb_w, :].max() > 0, "Kachel 3 (unten-links)"
        assert result[halb_h:, halb_w:, :].max() > 0, "Kachel 4 (unten-rechts)"

    def test_none_frame_kachel_schwarz(self):
        """None-Frame → entsprechende Kachel bleibt schwarz."""
        from video.compositor import compose_layout
        frames = [_rotes_frame(), None]
        result = compose_layout(frames, OUT)
        W, H = OUT
        halb = W // 2
        # Linke Kachel (Frame 0, rot) sollte nicht schwarz sein
        assert result[:, :halb, :].max() > 0, "Kachel 1 (rot) darf nicht schwarz sein"
        # Rechte Kachel (None) muss schwarz sein
        assert result[:, halb:, :].max() == 0, "None-Kachel muss schwarz sein"

    def test_alle_none_frames_canvas_schwarz(self):
        """Alle None-Frames → Canvas ist schwarz."""
        from video.compositor import compose_layout
        result = compose_layout([None, None], OUT)
        assert result.max() == 0, "Canvas muss schwarz sein wenn alle Frames None"

    def test_output_dtype_uint8(self):
        """Ausgabe-Frame hat dtype uint8."""
        from video.compositor import compose_layout
        result = compose_layout([_rotes_frame()], OUT)
        assert result.dtype == np.uint8

    def test_output_ist_c_contiguous(self):
        """Ausgabe-Frame ist C-contiguous (FFmpeg-Kompatibilität)."""
        from video.compositor import compose_layout
        result = compose_layout([_rotes_frame()], OUT)
        assert result.flags["C_CONTIGUOUS"]

    def test_verschiedene_eingangsgroessen(self):
        """Frames mit unterschiedlichen Größen → Canvas hat immer out_size."""
        from video.compositor import compose_layout
        f1 = np.zeros((100, 200, 3), dtype=np.uint8)
        f2 = np.zeros((50, 80, 3), dtype=np.uint8)
        result = compose_layout([f1, f2], OUT)
        W, H = OUT
        assert result.shape == (H, W, 3)

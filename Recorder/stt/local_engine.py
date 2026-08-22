"""stt.local_engine — Lokale STT-Engine auf Basis von faster-whisper.

Lazy-Import: ``faster_whisper`` wird ERST beim ersten :py:meth:`available`-Aufruf
importiert. Fehlt die Bibliothek, gibt :py:meth:`available` ``False`` zurück —
kein Prozess-Absturz.

faster-whisper ist KEIN Pflicht-Requirement. Optionales Extra:
    pip install faster-whisper
"""
from __future__ import annotations

import logging

import numpy as np

from stt.engine_base import LiveSttEngine
from stt.transcript_models import TranscriptChunk

_log = logging.getLogger(__name__)

# Standardgröße des Whisper-Modells. Kleiner = schneller, weniger Speicher.
_STANDARD_MODELL = "base"


class LocalWhisperEngine(LiveSttEngine):
    """STT-Engine auf Basis von faster-whisper (lokal, kein Netzwerk).

    Lazy-Import: ``faster_whisper`` wird beim ersten Aufruf von
    :py:meth:`available` importiert. Fehlt die Bibliothek, wird
    :py:meth:`available` dauerhaft ``False`` zurückgeben.

    Args:
        modell_groesse: Whisper-Modellgröße (z. B. ``"base"``, ``"small"``).
    """

    def __init__(self, modell_groesse: str = _STANDARD_MODELL) -> None:
        self._modell_groesse = modell_groesse
        self._modell = None
        self._lib_verfuegbar: bool | None = None  # None = noch nicht geprüft

    # -------------------------------------------------------------------------
    # LiveSttEngine-Interface
    # -------------------------------------------------------------------------

    @property
    def name(self) -> str:
        return "local"

    def available(self) -> bool:
        """Gibt zurück, ob faster-whisper verfügbar ist.

        Ergebnis wird gecacht — der Import findet nur einmal statt.
        """
        if self._lib_verfuegbar is not None:
            return self._lib_verfuegbar

        try:
            import faster_whisper  # type: ignore[import-untyped]  # noqa: F401
            self._lib_verfuegbar = True
        except ImportError:
            _log.info(
                "faster-whisper nicht installiert — lokale STT-Engine nicht verfügbar. "
                "Installation: pip install faster-whisper"
            )
            self._lib_verfuegbar = False

        return self._lib_verfuegbar

    def transcribe(
        self,
        audio: np.ndarray,
        samplerate: int,
        t_start: float,
    ) -> list[TranscriptChunk]:
        """Transkribiert mit dem lokal geladenen Whisper-Modell.

        Lädt das Modell beim ersten Aufruf (lazy). Kein Crash, wenn die
        Bibliothek nicht installiert ist — gibt leere Liste zurück und loggt.

        Args:
            audio:      Mono-Audioblock als ``float32``-Array.
            samplerate: Samplerate in Hz.
            t_start:    Startzeit des Blocks in Sekunden.

        Returns:
            Liste von :class:`~stt.transcript_models.TranscriptChunk`-Objekten.
        """
        if not self.available():
            return []

        try:
            from faster_whisper import WhisperModel  # type: ignore[import-untyped]

            if self._modell is None:
                _log.info(
                    "Lade Whisper-Modell '%s' (einmalig) …", self._modell_groesse
                )
                self._modell = WhisperModel(
                    self._modell_groesse,
                    device="cpu",
                    compute_type="int8",
                )
                _log.info("Whisper-Modell '%s' geladen.", self._modell_groesse)

            # Mono-Float32 sicherstellen
            audio_mono = _zu_mono_float32(audio)

            # Samplerate-Umwandlung auf 16 kHz (Whisper-Anforderung)
            audio_16k = _resample_auf_16k(audio_mono, samplerate)

            chunks: list[TranscriptChunk] = []
            segmente, _ = self._modell.transcribe(audio_16k, beam_size=5)
            for seg in segmente:
                chunks.append(
                    TranscriptChunk(
                        text=seg.text.strip(),
                        is_final=True,
                        t_start=t_start + seg.start,
                        engine=self.name,
                    )
                )
            return chunks

        except Exception as exc:
            _log.warning("LocalWhisperEngine.transcribe Fehler: %s", exc)
            return []


# ---------------------------------------------------------------------------
# Hilfsfunktionen (modulprivat)
# ---------------------------------------------------------------------------


def _zu_mono_float32(audio: np.ndarray) -> np.ndarray:
    """Konvertiert ein Audio-Array zu Mono float32.

    Unterstützt Shapes ``(N,)``, ``(N, 1)`` und ``(N, C)`` (C > 1).
    """
    arr = np.asarray(audio, dtype=np.float32)
    if arr.ndim == 1:
        return arr
    if arr.ndim == 2:
        if arr.shape[1] == 1:
            return arr[:, 0]
        return arr.mean(axis=1)
    # Unerwartetes Shape: flatten auf 1D
    return arr.flatten()


def _resample_auf_16k(audio: np.ndarray, src_rate: int) -> np.ndarray:
    """Resampled float32-Mono-Audio von src_rate auf 16 000 Hz.

    Einfaches lineares Resampeln (genügt für Spracherkennung).
    Kein zusätzliches Paket erforderlich.
    """
    target_rate = 16_000
    if src_rate == target_rate:
        return audio
    # Verhältnis der Abtastraten
    verhaeltnis = target_rate / src_rate
    neue_laenge = int(round(len(audio) * verhaeltnis))
    if neue_laenge == 0:
        return audio
    return np.interp(
        np.linspace(0, len(audio) - 1, neue_laenge),
        np.arange(len(audio)),
        audio,
    ).astype(np.float32)

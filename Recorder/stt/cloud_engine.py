"""stt.cloud_engine — Cloud-STT-Engine über die OpenAI Whisper API.

Lazy-Import: ``openai`` wird ERST beim ersten :py:meth:`available`-Aufruf
importiert. Fehlt die Bibliothek ODER der API-Schlüssel, gibt
:py:meth:`available` ``False`` zurück — kein Prozess-Absturz.

API-Schlüssel wird AUSSCHLIESSLICH aus der Umgebungsvariablen ``OPENAI_API_KEY``
gelesen (niemals hartcodiert). Opt-in: ohne Schlüssel ist die Engine inaktiv.

openai ist KEIN Pflicht-Requirement. Optionales Extra:
    pip install openai
"""
from __future__ import annotations

import io
import logging
import os

import numpy as np

from stt.engine_base import LiveSttEngine
from stt.transcript_models import TranscriptChunk

_log = logging.getLogger(__name__)

# Umgebungsvariable für den OpenAI API-Schlüssel
_KEY_ENV = "OPENAI_API_KEY"


class CloudSttEngine(LiveSttEngine):
    """STT-Engine über die OpenAI Whisper API (Cloud, opt-in).

    Lazy-Import: ``openai`` wird beim ersten Aufruf von :py:meth:`available`
    importiert. Der API-Schlüssel wird aus ``OPENAI_API_KEY`` gelesen.
    Fehlt Bibliothek oder Schlüssel → :py:meth:`available` = ``False``,
    kein Crash.

    Args:
        env_schluessel: Name der Umgebungsvariablen mit dem API-Schlüssel
                        (Standard: ``"OPENAI_API_KEY"``).
    """

    def __init__(self, env_schluessel: str = _KEY_ENV) -> None:
        self._env_schluessel = env_schluessel
        self._lib_verfuegbar: bool | None = None  # None = noch nicht geprüft
        self._client = None

    # -------------------------------------------------------------------------
    # LiveSttEngine-Interface
    # -------------------------------------------------------------------------

    @property
    def name(self) -> str:
        return "cloud"

    def available(self) -> bool:
        """Gibt zurück, ob Bibliothek UND API-Schlüssel vorhanden sind.

        Ergebnis wird gecacht — der Import findet nur einmal statt.
        """
        if self._lib_verfuegbar is not None:
            return self._lib_verfuegbar

        # Schritt 1: Bibliothek prüfen
        try:
            import openai  # type: ignore[import-untyped]  # noqa: F401
        except ImportError:
            _log.info(
                "openai nicht installiert — Cloud-STT-Engine nicht verfügbar. "
                "Installation: pip install openai"
            )
            self._lib_verfuegbar = False
            return False

        # Schritt 2: API-Schlüssel prüfen
        schluessel = os.environ.get(self._env_schluessel, "").strip()
        if not schluessel:
            _log.info(
                "Umgebungsvariable %s nicht gesetzt — "
                "Cloud-STT-Engine deaktiviert (opt-in erforderlich).",
                self._env_schluessel,
            )
            self._lib_verfuegbar = False
            return False

        self._lib_verfuegbar = True
        return True

    def transcribe(
        self,
        audio: np.ndarray,
        samplerate: int,
        t_start: float,
    ) -> list[TranscriptChunk]:
        """Transkribiert über die OpenAI Whisper-API.

        Wandelt Audio in WAV um (In-Memory) und schickt es zur API.
        Kein Crash bei fehlender Lib/Schlüssel — gibt leere Liste zurück.

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
            import openai  # type: ignore[import-untyped]

            schluessel = os.environ.get(self._env_schluessel, "").strip()
            if not schluessel:
                return []

            if self._client is None:
                self._client = openai.OpenAI(api_key=schluessel)

            # Mono-Float32 sicherstellen
            audio_mono = _zu_mono_float32(audio)

            # WAV in-memory kodieren (soundfile als stdlib-freier Weg)
            wav_bytes = _als_wav_bytes(audio_mono, samplerate)

            antwort = self._client.audio.transcriptions.create(
                model="whisper-1",
                file=("audio.wav", wav_bytes, "audio/wav"),
                response_format="json",
            )

            text = (antwort.text or "").strip()
            if not text:
                return []

            return [
                TranscriptChunk(
                    text=text,
                    is_final=True,
                    t_start=t_start,
                    engine=self.name,
                )
            ]

        except Exception as exc:
            _log.warning("CloudSttEngine.transcribe Fehler: %s", exc)
            return []


# ---------------------------------------------------------------------------
# Hilfsfunktionen (modulprivat)
# ---------------------------------------------------------------------------


def _zu_mono_float32(audio: np.ndarray) -> np.ndarray:
    """Konvertiert ein Audio-Array zu Mono float32."""
    arr = np.asarray(audio, dtype=np.float32)
    if arr.ndim == 1:
        return arr
    if arr.ndim == 2:
        if arr.shape[1] == 1:
            return arr[:, 0]
        return arr.mean(axis=1)
    return arr.flatten()


def _als_wav_bytes(audio: np.ndarray, samplerate: int) -> bytes:
    """Kodiert float32-Mono-Audio als WAV-Bytes (in-memory).

    Versucht soundfile; fällt auf scipy/wave zurück; schreibt sonst
    einen minimalen WAV-Header manuell.
    """
    buf = io.BytesIO()

    # Versuch 1: soundfile (bereits in den Requirements vorhanden)
    try:
        import soundfile as sf  # type: ignore[import-untyped]

        sf.write(buf, audio, samplerate, format="WAV", subtype="FLOAT")
        return buf.getvalue()
    except ImportError:
        pass

    # Versuch 2: scipy
    try:
        from scipy.io import wavfile  # type: ignore[import-untyped]

        pcm = (audio * 32767).astype(np.int16)
        wavfile.write(buf, samplerate, pcm)
        return buf.getvalue()
    except ImportError:
        pass

    # Fallback: stdlib wave-Modul
    import struct
    import wave

    pcm = (np.clip(audio, -1.0, 1.0) * 32767).astype(np.int16)
    with wave.open(buf, "wb") as wf:
        wf.setnchannels(1)
        wf.setsampwidth(2)  # 16-bit
        wf.setframerate(samplerate)
        wf.writeframes(pcm.tobytes())

    return buf.getvalue()

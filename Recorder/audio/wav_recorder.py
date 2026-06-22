"""audio.wav_recorder — WAV-Datei-Recorder (PCM_16, soundfile).

Kein GUI-Import. Nur soundfile + stdlib.
"""
import os
from typing import Optional

import numpy as np
import soundfile as sf


class WavRecorder:
    """Schreibt Audio-Blöcke in eine WAV-Datei (PCM_16, SF-kompatibel).

    Die Dauer wird aus der Anzahl geschriebener Frames geteilt durch
    die Samplerate berechnet (deterministische Frames/s-Logik,
    unabhängig von Wall-Clock-Zeit).
    """

    def __init__(self, samplerate: int, channels: int = 2) -> None:
        """Initialisiert den Recorder.

        Args:
            samplerate: Abtastrate in Hz (z. B. 48000).
            channels: Anzahl der Ausgangskanäle.
        """
        self._samplerate = samplerate
        self._channels = channels
        self._datei: Optional[sf.SoundFile] = None
        self._frames_geschrieben: int = 0

    def open(self, path: str) -> None:
        """Öffnet eine neue WAV-Datei zum Schreiben.

        Das übergeordnete Verzeichnis wird bei Bedarf angelegt.
        Ein bereits offener Handle wird vor dem Öffnen geschlossen
        (verhindert Ressourcen-Leck bei doppeltem open()-Aufruf).

        Args:
            path: Zielpfad der WAV-Datei.
        """
        # Schutz gegen Doppelaufruf: alten Handle schließen, bevor ein neuer geöffnet wird.
        if self._datei is not None:
            try:
                self._datei.close()
            except Exception:
                pass
            self._datei = None

        verzeichnis = os.path.dirname(path)
        if verzeichnis:
            os.makedirs(verzeichnis, exist_ok=True)

        self._frames_geschrieben = 0
        self._datei = sf.SoundFile(
            path,
            mode="w",
            samplerate=self._samplerate,
            channels=self._channels,
            format="WAV",
            subtype="PCM_16",
        )

    def write(self, block: np.ndarray) -> None:
        """Schreibt einen Audio-Block in die geöffnete Datei.

        Args:
            block: Audio-Daten, Shape (frames, channels), float32.
        """
        if self._datei is None:
            raise RuntimeError("WavRecorder nicht geöffnet — open() zuerst aufrufen.")
        self._datei.write(block)
        self._frames_geschrieben += len(block)

    def close(self) -> float:
        """Schließt die Datei und gibt die aufgezeichnete Dauer in Sekunden zurück.

        Die Dauer ergibt sich aus Frames/Samplerate (deterministische Berechnung).

        Returns:
            Aufgezeichnete Dauer in Sekunden.
        """
        if self._datei is not None:
            self._datei.flush()
            self._datei.close()
            self._datei = None

        return self._frames_geschrieben / self._samplerate

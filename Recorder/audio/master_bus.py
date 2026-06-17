"""audio.master_bus — Master-Summierer mit Solo-Auflösung und Clipping.

Kein GUI-Import. Nur numpy.
"""
import numpy as np
from audio.mixer_channel import MixerChannel


class MasterBus:
    """Summiert Kanal-Blöcke, löst Solo auf und clipped auf [-1, 1].

    Alle Kanäle werden verarbeitet (damit jeder seinen Peak kennt),
    aber nur Solo-Kanäle fließen in die Summe ein, wenn mindestens
    ein Kanal solo=True hat.
    """

    def __init__(self, channels: list[MixerChannel]) -> None:
        """Erstellt einen MasterBus für die gegebene Kanal-Liste.

        Args:
            channels: Geordnete Liste der Mischer-Kanäle.
        """
        self._channels = channels

    def mix(self, blocks: dict[str, np.ndarray]) -> np.ndarray:
        """Verarbeitet alle Kanäle und summiert sie zum Master-Mix.

        Verarbeitungsreihenfolge:
        1. Alle Kanäle verarbeiten (process → Peak aktualisieren).
        2. Solo-Filter: Wenn mind. ein Kanal solo=True, nur Solo-Blöcke summieren.
        3. Clippen auf [-1.0, 1.0].

        Args:
            blocks: Mapping source_id → Audio-Block (shape: block_size × ch).

        Returns:
            Gemischter und geclippter Block (gleiche Shape wie Eingangsblöcke).
        """
        # Schritt 1: Alle Kanäle verarbeiten (Peak-Update für ALLE)
        verarbeitete: dict[str, np.ndarray] = {}
        for kanal in self._channels:
            if kanal.source_id in blocks:
                verarbeitete[kanal.source_id] = kanal.process(blocks[kanal.source_id])

        # Shape aus erstem vorhandenen Block ermitteln
        if not verarbeitete:
            # Fallback: Null-Block mit vernünftiger Standardgröße
            return np.zeros((1024, 2), dtype=np.float32)

        beispiel = next(iter(verarbeitete.values()))
        summe = np.zeros_like(beispiel, dtype=np.float32)

        # Schritt 2: Solo-Auflösung
        hat_solo = any(kanal.solo for kanal in self._channels)

        for kanal in self._channels:
            if kanal.source_id not in verarbeitete:
                continue
            if hat_solo and not kanal.solo:
                continue  # Nicht-Solo-Kanal wird ausgeblendet
            summe += verarbeitete[kanal.source_id]

        # Schritt 3: Clippen
        np.clip(summe, -1.0, 1.0, out=summe)
        return summe

    def mix_with_channels(
        self, blocks: dict[str, np.ndarray]
    ) -> tuple[np.ndarray, dict[str, np.ndarray]]:
        """Wie mix(), gibt aber zusätzlich die verarbeiteten Einzel-Kanal-Blöcke zurück.

        Vermeidet Doppel-Verarbeitung: process() wird exakt einmal pro Kanal
        aufgerufen; die verarbeiteten Blöcke können direkt in die Kanal-WAVs
        geschrieben werden.

        Args:
            blocks: Mapping source_id → Roh-Audio-Block (shape: block_size × ch).

        Returns:
            (summe, verarbeitete) — summe ist der geclippte Mix-Block;
            verarbeitete bildet source_id auf den verarbeiteten Block ab.
        """
        # Schritt 1: Alle Kanäle genau einmal verarbeiten
        verarbeitete: dict[str, np.ndarray] = {}
        for kanal in self._channels:
            if kanal.source_id in blocks:
                verarbeitete[kanal.source_id] = kanal.process(blocks[kanal.source_id])

        if not verarbeitete:
            leer = np.zeros((1024, 2), dtype=np.float32)
            return leer, {}

        beispiel = next(iter(verarbeitete.values()))
        summe = np.zeros_like(beispiel, dtype=np.float32)

        # Schritt 2: Solo-Auflösung
        hat_solo = any(kanal.solo for kanal in self._channels)

        for kanal in self._channels:
            if kanal.source_id not in verarbeitete:
                continue
            if hat_solo and not kanal.solo:
                continue
            summe += verarbeitete[kanal.source_id]

        # Schritt 3: Clippen
        np.clip(summe, -1.0, 1.0, out=summe)
        return summe, verarbeitete

    def mix(self, blocks: dict[str, np.ndarray]) -> np.ndarray:
        """Verarbeitet alle Kanäle und summiert sie zum Master-Mix.

        Verarbeitungsreihenfolge:
        1. Alle Kanäle verarbeiten (process → Peak aktualisieren).
        2. Solo-Filter: Wenn mind. ein Kanal solo=True, nur Solo-Blöcke summieren.
        3. Clippen auf [-1.0, 1.0].

        Args:
            blocks: Mapping source_id → Audio-Block (shape: block_size × ch).

        Returns:
            Gemischter und geclippter Block (gleiche Shape wie Eingangsblöcke).
        """
        summe, _ = self.mix_with_channels(blocks)
        return summe

    def peaks(self) -> list[float]:
        """Gibt die aktuellen Kanal-Peaks in Kanal-Reihenfolge zurück.

        Returns:
            Liste der Peak-Werte (float), Länge = len(channels).
        """
        return [kanal.peak for kanal in self._channels]

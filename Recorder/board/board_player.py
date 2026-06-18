"""board.board_player — Spielt Board-Pads ab.

Keine GUI-Imports. Kein PySide6.

Thread-Modell:
    - Pro laufendem Audio-Pad läuft ein Feeder-Thread, der WAV-Blöcke
      in engine._board_puffer schreibt.
    - Fade-in/out per linearer Rampe über FADE_FRAMES Frames.
    - Ducking: DuckController wird aufgerufen, sobald ein Audio-Pad spielt.
    - Video/Bild-Pads: kein Audio — nur on_visual_pad-Callback.
    - Sauberes Thread-Handling: join(timeout=2.0) bei stop/stop_all.

Hinweis zum Mode „play_stop":
    trigger() togglet — läuft der Pad, wird er gestoppt; sonst gestartet.
"""
from __future__ import annotations

import logging
import threading
import time
from collections import deque
from typing import Callable, Optional

import numpy as np
import soundfile as sf

from board.board_model import Board, Pad
from board.duck_controller import DuckController

_log = logging.getLogger(__name__)

# Länge der Fade-Rampe in Frames (linear)
FADE_FRAMES = 512


class _PadFeeder:
    """Interner Feeder-Thread für einen einzelnen Audio-Pad.

    Liest das WAV-Asset blockweise, wendet Fade-in/out + volume an
    und schreibt Blöcke in seinen eigenen pro-Feeder-Puffer (Task 6a).

    Durch den pro-Feeder-Puffer können mehrere gleichzeitig spielende Pads
    (z. B. im Overlap-Mode oder Jingle über Musikbett) additiv summiert werden
    statt zeitlich verschachtelt — der MixWorker zieht je Tick aus ALLEN
    registrierten Feeder-Puffern und summiert.

    Der Feeder kennt weder MixerChannels noch WavRecorder — er
    kommuniziert ausschließlich über seine thread-safe deque.
    """

    def __init__(
        self,
        pad: Pad,
        engine,
        block_size: int,
        samplerate: int,
        audio_channels: int,
        duck: Optional[DuckController],
        on_finish: Callable[[], None],
        stop_event: threading.Event,
    ) -> None:
        self.pad = pad
        self._engine = engine
        self._block_size = block_size
        self._samplerate = samplerate
        self._audio_channels = audio_channels
        self._duck = duck
        self._on_finish = on_finish
        self._stop_event = stop_event

        self._thread: Optional[threading.Thread] = None
        # Amplitude des zuletzt geschriebenen Frames — für korrekten Fade-out
        self._letzter_amp: float = 0.0
        # Feeder ist fertig (Fütter-Schleife abgeschlossen) — gesetzt vor on_finish
        self._fertig: bool = False

        # Pro-Feeder-Puffer (Task 6a): wird beim Start via register_board_feeder()
        # bei der Engine registriert. Eindeutige ID = id(self) — verhindert Kollision
        # auch wenn mehrere Feeder für denselben Pad laufen (Overlap-Mode).
        self._feeder_id: int = id(self)
        self._puffer = None  # wird in start() gesetzt

    def start(self) -> None:
        """Startet den Feeder-Thread und registriert den pro-Feeder-Puffer.

        Falls die Engine die neue API (register_board_feeder) unterstützt,
        wird ein eigener Puffer registriert. Andernfalls Fallback auf den
        Legacy-_board_puffer (Rückwärtskompatibilität mit alten Engine-Stubs
        in Tests).
        """
        if hasattr(self._engine, "register_board_feeder"):
            self._puffer = self._engine.register_board_feeder(self._feeder_id)
        else:
            # Legacy-Fallback für Stub-Engines in Tests
            self._puffer = self._engine._board_puffer

        self._thread = threading.Thread(
            target=self._run,
            name=f"BoardFeeder-{self.pad.id}",
            daemon=True,
        )
        self._thread.start()

    def stop(self, timeout: float = 2.0) -> None:
        """Signalisiert dem Feeder, aufzuhören, und wartet auf Join."""
        self._stop_event.set()
        if self._thread is not None:
            self._thread.join(timeout=timeout)
            self._thread = None

    def is_alive(self) -> bool:
        """Gibt zurück, ob der Feeder-Thread noch aktiv Daten liefert.

        _fertig wird gesetzt bevor on_finish() aufgerufen wird — so zählt
        sich ein Feeder nicht mehr als aktiv, während er noch im finally-Block
        des Thread-Runners läuft (wichtig für Ducking-Stop-Entscheidung).
        """
        if self._fertig:
            return False
        return self._thread is not None and self._thread.is_alive()

    def _run(self) -> None:
        """Feeder-Schleife: liest WAV und schreibt in board-Puffer."""
        block_size = self._block_size
        sr = self._samplerate
        ch = self._audio_channels
        loop = self.pad.mode == "loop"

        # Ducking starten (stop_duck wird via on_finish aus BoardPlayer aufgerufen,
        # wenn kein weiterer Feeder mehr läuft — daher nicht hier stoppen).
        if self._duck is not None:
            self._duck.start_duck()

        try:
            self._feed_loop(block_size, sr, ch, loop)
        except Exception as exc:
            _log.warning("BoardFeeder %s: Fehler beim Abspielen: %s", self.pad.id, exc)
        finally:
            # Fade-out anhängen (echte Rampe, kein bloßes Schweigen)
            self._fade_out_in_puffer(block_size, ch)
            # Pro-Feeder-Puffer bei der Engine abmelden (Task 6a).
            # Idempotent — unregister_board_feeder() ist robust gegen doppelten Aufruf.
            if hasattr(self._engine, "unregister_board_feeder"):
                self._engine.unregister_board_feeder(self._feeder_id)
            # Als fertig markieren, BEVOR on_finish() aufgerufen wird,
            # damit _aktive_feeder_anzahl() diesen Feeder nicht mehr zählt.
            self._fertig = True
            # on_finish räumt Feeder auf und beendet Ducking wenn letzter Feeder
            self._on_finish()

    def _feed_loop(
        self, block_size: int, sr: int, ch: int, loop: bool
    ) -> None:
        """Innere Schleife — wiederholt wenn loop=True."""
        soll_intervall = block_size / sr

        while True:
            if self._stop_event.is_set():
                return

            # WAV laden
            try:
                daten, datei_sr = sf.read(
                    self.pad.asset_path, dtype="float32", always_2d=True
                )
            except Exception as exc:
                _log.warning(
                    "BoardFeeder %s: Asset nicht ladbar (%s): %s",
                    self.pad.id, self.pad.asset_path, exc,
                )
                return

            # Auf Engine-Samplerate resampling überspringen (einfach nehmen wie es ist)
            # Mono → Stereo konvertieren wenn nötig
            daten = self._passe_kanaele_an(daten, ch)

            gesamt_frames = daten.shape[0]
            gesamt_bloecke = max(1, (gesamt_frames + block_size - 1) // block_size)

            # Fade-in Rampe (erste FADE_FRAMES Frames)
            fade_frames = min(FADE_FRAMES, gesamt_frames)

            for block_idx in range(gesamt_bloecke):
                if self._stop_event.is_set():
                    return

                start = block_idx * block_size
                ende = min(start + block_size, gesamt_frames)
                block = daten[start:ende].copy()

                # Null-Padding wenn letzter Block kürzer als block_size
                if block.shape[0] < block_size:
                    pad_len = block_size - block.shape[0]
                    block = np.vstack([block, np.zeros((pad_len, ch), dtype=np.float32)])

                # Volume anwenden
                block = block * float(self.pad.volume)

                # Fade-in: erste fade_frames Frames des Assets
                frame_pos = start
                if frame_pos < fade_frames:
                    for frame_off in range(block_size):
                        abs_frame = frame_pos + frame_off
                        if abs_frame < fade_frames:
                            block[frame_off] *= abs_frame / fade_frames
                        else:
                            break

                # Amplitude des letzten Blocks merken (für Fade-out).
                # M-2-Fix: aus der echten Frame-Amplitude ableiten — nicht pauschal
                # pad.volume. Bei sehr kurzen Assets liegt das Ende noch innerhalb der
                # Fade-in-Rampe; pad.volume wäre dann ein zu hoher Startwert für
                # den Fade-out. float-Konversion sichert Serialisierbarkeit.
                self._letzter_amp = float(np.max(np.abs(block)))

                # I-4-Fix: Overflow-Log wenn Feeder-Puffer voll ist.
                # deque.append() bei maxlen würfelt links raus — kein Fehler, kein Log
                # normalerweise. Wir prüfen VOR dem Append, ob noch Platz ist.
                # _puffer ist der pro-Feeder-Puffer (Task 6a); Fallback auf _board_puffer
                # für Stub-Engines (Legacy-Tests).
                puffer = self._puffer if self._puffer is not None else self._engine._board_puffer
                if puffer.maxlen is not None and len(puffer) >= puffer.maxlen:
                    _log.warning(
                        "BoardFeeder %s: Feeder-Puffer voll (maxlen=%d) — "
                        "Block wird verworfen (Overlap-Überlastung?)",
                        self.pad.id,
                        puffer.maxlen,
                    )

                # Echtzeit-Throttling — nicht zu schnell füllen
                loop_start = time.monotonic()
                puffer.append(block)
                elapsed = time.monotonic() - loop_start
                schlaf = soll_intervall - elapsed
                if schlaf > 0:
                    time.sleep(schlaf)

            if not loop:
                return  # nicht wiederholen

    def _fade_out_in_puffer(self, block_size: int, ch: int) -> None:
        """Hängt einen echten Fade-out-Block (Rampe → Stille) in den Feeder-Puffer.

        Rampt linear vom letzten bekannten Amplitudenwert auf 0 über FADE_FRAMES
        Frames, gefolgt von Stille bis block_size.
        Schreibt in den pro-Feeder-Puffer (Task 6a) oder Fallback auf _board_puffer.
        """
        fade_frames = min(FADE_FRAMES, block_size)
        block = np.zeros((block_size, ch), dtype=np.float32)
        # Lineare Rampe: von _letzter_amp auf 0 über fade_frames Frames
        start_amp = self._letzter_amp
        if start_amp > 0.0 and fade_frames > 0:
            rampe = np.linspace(start_amp, 0.0, fade_frames, dtype=np.float32)
            for kanal_idx in range(ch):
                block[:fade_frames, kanal_idx] = rampe
        puffer = self._puffer if self._puffer is not None else self._engine._board_puffer
        puffer.append(block)

    @staticmethod
    def _passe_kanaele_an(daten: np.ndarray, ziel_kanaele: int) -> np.ndarray:
        """Konvertiert Mono→Stereo oder bricht auf ziel_kanaele zurück.

        Args:
            daten:          2D-Array (frames × source_channels), float32.
            ziel_kanaele:   Gewünschte Kanalzahl.

        Returns:
            2D-Array (frames × ziel_kanaele), float32.
        """
        src_ch = daten.shape[1]
        if src_ch == ziel_kanaele:
            return daten
        if ziel_kanaele == 2 and src_ch == 1:
            # Mono → Stereo duplizieren
            return np.hstack([daten, daten])
        if ziel_kanaele == 1 and src_ch > 1:
            # Stereo → Mono mitteln
            return daten.mean(axis=1, keepdims=True)
        # Allgemeiner Fall: erste ziel_kanaele nehmen oder mit Nullen füllen
        if src_ch > ziel_kanaele:
            return daten[:, :ziel_kanaele]
        pad = np.zeros((daten.shape[0], ziel_kanaele - src_ch), dtype=np.float32)
        return np.hstack([daten, pad])


class BoardPlayer:
    """Spielt Board-Pads ab — Audio über Engine, Video/Bild via Callback.

    Args:
        engine:  AudioEngine-Instanz (braucht ._board_puffer, ._config).
        board:   Board mit Pad-Definitionen.
        duck:    Optionaler DuckController für Mic-Ducking. Wenn None, kein Ducking.
        on_visual_pad: Callback für Video/Bild-Pads (wird mit Pad aufgerufen).
    """

    def __init__(
        self,
        engine,
        board: Board,
        duck: Optional[DuckController] = None,
        on_visual_pad: Optional[Callable[[Pad], None]] = None,
    ) -> None:
        self._engine = engine
        self._board = board
        self._duck = duck
        self._on_visual_pad = on_visual_pad

        # Aktive Feeder: pad_id → _PadFeeder
        self._lock = threading.Lock()
        self._feeder: dict[str, list[_PadFeeder]] = {}  # list für overlap

    # -------------------------------------------------------------------------
    # Öffentliche API
    # -------------------------------------------------------------------------

    def trigger(self, pad_id: str) -> None:
        """Triggert ein Pad.

        - Audio-Pad: Spielt Asset ab. Mode bestimmt Verhalten:
            - ``play_stop``: Toggle (läuft → stopp; gestoppt → start).
            - ``loop``: Startet endlose Wiederholung (play_stop-Toggle).
            - ``overlap``: Erlaubt mehrere gleichzeitige Instanzen.
        - Video/Bild-Pad: Ruft on_visual_pad-Callback auf, kein Audio.

        Args:
            pad_id: ID des Pads.
        """
        pad = self._board.get(pad_id)
        if pad is None:
            _log.warning("BoardPlayer.trigger: Pad '%s' nicht gefunden.", pad_id)
            return

        if pad.kind in ("video", "image"):
            if self._on_visual_pad is not None:
                self._on_visual_pad(pad)
            return

        # Audio-Pad
        mode = pad.mode

        with self._lock:
            laufende = self._feeder.get(pad_id, [])
            laufende = [f for f in laufende if f.is_alive()]
            self._feeder[pad_id] = laufende

            if mode == "play_stop" or mode == "loop":
                if laufende:
                    # Toggle: stoppen
                    for feeder in laufende:
                        feeder.stop(timeout=2.0)
                    self._feeder[pad_id] = []
                    return
                # Sonst: starten (play_stop/loop → genau 1 Feeder)
                feeder = self._neuer_feeder(pad)
                self._feeder[pad_id] = [feeder]
                # Duck registrieren bevor Feeder startet (kein Tick-Lücke)
                if self._duck is not None and hasattr(self._engine, "register_duck"):
                    self._engine.register_duck(self._duck)
                feeder.start()

            elif mode == "overlap":
                # Immer neuen Feeder starten, bestehende laufen weiter
                feeder = self._neuer_feeder(pad)
                laufende.append(feeder)
                self._feeder[pad_id] = laufende
                # Duck registrieren wenn erster Feeder (overlap kann mehrfach aufrufen)
                if self._duck is not None and hasattr(self._engine, "register_duck"):
                    self._engine.register_duck(self._duck)
                feeder.start()

    def stop(self, pad_id: str) -> None:
        """Stoppt alle laufenden Feeder für ein bestimmtes Pad.

        Args:
            pad_id: ID des Pads.
        """
        with self._lock:
            feeder_liste = self._feeder.pop(pad_id, [])

        for feeder in feeder_liste:
            feeder.stop(timeout=2.0)

    def stop_all(self) -> None:
        """Stoppt alle laufenden Pads und wartet auf Thread-Ende."""
        with self._lock:
            alle = list(self._feeder.items())
            self._feeder.clear()

        for _, feeder_liste in alle:
            for feeder in feeder_liste:
                feeder.stop(timeout=2.0)

    def active_pad_ids(self) -> list[str]:
        """Gibt die IDs aller Pads zurück, für die aktuell mindestens ein Feeder läuft.

        Returns:
            Liste von pad_ids (Reihenfolge nicht garantiert).
        """
        with self._lock:
            return [
                pad_id
                for pad_id, feeder_liste in self._feeder.items()
                if any(f.is_alive() for f in feeder_liste)
            ]

    # -------------------------------------------------------------------------
    # Intern
    # -------------------------------------------------------------------------

    def _aktive_feeder_anzahl(self) -> int:
        """Gibt die Gesamtzahl aller aktiven Feeder zurück (unter Lock aufrufen!)."""
        return sum(
            sum(1 for f in fl if f.is_alive())
            for fl in self._feeder.values()
        )

    def _neuer_feeder(self, pad: Pad) -> _PadFeeder:
        """Erzeugt einen neuen _PadFeeder für das gegebene Pad."""
        cfg = self._engine._config
        stop_event = threading.Event()

        def on_finish():
            # Feeder aus der Liste entfernen wenn fertig
            with self._lock:
                laufende = self._feeder.get(pad.id, [])
                # Alle nicht mehr alive entfernen
                self._feeder[pad.id] = [f for f in laufende if f.is_alive()]
                # Wenn kein Feeder mehr läuft: Ducking beenden
                if self._duck is not None and self._aktive_feeder_anzahl() == 0:
                    self._duck.stop_duck()
                    if hasattr(self._engine, "unregister_duck"):
                        self._engine.unregister_duck()

        return _PadFeeder(
            pad=pad,
            engine=self._engine,
            block_size=cfg.block_size,
            samplerate=cfg.samplerate,
            audio_channels=cfg.channels,
            duck=self._duck,
            on_finish=on_finish,
            stop_event=stop_event,
        )

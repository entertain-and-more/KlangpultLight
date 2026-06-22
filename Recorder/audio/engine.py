"""audio.engine — AudioEngine: bindet alle Audio-Komponenten zusammen.

Kein GUI-Import. Keine QMutex/PySide6. Nur stdlib + numpy + soundfile.

Thread-Modell (Task 3c — Architektur-Fix):
- **Pro-Kanal-Eingangspuffer** (`_kanal_puffer`): je ein `collections.deque`
  (thread-safe, bounded). Stream-Callbacks (real) und der Mock-Synth-Loop
  schreiben Roh-Blöcke AUSSCHLIESSLICH in den jeweiligen Kanalpuffer.
  Kein Mixen im Callback.
- **Zentraler MixWorker-Thread** (`_mix_worker`): läuft von start() bis stop().
  Zieht je Tick aus ALLEN Kanalpuffern einen Block (fehlt einer, werden Zeros
  verwendet — Ausrichtung bleibt erhalten), summiert via MasterBus.mix_with_channels
  und schreibt (wenn Aufnahme aktiv) in mix.wav und die Einzel-Kanal-WAVs.
  Peak-Updates und _produced-Zähler laufen ebenfalls im MixWorker.
- Der Mock-Synth-Loop füllt die Kanalpuffer mit synthetischem Audio (Sinus +
  Rauschen) in Echtzeit-Kadenz.
- Reale sounddevice-Callbacks schreiben empfangene Frames in die Kanalpuffer
  (WASAPI-Loopback nur auf Windows-Hardware verifizierbar).
- Peaks werden in eine collections.deque geschrieben (thread-safe append).
  latest_peaks() liest das neueste Element — für späteres QTimer-Polling.
- Kein direkter GUI-Aufruf aus Audio- oder MixWorker-Thread.
"""
import logging
import os
import threading
import time
from collections import deque
from typing import Optional

import numpy as np

from core.config import AppConfig
from core.app_state import AppState
from audio.mixer_channel import MixerChannel
from audio.master_bus import MasterBus
from audio.wav_recorder import WavRecorder

_log = logging.getLogger(__name__)

# Puffer-Tiefe je Kanal (Frames, Ringpuffer — bounded, kein blockierender put)
_PUFFER_MAXLEN = 128
# Anzahl Frames pro synthetischem Block im Mock-Modus
_MOCK_BLOCK_GROESSE = 1024
# Samplerate des synthetischen Signals (überschrieben durch AppConfig)
_MOCK_SAMPLERATE = 48000


class AudioEngine:
    """Koordiniert Geräte-Streams, Kanäle, MasterBus und WavRecorder.

    Im Mock-Modus (PODCAST_RECORDER_MOCK_AUDIO=1 oder config.mock_audio=True)
    läuft ein Hintergrund-Thread, der synthetisches Audio produziert.
    Kein Hardware-Zugriff.

    Öffentliche API (kompatibel zu Task 1a–3b):
        start / stop / start_recording / stop_recording /
        latest_peaks / queue_backlog / channel_count / is_running
    """

    def __init__(
        self,
        config: AppConfig,
        channels: list[MixerChannel],
        state: Optional[AppState] = None,
    ) -> None:
        """Initialisiert die Engine.

        Args:
            config: Anwendungskonfiguration.
            channels: Liste der Mischer-Kanäle.
            state: Optionaler AppState für Zustandsexport (kann None sein).
        """
        self._config = config
        self._channels = channels
        self._state = state
        self._bus = MasterBus(channels)

        # Pro-Kanal-Eingangspuffer (thread-safe deque, bounded)
        self._kanal_puffer: dict[str, deque] = {
            kanal.source_id: deque(maxlen=_PUFFER_MAXLEN)
            for kanal in channels
        }

        # Thread-safe Peak-Deque (maxlen verhindert unbegrenztes Wachstum)
        self._peak_deque: deque[list[float]] = deque(maxlen=10)

        # Backlog-Zähler: produziert minus konsumiert (für queue_backlog())
        # _produced wird im MixWorker bei jedem Tick hochgezählt.
        # _consumed wird in latest_peaks() gesetzt.
        # Eigener Lock (nicht _aufnahme_lock — getrenntes Concern).
        self._produced: int = 0
        self._consumed: int = 0
        self._backlog_lock = threading.Lock()

        # Aufnahme-Zustand
        self._recording = False
        self._mix_recorder: Optional[WavRecorder] = None
        self._kanal_recorder: dict[str, WavRecorder] = {}
        self._aufnahme_dir: Optional[str] = None
        self._aufnahme_lock = threading.Lock()

        # Thread-Steuerung
        self._mix_worker_thread: Optional[threading.Thread] = None
        self._mock_thread: Optional[threading.Thread] = None
        self._stop_event = threading.Event()
        self._laeuft = False

        # Reale sounddevice-Streams
        self._echte_streams: list = []

        # Board-Audio-Puffer (Task 4a — additiv, kein neuer MixerChannel).
        # Blöcke werden vom BoardPlayer eingereiht und im MixWorker auf den
        # fertig gemischten Block summiert (nach mix_with_channels, vor Aufnahme).
        # Eigene deque — ändert weder _channels noch channel_count().
        # Rückwärtskompatibel: Tests die direkt auf _board_puffer schreiben, nutzen
        # diesen Puffer. Er wird im MixWorker wie ein weiterer Feeder-Puffer behandelt.
        self._board_puffer: deque = deque(maxlen=_PUFFER_MAXLEN)

        # Pro-Feeder-Puffer (Task 6a — additives Board-Mischen).
        # Jeder _PadFeeder registriert beim Start seinen eigenen Puffer und
        # schreibt ausschließlich dorthin. Im MixWorker werden alle Feeder-Puffer
        # und _board_puffer gemeinsam summiert → gleichzeitige Pads werden additiv
        # gemischt, nicht zeitlich verschachtelt.
        # Schlüssel: eindeutige Feeder-ID (z. B. id(feeder) als int).
        self._board_feeders: dict[int, deque] = {}
        self._board_feeders_lock = threading.Lock()

        # Mic-Ducking (Task 4a) — optionaler DuckController, der im MixWorker
        # pro Tick getickt wird und Mic-Kanal-Blöcke vor dem Mix abschwächt.
        # Gesetzt via register_duck(), gelöscht via unregister_duck().
        self._duck = None
        self._duck_lock = threading.Lock()

        # Initialer Peak-Eintrag (Nullen der Kanal-Länge) — damit
        # latest_peaks() schon vor start() eine gültige Liste liefert.
        self._peak_deque.append([0.0] * len(channels))

        # Guard: Shape-Mismatch zwischen Board-Block und Mix-Block nur einmal loggen
        # (kein Spam pro verworfenen Block).
        self._board_shape_mismatch_geloggt: bool = False

        # Mix-Audio-Tap (Task 5b) — optionaler Callback, der je fertig gemischtem
        # Block aufgerufen wird.  Gesetzt via register_audio_sink(), gelöscht via
        # unregister_audio_sink().  Default None → kein Tap.
        # Der Callback wird NACH Board-Audio-Summierung aufgerufen (voller Mix).
        # Aufruf im MixWorker-Thread → Callback MUSS non-blocking sein und
        # darf NIEMALS die GUI direkt aufrufen.
        self._mix_sink = None
        self._mix_sink_lock = threading.Lock()

    # -------------------------------------------------------------------------
    # Lifecycle
    # -------------------------------------------------------------------------

    def start(self) -> None:
        """Startet die Audio-Engine (MixWorker + Mock-Thread oder echte Streams)."""
        if self._laeuft:
            return

        # Board-Shape-Mismatch-Guard bei Neustart zurücksetzen, damit nach einem
        # Board-/Kanal-Reload der erste Mismatch wieder geloggt wird.
        self._board_shape_mismatch_geloggt = False

        self._stop_event.clear()

        # MixWorker immer starten (Mock und Real).
        # WICHTIG: _laeuft wird erst NACH erfolgreichem Start aller Threads gesetzt.
        # Bei einem Fehler im Mock-/Stream-Start wird der bereits laufende MixWorker
        # über _stop_event gestoppt, damit kein Orphan-Thread entsteht und ein
        # erneutes start() sauber funktioniert.
        mix_worker = threading.Thread(
            target=self._mix_worker_loop,
            name="MixWorker",
            daemon=True,
        )
        mix_worker.start()
        self._mix_worker_thread = mix_worker

        try:
            if self._nutze_mock():
                mock_thread = threading.Thread(
                    target=self._mock_loop,
                    name="AudioEngine-Mock",
                    daemon=True,
                )
                mock_thread.start()
                self._mock_thread = mock_thread
            else:
                # Reale sounddevice-Streams (Task 3b).
                # ACHTUNG: WASAPI-Loopback ist nur auf Windows-Hardware verifizierbar —
                # im Mock-Pfad (PODCAST_RECORDER_MOCK_AUDIO=1) wird ein synthetischer
                # System-Kanal erzeugt; der reale Pfad hier ist für Produktionsbetrieb.
                self._starte_echte_streams()
        except Exception:
            # Rollback: MixWorker stoppen, damit kein Orphan-Thread entsteht
            self._stop_event.set()
            mix_worker.join(timeout=2.0)
            self._mix_worker_thread = None
            raise

        self._laeuft = True

    def stop(self) -> None:
        """Stoppt die Audio-Engine und beendet laufende Streams/Threads."""
        if not self._laeuft:
            return

        # Laufende Aufnahme abschließen, wenn aktiv.
        # _recording konsistent unter Lock lesen, danach lock-frei stop_recording() aufrufen
        # (stop_recording() nimmt _aufnahme_lock intern — kein Deadlock, da wir hier
        # schon freigegeben haben).
        with self._aufnahme_lock:
            laeuft_aufnahme = self._recording
        if laeuft_aufnahme:
            self.stop_recording()

        self._stop_event.set()

        # Mock-Thread beenden
        if self._mock_thread is not None:
            self._mock_thread.join(timeout=2.0)
            self._mock_thread = None

        # MixWorker beenden (nach Mock-Thread, damit restliche Puffer geleert)
        if self._mix_worker_thread is not None:
            self._mix_worker_thread.join(timeout=2.0)
            self._mix_worker_thread = None

        # Reale sounddevice-Streams schließen (wenn vorhanden)
        for stream in self._echte_streams:
            try:
                stream.stop()
                stream.close()
            except Exception as exc:
                # Task 3c Minor: Stream-close-Fehler nicht lautlos verschlucken
                _log.warning("Stream-close-Fehler beim Stoppen der Audio-Engine: %s", exc)
        self._echte_streams = []

        self._laeuft = False

    # -------------------------------------------------------------------------
    # Aufnahme
    # -------------------------------------------------------------------------

    def start_recording(self, out_dir: str) -> None:
        """Startet die Aufnahme in das angegebene Verzeichnis.

        Erzeugt je Kanal eine WAV-Datei (<source_id>.wav) sowie
        eine gemeinsame Mix-Datei (mix.wav).

        Args:
            out_dir: Zielverzeichnis (wird angelegt, falls nicht vorhanden).
        """
        with self._aufnahme_lock:
            if self._recording:
                return

            os.makedirs(out_dir, exist_ok=True)
            self._aufnahme_dir = out_dir

            sr = self._config.samplerate
            ch = self._config.channels

            # Mix-Recorder
            self._mix_recorder = WavRecorder(samplerate=sr, channels=ch)
            self._mix_recorder.open(os.path.join(out_dir, "mix.wav"))

            # Kanal-Recorder
            self._kanal_recorder = {}
            for kanal in self._channels:
                rec = WavRecorder(samplerate=sr, channels=ch)
                rec.open(os.path.join(out_dir, f"{kanal.source_id}.wav"))
                self._kanal_recorder[kanal.source_id] = rec

            self._recording = True

            if self._state is not None:
                self._state.recording = True

    def stop_recording(self) -> dict:
        """Beendet die Aufnahme und gibt Metadaten zurück.

        Returns:
            dict mit:
                "duration": float — Aufnahmedauer in Sekunden
                "mix": str — Pfad zur Mix-WAV
                "channels": dict[str, str] — source_id → Kanal-WAV-Pfad
        """
        with self._aufnahme_lock:
            if not self._recording:
                return {"duration": 0.0, "mix": "", "channels": {}}

            self._recording = False

            if self._state is not None:
                self._state.recording = False

            # Mix-Datei schließen
            mix_dauer = 0.0
            mix_pfad = ""
            if self._mix_recorder is not None:
                mix_dauer = self._mix_recorder.close()
                mix_pfad = os.path.join(self._aufnahme_dir or "", "mix.wav")
                self._mix_recorder = None

            # Kanal-Dateien schließen
            kanal_pfade: dict[str, str] = {}
            for source_id, rec in self._kanal_recorder.items():
                rec.close()
                kanal_pfade[source_id] = os.path.join(
                    self._aufnahme_dir or "", f"{source_id}.wav"
                )
            self._kanal_recorder = {}

            return {
                "duration": mix_dauer,
                "mix": mix_pfad,
                "channels": kanal_pfade,
            }

    # -------------------------------------------------------------------------
    # Peaks (für GUI-QTimer-Polling)
    # -------------------------------------------------------------------------

    def latest_peaks(self) -> list[float]:
        """Gibt die zuletzt gemessenen Kanal-Peaks zurück.

        Thread-safe: liest das letzte Element der deque.
        Liefert immer eine Liste der Länge len(channels), auch ohne start().

        Setzt _consumed = _produced (vollständiger Abgleich), weil deque[-1]
        stets den neuesten Block zurückgibt — alle dazwischenliegenden gelten
        als konsumiert. Dadurch misst queue_backlog() den Rückstand seit dem
        letzten Poll, nicht einen kumulativen Zähler.

        Returns:
            Liste von Peak-Floats, Länge = len(channels).
        """
        with self._backlog_lock:
            self._consumed = self._produced
        if self._peak_deque:
            return list(self._peak_deque[-1])
        return [0.0] * len(self._channels)

    def queue_backlog(self) -> int:
        """Gibt den aktuellen Audio-Queue-Rückstau zurück.

        Thread-safe: liest _produced und _consumed unter Lock.
        Misst, wie viele Mix-Ticks seit dem letzten latest_peaks()-Aufruf
        noch nicht abgeholt wurden. Nützlich als Eingabe für den DriftMonitor.

        Returns:
            Anzahl unabgeholter Ticks (≥ 0).
        """
        with self._backlog_lock:
            return max(0, self._produced - self._consumed)

    def channel_count(self) -> int:
        """Gibt die Anzahl der MixerChannels zurück.

        Öffentlicher Accessor — vermeidet privaten _channels-Zugriff aus der GUI.

        Returns:
            Anzahl der registrierten MixerChannels.
        """
        return len(self._channels)

    def is_running(self) -> bool:
        """Gibt zurück, ob die Engine läuft.

        Returns:
            True, wenn start() aufgerufen wurde und stop() noch nicht.
        """
        return self._laeuft

    def register_duck(self, duck) -> None:
        """Registriert einen DuckController für Mic-Ducking.

        Der MixWorker tickt den Controller jede Block-Periode und skaliert
        alle Mic-Kanal-Blöcke mit dem aktuellen Gain-Faktor.

        Args:
            duck: DuckController-Instanz (muss tick(dt) und current_gain_factor() haben).
        """
        with self._duck_lock:
            self._duck = duck

    def unregister_duck(self) -> None:
        """Entfernt den aktiven DuckController (Mic-Verstärkung kehrt auf 1.0 zurück)."""
        with self._duck_lock:
            self._duck = None

    # -------------------------------------------------------------------------
    # Mix-Audio-Tap (Task 5b)
    # -------------------------------------------------------------------------

    def register_audio_sink(self, callback) -> None:
        """Registriert einen Mix-Audio-Tap-Callback.

        Der Callback wird einmal pro Mix-Tick mit einer Kopie des vollständig
        gemischten Blocks (inkl. Board-Audio) aufgerufen.  Signatur::

            callback(mix_block: np.ndarray) -> None

        Der Callback läuft im MixWorker-Thread und MUSS non-blocking sein.
        Kein GUI-Aufruf im Callback.  Exceptions im Callback werden abgefangen
        und geloggt — sie dürfen die Aufnahme NIEMALS unterbrechen.

        Args:
            callback: Aufrufbares Objekt mit Signatur ``callback(np.ndarray)``.
        """
        with self._mix_sink_lock:
            self._mix_sink = callback

    def unregister_audio_sink(self) -> None:
        """Entfernt den aktiven Mix-Audio-Tap (kein weiterer Callback)."""
        with self._mix_sink_lock:
            self._mix_sink = None

    # -------------------------------------------------------------------------
    # Pro-Feeder-Board-API (Task 6a — additives Board-Mischen)
    # -------------------------------------------------------------------------

    def register_board_feeder(self, feeder_id: int) -> deque:
        """Registriert einen neuen Board-Feeder-Puffer und gibt ihn zurück.

        Jeder _PadFeeder ruft dies beim Start auf und schreibt alle Board-Blöcke
        ausschließlich in seinen eigenen Puffer. Der MixWorker summiert alle
        registrierten Feeder-Puffer (plus _board_puffer) additiv.

        Feeder-ID muss pro Instanz eindeutig sein — nicht pro Pad (Overlap-Mode
        erzeugt mehrere Feeder für denselben Pad).

        Args:
            feeder_id: Eindeutige Integer-ID des Feeders (z. B. id(feeder_objekt)).

        Returns:
            Gebundene deque (maxlen=_PUFFER_MAXLEN), in die der Feeder schreibt.
        """
        puffer: deque = deque(maxlen=_PUFFER_MAXLEN)
        with self._board_feeders_lock:
            self._board_feeders[feeder_id] = puffer
        return puffer

    def unregister_board_feeder(self, feeder_id: int) -> None:
        """Entfernt den Feeder-Puffer des beendeten Feeders.

        Idempotent — doppelter Aufruf wirft keinen Fehler.

        Args:
            feeder_id: Dieselbe ID, die bei register_board_feeder() übergeben wurde.
        """
        with self._board_feeders_lock:
            self._board_feeders.pop(feeder_id, None)

    # -------------------------------------------------------------------------
    # Zentraler MixWorker (Kern des Task-3c-Fixes)
    # -------------------------------------------------------------------------

    def _mix_one_tick(self) -> bool:
        """Führt einen einzelnen Mix-Tick aus (synchron, testbar).

        Zieht aus JEDEM Kanalpuffer einen Block (fehlt einer, werden Zeros
        verwendet), ruft MasterBus.mix_with_channels auf und schreibt
        (wenn Aufnahme aktiv) in mix.wav und Kanal-WAVs.

        Returns:
            True wenn mindestens ein Kanal Daten hatte (kein reiner Idle-Tick),
            False wenn alle Puffer leer waren.
        """
        block_size = self._config.block_size
        ch = self._config.channels

        # Duck-Controller ticken (vor dem Mix, damit Gain-Faktor aktuell ist)
        dt = block_size / max(1, self._config.samplerate)
        with self._duck_lock:
            duck = self._duck
        if duck is not None:
            duck.tick(dt)
            duck_faktor = duck.current_gain_factor()
        else:
            duck_faktor = 1.0

        # Daten aus Kanalpuffern ziehen
        blocks: dict[str, np.ndarray] = {}
        hat_daten = False

        for kanal in self._channels:
            puffer = self._kanal_puffer[kanal.source_id]
            if puffer:
                blk = puffer.popleft()
                # Mic-Ducking: Block per Gain-Faktor skalieren (erzeugt neues Array)
                if duck_faktor != 1.0:
                    blk = blk * duck_faktor
                blocks[kanal.source_id] = blk
                hat_daten = True
            else:
                # Zeros für fehlenden Block (Ausrichtung erhalten)
                blocks[kanal.source_id] = np.zeros((block_size, ch), dtype=np.float32)

        if not hat_daten:
            # Alle Puffer leer → Idle, nichts schreiben
            return False

        # Mix berechnen (process() einmalig pro Kanal)
        mix_block, verarbeitete = self._bus.mix_with_channels(blocks)

        # Board-Audio additiv summieren (Task 6a — Pro-Feeder-Puffer + Legacy-Puffer).
        # Alle registrierten Feeder-Puffer + _board_puffer (Rückwärtskompatibilität)
        # werden je Tick addiert. Gleichzeitige Pads summierten so wirklich additiv.
        # Snapshot der Feeder-Puffer unter Lock erstellen (verhindert dict-Mutation
        # durch register/unregister während der Iteration im MixWorker-Thread).
        with self._board_feeders_lock:
            feeder_puffer_liste = list(self._board_feeders.values())

        # Alle Board-Quellen sammeln: Legacy-Puffer + pro Feeder-Puffer
        board_summe = np.zeros_like(mix_block, dtype=np.float32)
        hat_board = False

        # Legacy-Puffer (_board_puffer) — für Tests die direkt einschreiben
        if self._board_puffer:
            board_block = self._board_puffer.popleft()
            if board_block.shape == mix_block.shape:
                board_summe += board_block
                hat_board = True
            else:
                if not self._board_shape_mismatch_geloggt:
                    _log.warning(
                        "Board-Block shape %s passt nicht zu Mix-Block shape %s — "
                        "Block verworfen. Weitere Mismatch-Warnungen werden unterdrückt.",
                        board_block.shape,
                        mix_block.shape,
                    )
                    self._board_shape_mismatch_geloggt = True

        # Pro-Feeder-Puffer (Zeros wenn Feeder gerade keine Daten hat)
        for fpuffer in feeder_puffer_liste:
            if fpuffer:
                board_block = fpuffer.popleft()
                if board_block.shape == mix_block.shape:
                    board_summe += board_block
                    hat_board = True
                else:
                    if not self._board_shape_mismatch_geloggt:
                        _log.warning(
                            "Board-Feeder-Block shape %s passt nicht zu Mix-Block shape %s — "
                            "Block verworfen. Weitere Mismatch-Warnungen werden unterdrückt.",
                            board_block.shape,
                            mix_block.shape,
                        )
                        self._board_shape_mismatch_geloggt = True

        if hat_board:
            mix_block = np.clip(mix_block + board_summe, -1.0, 1.0)

        # Mix-Audio-Tap (Task 5b): vollständig gemischten Block an registrierten
        # Callback weitergeben (z. B. SttManager.feed).  Eine Kopie übergeben,
        # damit der Empfänger den Block gefahrlos puffern kann.
        # Exceptions im Callback abfangen — Aufnahme darf NIE unterbrochen werden.
        with self._mix_sink_lock:
            sink = self._mix_sink
        if sink is not None:
            try:
                sink(mix_block.copy())
            except Exception as _sink_exc:
                _log.warning("Mix-Audio-Tap Fehler: %s", _sink_exc)

        # Peak-Update
        peaks = self._bus.peaks()
        self._peak_deque.append(peaks)
        with self._backlog_lock:
            self._produced += 1

        # AppState aktualisieren
        if self._state is not None:
            self._state.peaks = peaks

        # Aufnahme schreiben (Lock für close-Schutz).
        # _recording wird konsistent unter _aufnahme_lock geprüft und geschrieben,
        # damit kein lock-freier Lesezugriff auf eine veränderliche Variable (M-5).
        with self._aufnahme_lock:
            if self._recording:
                if self._mix_recorder is not None:
                    self._mix_recorder.write(mix_block)
                for kanal in self._channels:
                    rec = self._kanal_recorder.get(kanal.source_id)
                    if rec is not None:
                        blk = verarbeitete.get(kanal.source_id)
                        if blk is not None:
                            rec.write(blk)

        return True

    def _mix_worker_loop(self) -> None:
        """Zentraler MixWorker-Thread: drainiert alle Kanalpuffer und mischt.

        Läuft von start() bis stop(). Nur das WAV-Schreiben ist durch
        self._recording gegattet. Peaks werden immer aktualisiert.

        Polling-Intervall: halbe Block-Kadenz, um Latenzen klein zu halten.
        """
        sr = self._config.samplerate
        block_size = self._config.block_size
        poll_intervall = (block_size / sr) * 0.5  # halbe Block-Kadenz

        while not self._stop_event.is_set():
            self._mix_one_tick()
            time.sleep(poll_intervall)

        # Restliche Blöcke drainieren (sauberes Flush beim Stop)
        hat_rest = True
        while hat_rest:
            hat_rest = self._mix_one_tick()

    # -------------------------------------------------------------------------
    # Interne Hilfsmethoden
    # -------------------------------------------------------------------------

    def _starte_echte_streams(self) -> None:
        """Öffnet reale sounddevice-InputStreams je Kanal.

        Mic-Kanäle (capture_method != "wasapi_loopback") werden als normales
        InputStream(device=device_index) geöffnet.

        System-Kanäle (capture_method="wasapi_loopback") werden als Loopback
        geöffnet: InputStream(device=device_index,
                              extra_settings=sounddevice.WasapiSettings(loopback=True)).

        WASAPI-Loopback ist Windows-only und nur auf echter Hardware verifizierbar.
        Bei Fehler (ImportError, fehlende WASAPI-Unterstützung) wird der Kanal
        übersprungen und ein Hinweis geloggt.

        Die Callbacks schreiben NUR in _kanal_puffer (kein Mixen im Callback).
        Die Streams werden in self._echte_streams gespeichert und in stop()
        wieder geschlossen.
        """
        self._echte_streams = []
        sr = self._config.samplerate
        ch = self._config.channels
        block_size = self._config.block_size

        try:
            import sounddevice as sd  # type: ignore[import-untyped]
        except ImportError:
            # sounddevice nicht installiert — kein Absturz, stilles Fallback
            return

        for kanal in self._channels:
            if kanal.device_index is None:
                continue  # Kanal ohne zugewiesenes Gerät überspringen

            try:
                if kanal.capture_method == "wasapi_loopback":
                    # WASAPI-Loopback: Ausgabegerät im Loopback-Modus öffnen.
                    # Nur auf Windows mit WASAPI-HostAPI verifizierbar.
                    try:
                        extra = sd.WasapiSettings(loopback=True)
                    except AttributeError:
                        # Ältere sounddevice-Version ohne WasapiSettings
                        continue
                    stream = sd.InputStream(
                        samplerate=sr,
                        channels=ch,
                        dtype="float32",
                        blocksize=block_size,
                        device=kanal.device_index,
                        extra_settings=extra,
                        callback=self._stream_callback_factory(kanal.source_id),
                    )
                else:
                    # Normales Mic/Line-Input
                    stream = sd.InputStream(
                        samplerate=sr,
                        channels=ch,
                        dtype="float32",
                        blocksize=block_size,
                        device=kanal.device_index,
                        callback=self._stream_callback_factory(kanal.source_id),
                    )
                stream.start()
                self._echte_streams.append(stream)
            except Exception:
                # Gerät nicht öffenbar (unplugged, falsche HostAPI, etc.) — überspringen
                pass

    def _stream_callback_factory(self, source_id: str):
        """Erzeugt einen sounddevice-Callback für einen bestimmten Kanal.

        Der Callback schreibt empfangene Frames NUR in den Kanalpuffer —
        kein Mixen im Callback (Task 3c Fix).
        Kein GUI-Aufruf im Callback — Thread-Sicherheit via bounded deque.
        """
        def _callback(indata, frames, time_info, status):
            if status:  # PortAudio input overflow o.ä. — nicht still verschlucken
                _log.warning("Audio-Callback-Status auf %s: %s", source_id, status)
            block = indata.copy()
            puffer = self._kanal_puffer.get(source_id)
            if puffer is not None:
                # Überlauf sichtbar machen: deque(maxlen) verwirft sonst still den
                # ältesten Frame, wenn der MixWorker nicht hinterherkommt.
                if puffer.maxlen is not None and len(puffer) >= puffer.maxlen:
                    _log.warning(
                        "Kanalpuffer %s voll — Frame verworfen (Writer zu langsam)", source_id
                    )
                puffer.append(block)

        return _callback

    def _nutze_mock(self) -> bool:
        """Prüft zur Laufzeit, ob Mock-Audio aktiv sein soll."""
        import os as _os
        if self._config.mock_audio:
            return True
        if _os.environ.get("PODCAST_RECORDER_MOCK_AUDIO", "").strip() == "1":
            return True
        try:
            import sounddevice as sd  # noqa: F401
            return False
        except Exception:
            return True

    def _mock_loop(self) -> None:
        """Mock-Synth-Thread: produziert synthetisches Audio und befüllt Kanalpuffer.

        Erzeugt einen Sinus-Block je Kanal und legt ihn in den jeweiligen
        Kanalpuffer. Kein Mixen hier — das übernimmt der MixWorker.
        """
        sr = self._config.samplerate
        block_size = self._config.block_size
        ch = self._config.channels
        soll_intervall = block_size / sr  # Echtzeit-Intervall pro Block

        t = 0  # Zeit-Zähler für Sinus
        freq = 440.0  # Sinuston Kammerton A

        while not self._stop_event.is_set():
            start = time.monotonic()

            # Synthetisches Audio: Sinus + leichtes Rauschen
            frames = np.arange(block_size)
            sinus = 0.3 * np.sin(2 * np.pi * freq * (t + frames) / sr)
            rauschen = 0.01 * np.random.randn(block_size)
            mono = (sinus + rauschen).astype(np.float32)

            # Stereo-Block erzeugen (block_size × channels)
            block = np.stack([mono] * ch, axis=1)
            t += block_size

            # Jeden Kanal mit einem Block-Kopie befüllen
            for kanal in self._channels:
                self._kanal_puffer[kanal.source_id].append(block.copy())

            # Echtzeit-Throttling
            elapsed = time.monotonic() - start
            schlaf = soll_intervall - elapsed
            if schlaf > 0:
                time.sleep(schlaf)

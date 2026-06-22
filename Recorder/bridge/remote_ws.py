"""bridge.remote_ws — WebSocket-Dienst nach remote_protocol_v1.

Implementiert:
    Desktop→Companion:
        - ``state_update`` periodisch (~20–30/s): channel_peaks, recording,
          active_pad_ids, prompter_line
        - ``transcript_chunk`` via push_transcript_chunk() (Hook für Task 5b)

    Companion→Desktop:
        - ``trigger_pad``          → board_player.trigger(pad_id)
        - ``toggle_mute``          → Engine-Kanal mute togglen
        - ``insert_chapter_marker`` → Event-Log-Eintrag (Platzhalter)
        - ``scroll_teleprompter``   → Callback (Platzhalter)

Betrieb in eigenem Thread mit eigenem asyncio-Event-Loop.
Sauberes stop() — kein Orphan-Thread, keine offenen Sockets.

Abhängigkeiten sind vollständig injizierbar (engine, state, board_player,
library) — kein GUI-Import, headless testbar.
"""
from __future__ import annotations

import asyncio
import json
import logging
import threading
from typing import Callable, Optional, Set

_log = logging.getLogger(__name__)

# Intervall für state_update in Sekunden (≈25/s)
_STATE_UPDATE_INTERVALL = 0.04


class RemoteWsServer:
    """WebSocket-Dienst nach remote_protocol_v1.

    Args:
        engine:       AudioEngine-Instanz (latest_peaks(), _channels).
        state:        AppState-Instanz (recording).
        board_player: BoardPlayer-Instanz (trigger, active_pad_ids).
        library:      RecordingLibrary-Instanz (optional, für spätere Erweiterungen).
        on_chapter_marker: Callback für insert_chapter_marker (optional).
        on_scroll_teleprompter: Callback für scroll_teleprompter (optional).
        state_update_interval: Sekunden zwischen state_update-Sendungen (override für Tests).
    """

    def __init__(
        self,
        engine=None,
        state=None,
        board_player=None,
        library=None,
        on_chapter_marker: Optional[Callable[[str], None]] = None,
        on_scroll_teleprompter: Optional[Callable[[int], None]] = None,
        state_update_interval: float = _STATE_UPDATE_INTERVALL,
    ) -> None:
        self._engine = engine
        self._state = state
        self._board_player = board_player
        self._library = library
        self._on_chapter_marker = on_chapter_marker
        self._on_scroll_teleprompter = on_scroll_teleprompter
        self._state_update_interval = state_update_interval

        self._loop: Optional[asyncio.AbstractEventLoop] = None
        self._ws_server = None          # websockets.asyncio.server.Server
        self._thread: Optional[threading.Thread] = None
        self._stop_event = threading.Event()

        # Verbundene Clients. Der asyncio.Lock wird erst im Event-Loop-Thread
        # erzeugt (_run_loop), da er an den dort laufenden Loop gebunden sein muss.
        self._clients: Set = set()
        self._clients_lock: Optional[asyncio.Lock] = None

        # Tatsächlich gebundener Port (nach start(), für Tests mit port=0)
        self._bound_port: Optional[int] = None
        self._port_ready = threading.Event()

    @property
    def port(self) -> Optional[int]:
        """Tatsächlich gebundener Port (nach start())."""
        return self._bound_port

    # -------------------------------------------------------------------------
    # Lifecycle
    # -------------------------------------------------------------------------

    def start(self, host: str = "127.0.0.1", port: int = 8768) -> None:
        """Startet den WebSocket-Server in einem eigenen Thread.

        Blockiert bis der Server tatsächlich gebunden ist (max. 10 s).

        Args:
            host: Bind-Adresse (Standard: 127.0.0.1).
            port: Port (Standard: 8768). Port 0 = Betriebssystem wählt freien Port.
        """
        if self._thread is not None:
            return  # Bereits gestartet

        self._stop_event.clear()
        self._port_ready.clear()

        thread = threading.Thread(
            target=self._run_loop,
            args=(host, port),
            name="RemoteWsServer",
            daemon=True,
        )
        try:
            thread.start()
        except Exception:
            # Thread-Start fehlgeschlagen: self._thread bleibt None,
            # damit ein erneuter start()-Aufruf nicht blockiert wird.
            raise
        self._thread = thread

        # Warten bis Server gebunden ist
        if not self._port_ready.wait(timeout=10.0):
            _log.warning("RemoteWsServer: Timeout beim Warten auf Server-Start")

    def stop(self) -> None:
        """Fährt den WebSocket-Server sauber herunter."""
        self._stop_event.set()

        # Thread joinieren — der asyncio-Loop beendet sich selbst via Polling des stop_event
        if self._thread is not None:
            thread = self._thread
            self._thread = None
            thread.join(timeout=5.0)
            if thread.is_alive():
                _log.warning(
                    "RemoteWsServer: Thread hat nach 5 s Timeout nicht beendet — "
                    "möglicher Orphan-Thread."
                )

        self._loop = None
        self._ws_server = None
        self._bound_port = None
        _log.info("RemoteWsServer gestoppt.")

    # -------------------------------------------------------------------------
    # Push-Hooks (für Task 5b und externe Aufrufer)
    # -------------------------------------------------------------------------

    def push_transcript_chunk(
        self,
        text: str,
        is_final: bool,
        t_start: float,
        engine: str,
    ) -> None:
        """Sendet ein transcript_chunk an alle verbundenen Clients.

        Thread-safe: delegiert an den asyncio-Loop.

        Args:
            text:     Transkribierter Text.
            is_final: True = endgültiges Ergebnis.
            t_start:  Startzeit in Sekunden (relativ zur Aufnahme).
            engine:   Name der STT-Engine (z. B. 'whisper').
        """
        msg = json.dumps({
            "type": "transcript_chunk",
            "text": text,
            "is_final": is_final,
            "t_start": t_start,
            "engine": engine,
        }, ensure_ascii=False)
        self._broadcast_threadsafe(msg)

    # -------------------------------------------------------------------------
    # Internes — asyncio-Loop im Thread
    # -------------------------------------------------------------------------

    def _run_loop(self, host: str, port: int) -> None:
        """Startet und betreibt den asyncio-Loop im eigenen Thread."""
        loop = asyncio.new_event_loop()
        asyncio.set_event_loop(loop)
        self._loop = loop
        self._clients: Set = set()
        self._clients_lock = asyncio.Lock()

        try:
            loop.run_until_complete(self._serve(host, port))
        except Exception as exc:
            _log.debug("RemoteWsServer: Loop beendet: %s", exc)
        finally:
            # Verbleibende Tasks abbrechen und sauber finalisieren
            try:
                pending = asyncio.all_tasks(loop)
                for task in pending:
                    task.cancel()
                if pending:
                    loop.run_until_complete(
                        asyncio.gather(*pending, return_exceptions=True)
                    )
            except Exception:
                pass
            try:
                loop.close()
            except Exception:
                pass
            _log.debug("RemoteWsServer: asyncio-Loop geschlossen.")

    async def _serve(self, host: str, port: int) -> None:
        """Startet websockets-Server und periodischen state_update-Task."""
        try:
            import websockets.asyncio.server as ws_server_mod
        except ImportError:
            import websockets.server as ws_server_mod  # type: ignore[no-redef]

        async with ws_server_mod.serve(self._handle_client, host, port) as server:
            self._ws_server = server
            # Tatsächlichen Port ermitteln
            sockets = list(server.sockets)
            if sockets:
                self._bound_port = sockets[0].getsockname()[1]
            else:
                self._bound_port = port
            self._port_ready.set()
            _log.info(
                "RemoteWsServer gestartet auf ws://%s:%d", host, self._bound_port
            )

            # Periodischen state_update-Task starten
            push_task = asyncio.ensure_future(self._push_state_updates())
            try:
                # Polling bis stop() aufgerufen wird (kein run_in_executor — vermeidet
                # "Event loop stopped before Future completed"-Fehler beim Herunterfahren)
                while not self._stop_event.is_set():
                    await asyncio.sleep(0.05)
            finally:
                push_task.cancel()
                try:
                    await push_task
                except (asyncio.CancelledError, Exception):
                    pass

    async def _handle_client(self, websocket) -> None:
        """Verarbeitet eine einzelne WebSocket-Verbindung."""
        async with self._clients_lock:
            self._clients.add(websocket)
        _log.debug("RemoteWsServer: Client verbunden (%d total)", len(self._clients))

        try:
            async for raw_msg in websocket:
                if isinstance(raw_msg, bytes):
                    raw_msg = raw_msg.decode("utf-8")
                await self._handle_message(websocket, raw_msg)
        except Exception as exc:
            # ConnectionClosed und andere Verbindungsfehler — kein Absturz
            _log.debug("RemoteWsServer: Client-Verbindung getrennt: %s", exc)
        finally:
            async with self._clients_lock:
                self._clients.discard(websocket)
            _log.debug("RemoteWsServer: Client entfernt (%d total)", len(self._clients))

    async def _handle_message(self, websocket, raw_msg: str) -> None:
        """Verarbeitet eine eingehende Nachricht vom Companion."""
        try:
            msg = json.loads(raw_msg)
        except json.JSONDecodeError:
            _log.warning("RemoteWsServer: Ungültige JSON-Nachricht empfangen.")
            return

        msg_type = msg.get("type")

        if msg_type == "trigger_pad":
            pad_id = msg.get("pad_id", "")
            if self._board_player is not None and pad_id:
                try:
                    self._board_player.trigger(pad_id)
                    _log.debug("RemoteWsServer: trigger_pad '%s'", pad_id)
                except Exception as exc:
                    _log.warning("RemoteWsServer: trigger_pad Fehler: %s", exc)

        elif msg_type == "toggle_mute":
            source_id = msg.get("source_id", "")
            self._toggle_mute(source_id)

        elif msg_type == "insert_chapter_marker":
            label = msg.get("label", "")
            _log.info("RemoteWsServer: Kapitelmarker gesetzt (label=%r)", label)
            if self._on_chapter_marker is not None:
                try:
                    self._on_chapter_marker(label)
                except Exception as exc:
                    _log.warning("RemoteWsServer: on_chapter_marker Fehler: %s", exc)

        elif msg_type == "scroll_teleprompter":
            delta = msg.get("delta", 0)
            _log.debug("RemoteWsServer: scroll_teleprompter delta=%d", delta)
            if self._on_scroll_teleprompter is not None:
                try:
                    self._on_scroll_teleprompter(delta)
                except Exception as exc:
                    _log.warning("RemoteWsServer: on_scroll_teleprompter Fehler: %s", exc)

        else:
            _log.warning("RemoteWsServer: Unbekannter Nachrichtentyp: %r", msg_type)

    def _toggle_mute(self, source_id: str) -> None:
        """Schaltet den Mute-Status eines Kanals in der Engine um."""
        if self._engine is None or not source_id:
            return
        try:
            channels = getattr(self._engine, "_channels", [])
            for kanal in channels:
                if kanal.source_id == source_id:
                    kanal.mute = not kanal.mute
                    _log.debug(
                        "RemoteWsServer: toggle_mute '%s' → mute=%s",
                        source_id, kanal.mute,
                    )
                    return
            _log.warning("RemoteWsServer: toggle_mute — Kanal '%s' nicht gefunden.", source_id)
        except Exception as exc:
            _log.warning("RemoteWsServer: toggle_mute Fehler: %s", exc)

    async def _push_state_updates(self) -> None:
        """Sendet periodisch state_update an alle verbundenen Clients."""
        while not self._stop_event.is_set():
            try:
                await asyncio.sleep(self._state_update_interval)
                if not self._clients:
                    continue
                msg = self._baue_state_update()
                await self._broadcast(msg)
            except asyncio.CancelledError:
                break
            except Exception as exc:
                _log.debug("RemoteWsServer: _push_state_updates Fehler: %s", exc)

    def _baue_state_update(self) -> str:
        """Baut die state_update-Nachricht als JSON-String."""
        channel_peaks: list = []
        if self._engine is not None:
            try:
                channel_peaks = list(self._engine.latest_peaks())
            except Exception:
                channel_peaks = []

        recording = False
        if self._state is not None:
            try:
                recording = bool(self._state.recording)
            except Exception:
                recording = False

        active_pad_ids: list = []
        if self._board_player is not None:
            try:
                active_pad_ids = list(self._board_player.active_pad_ids())
            except Exception:
                active_pad_ids = []

        return json.dumps({
            "type": "state_update",
            "channel_peaks": channel_peaks,
            "recording": recording,
            "active_pad_ids": active_pad_ids,
            "prompter_line": 0,
        }, ensure_ascii=False)

    async def _broadcast(self, msg: str) -> None:
        """Sendet eine Nachricht an alle verbundenen Clients (async)."""
        async with self._clients_lock:
            clients = set(self._clients)

        if not clients:
            return

        import websockets.exceptions

        for ws in clients:
            try:
                await ws.send(msg)
            except websockets.exceptions.ConnectionClosed:
                # Client hat die Verbindung getrennt — still ignorieren
                pass
            except Exception as exc:
                _log.debug("RemoteWsServer: Broadcast-Fehler: %s", exc)

    def _broadcast_threadsafe(self, msg: str) -> None:
        """Thread-safe Variante von _broadcast (für push_transcript_chunk)."""
        if self._loop is None or self._loop.is_closed():
            return
        asyncio.run_coroutine_threadsafe(self._broadcast(msg), self._loop)

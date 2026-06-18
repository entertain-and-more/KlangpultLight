"""bridge.bridge_service — BridgeService bündelt LibraryApiServer + RemoteWsServer.

Wird von main.py optional gestartet (Env PODCAST_RECORDER_BRIDGE=1 oder Standard an).
Sauberes Herunterfahren beim App-Ende.
"""
from __future__ import annotations

import logging
import os
from typing import Optional

from bridge.library_api import LibraryApiServer
from bridge.remote_ws import RemoteWsServer

_log = logging.getLogger(__name__)

# Standard-Ports
_LIBRARY_PORT = 8767
_WS_PORT = 8768


class BridgeService:
    """Bündelt LibraryApiServer und RemoteWsServer zu einem einzelnen Dienst.

    Args:
        library:      RecordingLibrary-Instanz.
        engine:       AudioEngine-Instanz.
        state:        AppState-Instanz.
        board_player: BoardPlayer-Instanz.
        library_port: HTTP-Port (Standard: 8767; 0 = Betriebssystem wählt).
        ws_port:      WebSocket-Port (Standard: 8768; 0 = Betriebssystem wählt).
        host:         Bind-Adresse (Standard: 127.0.0.1).
    """

    def __init__(
        self,
        library=None,
        engine=None,
        state=None,
        board_player=None,
        library_port: int = _LIBRARY_PORT,
        ws_port: int = _WS_PORT,
        host: str = "127.0.0.1",
    ) -> None:
        self._library = library
        self._engine = engine
        self._state = state
        self._board_player = board_player
        self._library_port = library_port
        self._ws_port = ws_port
        self._host = host

        self._api: Optional[LibraryApiServer] = None
        self._ws: Optional[RemoteWsServer] = None
        self._gestartet = False

    # -------------------------------------------------------------------------
    # Lifecycle
    # -------------------------------------------------------------------------

    def start(self) -> None:
        """Startet beide Dienste."""
        if self._gestartet:
            return

        self._api = LibraryApiServer(library=self._library)
        self._api.start(host=self._host, port=self._library_port)

        self._ws = RemoteWsServer(
            engine=self._engine,
            state=self._state,
            board_player=self._board_player,
            library=self._library,
        )
        self._ws.start(host=self._host, port=self._ws_port)

        self._gestartet = True
        _log.info(
            "BridgeService gestartet (Library-API Port %s, WebSocket Port %s)",
            self._api.port,
            self._ws.port,
        )

    def stop(self) -> None:
        """Fährt beide Dienste sauber herunter."""
        if not self._gestartet:
            return

        if self._ws is not None:
            self._ws.stop()
            self._ws = None

        if self._api is not None:
            self._api.stop()
            self._api = None

        self._gestartet = False
        _log.info("BridgeService gestoppt.")

    @property
    def api(self) -> Optional[LibraryApiServer]:
        """Zugriff auf den LibraryApiServer (für Port-Abfrage in Tests)."""
        return self._api

    @property
    def ws(self) -> Optional[RemoteWsServer]:
        """Zugriff auf den RemoteWsServer (für Port-Abfrage in Tests)."""
        return self._ws

    # -------------------------------------------------------------------------
    # Klassenmethode: aus Env-Variable starten
    # -------------------------------------------------------------------------

    @classmethod
    def soll_starten(cls) -> bool:
        """Gibt zurück, ob der BridgeService laut Env-Variable gestartet werden soll.

        Standard: an (PODCAST_RECORDER_BRIDGE nicht gesetzt oder "1").
        Deaktivieren: PODCAST_RECORDER_BRIDGE=0.
        """
        wert = os.environ.get("PODCAST_RECORDER_BRIDGE", "1").strip()
        return wert != "0"

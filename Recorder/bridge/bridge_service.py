"""bridge.bridge_service — BridgeService bündelt LibraryApiServer, RemoteWsServer
und ProjectsApiServer.

Wird von main.py optional gestartet (Env PODCAST_RECORDER_BRIDGE=1 oder Standard an).
Sauberes Herunterfahren beim App-Ende.
"""
from __future__ import annotations

import logging
import os
from typing import Optional

from bridge.library_api import LibraryApiServer
from bridge.projects_api import ProjectsApiServer
from bridge.remote_ws import RemoteWsServer

_log = logging.getLogger(__name__)

# Standard-Ports
_LIBRARY_PORT = 8767
_WS_PORT = 8768
_PROJECTS_PORT = 8769


class BridgeService:
    """Bündelt LibraryApiServer, RemoteWsServer und ProjectsApiServer.

    Args:
        library:       RecordingLibrary-Instanz.
        engine:        AudioEngine-Instanz.
        state:         AppState-Instanz.
        board_player:  BoardPlayer-Instanz.
        library_port:  HTTP-Port für Bibliothek-API (Standard: 8767; 0 = OS wählt).
        ws_port:       WebSocket-Port (Standard: 8768; 0 = OS wählt).
        projects_port: HTTP-Port für Projektplanung-API (Standard: 8769; 0 = OS wählt).
        projects_data_dir: Verzeichnis für Projektdaten (Standard: workspace/projects).
        host:          Bind-Adresse (Standard: 127.0.0.1).
    """

    def __init__(
        self,
        library=None,
        engine=None,
        state=None,
        board_player=None,
        library_port: int = _LIBRARY_PORT,
        ws_port: int = _WS_PORT,
        projects_port: int = _PROJECTS_PORT,
        projects_data_dir: str = "./workspace/projects",
        host: str = "127.0.0.1",
    ) -> None:
        self._library = library
        self._engine = engine
        self._state = state
        self._board_player = board_player
        self._library_port = library_port
        self._ws_port = ws_port
        self._projects_port = projects_port
        self._projects_data_dir = projects_data_dir
        self._host = host

        self._api: Optional[LibraryApiServer] = None
        self._ws: Optional[RemoteWsServer] = None
        self._projects: Optional[ProjectsApiServer] = None
        self._gestartet = False

    # -------------------------------------------------------------------------
    # Lifecycle
    # -------------------------------------------------------------------------

    def start(self) -> None:
        """Startet alle drei Dienste.

        Wenn einer der Dienste beim Start eine Exception wirft, werden bereits
        gestartete Dienste sauber heruntergefahren (kein Ressourcenleck bei
        partiellem Start).
        """
        if self._gestartet:
            return

        try:
            self._api = LibraryApiServer(library=self._library)
            self._api.start(host=self._host, port=self._library_port)

            self._ws = RemoteWsServer(
                engine=self._engine,
                state=self._state,
                board_player=self._board_player,
                library=self._library,
            )
            self._ws.start(host=self._host, port=self._ws_port)

            self._projects = ProjectsApiServer(data_dir=self._projects_data_dir)
            self._projects.start(host=self._host, port=self._projects_port)

        except Exception:
            # Partiellen Start aufräumen: bereits gestartete Dienste stoppen
            for dienst in [self._projects, self._ws, self._api]:
                if dienst is not None:
                    try:
                        dienst.stop()
                    except Exception:
                        pass
            self._api = None
            self._ws = None
            self._projects = None
            raise

        self._gestartet = True
        _log.info(
            "BridgeService gestartet (Library-API Port %s, WebSocket Port %s,"
            " Projects-API Port %s)",
            self._api.port,
            self._ws.port,
            self._projects.port,
        )

    def stop(self) -> None:
        """Fährt alle Dienste sauber herunter."""
        if not self._gestartet:
            return

        if self._projects is not None:
            self._projects.stop()
            self._projects = None

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

    @property
    def projects(self) -> Optional[ProjectsApiServer]:
        """Zugriff auf den ProjectsApiServer (für Port-Abfrage in Tests)."""
        return self._projects

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

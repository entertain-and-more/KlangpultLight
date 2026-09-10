"""bridge.bridge_service — BridgeService bündelt LibraryApiServer, RemoteWsServer
und ProjectsApiServer.

Wird von main.py optional gestartet (Env PODCAST_RECORDER_BRIDGE=1 oder Standard an).
Sauberes Herunterfahren beim App-Ende.
"""
from __future__ import annotations

import logging
import os
import sys
from pathlib import Path
from typing import Optional

from bridge.library_api import LibraryApiServer
from bridge.projects_api import ProjectsApiServer
from bridge.remote_ws import RemoteWsServer

_log = logging.getLogger(__name__)

# Standard-Ports
_LIBRARY_PORT = 8767
_WS_PORT = 8768
_PROJECTS_PORT = 8769
_PLANER_PORT = 8770


def _get_planer_server_cls():
    """Importiert PlanerServer dynamisch, ohne feste Pfadabhängigkeit."""
    try:
        from planer_server import PlanerServer  # type: ignore
        return PlanerServer
    except ImportError:
        pass

    base = Path(__file__).resolve().parent.parent.parent
    cand = base / "planer" / "server"
    if cand.is_dir() and str(cand) not in sys.path:
        sys.path.insert(0, str(cand))
        try:
            from planer_server import PlanerServer  # type: ignore
            return PlanerServer
        except ImportError:
            pass
    return None


class BridgeService:
    """Bündelt LibraryApiServer, RemoteWsServer, ProjectsApiServer und PlanerServer.

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
        planer_port:   HTTP-Port für den Planer-Webserver (Optional; None = nicht starten, 8770 / 0).
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
        planer_port: Optional[int] = None,
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
        self._planer_port = planer_port

        self._api: Optional[LibraryApiServer] = None
        self._ws: Optional[RemoteWsServer] = None
        self._projects: Optional[ProjectsApiServer] = None
        self._planer: Optional[object] = None
        self._gestartet = False

    # -------------------------------------------------------------------------
    # Lifecycle
    # -------------------------------------------------------------------------

    def start(self) -> None:
        """Startet die Dienste (Library, WS, Projects und optional Planer).

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

            if self._planer_port is not None:
                planer_cls = _get_planer_server_cls()
                if planer_cls is not None:
                    try:
                        srv = planer_cls(
                            library_port=self._api.port,
                            projects_port=self._projects.port,
                        )
                        srv.start(host=self._host, port=self._planer_port)
                        self._planer = srv
                    except OSError as err:
                        _log.warning(
                            "PlanerServer konnte auf Port %s nicht gebunden werden: %s "
                            "(läuft vermutlich bereits extern)",
                            self._planer_port,
                            err,
                        )
                        self._planer = None

        except Exception:
            # Partiellen Start aufräumen: bereits gestartete Dienste stoppen
            for dienst in [self._planer, self._projects, self._ws, self._api]:
                if dienst is not None:
                    try:
                        dienst.stop()
                    except Exception:
                        pass
            self._api = None
            self._ws = None
            self._projects = None
            self._planer = None
            raise

        self._gestartet = True
        planer_msg = f", Planer-Server Port {self._planer.port}" if self._planer else ""
        _log.info(
            "BridgeService gestartet (Library-API Port %s, WebSocket Port %s,"
            " Projects-API Port %s%s)",
            self._api.port,
            self._ws.port,
            self._projects.port,
            planer_msg,
        )

    def stop(self) -> None:
        """Fährt alle Dienste sauber herunter."""
        if not self._gestartet:
            return

        if self._planer is not None:
            try:
                self._planer.stop()
            except Exception:
                pass
            self._planer = None

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

    @property
    def planer(self) -> Optional[object]:
        """Zugriff auf den PlanerServer (für Port-Abfrage in Tests und UI)."""
        return self._planer

    @property
    def planer_port(self) -> Optional[int]:
        """Tatsächlich gebundener Planer-Port oder None."""
        if self._planer is not None and hasattr(self._planer, "port"):
            return self._planer.port
        return None

    # -------------------------------------------------------------------------
    # Klassenmethoden: aus Env-Variable starten
    # -------------------------------------------------------------------------

    @classmethod
    def soll_starten(cls) -> bool:
        """Gibt zurück, ob der BridgeService laut Env-Variable gestartet werden soll.

        Standard: an (PODCAST_RECORDER_BRIDGE nicht gesetzt oder "1").
        Deaktivieren: PODCAST_RECORDER_BRIDGE=0.
        """
        wert = os.environ.get("PODCAST_RECORDER_BRIDGE", "1").strip()
        return wert != "0"

    @classmethod
    def soll_planer_starten(cls) -> bool:
        """Gibt zurück, ob der integrierte PlanerServer gestartet werden soll.

        Standard: an (PODCAST_RECORDER_PLANER nicht gesetzt oder "1").
        Deaktivieren: PODCAST_RECORDER_PLANER=0.
        """
        wert = os.environ.get("PODCAST_RECORDER_PLANER", "1").strip()
        return wert != "0"


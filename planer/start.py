"""planer/start.py — Startet den Klangpult light – Planer-Webserver.

Öffnet http://127.0.0.1:8770 im Standard-Browser und wartet auf Ctrl+C.

Verwendung:
    python planer/start.py

Umgebungsvariablen:
    PLANER_HOST       Bind-Adresse (Standard: 127.0.0.1; Opt-in z. B. 192.168.x.x für Tablet-Companion)
    PLANER_PORT       Port für den Planer-Server (Standard: 8770)
    LIBRARY_PORT      Port des LibraryApiServers  (Standard: 8767)
    PROJECTS_PORT     Port des ProjectsApiServers (Standard: 8769)
    PLANER_NO_BROWSER Wenn gesetzt: Browser nicht automatisch öffnen
"""
from __future__ import annotations

import logging
import os
import sys
import threading
import webbrowser
from pathlib import Path

# Sicherstellen, dass planer/server/ im Suchpfad liegt
_here = Path(__file__).parent
sys.path.insert(0, str(_here / "server"))

from planer_server import PlanerServer  # noqa: E402


def main() -> None:
    logging.basicConfig(
        level=logging.INFO,
        format="%(asctime)s %(levelname)s %(name)s: %(message)s",
        datefmt="%H:%M:%S",
    )

    host = os.environ.get("PLANER_HOST", "127.0.0.1").strip() or "127.0.0.1"
    port = int(os.environ.get("PLANER_PORT", "8770"))
    library_port = int(os.environ.get("LIBRARY_PORT", "8767"))
    projects_port = int(os.environ.get("PROJECTS_PORT", "8769"))

    srv = PlanerServer(library_port=library_port, projects_port=projects_port)
    srv.start(host=host, port=port)

    browser_host = "127.0.0.1" if host in ("0.0.0.0", "::") else host
    url = f"http://{browser_host}:{srv.port}"
    print(f"\nKlangpult light – Planer läuft auf {url} (gebunden an {host}:{srv.port})")
    print("Stoppen mit Ctrl+C\n")

    if not os.environ.get("PLANER_NO_BROWSER"):
        webbrowser.open(url)

    try:
        threading.Event().wait()
    except KeyboardInterrupt:
        print("\nBeende Klangpult light – Planer…")
        srv.stop()


if __name__ == "__main__":
    main()

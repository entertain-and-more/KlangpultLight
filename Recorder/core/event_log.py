"""core.event_log — JSON-Lines-Ereignisprotokoll.

Schreibt jeden Event als eine Zeile valides JSON (UTF-8, kein BOM).
Geeignet für Debugging, Audits und spätere Analyse.
"""
import json
import os
from datetime import datetime
from typing import Any


class EventLog:
    """Schreibt Ereignisse als JSON-Lines in eine Datei.

    Jede Zeile hat mindestens die Felder:
        ``t``    — ISO-8601-Zeitstempel des Ereignisses
        ``type`` — Ereignistyp (frei wählbarer String)
        ...      — beliebige weitere Schlüsselwortargumente

    Das Verzeichnis wird bei Bedarf automatisch angelegt.
    """

    def __init__(self, path: str) -> None:
        """Öffnet die Logdatei zum Anhängen (append).

        Args:
            path: Dateipfad der JSONL-Datei. Verzeichnis wird angelegt.
        """
        verzeichnis = os.path.dirname(path)
        if verzeichnis:
            os.makedirs(verzeichnis, exist_ok=True)

        # UTF-8 ohne BOM, Zeilenweise puffern
        self._datei = open(path, "a", encoding="utf-8", buffering=1)

    def log(self, event_type: str, **felder: Any) -> None:
        """Schreibt einen Event als JSON-Zeile.

        Args:
            event_type: Bezeichner des Ereignisses.
            **felder: Beliebige zusätzliche Schlüssel-Wert-Paare.
        """
        eintrag: dict[str, Any] = {
            "t": datetime.now().isoformat(),
            "type": event_type,
            **felder,
        }
        # ensure_ascii=False → echte Umlaute statt \uXXXX-Escapes
        zeile = json.dumps(eintrag, ensure_ascii=False)
        self._datei.write(zeile + "\n")

    def close(self) -> None:
        """Schließt die Logdatei und flusht ausstehende Puffer."""
        self._datei.flush()
        self._datei.close()

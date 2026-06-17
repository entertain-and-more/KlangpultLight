"""recordings.recording_session — Koordiniert Library, AudioEngine und EventLog.

Kein GUI-Import. Verbindet Aufnahme-Verwaltung mit der Audio-Engine.
"""
import os
from typing import Optional

from core.app_state import AppState
from core.event_log import EventLog
from recordings.library import RecordingLibrary
from recordings.models import RecordingMetadata


class RecordingSession:
    """Koordiniert RecordingLibrary, AudioEngine und EventLog.

    Verwaltet genau eine aktive Aufnahme pro Session-Instanz.
    Die AudioEngine muss bereits gestartet (engine.start() aufgerufen) sein,
    bevor start() aufgerufen wird — sonst werden keine Audio-Frames geschrieben
    und duration=0.
    """

    def __init__(
        self,
        library: RecordingLibrary,
        engine,  # AudioEngine (kein direkter Import → vermeidet zirkuläre Abhängigkeit)
        state: Optional[AppState] = None,
    ) -> None:
        """Initialisiert die RecordingSession.

        Args:
            library: RecordingLibrary für Metadaten-Verwaltung.
            engine: AudioEngine-Instanz (muss bereits gestartet sein).
            state: Optionaler AppState für Zustandssynchronisation.
        """
        self._library = library
        self._engine = engine
        self._state = state
        self._aktuelle_meta: Optional[RecordingMetadata] = None
        self._event_log: Optional[EventLog] = None

    def start(self, title: str) -> RecordingMetadata:
        """Startet eine neue Aufnahme.

        Legt die Aufnahme in der Library an, startet engine.start_recording()
        und protokolliert das start-Event.

        Args:
            title: Titel der Aufnahme.

        Returns:
            RecordingMetadata der gestarteten Aufnahme.

        Raises:
            RuntimeError: Wenn bereits eine Aufnahme läuft.
        """
        if self._aktuelle_meta is not None:
            raise RuntimeError("Aufnahme läuft bereits — zuerst stop() aufrufen.")

        meta = self._library.create_recording(title)
        self._aktuelle_meta = meta

        # EventLog im Aufnahme-Ordner öffnen
        events_pfad = os.path.join(
            self._library.recording_dir(meta.recording_id), "events.jsonl"
        )
        self._event_log = EventLog(events_pfad)

        # Audio-Aufnahme in main/-Unterordner starten
        main_dir = os.path.join(
            self._library.recording_dir(meta.recording_id), "main"
        )
        self._engine.start_recording(main_dir)

        # AppState aktualisieren
        if self._state is not None:
            self._state.recording = True

        self._event_log.log("start", title=title, recording_id=meta.recording_id)
        return meta

    def stop(self) -> RecordingMetadata:
        """Beendet die laufende Aufnahme.

        Ruft engine.stop_recording() auf, schreibt Dauer und Audio-Pfad
        in den Original-Branch, persistiert die Metadaten und protokolliert stop.

        Returns:
            Aktualisierte RecordingMetadata.

        Raises:
            RuntimeError: Wenn keine Aufnahme läuft.
        """
        if self._aktuelle_meta is None:
            raise RuntimeError("Keine Aufnahme aktiv — zuerst start() aufrufen.")

        ergebnis = self._engine.stop_recording()
        dauer = float(ergebnis.get("duration", 0.0))
        mix_pfad = ergebnis.get("mix", "")

        # Original-Branch mit Ergebnis aktualisieren
        meta = self._aktuelle_meta
        for branch in meta.branches:
            if branch.is_original:
                branch.audio_path = mix_pfad
                branch.duration = dauer
                break

        meta.duration = dauer
        self._library.update_metadata(meta)

        # AppState aktualisieren
        if self._state is not None:
            self._state.recording = False

        if self._event_log is not None:
            self._event_log.log(
                "stop",
                recording_id=meta.recording_id,
                duration=dauer,
                mix=mix_pfad,
            )
            self._event_log.close()
            self._event_log = None

        self._aktuelle_meta = None
        return meta

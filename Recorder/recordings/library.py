"""recordings.library — Verwaltung der Aufnahme-Bibliothek.

Kein GUI-Import. Nur stdlib + recordings.models.
"""
import json
import os
import uuid
from datetime import datetime, timezone
from typing import List

from recordings.models import Branch, RecordingMetadata


class RecordingLibrary:
    """Verwaltet Aufnahmen unter <workspace_dir>/recordings/.

    Jede Aufnahme liegt in einem eigenen Unterordner mit eindeutiger ID.
    Originalaufnahmen sind unveränderlich — Bearbeitungen entstehen als Branches.
    """

    def __init__(self, workspace_dir: str) -> None:
        """Initialisiert die Bibliothek.

        Args:
            workspace_dir: Wurzelverzeichnis des Workspace (z. B. './workspace').
                           Aufnahmen landen unter <workspace_dir>/recordings/.
        """
        self._workspace = os.path.abspath(workspace_dir)
        self._recordings_dir = os.path.join(self._workspace, "recordings")
        os.makedirs(self._recordings_dir, exist_ok=True)


    def create_recording(self, title: str) -> RecordingMetadata:
        """Legt eine neue Aufnahme an.

        Erstellt:
          - <recordings_dir>/recording_<YYYYMMDD_HHMMSS>_<uuid4_kurz>/
          - Unterordner main/
          - metadata.json (UTF-8 ohne BOM)
          - events.jsonl (leere Datei, bereit zum Beschreiben)

        Setzt automatisch einen Original-Branch (is_original=True).

        Args:
            title: Titel der Aufnahme.

        Returns:
            RecordingMetadata der neuen Aufnahme.
        """
        jetzt = datetime.now(tz=timezone.utc)
        zeitstempel = jetzt.strftime("%Y%m%d_%H%M%S")
        kurz_id = uuid.uuid4().hex[:8]
        recording_id = f"recording_{zeitstempel}_{kurz_id}"

        aufnahme_ordner = os.path.join(self._recordings_dir, recording_id)
        os.makedirs(aufnahme_ordner, exist_ok=True)
        os.makedirs(os.path.join(aufnahme_ordner, "main"), exist_ok=True)

        # Events-Log anlegen (leer)
        events_pfad = os.path.join(aufnahme_ordner, "events.jsonl")
        with open(events_pfad, "w", encoding="utf-8"):
            pass  # Leere Datei

        # Original-Branch
        original_branch = Branch(
            branch_id=f"branch_{kurz_id}_main",
            recording_id=recording_id,
            name="Original",
            created_at=jetzt.isoformat(),
            audio_path="",
            video_path="",
            duration=0.0,
            is_original=True,
        )

        meta = RecordingMetadata(
            recording_id=recording_id,
            title=title,
            created_at=jetzt.isoformat(),
            duration=0.0,
            sources=[],
            branches=[original_branch],
            tags=[],
            description="",
        )

        self.update_metadata(meta)
        return meta

    def recording_dir(self, recording_id: str) -> str:
        """Gibt den Pfad zum Aufnahme-Ordner zurück.

        Args:
            recording_id: ID der Aufnahme.

        Returns:
            Absoluter Pfad zum Aufnahme-Ordner.

        Raises:
            ValueError: Wenn die recording_id ungültig ist oder Path-Traversal enthält.
        """
        if not isinstance(recording_id, str) or not recording_id.strip():
            raise ValueError("Ungültige recording_id: darf nicht leer sein.")
        bereinigt = recording_id.strip()
        if any(sep in bereinigt for sep in ("/", "\\")) or bereinigt in (".", ".."):
            raise ValueError(
                f"Ungültige recording_id mit Pfadtrennzeichen oder Traversal: '{recording_id}'"
            )
        abs_recordings = os.path.abspath(self._recordings_dir)
        ziel_pfad = os.path.abspath(os.path.join(abs_recordings, bereinigt))
        if os.path.dirname(ziel_pfad) != abs_recordings or os.path.basename(ziel_pfad) != bereinigt:
            raise ValueError(
                f"Ungültige recording_id außerhalb des Zielverzeichnisses: '{recording_id}'"
            )
        return ziel_pfad


    def list_recordings(self) -> List[RecordingMetadata]:
        """Gibt alle gespeicherten Aufnahmen zurück, neueste zuerst.

        Liest alle metadata.json-Dateien aus dem Recordings-Verzeichnis.
        Ungültige oder nicht lesbare Dateien werden übersprungen.

        Returns:
            Liste von RecordingMetadata, sortiert nach created_at (neueste zuerst).
        """
        aufnahmen: list[RecordingMetadata] = []

        if not os.path.isdir(self._recordings_dir):
            return aufnahmen

        for eintrag in os.scandir(self._recordings_dir):
            if not eintrag.is_dir():
                continue
            meta_pfad = os.path.join(eintrag.path, "metadata.json")
            if not os.path.isfile(meta_pfad):
                continue
            try:
                with open(meta_pfad, encoding="utf-8") as f:
                    daten = json.load(f)
                aufnahmen.append(RecordingMetadata.from_dict(daten))
            except (json.JSONDecodeError, KeyError, ValueError):
                continue

        # Neueste zuerst, stabiler Tiebreaker über recording_id
        aufnahmen.sort(
            key=lambda m: (m.created_at, m.recording_id),
            reverse=True,
        )
        return aufnahmen

    def add_branch(self, recording_id: str, name: str) -> Branch:
        """Legt einen neuen Branch unter einer bestehenden Aufnahme an.

        Das Original (is_original=True) bleibt unverändert. Dieser Branch
        ist nur ein Verwaltungseintrag — kein Schnitt, kein EDL.

        Args:
            recording_id: ID der übergeordneten Aufnahme.
            name:         Anzeigename des neuen Branches (nicht leer).

        Returns:
            Neu angelegter Branch.

        Raises:
            ValueError: Wenn die Aufnahme nicht gefunden wird oder der Name leer ist.
        """
        branch_name = (name or "").strip()
        if not branch_name:
            raise ValueError("Branch-Name darf nicht leer sein.")

        aufnahmen = self.list_recordings()
        meta = next((m for m in aufnahmen if m.recording_id == recording_id), None)
        if meta is None:
            raise ValueError(f"Aufnahme '{recording_id}' nicht gefunden.")

        jetzt = datetime.now(tz=timezone.utc)
        kurz_id = uuid.uuid4().hex[:8]
        neuer_branch = Branch(
            branch_id=f"branch_{kurz_id}",
            recording_id=recording_id,
            name=branch_name,
            created_at=jetzt.isoformat(),
            audio_path="",
            video_path="",
            duration=0.0,
            is_original=False,
        )
        meta.branches.append(neuer_branch)
        self.update_metadata(meta)
        return neuer_branch

    def rename_recording(self, recording_id: str, new_title: str) -> RecordingMetadata:
        """Benennt eine Aufnahme nachträglich um (nur der Anzeige-Titel).

        Der Ordnername/die ID bleibt unverändert (stabile Referenzen). Nur das
        ``title``-Feld in metadata.json wird neu geschrieben.

        Args:
            recording_id: ID der Aufnahme.
            new_title:    Neuer Anzeigename (nicht leer).

        Returns:
            Aktualisierte RecordingMetadata.

        Raises:
            ValueError: Wenn die Aufnahme fehlt oder der Titel leer ist.
        """
        titel = (new_title or "").strip()
        if not titel:
            raise ValueError("Neuer Titel darf nicht leer sein.")
        aufnahmen = self.list_recordings()
        meta = next((m for m in aufnahmen if m.recording_id == recording_id), None)
        if meta is None:
            raise ValueError(f"Aufnahme '{recording_id}' nicht gefunden.")
        meta.title = titel
        self.update_metadata(meta)
        return meta

    def delete_recording(self, recording_id: str) -> None:
        """Löscht eine Aufnahme samt Ordner (Audio/Video/Metadaten) endgültig.

        Args:
            recording_id: ID der zu löschenden Aufnahme.

        Raises:
            ValueError: Wenn die Aufnahme nicht existiert oder ungültig ist.
        """
        import shutil
        import time

        ordner = self.recording_dir(recording_id)
        if not os.path.isdir(ordner):
            raise ValueError(f"Aufnahme '{recording_id}' nicht gefunden.")
        # Verifizieren, dass es sich um einen validen Aufnahmeordner mit metadata.json handelt
        meta_pfad = os.path.join(ordner, "metadata.json")
        if not os.path.isfile(meta_pfad):
            raise ValueError(f"Aufnahme '{recording_id}' nicht gefunden.")
        # OneDrive-/Windows-Lock: kurzer Retry, falls eine Datei noch gehalten wird.
        for versuch in range(3):
            try:
                shutil.rmtree(ordner)
                return
            except OSError:
                if versuch == 2:
                    raise
                time.sleep(0.3)


    def update_metadata(self, meta: RecordingMetadata) -> None:
        """Schreibt die Metadaten einer Aufnahme neu (atomic via Temp-Datei + Rename).

        Schreibt zunächst in eine temporäre Datei neben metadata.json, dann
        per ``os.replace()`` atomar umbenannt. Dadurch bleibt die bestehende
        Datei bei einem vorzeitigen Absturz unverändert (kein truncated JSON).

        Args:
            meta: Zu speichernde Metadaten.
        """
        aufnahme_ordner = self.recording_dir(meta.recording_id)
        os.makedirs(aufnahme_ordner, exist_ok=True)

        meta_pfad = os.path.join(aufnahme_ordner, "metadata.json")
        tmp_pfad = meta_pfad + ".tmp"
        with open(tmp_pfad, "w", encoding="utf-8") as f:
            json.dump(meta.to_dict(), f, indent=2, ensure_ascii=False)
            f.flush()
            os.fsync(f.fileno())
        os.replace(tmp_pfad, meta_pfad)

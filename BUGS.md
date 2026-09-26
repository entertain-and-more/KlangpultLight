# BUGS — Klangpult light (Recorder + Planer)

Offene/zurückgestellte Bugs. Behobene siehe Git-Historie.
Angelegt: 2026-06-22.

---

## Behoben (2026-06-22) — zur Referenz

- **[FIXED] Kombinierter Start (`START.bat`) startete den Recorder nicht.** Die
  Hintergrund-Launch-Zeile nutzte verschachtelte Quotes
  (`cmd /C "call ""%~dp0Recorder\START.bat"""`) → der Aufruf brach, der Recorder
  fiel auf **System-Python + falschen Pfad** (`Klangpult light\main.py` statt
  `Recorder\main.py`) zurück; nur der Planer lief (Proxy-Fehler zu 8767/8769).
  Fix: `start "Klangpult light - Recorder" /D "%~dp0Recorder" cmd /C START.bat`.
- **[FIXED] Recorder-Startfix:** Kamera-`obsensor`-Probing blockierte den GUI-Start
  („schwarze Konsole"). Fix: DSHOW-Backend (`video/video_source.py`), cv2-Log
  SILENT + `max_index` 5→3 (`video/video_manager.py`).
- **[FIXED] Audio-Härtung:** Callback-`status` (Overflow) + deque-Überlauf werden
  jetzt geloggt (`audio/engine.py`). Hauptbug der Schwestersoftware (GUI-Thread-
  Drain) war hier NICHT vorhanden — der Recorder nutzt bereits einen dedizierten
  MixWorker-Thread.
- **[FIXED] Recorder-Aufnahmemodi und Audioquellenauswahl (2026-06-29):**
  Audioquellen sind im Quellenpanel auswählbar und wirken sofort auf die Engine.
  Der Recorder kann jetzt `Ton + Video`, `Nur Ton` oder `Nur Video` starten.
  Video-only erzeugt `program.mp4` ohne Audio-WAV-Dummy.
- **[FIXED] WAV-Write hielt den Aufnahmezustandslock während des Disk-Writes
  (2026-07-14):** `AudioEngine._mix_one_tick()` führte `WavRecorder.write()`
  unter `_aufnahme_lock` aus; bei langsamer Platte blockierte damit unnötig der
  gesamte Aufnahmezustand. Fix: Recorder-I/O läuft jetzt unter separatem
  `_recorder_io_lock`, laufende Schreibvorgänge werden vor `stop_recording()`
  über eine Pending-Write-Koordination sauber ausgeräumt. Regression:
  `Recorder/tests/test_mix_loop.py::test_wav_write_laueft_nicht_unter_aufnahme_lock`.

- **[FIXED] Video FFmpeg-stdin-Write entkoppelt & Bounded Queue (2026-08-03):**
  `Recorder/video/video_recorder.py` entkoppelt den Capture-Thread vom FFmpeg-stdin-Write
  über `_writer_queue` (maxsize=writer_queue_size) und einen dedizierten `_writer_loop`-Thread.
  Rückstau führt zu kontrollierten Frame-Drops mit Zähler (`frames_dropped`) und Diagnostik.
  Shutdown über `_request_writer_stop()` schließt stdin kontrolliert.
  Regressionstests: `Recorder/tests/test_video_recorder.py::test_video_recorder_verwirft_frames_bei_writer_rueckstau`
  und `test_video_recorder_beendet_blockierten_writer_kontrolliert`.
- **[FIXED] Planer Accessibility & ARIA Follow-up (2026-08-03):**
  `planer/app/projekte.js`, `planer/app/bibliothek.js` und `planer/app/util.js` um
  Tastatursemantik (`tabIndex=0`, `role="button"`, `aria-selected`, Enter/Space Keydown),
  ARIA-Namen (`aria-label`), Fokus-Falle für Modal-Dialoge und Ersetzung des nativen
  `window.confirm` durch ein zugängliches Confirmation-Modal erweitert.
  Regressionstest: `Recorder/tests/test_planer_a11y.py`.
- **[FIXED] Path-Traversal-Schutz und Aufnahme-Validierung in RecordingLibrary (2026-09-06):**
  `Recorder/recordings/library.py` prüfte in `recording_dir()` und `delete_recording()`
  keine relativen Pfadelemente (`..`, `.`), Pfadtrennzeichen (`/`, `\\`) oder ungültige
  IDs ab. Dadurch konnte `delete_recording("..")` über `shutil.rmtree()` den gesamten
  übergeordneten Workspace samt Projekten und Einstellungen unwiderruflich löschen,
  und Ordner ohne `metadata.json` konnten versehentlich entfernt werden.
  Fix: `__init__()` normalisiert das Basisverzeichnis absolut, `recording_dir()`
  validiert Eingaben strikt gegen Pfadtrenner und Directory Traversal und liefert
  garantiert einen absoluten Pfad. `delete_recording()` prüft vor dem Löschen auf
  Existenz von `metadata.json`. `add_branch()` validiert auf nicht-leere Namen.
  Regressionstests: `Recorder/tests/test_recordings_library.py::TestDeleteRecording::test_loeschen_mit_path_traversal_verhindert`,
  `test_loeschen_ignoriert_ordner_ohne_metadata_json`,
  `TestRecordingDirValidation::test_recording_dir_absoluter_pfad_und_traversal_schutz`,
  `TestAddBranchValidation::test_add_branch_leerer_name_wirft`.

- **[FIXED] Payload-Robustheit, Volume-Normalisierung und Traversal-Schutz in ProjectsApiServer (2026-09-19):**
  `Recorder/bridge/projects_api.py` führte beim Verarbeiten von Assets (`_handle_asset_post`, `_handle_asset_put`)
  sowie beim Workspace-Import (`workspace_importieren`) ungeschützte Casts mit `float(body.get("volume", 1.0))` aus.
  Wurden Payloads mit `volume: null` oder nicht-numerischen Strings übermittelt, stürzte der Server-Thread
  mit ungehandhabten `TypeError` bzw. `ValueError` ab und brach die HTTP-Verbindung ohne Antwort ab (`RemoteDisconnected`).
  Zudem akzeptierte `_lese_body()` beliebige JSON-Roots; bei Arrays (`[]`), Strings oder `null` kam es zu
  `AttributeError: 'list' object has no attribute 'get'` bzw. Socket-Hängern. `_ProjektStore.aufnahme_entfernen()`
  vergaß zudem die Aktualisierung des Zeitstempels `updated_at`.
  Fix: Hilfsfunktion `_safe_volume()` mit Clamping `[0.0, 4.0]` und Fallback auf Defaultwert, Typ-Validierung
  in `_lese_body()` mit sauberem `HTTP 400 Bad Request` bei Nicht-Objekt-Bodies, Zeitstempel-Update in
  `aufnahme_entfernen()` sowie Traversal-Prüfung `_validate_id()` in den internen Pfad-Generatoren.
  Regressionstests: `Recorder/tests/test_projects_api.py::test_asset_post_and_put_volume_robustness`,
  `test_workspace_import_with_null_and_invalid_volume`,
  `test_non_dict_json_body_returns_400_instead_of_crashing`,
  `test_aufnahme_entfernen_aktualisiert_updated_at`.

- **[FIXED] Board-Model Robustheit, Workspace-v1 Validierung und Ducking Release-Lebenszyklus (2026-09-26):**
  `Recorder/board/board_model.py`, `Recorder/board/duck_controller.py`, `Recorder/audio/engine.py` und `Recorder/board/board_player.py`:
  1. `load_board()` stürzte mit ungehandhabtem `AttributeError: 'list' object has no attribute 'get'` ab, wenn die `board.json` kein Root-Dictionary enthielt (z. B. `[]`, `null`, `"str"`). Jetzt Validierung und robuster Fallback auf leeres `Board()`.
  2. `Pad.from_dict()` akzeptierte `volume: None` und nicht-numerische Typen, was im Audio-Feeder-Thread bei `block * float(pad.volume)` zu einem unbehandelten `TypeError` führte. Jetzt Clamping `[0.0, 4.0]` und Fallback auf `1.0`, String-Sanitisierung für `id` und Defaults für ungültige `kind`/`mode`.
  3. `validate_workspace_payload()` akzeptierte `version: True` (bool erbt in Python von int) und validierte Teleprompter-Eigenschaften nicht gegen `shared/workspace_v1.json`. Teleprompter-Validierung (String-Typ, `font_size >= 8`, `scroll_speed >= 0`) und strikte int-Prüfung ergänzt.
  4. `export_workspace_full()` erzeugte bei None/ungültigen Teleprompter-Zahlen `TypeError`/`ValueError` und korrumpierte `text: None` zu `"None"`. Jetzt defensive Normalisierung.
  5. `save_board()` erzeugte bei leerem Pfad verwaiste `.tmp`-Dateien.
  6. Ducking Release-Lebenszyklus: `AudioEngine._mix_one_tick()` deregistrierte den Duck-Controller sofort beim Stop-Signal, wodurch der Pegelsprung schlagartig (Knacken) stattfand statt über die konfigurierte Release-Rampe abzublenden. Mit `duck.is_idle()` bleibt der Controller aktiv, bis die Rampe vollendet ist.
  Regressionstests: `Recorder/tests/test_bugsweep_board_model_and_ducking_20260926.py` (17 Tests).

---

## Offen

### Aktuell keine offenen kritischen P1-P3 Software-Bugs.

## Behobene User-Test-Funktionslücken (2026-06-22 / 2026-08-03)

- **[FIXED P1] Planer:** Episoden editieren UND löschen — Backend (PUT/DELETE) + Frontend.
- **[FIXED P1] Planer:** Projektzuordnung von Aufnahmen — Backend + Frontend-UI.
- **[FIXED P1] Recorder:** Einspieler hinzufügbar — Datei-Dialog → Pad → board.json.
- **[FIXED P1] Recorder:** Aufnahmen in der GUI löschbar, umbenennbar und abspielbar.


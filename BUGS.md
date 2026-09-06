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

---

## Offen

### Aktuell keine offenen kritischen P1-P3 Software-Bugs.

## Behobene User-Test-Funktionslücken (2026-06-22 / 2026-08-03)

- **[FIXED P1] Planer:** Episoden editieren UND löschen — Backend (PUT/DELETE) + Frontend.
- **[FIXED P1] Planer:** Projektzuordnung von Aufnahmen — Backend + Frontend-UI.
- **[FIXED P1] Recorder:** Einspieler hinzufügbar — Datei-Dialog → Pad → board.json.
- **[FIXED P1] Recorder:** Aufnahmen in der GUI löschbar, umbenennbar und abspielbar.


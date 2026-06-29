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

---

## Offen

### P3 — WAV-Write hält das Aufnahme-Lock während des Platten-Writes
- **Datei:** `Recorder/audio/engine.py` (`_mix_one_tick`, `_aufnahme_lock`)
- **Problem:** Die WAV-`write()`-Aufrufe laufen unter `_aufnahme_lock`. Bei einer
  langsamen Platte staut sich der MixWorker → indirekter Druck auf die Eingangs-
  Puffer. Bei lokaler SSD unkritisch; riskant nur, wenn fälschlich nach OneDrive
  aufgenommen würde (Regel: nie nach OneDrive aufnehmen).
- **Fix-Idee:** WAV-Schreiben in einen separaten Writer-Thread mit eigener Queue.

### P3 — Video: FFmpeg-stdin-Write blockiert im Capture-Thread (kein Drop-Logging)
- **Datei:** `Recorder/video/video_recorder.py` (`write_frame` → `stdin.write`)
- **Problem:** Blockierender Pipe-Write im Capture-Thread; wenn der Encoder nicht
  hinterherkommt, gehen reale Kamera-Frames auf Treiber-Ebene verloren — ohne
  sichtbares Drop-Logging.
- **Fix-Idee:** Frame-Drop-Erkennung über Soll-/Ist-Framezahl beim `close()`;
  optional bounded Writer-Queue mit bewusstem Drop-Zähler.

## Offen — aus User-Tests 2026-06-22 (Funktionslücken)

- **[P1] Planer:** Episoden lassen sich nicht (mehr) editieren/löschen (Weboberfläche).
- **[P1] Planer:** Keine Aktion „Aufnahme einem Projekt zuordnen" in der Weboberfläche.
- **[P1] Recorder:** „Einspieler hinzufügen" ist nur ein Stub — fügt nichts hinzu.
- **[P1] Recorder:** Aufnahmen in der GUI nicht löschbar / nicht umbenennbar / nicht abspielbar.
- Details + Feature-Wünsche (einklappbare Bereiche, Symbole, ablösbare Fenster) siehe TODO.md „User-Test-Feedback 2026-06-22".

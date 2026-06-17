# CLAUDE.md — PodcastRecorder (Instructions für AI Coding Agents)

## Projekt

**PodcastRecorder** — schlanke Desktop-App zum Aufnehmen (Audio + Video + gemeinsames
Audio-Videoboard, Aufnahmen mit Branches). Eigenständig, **kein** geteilter Code mit
`DEV_USBPodcastStudio`. Bewährtes aus dem Studio darf als Vorbild dienen (gleiche `sounddevice`-/
FFmpeg-Muster), aber neu und schlanker geschrieben.

**Stack:** Python 3.11+, PySide6 6.x, sounddevice, numpy, soundfile, OpenCV, mss, FFmpeg (subprocess).
**Modul-Layout:** Python-Package `recorder/` (mit `__init__.py`), Start über `python -m recorder.main`.

## Hard Rules

- **IMMER** `PYTHONIOENCODING=utf-8` bei Python-Aufrufen (Windows cp1252!).
- **IMMER** echte Umlaute (ä ö ü Ä Ö Ü ß) in deutschen UI-Texten und Doku.
- **NIEMALS** venv in OneDrive — stets `C:\_Local_DEV\venvs\podcast_packages\`.
- **NIEMALS** Credentials/`.env`/Keys committen.
- **Aufnahmen nie überschreiben** — Original unveränderlich, Branches als Kinder.
- JSON immer UTF-8 ohne BOM.

## Thread-Sicherheit (kritisch)

- Audio-Callbacks (sounddevice) dürfen **NIEMALS** direkt die GUI aufrufen.
- Datenaustausch: `collections.deque` (thread-safe) + `QTimer` im GUI-Thread liest sie.
- Gemeinsamer Zustand über `QMutex` oder klar gekapselten thread-safen State.

## Robustheit ohne Hardware

- Jeder Hardware-Zugriff (Audio-Geräte, Kamera, Bildschirm, FFmpeg) braucht einen **Mock-/Fallback-Pfad**,
  damit Headless-Selftest und CI ohne Geräte laufen.
- **Geräte-Verifikation:** Quellen nicht nur auflisten, sondern testweise öffnen — nur wirklich
  nutzbare Quellen anbieten.
- Einschränkungen (Loopback fehlt, USB-Drift) **ehrlich** in der UI/Statusleiste benennen, nie
  „läuft einfach" vortäuschen (Faktentreue-Regel).

## Tests

- TDD: erst Tests, dann Implementierung. `python -m pytest recorder/tests -q`.
- Headless-Selftest: `PODCAST_RECORDER_SELFTEST=1` + `QT_QPA_PLATFORM=offscreen` → App startet,
  baut UI auf, beendet sich mit Exit-Code 0 ohne Fenster.
- GUI-Tests laufen offscreen; Audio/Video gegen Mocks.

## Design

- Frisches, ruhiges, schlankes UI — **nicht** den alten Studio-PySide-Look kopieren.
- Automation-first: sinnvolle Defaults, minimale Pflicht-Klicks bis zur ersten Aufnahme.

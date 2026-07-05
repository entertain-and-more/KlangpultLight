# Changelog / Änderungsprotokoll

Alle wesentlichen Änderungen an diesem Projekt werden hier dokumentiert.
Format basiert auf [Keep a Changelog](https://keepachangelog.com/de/1.1.0/).

## [Rebrand 2026-06-27]

### Geändert
- Produkt umbenannt: PodcastPackages → Klangpult light
- Lizenz: Proprietär/Freeware, Closed-Source
- Sub-Tools: PodcastRecorder → Klangpult light – Recorder; PodcastPlaner → Klangpult light – Planer
- Strategie verankert: kein öffentliches GitHub-Repo; Free/Freeware-Funnel für Klangpult (Vollversion)

## [Unreleased]

### Hinzugefügt / Added
- **Recorder Aufnahme-Robustheit (portiert aus Vollversion-Review, 2026-06-30):**
  - **Roh-Capture-Diagnose:** `AudioEngine` zählt Nullen im ROHEN sounddevice-Callback-Input
    (vor jeder Verarbeitung); `capture_metrics()` liefert Roh-Null-Anteil je Kanal,
    `RecordingSession.stop()` schreibt `capture_metrics.json` ins Take-`main/`-Verzeichnis →
    beweist WASAPI/Treiber vs. App bei Stille-Aussetzern. Tests: `tests/test_capture_metrics.py`.
  - **RT-Callback-Status-Drossel:** Overflow-Status wird im Audio-Callback nur noch max. 1×/2s
    geloggt (I/O im Echtzeitpfad verstärkte sonst unter Last die Aussetzer).
  - **`latency='high'`** auf den Capture-InputStreams (größerer Puffer, Jitter-Toleranz).
  - **Prozess-Priorität HIGH während der Aufnahme** (`core/process_priority.py`, in
    `RecordingSession.start/stop`) — schützt den Audio-Callback vor CPU-Aushungerung.
  - Hinweis: Die großen Architektur-Fixes der Vollversion (Roh-Stems aus dem GUI-Tick,
    Offline-Mix, `align()`-Entfernung) sind hier gegenstandslos — der Recorder nutzt bereits
    einen MixWorker-Thread mit block-synchronem Mix (kein „mix länger als Stems").
- Projektweite `CHANGELOG.md` als Bootstrap-Baustein angelegt, damit künftige Recorder-/Planer-Änderungen versionierbar dokumentiert werden können.
- Recorder: Aufnahme-Moduswahl `Ton + Video`, `Nur Ton`, `Nur Video`.
- Recorder: auswählbare Audioquellen pro Mic-/Line-Quelle mit persistenter und direkt übernommener Gerätezuweisung.

### Geändert / Changed
- Root-Registry-Status synchronisiert: `KlangpultLight` ist in `releases.json` registriert und `PROJECT_STATUS.md` führt das Projekt jetzt konsistent mit Registry `ja`; GitHub bleibt bewusst kein Ziel für die Closed-Source-Freeware.

### Behoben / Fixed
- Recorder: Videoaufnahme ist nicht mehr implizit immer aktiv; `Nur Ton` startet ohne Videoquelle.
- Recorder: `Nur Video` erzeugt eine echte Video-only-Aufnahme ohne Audio-WAV-Dummy.
- Recorder: Audioquellen-Checkboxen wirken sofort auf die laufende Engine statt nur in `sources.json`.

## [0.1.0] - 2026-06-17

### Hinzugefügt / Added
- Konzeptprojekt `Klangpult light` als schlanke Aufspaltung von `DEV_USBPodcastStudio` in `Recorder` und `planer` dokumentiert.
- Root-Dokumente `README.md`, `KONZEPT.md` und `TODO.md` als erste Projektbasis angelegt.

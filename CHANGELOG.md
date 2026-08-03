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

### Hinzugefügt / Added (SOFTWARE HIGH END 2026-08-03)
- Reproduzierbare, isolierte Live-Fixture für die echte Planer-Browserabnahme:
  `scripts/planer_browser_fixture.py` startet die produktiven Library-,
  Projects- und Planer-Dienste auf freien localhost-Ports und verwendet nur
  explizite temporäre Laufzeitdaten.
- Browser-Runbook `docs/PLANER_BROWSER_ACCEPTANCE.md` mit Projekt-, Episoden-,
  Bibliotheks-, Zuordnungs-, Lösch-, Konsolen- und Netzwerk-Readback.
- `TW-KLANGPULTLIGHT-05` mit einem realen Chromium-/Playwright-CLI-Lauf
  abgeschlossen; erwartete API-Status 200/201/204, finale Konsole ohne Fehler
  oder Warnungen.

### Behoben / Fixed (SOFTWARE HIGH END 2026-08-03)
- Die Planer-Startseite deklariert explizit ein leeres Data-Favicon und erzeugt
  dadurch beim lokalen Browserstart keinen impliziten `/favicon.ico`-404 mehr.
- Regression in `Recorder/tests/test_planer_a11y.py` ergänzt.

### Behoben / Fixed (TASKSOLVER 2026-07-28, #1341–#1343)
- `DeviceManager` verwendet für UI-Status und Defaultbelegung denselben verifizierten
  Gerätescan, statt Eingabegeräte mehrfach testweise zu öffnen.
- Systeme mit ausschließlich Ausgabegeräten wechseln wie hardwarelose Systeme auf
  den explizit gekennzeichneten Mock-Fallback.
- Der Offscreen-Vertrag prüft Quellen-Panel, Aufnahme-Button, Pegelanzeigen,
  Aufnahmeliste und aktiven GUI-Timer direkt.
- Phase-1-Status auf 406 bestandene Pytest-Tests synchronisiert; der zusätzliche,
  ortsgebundene Registry-Test bleibt wegen nicht hydrierbarer OneDrive-Rootdateien gegatet.

### Hinzugefügt / Added (Technische Hygiene & Maintenance 2026-07-27)
- Doku- & Hygiene-Wartung: `llms.txt` Last-checked Datum auf `2026-07-27` und Pytest Testsuite-Pass-Vertrag (404 passed tests) re-verifiziert.
- `README.md` & `README_de.md` Last-checked Timestamps und Verweise auf `llms.txt` auf `2026-07-27` aktualisiert.
- Pytest Testsuite (404 tests passed) vollständig ausgeführt und verifiziert.

### Hinzugefügt / Added (Discoverability-, SEO- & Visuals-Audit 2026-07-25)
- Standardisiertes PEP 621 `pyproject.toml` mit Pytest-Konfiguration (`testpaths = ["Recorder/tests", "tests"]`, `pythonpath = "."`) angelegt.
- Shields.io Badges (Python 3.10+, Pytest 404 passed, Freeware, Local-First, LLM-Ready) & GFM KI/LLM-Integrationshinweis (`> [!NOTE]`) in `README.md` und `README_de.md` eingebunden.
- Deutsche Landing-Page `README_de.md` mit Sprachwechsler-Navigation erstellt.
- Mermaid Systemarchitektur-Diagramme für Recorder/Planer-Komponenten in `README.md` und `README_de.md` integriert.
- `llms.txt` Header `Last-checked` Datum auf `2026-07-25` und Testsuite-Bestätigung (404/404 Pytest passed) aktualisiert.


### Hinzugefügt / Added (Technische Hygiene & Maintenance 2026-07-24)
- Root-Datei `llms.txt` für KI-Agenten und strukturierte Maschinenlesbarkeit angelegt.
- `README.md` um Referenz auf `llms.txt` und Last-Checked-Datum (2026-07-24) ergänzt.
- Technische Hygiene und Doku-Check durchgeführt: Pytest-Suite (2/2 passed) verifiziert.


### Hinzugefügt / Added
- Privates GitHub-Repo `entertain-and-more/KlangpultLight` angelegt und `main` gepusht (2026-07-23); Sichtbarkeit private, kein öffentlicher Publish (Strategie aus Rebrand 2026-06-27 unverändert: kein öffentliches Repo)


### Behoben / Fixed (Review-Loop 2026-07-23)
- `build_exe.bat`: kaputte Umlaute (`Abh?ngigkeiten` → `Abhängigkeiten`, ASCII-Mojibake
  ohne Zusammenhang mit den übrigen Skripten) korrigiert.
- `TODO.md`: veraltete „offen"-Markierung für den bereits am 2026-07-14 behobenen
  WAV-Write-Lock-Bug entfernt (stand im Widerspruch zu `BUGS.md`).
- `assets/`: 6 unreferenzierte Expo/React-Native-Icon-PNGs (`android-icon-*`,
  `favicon.png`, `icon.png`, `splash-icon.png` — falscher Tech-Stack, keine Codereferenz)
  nach `_archive/unreferenzierte-expo-icons_2026-07-23/` verschoben (gitignored, nicht gelöscht).

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
- Lokaler Recorder-EXE-Workflow: `KlangpultLightRecorder.spec`, `build_exe.bat`,
  Root-EXE `KlangpultLightRecorder.exe`, versioniertes Release-Artefakt und SHA256-Summen.
- Root-Icon (`DesktopIcon.png`/`.ico`) und README-Screenshot `README/screenshots/main.png`.

### Geändert / Changed
- Root-Registry-Status synchronisiert: `KlangpultLight` ist in `releases.json` registriert und `PROJECT_STATUS.md` führt das Projekt jetzt konsistent mit Registry `ja`; GitHub bleibt bewusst kein Ziel für die Closed-Source-Freeware.
- `Recorder/START.bat` startet bevorzugt die gebaute Recorder-EXE und fällt erst dann auf Python zurück.
- Im Frozen-Betrieb nutzt der Recorder den EXE-Ordner als Workspace-Basis statt ein temporäres Bundle-Verzeichnis.

### Behoben / Fixed
- Recorder: Videoaufnahme ist nicht mehr implizit immer aktiv; `Nur Ton` startet ohne Videoquelle.
- Recorder: `Nur Video` erzeugt eine echte Video-only-Aufnahme ohne Audio-WAV-Dummy.
- Recorder: Audioquellen-Checkboxen wirken sofort auf die laufende Engine statt nur in `sources.json`.
- Recorder: Die kompakten `⧉`-Panelbuttons bleiben visuell knapp, exponieren jetzt aber panelbezogene Tooltips sowie klare Accessible Names und Descriptions für Screenreader und Tastaturnutzung.

## [0.1.0] - 2026-06-17

### Hinzugefügt / Added
- Konzeptprojekt `Klangpult light` als schlanke Aufspaltung von `DEV_USBPodcastStudio` in `Recorder` und `planer` dokumentiert.
- Root-Dokumente `README.md`, `KONZEPT.md` und `TODO.md` als erste Projektbasis angelegt.

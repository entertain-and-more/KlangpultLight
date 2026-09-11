# Changelog / Änderungsprotokoll

Alle wesentlichen Änderungen an diesem Projekt werden hier dokumentiert.
Format basiert auf [Keep a Changelog](https://keepachangelog.com/de/1.1.0/).

## [Rebrand 2026-06-27]

### Geändert
- Produkt umbenannt: PodcastPackages → Klangpult light
- Lizenz: Proprietär/Freeware, Closed-Source
- Sub-Tools: PodcastRecorder → Klangpult light – Recorder; PodcastPlaner → Klangpult light – Planer
- Strategie verankert: kein öffentliches GitHub-Repo; Free/Freeware-Funnel für Klangpult (Vollversion)

## [0.1.0] - 2026-08-22

### Hinzugefügt / Added (Pfad B: Discoverability, CI Matrix, Security & Contract Parity 2026-08-22)
- Multi-OS GitHub Actions CI Matrix (`.github/workflows/ci.yml`) für Ubuntu & Windows mit Python 3.10–3.13 und automatisierten Ruff Linter- und Vertragstests.
- Bilinguale Sicherheitsrichtlinie (`SECURITY.md`) mit Zero-Egress-, Local-First- und Loopback-Netzwerk-Garantien, unprivilegiertem User-Mode und dedizierten Meldewegen.
- Umfassende Metadaten- und Paritäts-Vertragstestsuite (`tests/test_metadata.py`) mit 8 Assertions zu pyproject.toml, Pflichtdokumenten, CI Matrix, llms.txt, bilingualen READMEs und Geschwister-Ökosystem.
- Eigenständige Freeware-Lizenzdatei (`LICENSE`) mit klaren Nutzungsbedingungen und Abgrenzung zur kommerziellen Klangpult-Suite.
- README.md und README_de.md mit hochauflösenden Badges, dualen Mermaid-Diagrammen (Architektur-Graph & Sequenzablauf), Geschwister-Ökosystem-Matrix (`entertain-and-more`, `open-bricks`), Schnellnavigation und Feature-Übersicht.
- `pyproject.toml` mit reichhaltigen Metadaten, URLs (Homepage, Repository, Documentation, Issues, Changelog, Security, Umbrella) und Tool-Konfigurationen (ruff, pytest).
- Vollständige Code-Hygiene: 86 Ruff-Linter-Meldungen restlos bereinigt, 0 Fehler.
- `llms.txt` auf Stand 2026-08-22 synchronisiert.

## [0.1.4] - 2026-09-11

### Onedir-Packaging, Desktop-Integration & Standalone-Planer-Bundling (TW-KLANGPULTLIGHT-12) [G 2026-09-11]
- **PyInstaller Onedir-Spezifikation**: `KlangpultLightRecorderOnedir.spec` für schnellen Sofortstart ohne Laufzeit-Dekompressionsaufwand hinzugefügt; `build_onedir.bat` erzeugt die entpackte Standalone-Distribution unter `dist/KlangpultLightRecorder/` und `releases/v0.1.0/onedir/` inklusive SHA256-Prüfsummen (`TW-KLANGPULTLIGHT-12`).
- **Standalone-Planer-Bundling**: `shared/` und `planer/` (HTML, JS, CSS, Server) sowohl in `KlangpultLightRecorder.spec` als auch `KlangpultLightRecorderOnedir.spec` eingebunden, sodass der compilierte Desktop-Recorder den Web-Planer ohne separate Python-Umgebung ausliefern kann.
- **Resiliente Frozen-Pfadauflösung**: `BridgeService._get_planer_server_cls` und `planer_server._resolve_static_root` erkennen Quellbaum, PyInstaller `_MEIPASS` (Onefile) sowie Anwendungsverzeichnis und `_internal/` (Onedir) nahtlos.
- **Desktop-Shortcut-Generator**: `scripts/create_desktop_shortcut.py` und `CREATE_DESKTOP_SHORTCUT.bat` erlauben die 1-Klick-Einrichtung einer Windows-Desktopverknüpfung (`.lnk`) mit `DesktopIcon.ico` und korrektem Arbeitsverzeichnis.
- **Automatisierte Absicherung**: 9 neue Tests in `Recorder/tests/test_onedir_packaging_and_shortcut.py` prüfen Specs, Skripte, Verknüpfungs-Dry-Run und Pfadauflösung.

## [0.1.3] - 2026-09-10

### One-Click Planer-Integration & Lizenzvertrag (TW-KLANGPULTLIGHT-08 / TW-KLANGPULTLIGHT-10) [G 2026-09-10]
- **Integrierter Planer-Lebenszyklus in BridgeService**: `BridgeService` startet den `PlanerServer` standardmäßig mit (`PODCAST_RECORDER_PLANER=1`, Port 8770), leitet Aufrufe an Library- und Projects-APIs weiter, fängt Portkonflikte resilient ab und fährt den Server beim Schließen der Anwendung sauber herunter (`TW-KLANGPULTLIGHT-10`).
- **Recorder UI Schnellstart**: Neuer Aktions-Button „🌐 Planer im Browser öffnen" in der Recorder-Aufnahmeliste (`MainWindow`) mit barrierefreier Beschriftung (`accessibleName`, `toolTip`), automatischer Ermittlung des aktiven Bridge-Ports und Rückmeldung in der Statusleiste.
- **Lizenz- und Identitäts-Vertragstest**: `tests/test_license_identity_contract.py` validiert Root-`LICENSE` (Klangpult light — Freeware License Agreement, Copyright 2026 Lukas Geiger), `pyproject.toml` Metadaten und `README.md`-Referenzen automatisiert gegen Widersprüche (`TW-KLANGPULTLIGHT-08`).
- **Integrationstests**: `Recorder/tests/test_planer_oneclick_integration.py` und erweiterte `Recorder/tests/test_bridge_service.py` prüfen den vollständigen 4-Dienste-Verbund (Library HTTP, Remote WS, Projects HTTP, Planer Web) Ende-zu-Ende. Gesamte Testsuite: 460 Tests bestanden.

## [0.1.2] - 2026-09-09

### Marketing, Discoverability & Visuelle Architektur (Pfad B [G 2026-09-09])
- **14-Punkte-Schnellnavigation mit bidirektionaler Anker-Parität**: `README.md` und `README_de.md` auf eine standardisierte 14-Punkte-Navigationsstruktur synchronisiert, inklusive expliziter HTML-Anker-Tags für lückenlose Funktionsfähigkeit in allen Markdown-Renderern.
- **Tabelle der 10 Governance- & Laufzeit-Invarianten**: Verbindliche Spezifikation der 10 Kerninvarianten (100% Local-First & Zero-Egress, unprivilegierter Betrieb / RunAsInvoker, strikte Loopback-IPC-Isolation, sichere FFmpeg-Subprozessgrenzen, begrenzte Audio-Pufferintegrität, Offline-STT-Degradationsgrenze, Nutzer-kontrollierte Session-Speicherung, plattformübergreifende Betriebsparität, Multi-Host- & Synchronisations-Resilienz, 48h Antwort- & 5-Tage-Triage-SLA) in beiden README-Dateien.
- **Shields.io Badge-Suite Modernisierung**: Status Public Alpha, Python 3.10–3.13, Pytest 450 Tests (449 bestanden, 1 Registry-Test extern gegatet), Multi-OS CI Matrix, Freeware-Lizenz, Local-First / Zero-Egress Architektur, unprivilegierter Betrieb (RunAsInvoker), Security SLA (48h Antwort | 5d Triage), Code-Stil Ruff, Ökosystem `entertain-and-more`, Dachorganisation `open-bricks`, LLM-Ready `llms.txt`.
- **Duale Mermaid-Visualisierungen**: Vollständiges Systemarchitektur-Ablaufdiagramm (`graph TD`) und End-to-End Medien- & Aufnahme-Lebenszyklus (`sequenceDiagram` mit automatischer Nummerierung und 14 Schritten) in beiden READMEs verankert.
- **Geschwister-Ökosystem & Werkzeug-Matrix**: Dokumentation von 17 verwandten und kooperierenden Projekten über `entertain-and-more` (BattleStage, ChainReaction, StreetRacer, RealmWars, GhostTrain, RescueMe, HauntedHouse, MafiaCastle, CuteStrike, BattleChess3D, Klangpult) und `open-bricks` (system-auditor, automation-master, ExplorerPro, CleanMarkdown, ellmos-voice-io, WikiStub-Seed).
- **Sicherheitsrichtlinie & Triage-Zusage (`SECURITY.md`)**: Verbindliche 5-Werktage-Triage-Zusage (5 business days / 5 Werktagen) neben dem 48-Stunden-Reaktions-SLA zweisprachig verankert; offizielle Kontakte `security@open-bricks.org`, `security@ellmos.ai`, `support@lukasgeiger.com` und `lukas@open-bricks.org` sowie GitHub Security Advisories hinterlegt.
- **CI-Bytecode-Kompilierungsgate (`.github/workflows/ci.yml`)**: Automatischer Syntax- und Bytecode-Validierungsschritt (`python -m compileall -q .`) vor Ausführung der Vertragstests integriert.
- **.gitignore-Härtung**: Vollständiger Schutz vor Multi-Host-Synchronisationskonflikten (`*-conflict-*`, `*.sync-temp-*`, `*.sync-conflict-*`, `*.conflict`, `*-CONFLIT-*`), Multi-Agent-Locks (`LOCK.*`, `*.lock`, `LOCK*.txt`, `LOCK`), Caches (`.ruff_cache/`, `.pytest_cache/`, `.coverage`, `wheelhouse/`, `.wheel-smoke/`) und temporären Dateien (`*.tmp`, `*.bak`, `*.swp`, `*~`, `*.log`).
- **Lokales Marketing-Register (`MARKETING-LOG.txt`)**: Detaillierter Audit- und Discoverability-Bericht für SEO-Keywords, Positionierung, Zielgruppen, Visual Assets und Invarianten angelegt.
- **Vertragstestsuite (`tests/test_metadata.py`)**: Umfassend erweitert zur automatisierten Validierung der 14-Punkte-Navigationsparität, 10 Governance-Invarianten, CI-Bytecode-Kompilierungsgates, Sicherheits-SLAs, .gitignore-Hygiene und Sibling-Ecosystem-Vollständigkeit.

## [0.1.1] - 2026-09-08

### Härtung & Hygiene (Pfad A: Repository-Hygiene & CI-Workflow-Härtung [G 2026-09-08])
- **CI-Workflow-Härtung (`.github/workflows/ci.yml`)**: Concurrency-Steuerung mit `cancel-in-progress: true` integriert; Multi-OS-Matrix um `macos-latest` erweitert (Ubuntu, Windows & macOS auf Python 3.10–3.13); Pip-Dependency-Caching (`cache: 'pip'`) in `actions/setup-python@v5` aktiviert.
- **PEP 621 Metadaten & URLs (`pyproject.toml`)**: Vollständige Ökosystem-Links (`Parent Organization`, `Ecosystem`), OS-Klassifikatoren (`Operating System :: MacOS`, `Operating System :: OS Independent`) sowie standardisierte `[tool.ruff.lint]`-Sektion ergänzt.
- **Sicherheitsrichtlinie & Bilinguale Parität (`SECURITY.md`)**: Zweisprachige Unterstützte-Versionen-Matrix (0.1.x aktiv, <0.1 deprecated) im deutschen Abschnitt nachgezogen; Meldewege um Dachorganisations-Kontakt (`security@open-bricks.org` / `lukas@open-bricks.org`) erweitert.
- **Linter- & Code-Hygiene**: Unbenutzten Import `patch` in `Recorder/tests/test_stt_e2e_degradation_contract.py` bereinigt; `ruff check .` meldet 0 Fehler / 100% sauber.
- **Automatisierte Vertragstestsuite (`tests/test_metadata.py`)**: Assertions für CI-Concurrency, macOS-Runner, PEP-621-Ecosystem-URLs, bilinguale SECURITY.md-Tabellen und aktuelle Synchronisationsstempel gehärtet (8 Tests, 100% grün).
- **Dokumentations- & Badge-Parität**: Pytest-Testabdeckung in `README.md`, `README_de.md` und `llms.txt` auf 450 Tests (449 passed, 1 skipped) und Stempel 2026-09-08 aktualisiert.

## [Unreleased]

### Hinzugefügt / Added (SOFTWARE ENTWICKLUNG 2026-08-24)
- Live-STT End-to-End-Pfad & Degradationsgrenzen (`TW-KLANGPULTLIGHT-04`): Vollständige Verifikation und Härtung des Live-Transkriptions-Subsystems.
- Neue automatisierte Vertragstestsuite `Recorder/tests/test_stt_e2e_degradation_contract.py` (11 Tests):
  - End-to-End-Pipeline: AudioEngine-Sink (`feed`) → SttManager-Fensterakkumulation → LiveSttEngine → BridgeService (WebSocket Port 8768) → Planer-Event `transcript_chunk` mit vollständigen Metadaten (`type`, `text`, `is_final`, `t_start`, `engine`).
  - Fehlertolerante Degradation für `LocalWhisperEngine` bei fehlendem `faster-whisper`, Modellladefehlern oder Inferenz-Exceptions (sauberes `[]`, kein GUI-/Aufnahme-Block).
  - Striktes Opt-in und Resilienz für `CloudSttEngine` bei fehlendem `OPENAI_API_KEY`, Timeouts, Connection Drops oder 401/429-API-Fehlern.
  - Deterministische Fallback-Hierarchie in `select_engine` (Cloud → Local → Mock → inaktive Instanz, niemals `None`).
  - Puffer- und Format-Resilienz bei NaN-/Inf-Audiodaten, leeren Blöcken und kontrolliertem Shutdown ohne verwaiste Threads.
- Runbook und Nachweisdokument in `docs/STT_E2E_DEGRADATION_REPORT.md`.
- Pytest-Gesamtsuite auf 437 bestandene Tests (437 passed, 100% grün) erweitert.

### Hinzugefügt / Added (SOFTWARE ENTWICKLUNG 2026-08-21)
- Phase-8-Planer-Slice (`TW-KLANGPULTLIGHT-03`): End-to-End-Integration von Teleprompter, KI-Monitor und WebSocket-Live-Sync.
- Teleprompter-Modul (`planer/app/teleprompter.js`): 4 Betriebsmodi (manuell, zeitgesteuert, sprachgesteuert via STT-Token-Sync, hybrid), horizontaler Spiegelmodus für Beamer/Prompter-Glas, Schriftgrößen- (16–64px) und Geschwindigkeitsregler (0.2–3.0x), Cue-Cursor, Tastaturnavigation (Leertaste, Pfeiltasten, Escape) und automatisches Speichern.
- KI-Monitor-Modul (`planer/app/monitor.js`): Live-Transkriptstream aus Recorder-STT-Events, strukturierte Offline-Heuristik (Faktenchecks, vertiefende Nachfragen, Zusammenfassungs-Punkte), 1-Klick-Kapitelmarken-Dispatch per WebSocket in den Recorder sowie opt-in Schalter für Web- und Cloud-Recherche.
- WebSocket-Remote-Client (`planer/app/remote.js`): Verbindungs- und Protokollverwaltung (`remote_protocol_v1.json`) auf Port 8768 mit Reconnect-Logik, Event-Broadcasting (`transcript_chunk`, `state_update`) und bidirektionalem Dispatch.
- Backend REST-Endpunkte in `Recorder/bridge/projects_api.py`: `/api/projects/{id}/teleprompter` (GET/PUT), `/api/projects/{id}/monitor` (GET/PUT) und `/api/projects/{id}/monitor/analyze` (POST) mit Persistenz (`teleprompter_{id}.json`, `monitor_{id}.json`) und voller Integration in den `workspace-v1` Export/Import.
- Testabdeckung: Neue Unit- & Persistenztests in `Recorder/tests/test_projects_api.py`, Protocol- & Matching-Vertragstests in `test_phase8_teleprompter_monitor.py` und Accessibility-Tests in `test_planer_a11y.py`. Pytest-Gesamtsuite auf 425 bestandene Tests (425 passed, 100% grün) erweitert.

### Hinzugefügt / Added (SOFTWARE HIGH END 2026-08-14)
- Phase-7-Planer-Slice (`TW-KLANGPULTLIGHT-02`): End-to-End-Integration von Assets, Line-Ablaufsteuerung und Workspace-v1 JSON Export/Import.
- Integrationstests in `Recorder/tests/test_projects_api.py`: 4 neue Testfunktionen mit 15+ Assertions für Assets-CRUD, automatisches Line-Cleanup beim Löschen von Assets, Line-Validierung und Persistenz nach Serverneustart.
- Pytest-Vollsuite auf 417 bestandene Tests (417 passed, 1 skipped) erweitert.

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

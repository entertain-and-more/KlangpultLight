# Changelog / Änderungsprotokoll

Alle wesentlichen Änderungen an diesem Projekt werden hier dokumentiert.
Format basiert auf [Keep a Changelog](https://keepachangelog.com/de/1.1.0/).

## [Unreleased]

### Security & License Audit, CVE-2025-7117 Floor, 5-Field SBOM & Contract Tests (2026-10-04) [G 2026-10-04]
- **Dependency Floors & CVE-Schutz (CVE-2025-7117 / GHSA-6w46-j5rx-g56g)**:
  - `pyproject.toml`: Mindestversion in `[tool.pytest.ini_options]` von `7.0` auf `9.1.1` gehärtet; `[project.optional-dependencies]` für `test` und `dev` auf `pytest>=9.1.1` und `ruff>=0.9.0` festgelegt; `build`-Toolchain-Floors für `pyinstaller>=6.10.0`, `pyinstaller-hooks-contrib>=2024.0`, `altgraph>=0.17.4`, `packaging>=24.0` und `setuptools>=61.0` etabliert.
  - `requirements.txt`: `pytest>=8.0` auf `pytest>=9.1.1` angehoben.
  - `requirements-dev.txt`: Neue reproduzierbare Entwicklungsspezifikation angelegt.
  - `pyproject.toml` `[project.urls]`: Direkte private Melde-URL `"Security Advisories" = "https://github.com/entertain-and-more/KlangpultLight/security/advisories/new"` registriert.
- **5-Felder-SBOM-Standardisierung (`THIRD_PARTY_LICENSES.txt` / `THIRD_PARTY_LICENSES.md`)**:
  - `THIRD_PARTY_LICENSES.txt`: Vollständig auf das kanonische 5-Felder-Schema (`Package:`, `License:`, `SPDX:`, `URL:`, `Notice:`) umgestellt; alle 14 Laufzeit- und Toolchain-Komponenten inventarisiert; Floor-Härtung gegen CVE-2025-7117 dokumentiert; Re-Zertifizierung der 10 Level 1 Invarianten (`INV-LOCAL-01` bis `INV-SLA-10`) auf Stand 2026-10-04.
  - `THIRD_PARTY_LICENSES.md`: Audit-Datum und Querverweise synchronisiert.
- **Repository- & Gitignore-Hygiene**:
  - `.gitignore`: Um Zertifikatsmuster (`*.crt`, `*.cer`), Token-Dateien (`token*.json`, `credentials*.json`) und Test-Log-Muster (`pytest_out.txt`, `pytest*.txt`) gehärtet.
  - Hygiene-Scan bestätigt 0 Secrets, 0 API-Keys und 0 unberechtigte private Nutzerpfade im Quellcode.
- **Vertragstest-Suite (`tests/test_security_license_contract.py`)**:
  - Ausgebaut auf 10 hermetische Vertragstests inklusive 5-Felder-SBOM-Validierung, Dependency-Floors (`pytest>=9.1.1`, `minversion = "9.1.1"`), Security-Advisories-URL, Gitignore-Hardening und Local-First Invarianten (10/10 passed).

### Pfad B Marketing, Discoverability, Visual Architecture & ASCII Four-View Topology (2026-10-02) [G 2026-10-02]
- **Version-Freeze Disziplin (`T-20260920-167562623`)**: Versionskonstante `0.1.0` in `pyproject.toml` und Manifesten strikt beibehalten (kein Version-Bump; Release-Vorgang und Distribution bleiben separater Autorisierung vorbehalten).
- **ASCII-Vier-Sichten-Architekturtopologie**:
  - `README.md` (Section 02) & `README_de.md` (Section 02) mit kanonischer ASCII Four-View Architectural Topology Projektion erweitert:
    - *VIEW 1 / SICHT 1*: Client-Laufzeiten, Recorder-Desktop-HUD (PySide6/Qt6), Web-Planer-Dashboard, Teleprompter & KI-Monitor sowie interaktives Soundboard.
    - *VIEW 2 / SICHT 2*: Autonome Audio-Pipeline, SoundDevice WASAPI-Loopback-Erfassung, lokaler Faster-Whisper STT-Thread, bidirektionale WebSocket-IPC-Bridge (:8767/:8769) & HTTP-Medien-API mit RFC-7233 Range-Requests.
    - *VIEW 3 / SICHT 3*: Laufzeit-Persistenz, 32-Bit-Float/24-Bit-PCM WAV-Schreiben mit NaN-Sanitisierung, FFmpeg-Muxing (MP4), Workspace-v1 Schema-Speicher & strukturierte Session-Logs (`events.jsonl`).
    - *VIEW 4 / SICHT 4*: Air-Gap-Sicherheitsperimeter, 100% Local-First Isolation (`127.0.0.1`), unprivilegiertes `RunAsInvoker`-Modell (`INV-USER-02`), Zero-Copyleft-Schutz durch dynamische PySide6 LGPL-3.0 § 4 Bindung & Level 1 SBOM Transparenz.
- **Level 1 SBOM Re-Audit & Plain-Text Companion (`THIRD_PARTY_LICENSES.txt` / `THIRD_PARTY_LICENSES.md`)**:
  - Re-Auditierung auf Stand 2026-10-02 über alle 10 Governance- und Laufzeitinvarianten (`INV-LOCAL-01` bis `INV-SLA-10`) mit Bestätigung von 100% Permissive / LGPL-3.0 Dynamic Linking.
- **Dokumentations- & Testsuite-Synchronisation**:
  - `README.md` & `README_de.md`: Badges auf die reale Testsuite-Baseline aktualisiert (`570 tests (570 passed) | 100% green`), Marketing-Log Badge auf `2026-10-02`.
  - `llms.txt`: Aktualisiert auf Stand 2026-10-02 mit 570 bestandenen Pytest-Tests und Vermerk zur ASCII-Topologie.
- **Vertragstest-Erweiterung (`tests/test_metadata.py`)**:
  - Neue Vertragstests für ASCII Four-View Topologie Parität zwischen englischer und deutscher Dokumentation (`test_ascii_four_view_topology_parity`), Testcount- und Datumskorrektheit sowie strikte Version-Freeze-Disziplin (`test_version_freeze_discipline`).

### Behoben / Fixed (Bugsweep: Bibliotheks-API & Proxy Streaming, HTTP Range-Requests, CORS & HEAD-Support 2026-10-01) [G 2026-10-01]
- **HTTP Byte-Range Requests & Partial Content (`Recorder/bridge/library_api.py`)**:
  - `_LibraryHandler._antwort_audio()` unterstützt RFC-7233-Byte-Ranges (`Range: bytes=start-end`, `bytes=start-`, `bytes=-suffix`) mit `HTTP 206 Partial Content`, `Content-Range: bytes {start}-{end}/{total}`, `Accept-Ranges: bytes` und partiellem Stream, wodurch Seeking und Scrubbing in HTML5 `<audio>`/`<video>`-Playern zuverlässig funktionieren.
  - Abweisung ungültiger bzw. unbefriedigbarer Ranges (`start >= total` oder `start > end`) mit standardkonformem `HTTP 416 Range Not Satisfiable` (`Content-Range: bytes */{total}`).
- **CORS & OPTIONS Preflight (`Recorder/bridge/library_api.py`, `planer/server/planer_server.py`)**:
  - `_LibraryHandler`: `do_OPTIONS` (204 No Content) und `_set_cors_headers()` für `Access-Control-Allow-Origin: *`, `Access-Control-Allow-Methods` (GET, HEAD, OPTIONS) und `Access-Control-Allow-Headers` integriert; analog zu `ProjectsApiServer` werden alle JSON- und Audio-Antworten mit CORS-Headern ausgestattet.
  - `PlanerHandler`: `do_OPTIONS` (204 No Content) und `_set_cors_headers()` ergänzt, um browserseitige Preflight-Anfragen über den PlanerServer transparent zu beantworten.
- **HEAD Method Support (`Recorder/bridge/library_api.py`, `planer/server/planer_server.py`)**:
  - `_LibraryHandler`: `do_HEAD` implementiert; liefert identische Response-Header (`Content-Length`, `Content-Type`, `Accept-Ranges`, `CORS`) ohne Body-Stream aus, sodass Vorabprüfungen von Media-Playern nicht mit `HTTP 501 Unsupported method` scheitern.
  - `PlanerHandler`: `do_HEAD` implementiert und für alle internen sowie geproxyten Routen bereitgestellt.
- **URL-Decoding & Path-Traversal-Schutz (`Recorder/bridge/library_api.py`)**:
  - `_antwort_audio()` und `_antwort_recording()` normalisieren `recording_id` via `urllib.parse.unquote()`, wodurch prozent-kodierte URLs (`recording%5F...`) aufgelöst und ungültige Pfadtrenner über `library.recording_dir()` sauber mit 404 abgefangen werden.
- **Metadaten-Detailabfrage für Einzelaufnahmen (`Recorder/bridge/library_api.py`)**:
  - Neuer Endpoint `GET /api/library/<recording_id>` liefert Metadaten (`{"recording": meta.to_dict()}`) oder `HTTP 404 Not Found`.
- **Chunked Proxy-Streaming & Header-Durchleitung (`planer/server/planer_server.py`)**:
  - `PlanerHandler._proxy()` leitet `Range`-Header aus eingehenden Client-Anfragen an das Backend weiter, reicht `Content-Range` und `Accept-Ranges` durch und streamt Daten in 64-KB-Blöcken statt den gesamten Response-Body in den Arbeitsspeicher zu laden.
- **Regressionstest-Suite (`Recorder/tests/test_bugsweep_library_api_streaming_resilience_20261001.py`)**: 7 neue automatisierte Regressionstests zur lückenlosen Absicherung von CORS, Range-Requests, 416-Fehlern, HEAD-Support, Detail-Endpoint, URL-Decoding und Proxy-Streaming.

### Pfad A Repository Lifecycle Hardening, CI Lifecycle Workflows & Level 1 SBOM Text-Companion (2026-09-30) [G 2026-09-30]
- **Version-Freeze Disziplin (`T-20260920-167562623`)**: Versionskonstante `0.1.0` in `pyproject.toml` und Manifesten unverändert beibehalten (kein Version-Bump; Release-Vorgang und Distribution bleiben separater Autorisierung vorbehalten).
- **CI/CD Lifecycle Workflows & Labels Parität**:
  - `.github/workflows/auto-assign.yml`: Neu bereitgestellt mit `actions/github-script@v7`, `timeout-minutes: 5`, Concurrency `group: auto-assign-${{ github.ref }}` (`cancel-in-progress: true`) und least-privilege permissions `issues: write`, `pull-requests: write`.
  - `.github/workflows/label-sync.yml`: Neu bereitgestellt mit `EndBug/label-sync@v2`, `timeout-minutes: 5`, Concurrency `group: label-sync-${{ github.ref }}` (`cancel-in-progress: true`) und least-privilege permissions `issues: write`.
  - `.github/labels.yml`: Kanonische 11 Standard-Labels gemäß GOVERNANCE.md §4.2 angelegt.
  - `.github/workflows/stale.yml` und `welcome.yml`: Verifiziert und mit Concurrency `cancel-in-progress: true` gehärtet.
- **CONTRIBUTING.md**:
  - Neu angelegt mit Invarianten (Local-First, Zero-Egress, RunAsInvoker), Quality Gates (`pytest`, `ruff check .`, `python -m compileall -q .`, `git diff --check`), lokalem Development-Setup und strikter Version-Freeze-Regel.
- **Level 1 SBOM Plain-Text Companion (`THIRD_PARTY_LICENSES.txt`)**:
  - Stand 2026-09-30 mit formaler Bestätigung aller 10 Governance- und Laufzeitinvarianten (`INV-LOCAL-01` bis `INV-SLA-10`), `RunAsInvoker`-Zertifizierung (`INV-USER-02`), Zero-Copyleft-Garantie und 100% Offline Air-Gap Verifikation.
  - Vollständige Lizenztexte der Kernlizenzen (LGPL-3.0, MIT, BSD-3-Clause, Apache-2.0, PSF-2.0).
  - `NOTICE` und `THIRD_PARTY_LICENSES.md` mit formalem Querverweis auf den Plain-Text Companion synchronisiert.
- **Multi-Host Cloud-Sync-, Lock- und Cache-Defense in `.gitignore`**:
  - Gehärtet gegen Cloud-Sync-Muster (`*-IDEAPAD*`, `*-IDEAPAD-GEI*`, `*-WORKSTATION.*`, `*-WORKSTATION-LG.*`), kanonische Multi-Agent Locks (`LOCK.dev.*`, `LOCK.antigravity.*`, `LOCK.bugsearch.*`), OS-Artefakte (`Desktop.ini`, `desktop.ini`, `ehthumbs.db`, `*.swo`), Task-Dateien (`TASKPLAN_*.md`) sowie Test- und Coverage-Caches (`.pytest_temp/`, `.pytest_tmp*/`).
- **PEP 621 Standardisierung in `pyproject.toml`**:
  - URLs für `Contributing`, `Plain-Text License` und `Level 1 SBOM` unter `[project.urls]` registriert.
  - Pytest `addopts = "-ra -v --basetemp=.pytest_temp"` und gehärtete `norecursedirs` mit `.pytest_temp`, `.pytest_tmp*`.
- **Dokumentations- & Badge-Synchronisation**:
  - `README.md`, `README_de.md` und `README.es.md` Badges für `Verified-2026--09--30` aktualisiert unter Beibehaltung aller 18 bilateralen Schnellnavigations-Anker und dualen Diagramme.
  - `llms.txt` Stand 2026-09-30 mit Testsuite-Baseline und Querverweisen auf `CONTRIBUTING.md` und `THIRD_PARTY_LICENSES.txt` aktualisiert.
  - `MARKETING-LOG.txt`: Pfad A Revisionsbericht Stand 2026-09-30 dokumentiert.
- **Vertragstest-Erweiterung (`tests/test_metadata.py`)**:
  - 8 neue Contract-Tests für CI-Workflows (`auto-assign.yml`, `label-sync.yml`, `labels.yml`), `CONTRIBUTING.md`, Level 1 SBOM Text-Companion Invarianten, PEP 621 URLs, pytest basetemp options und .gitignore Multi-Host Guards.

### Behoben / Fixed (Bugsweep: Planer-Backend API ProjectsApiServer Resilienz, Volume-Parität & CORS 2026-09-29) [G 2026-09-29]
- **Titel- & Payload-Typsicherheit (`Recorder/bridge/projects_api.py`)**:
  - `_handle_projekt_post`, `_handle_projekt_put`, `_handle_episode_post` und `_handle_episode_put`: `_parse_title()` validiert den Typ strikt gegen Nicht-Strings (`null`, Zahlen, Listen) und liefert `HTTP 400 Bad Request` statt ungefangener `AttributeError`-Abstürze im Request-Handler.
  - `_handle_workspace_import_post`: `AttributeError` wird im Exception-Handler abgefangen; `workspace_importieren()` prüft `board`, `line` und `teleprompter` vor der Verarbeitung auf deren Schema-Typ (`dict` bzw. `list`).
- **Workspace-Export Lautstärke-Parität (`Recorder/bridge/projects_api.py`)**:
  - `workspace_exportieren()`: Ergänzung des fehlenden Feldes `"volume": _safe_volume(a.get("volume", 1.0), 1.0)` bei exportierten Pad-Dictionaries, sodass benutzerdefinierte Pad-Lautstärken bei Export/Import-Zyklen unverändert erhalten bleiben.
- **Teleprompter Float-Resilienz & Line-Filterung (`Recorder/bridge/projects_api.py`)**:
  - `_safe_scroll_speed()`: Abfangen von `NaN`, `Infinity` und ungültigen Typen mit Clamping auf `[0.1, 10.0]` (Default `1.0`), um Non-RFC-8259 JSON-Korruption in `speichere_teleprompter()` und `workspace_importieren()` auszuschließen.
  - `speichere_line()` & `workspace_importieren()`: Sanitisierung filtert `None`, Whitespace-Einträge und ungültige Phantom-Tokens (`"None"`, `"none"`) zuverlässig heraus.
- **CORS & OPTIONS Preflight (`Recorder/bridge/projects_api.py`)**:
  - `_ProjectsHandler`: `do_OPTIONS` (204 No Content) und `_set_cors_headers()` für `Access-Control-Allow-Origin`, `Access-Control-Allow-Methods` und `Access-Control-Allow-Headers` integriert, um browserseitige Cross-Origin-Aufrufe mit Preflight-Anfragen standardkonform zu bedienen.
- **Regressionstest-Suite (`Recorder/tests/test_bugsweep_projects_api_resilience_20260929.py`)**: 9 hermetische End-to-End-Tests zur Absicherung aller Defektbereiche.

### Behoben / Fixed (Bugsweep: Board-Model, Workspace-v1 Validierung & Ducking Lifecycle 2026-09-26) [G 2026-09-26]
- **Board-Model & Workspace-v1 Schema-Härtung (`Recorder/board/board_model.py`)**:
  - `load_board()`: Schutz vor Nicht-Dict JSON-Roots (Listen, Strings, null) mit automatischem Fallback auf leeres `Board()`.
  - `Pad.from_dict()`: Defensive Typkonvertierung und Clamping von `volume` auf `[0.0, 4.0]` (Default 1.0) gegen Thread-Abstürze (`TypeError`) im Audio-Feeder; Sanitisierung von `id`, `kind` und `mode`.
  - `validate_workspace_payload()`: Strikte Typvalidierung (`type(v) is int`) für Schema-Versionen und Teleprompter-Konformität (`text`, `font_size >= 8`, `scroll_speed >= 0`) nach `shared/workspace_v1.json`.
  - `export_workspace_full()`: Defensive Fallbacks für ungültige Teleprompter-Parameter und Schutz vor `None`-Stringifizierung.
  - `save_board()`: Validierung des Zielpfads gegen verwaiste `.tmp`-Dateien.
- **Ducking Release-Lebenszyklus & Audio-Engine Entkopplung (`Recorder/board/duck_controller.py`, `Recorder/audio/engine.py`, `Recorder/board/board_player.py`)**:
  - `DuckController.is_idle()`: Indikator für den Abschluss der exponentiellen Release-Rampe (`faktor >= 1.0 - 1e-6`).
  - `AudioEngine._mix_one_tick()`: Verzögert die Deregistrierung des Duck-Controllers, bis die Release-Rampe vollständig abgearbeitet ist, wodurch Pegelsprünge und Knackgeräusche verhindert werden.
  - `BoardPlayer.on_finish()`: Entkoppelte Ducking-Freigabe und Bereinigung leerer Feeder-Schlüssel.
- **Regressionstest-Suite (`Recorder/tests/test_bugsweep_board_model_and_ducking_20260926.py`)**: 17 hermetische Unittests zur Verifikation aller Edge Cases.

### Pfad B Marketing, Discoverability, Visual Architecture & Bilateral Navigation Parity (2026-09-24) [G 2026-09-24]
- **Version-Freeze Disziplin (`T-20260920-167562623`)**: Versionskonstante `0.1.0` in `pyproject.toml` und Manifesten unverändert beibehalten (Release-Isolation, kein Bump bei Pfad-A/B-Läufen).
- **Remote-Metadaten & 20-Topic-Sättigung**: 20 GitHub-Topics gesättigt (`audio`, `audio-mixer`, `audio-production`, `audio-recorder`, `desktop-app`, `freeware`, `local-first`, `mixing-console`, `podcast`, `python`, `windows`, `live-transcription`, `pyside6`, `teleprompter`, `ai-monitor`, `multitrack-recording`, `offline-first`, `podcast-studio`, `zero-egress`, `episode-planner`), kanonische Homepage-URL `https://github.com/entertain-and-more/KlangpultLight#readme` bestätigt.
- **Kanonische NOTICE Attribution**: Neue Datei `NOTICE` im Root für formale Copyright- und Open-Bricks-Ökosystem-Attribution.
- **PEP 621 Standardisierung (`pyproject.toml`)**: `keywords` auf alle 20 kuratierten Topics synchronisiert, `license-files` definiert und `Notice`-URL unter `[project.urls]` registriert.
- **Level 1 SBOM Invarianten-Kreuzreferenzmatrix (`THIRD_PARTY_LICENSES.md`)**: Vollständiges Re-Audit mit Stand 2026-09-24, Level 1 SBOM Matrix für alle 10 Invarianten (`INV-LOCAL-01` bis `INV-SLA-10`), `RunAsInvoker`-Zertifizierung und Verweis auf die `NOTICE`.
- **18-Punkte Bilaterale Schnellnavigation & Duale Anker**: `README.md`, `README_de.md` und `README.es.md` um duale reziproke Anker (`<a id="sec-01"></a>` bis `<a id="sec-18"></a>`) erweitert, Badges für `NOTICE`, `Verified-2026--09--24` und 516 Tests harmonisiert.
- **Gesetzlicher Haftungsausschluss (§ 521 BGB Gefälligkeitsrecht)**: Haftungsbeschränkung auf Vorsatz und grobe Fahrlässigkeit bei unentgeltlicher Software-Bereitstellung in Abschnitt 18 der Dokumentation und Governance verankert.
- **Vertragstests & Testsuite**: Neue Vertragstests in `tests/test_metadata.py` für NOTICE, PEP 621, 18-Punkte-Navigation, Level 1 SBOM Matrix, § 521 BGB Disclaimer und MARKETING-LOG-Dokumentation. Testsuite: 516 Tests 100% bestanden.

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

## [0.1.7] - 2026-09-18

### Repository-Hygiene, CI-Workflow-Härtung & Multi-Host Synchronisations-Schutz (Pfad A) [G 2026-09-18]
- **CI-Workflow-Härtung (`.github/workflows/ci.yml`)**: `timeout-minutes: 15` für Testjobs ergänzt, Least-Privilege-Sicherheitsstandard `permissions: contents: read` hinterlegt und Matrix-Testing über Ubuntu, Windows und macOS abgesichert.
- **Automatisierte Stale- & Welcome-Workflows (`.github/workflows/stale.yml`, `.github/workflows/welcome.yml`)**:
  - `stale.yml`: `actions/stale@v9` mit täglichem Cron-Lauf (`30 1 * * *`), `timeout-minutes: 10`, `concurrency: cancel-in-progress: true`, `permissions: issues: write, pull-requests: write`.
  - `welcome.yml`: `actions/first-interaction@v3` mit `timeout-minutes: 5`, `concurrency: cancel-in-progress: true`, `permissions: issues: write, pull-requests: write`.
- **Multi-Host Synchronisations- & Lock-Schutz (`.gitignore`)**: Vollständige Muster für Cloud-Sync-Konfliktdateien (`*conflicted copy*`, `* (Kopie)*`, `* (Copy)*`, `*-ASUS*`, `*-ASUS-GEI*`, `*-LAPTOP*`, `*-WORKSTATION*`, `*-WORKSTATION-LG*`, `*-Mac Studio*`, `*-MacBook*`), Multi-Agent-Locks (`LOCK`, `LOCK.*`, `LOCK*.txt`, `LOCK.permissions.json`, `LOCK.user.*`, `LOCK.until.*`, `LOCK.condition.*`, `uv.lock`, `!package-lock.json`) und Test-/Coverage-Caches (`.coverage*`, `htmlcov/`, `.hypothesis/`, `.turbo/`, `.nyc_output/`, `.tox/`, `.mypy_cache/`) konsolidiert.
- **Pytest- & Packaging-Härtung (`pyproject.toml`)**: `[tool.pytest.ini_options]` um `norecursedirs` ergänzt.
- **Barrierefreiheit & Favicon-Handhabung (`Recorder/tests/test_planer_a11y.py`)**: Semantik-Prüfung in `test_planer_index_html_semantics` aktualisiert, um sowohl reale Favicon-Assets (`favicon.ico`) als auch data-URI Deklarationen zu unterstützen.
- **Drittanbieter-Lizenz- & Governance-Reaudit (`THIRD_PARTY_LICENSES.md`, `MARKETING-LOG.txt`)**: Re-Audit mit Stempel 2026-09-18, Re-Affirmation aller 10 Governance-Invarianten (`INV-LOCAL-01` bis `INV-SLA-10`), Zero-Copyleft und unprivilegiertem `RunAsInvoker`-Betriebsmodus.
- **Vertragstest-Suite (`tests/test_metadata.py`)**: Umfassend erweitert mit Vertragstests für CI-Workflows (`ci.yml`, `stale.yml`, `welcome.yml`), Gitignore-Härtung, Changelog-Aktualität und Test-Suite-Parität.

## [0.1.6] - 2026-09-16

### Tier-2 Internationalisierung, UI-Sprachwechsel, Web-Planer-Adapter & README.es.md (TW-KLANGPULTLIGHT-13) [G 2026-09-16]
- **Tier-2 Mehrsprachigkeit (Policy P-006)**: Vollständige Unterstützung von 6 Zielsprachen (Deutsch `de`, Englisch `en`, Spanisch `es`, Chinesisch `zh`, Japanisch `ja`, Russisch `ru`) mit 100% Übersetzungsschlüssel-Parität (49 Schlüssel) über alle drei Wörterbücher (`locales/translations.json`, `Recorder/locales/translations.json`, `planer/locales/translations.json`).
- **Dynamischer Desktop-UI-Sprachwechsel (`Recorder/ui/main_window.py`)**: Neues Sprachauswahlmenü in der Menüleiste mit exklusiver `QActionGroup`, sofortiger Live-Aktualisierung aller Fenstertitel, Labels, Buttons, Tooltips und Tree-Header über `retranslate_ui()` sowie persistenter Speicherung der Benutzerauswahl in `QSettings("Klangpult", "KlangpultLight")` unter `ui/language`.
- **Web-Planer Client-Adapter (`planer/app/i18n.js`)**: Modulare i18n-Bibliothek für den Web-Planer mit Sprachauswahl-Dropdown im Kopfbereich, DOM-Retranslation via `data-i18n`, `lang`-Attribut-Aktualisierung, asynchronem Nachladen vom Server und autarkem Offline-Wörterbuch-Fallback.
- **Planer-Server Translations-API (`planer/server/planer_server.py`)**: Neuer Endpunkt `/api/translations` (Alias `/api/i18n`) zur sicheren Bereitstellung des Wörterbuchs über den lokalen Loopback-HTTP-Server.
- **Spanische Dokumentation (`README.es.md`)**: Vollständige spanische Übersetzung mit 100% Struktur- und Ankerparität zu `README.md` (17 Schnellnavigationspunkte, Invarianten- und Vergleichstabellen, Mermaid-Diagramme, Quickstarts).
- **Automatisierte Testabdeckung & Audit**: 4 neue Desktop-UI-Tests in `Recorder/tests/test_ui_i18n.py` und 5 neue Planer/API/Doku-Tests in `tests/test_planer_i18n.py`; `manage_translations.py --check` meldet 100% Audit-Bestanden; Gesamtsuite mit 500+ Tests 100% grün.

## [0.1.5] - 2026-09-14

### Discoverability, 17-Punkte-Navigation, Vergleichsmatrix & Drittanbieter-Lizenzaudit (Pfad B) [G 2026-09-14]
- **17-Punkte Schnellnavigation & Bilinguale Ankerparität**: `README.md` und `README_de.md` um Zielgruppen & Auffindbarkeit, Vergleichsmatrix und Drittanbieter-Lizenzen auf 17 Schnellnavigationspunkte erweitert mit 100% mutualer Ankerparität.
- **Zielgruppen & SEO-Auffindbarkeit**: 4 Kern-Personas (`[PERSONA-01]` bis `[PERSONA-04]`) sowie High-Intent Suchbegriffe auf Deutsch und Englisch für Podcaster, Streamer, Medienplaner und Multi-Agenten-Entwickler integriert.
- **10-Dimensionale Vergleichsmatrix**: Umfassender technischer Vergleich von Klangpult light gegenüber Audacity, OBS Studio, Riverside.fm/Descript und Ad-Hoc OS-Tools über alle 10 Governance-Invarianten (`INV-LOCAL-01` bis `INV-SLA-10`).
- **Drittanbieter-Lizenz- & Transparenz-Audit (`THIRD_PARTY_LICENSES.md`)**: Vollständiges SPDX-Lizenzaudit aller Laufzeit- und Entwicklungsbibliotheken (PySide6 LGPL-3.0 dynamische Bindung nach LGPLv3 § 4, sounddevice, soundfile, numpy, websockets, mss, opencv-python, faster-whisper, FFmpeg Subprozess-Isolation, Zero-Copyleft-Garantie auf Nutzermedien).
- **PEP 621 Projekt-Metadaten**: `pyproject.toml` URLs um `Third-Party Licenses` und `Marketing Log` erweitert.
- **Automatisierte Vertragstests**: `tests/test_metadata.py` um Prüfungen für die 17-Punkte-Navigation, 4 Personas, 10-dimensionale Vergleichsmatrix, Governance-Invarianten, Third-Party URLs und `THIRD_PARTY_LICENSES.md` erweitert.

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
### Hinzugefügt / Added (Web-Bridge-Status 2026-08-20)
- Der lokale Planer stellt mit `GET /api/status` einen datenfreien Readback für
  Library- und Projects-Dienst bereit. Die Kopfzeile unterscheidet nun
  vollständige Verbindung, Teilausfall und fehlende Recorder-Bridge, ohne dafür
  Aufnahmen oder Projekte laden zu müssen.
- Regressionen decken Online-, Teil- und Offline-Status des Proxy-Verbunds sowie
  die verständliche sichtbare Teilausfallanzeige ab.

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

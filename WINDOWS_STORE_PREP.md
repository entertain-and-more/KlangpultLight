# Windows Store Preparation & Packaging Guide — Klangpult light

- **Stand:** 2026-11-15
- **Version:** 0.1.0.0 (Store Package) / 0.1.0 (Core Engine)
- **Standard:** Tier-2 6-Sprachen-Harmonisierung nach Policy P-006 · Multi-Target-Architektur siehe [`PORTIERUNGSPLAN.md`](./PORTIERUNGSPLAN.md)

## Übersicht

Klangpult light wird als modernes Desktop-Bridge-Paket (MSIX / Centennial) für den Microsoft Windows Store paketiert. Das Paket kapselt die lokale PySide6-Desktop-Anwendung zusammen mit den Audio-Recording-Engines, dem Soundboard-Player, den 6-Sprachen-Wörterbüchern (`locales/translations.json`) und der eingebetteten lokalen Planer-PWA (`planer/`) in einer sicheren, offline-fähigen Windows-Desktop-Container-Umgebung (`RunAsInvoker`, keinerlei UAC-Elevation).

## Metadaten & Identität

- **Publisher-DN:** `CN=52596601-BAB4-4F3F-B182-E8F3F273B202`
- **Publisher Display Name:** `Geiger`
- **Package Identity:** `Geiger.KlangpultLight`
- **Package Version:** `0.1.0.0`
- **Processor Architecture:** `x64`
- **Target Device Family:** `Windows.Desktop` (MinVersion `10.0.17763.0`, MaxVersionTested `10.0.26100.0`)
- **Capabilities:** `runFullTrust`, `microphone`, `internetClient` (Local Loopback `127.0.0.1` / optionales Studio-LAN)
- **Category:** `Music`
- **Age Rating:** `3+`
- **Zielsprachen (Tier-2):** `de-DE`, `en-US`, `es-ES`, `zh-CN`, `ja-JP`, `ru-RU`
- **Hauptprogramm:** `KlangpultLightRecorder.exe`
- **CLI Execution Alias:** keiner deklariert (`AppxManifest.xml` registriert bewusst keinen `<uap5:AppExecutionAlias>`, Start über Startmenü-/Store-Kachel)

## Staging & Artefakte

Das Staging-Verzeichnis `releases/windowsstore/` enthält alle für die Einreichung im Partner Center erforderlichen Artefakte:
1. `store_settings.json`: Synchronisierte Metadaten mit Kurzbeschreibungen und Keywords.
2. `StoreLogo.png`: Partner-Center-konformes 50×50 PNG-Logo.
3. `icons/`: Vollständiges Kachel- und Logo-Set (Square44, Square50, Square150, Wide310, Square310).
4. `store_listing_<lang>.md`: 6 eigenständige Staging-Dateien für Deutsch, Englisch, Spanisch, Chinesisch, Japanisch und Russisch.
5. `BUILD.md`: Technische Dokumentation zur Erstellung der Binärdateien, des MSIX-Staging-Ordners (`build/msix_stage`) und des WACK-Laufs.
6. `WACK_PROTOCOL.md`: Kriterienkatalog und Testprotokoll für das Windows App Certification Kit (`scripts/run_windows_wack.py`).

## Partner Center Richtlinie 10.1.3 Compliance

Alle Schlüsselwörter genügen den Richtlinien von Microsoft Partner Center:
- Genau 7 Keywords je Zielsprache.
- Jedes Keyword ist maximal 30 Zeichen lang.
- Keine fremden, geschützten Markennamen (kein „Microsoft“, „Windows“, etc.).
- Relevante und präzise Suchbegriffe für Podcast-Aufnahme, Audio-Workstations und Medienplanung.

## Frozen-Packaging-Garantien (PyInstaller Onefile & Onedir)

Sowohl `KlangpultLightRecorder.spec` als auch `KlangpultLightRecorderOnedir.spec` bündeln alle fünf Laufzeit-Datenbäume explizit:
- `("shared", "shared")`
- `("planer", "planer")` (inklusive `manifest.json`, `sw.js` und `app/pwa.js`)
- `("assets", "assets")`
- `("mobile_icons", "mobile_icons")` (für allowlist-geschützte PWA-Icons ohne Datei-Duplikate)
- `("locales", "locales")` (damit alle 6 Tier-2-Sprachen auch im Frozen-EXE-/MSIX-Betrieb sofort ohne Key-Fallback geladen werden)

## Automatisierte Validierung & WACK-Preflight

1. **Store-Readiness-Preflight (`60+` Prüfungen inkl. Multi-Target- & PWA-Gates):**
   ```cmd
   python scripts/check_store_readiness.py
   ```
2. **Hermetischer Windows App Certification Kit (WACK) Preflight-Runner:**
   ```cmd
   python scripts/run_windows_wack.py
   ```
   *(Optional gegen ein gebautes `.msix` mit installiertem Windows SDK `appcert.exe`: `python scripts/run_windows_wack.py --msix releases/windowsstore/Geiger.KlangpultLight_0.1.0.0_x64.msix --invoke-appcert`)*
3. **Zustandsisolierter Cross-Platform- & Store-Smoke-Test:**
   ```cmd
   python tests/source_platform_smoke.py
   ```
4. **Dauerhafte Pytest-Vertragssicherung:**
   `tests/test_store_materials.py` und `tests/test_multitarget_porting_and_pwa.py`.

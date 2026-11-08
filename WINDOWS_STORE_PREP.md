# Windows Store Preparation & Packaging Guide — Klangpult light

Stand: 2026-11-08  
Version: 0.1.0.0 (Store Package) / 0.1.0 (Core Engine)  
Tier-2 6-Sprachen-Harmonisierung nach Policy P-006

## Übersicht

Klangpult light wird als modernes Desktop-Bridge-Paket (MSIX / Centennial) für den Microsoft Windows Store paketiert. Das Paket kapselt die lokale PySide6-Desktop-Anwendung zusammen mit den Audio-Recording-Engines, dem Soundboard-Player und dem eingebetteten lokalen Web-Planer in einer sicheren, offline-fähigen Windows-Desktop-Container-Umgebung.

## Metadaten & Identität

- **Publisher-DN:** `CN=52596601-BAB4-4F3F-B182-E8F3F273B202`
- **Publisher Display Name:** `Geiger`
- **Package Identity:** `Geiger.KlangpultLight`
- **Package Version:** `0.1.0.0`
- **Target Device Family:** `Windows.Desktop` (MinVersion `10.0.17763.0`, MaxVersionTested `10.0.26100.0`)
- **Capabilities:** `runFullTrust`, `microphone`, `internetClient` (Local Loopback)
- **Category:** `Music`
- **Age Rating:** `3+`
- **Zielsprachen (Tier-2):** `de-DE`, `en-US`, `es-ES`, `zh-CN`, `ja-JP`, `ru-RU`
- **Hauptprogramm:** `KlangpultLightRecorder.exe`
- **Execution Alias:** `klangpultlight.exe`

## Staging & Artefakte

Das Staging-Verzeichnis `releases/windowsstore/` enthält alle für die Einreichung im Partner Center erforderlichen Artefakte:
1. `store_settings.json`: Synchronisierte Metadaten mit Kurzbeschreibungen und Keywords.
2. `StoreLogo.png`: Partner-Center-konformes 50×50 PNG-Logo.
3. `icons/`: Vollständiges Kachel- und Logo-Set (Square44, Square50, Square150, Wide310, Square310).
4. `store_listing_<lang>.md`: 6 eigenständige Staging-Dateien für Deutsch, Englisch, Spanisch, Chinesisch, Japanisch und Russisch.
5. `BUILD.md`: Technische Dokumentation zur Erstellung der Binärdateien und des MSIX-Containers.
6. `WACK_PROTOCOL.md`: Kriterienkatalog und Testprotokoll für das Windows App Certification Kit.

## Partner Center Richtlinie 10.1.3 Compliance

Alle Schlüsselwörter genügen den Richtlinien von Microsoft Partner Center:
- Genau 7 Keywords je Zielsprache.
- Jedes Keyword ist maximal 30 Zeichen lang.
- Keine fremden, geschützten Markennamen (kein "Microsoft", "Windows", etc.).
- Relevante und präzise Suchbegriffe für Podcast-Aufnahme, Audio-Workstations und Medienplanung.

## Automatisierte Validierung

Der Preflight-Linter `scripts/check_store_readiness.py` führt über 50 hermetische Prüfungen durch:
```cmd
python scripts/check_store_readiness.py
```
Zusätzlich sichert `tests/test_store_materials.py` die Verträge dauerhaft im Rahmen der Pytest-Testsuite ab.

# Windows App Certification Kit (WACK) Protokoll — Klangpult light

## Übersicht
- **Anwendung:** Klangpult light (Desktop Bridge / Centennial)
- **Version:** `0.1.0.0` (Core `0.1.0`)
- **Paket-Identität:** `Geiger.KlangpultLight`
- **Herausgeber:** `CN=52596601-BAB4-4F3F-B182-E8F3F273B202` (`Geiger`)
- **Zielarchitektur:** `x64` (explizit gebunden für PyInstaller-64-Bit-PE)
- **Ausführungsmodus:** `Windows.FullTrustApplication` (`runFullTrust`, `RunAsInvoker`, keine UAC-Elevation)
- **Automatisierter Prüf-Runner:** `python scripts/run_windows_wack.py [--json]`

## Prüfungsbereiche & Kriterien

1. **Appx-Manifest-Konformität (`_check_manifest_wack_rules`):**
   - [x] Schema-Wohlgeformtheit nach Windows 10/11 Manifest-Definition (`MinVersion="10.0.17763.0"`, `MaxVersionTested="10.0.26100.0"`).
   - [x] Korrekte Deklaration von `runFullTrust`, `internetClient` (lokaler Loopback `127.0.0.1`) und `microphone`.
   - [x] Keine verbotenen Elevation-Attribute (`requireAdministrator`, `highestAvailable`, `allowElevation`).
   - [x] Deklaration aller 6 Tier-2-Ressourcensprachen (`de-de`, `en-us`, `es-es`, `zh-cn`, `ja-jp`, `ru-ru`).
   - [x] Alle im Manifest referenzierten Kachel-, Logo- und Splash-Ressourcen (`icons\*.png`) existieren physisch als valide RGB/RGBA-PNGs.

2. **Frozen-Packaging & Laufzeit-Sicherheit (`_check_frozen_packaging_and_security`):**
   - [x] `KlangpultLightRecorder.spec` und `KlangpultLightRecorderOnedir.spec` deaktivieren UAC-Elevation (`uac_admin=False`) und bündeln `shared`, `planer`, `assets`, `mobile_icons` und `locales`.
   - [x] `Recorder/i18n/translator.py` löst `locales/translations.json` deterministisch auch unter PyInstaller `_MEIPASS` und `_internal` auf (verhindert rohe Schlüsselnamen im Frozen-MSIX-Betrieb).
   - [x] 100 % Local-First & Zero-Egress (`INV-LOCAL-01`): `BridgeService` und `PlanerServer` binden standardmäßig strikt auf `127.0.0.1`.

3. **Dateisystem, Partner-Center-Richtlinie 10.1.3 & Multi-Target-Hygiene (`_check_partner_center_policy_10_1_3`):**
   - [x] Vollständiges Logo-Set (`StoreLogo.png` 50×50, Square44, Square50, Square150, Wide310, Square310).
   - [x] Synchronisierte Identitäts-, Lizenz- (`Freeware`) und Sprachmetadaten zwischen `store_package.json` und `releases/windowsstore/store_settings.json`.
   - [x] Lokalisierte Store-Listings für alle 6 Tier-2-Sprachen (Kurzbeschreibung ≤ 100 Zeichen, je exakt 7 markenrechtsfreie Keywords ≤ 30 Zeichen).

## Testergebnis
- **Status:** PASS (`0` Beanstandungen in `scripts/run_windows_wack.py`, `scripts/check_store_readiness.py` und `tests/source_platform_smoke.py`; Partner-Center-Upload wartet regulär auf manuelle Nutzerfreigabe).
- **Letzte Prüfung:** 2026-11-15

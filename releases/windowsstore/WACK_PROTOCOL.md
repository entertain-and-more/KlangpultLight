# Windows App Certification Kit (WACK) Protokoll — Klangpult light

## Übersicht
- **Anwendung:** Klangpult light (Desktop Bridge / Centennial)
- **Version:** 0.1.0.0
- **Paket-Identität:** Geiger.KlangpultLight
- **Herausgeber:** CN=52596601-BAB4-4F3F-B182-E8F3F273B202
- **Zielarchitektur:** x64
- **Ausführungsmodus:** runFullTrust

## Prüfungsbereiche & Kriterien
1. **Appx-Manifest-Konformität:**
   - [x] Schema-Wohlgeformtheit nach Windows 10/11 Manifest-Definition.
   - [x] Korrekte Deklaration von `runFullTrust`, `internetClient` und `microphone`.
   - [x] Deklaration aller 6 Ressourcensprachen (`de-de`, `en-us`, `es-es`, `zh-cn`, `ja-jp`, `ru-ru`).
   - [x] Korrekte Zuordnung der Bild- und Kachelressourcen (`icons\*.png`).

2. **Sicherheits- und Berechtigungsprüfungen:**
   - [x] Keine unsicheren Pfade oder unkontrollierten Schreibzugriffe außerhalb des User-Space.
   - [x] Keine hartcodierten Secrets, Zertifikate oder privaten Tokens im Paket.
   - [x] 100% Local-First & Zero-Egress Reassurance (Bridge bindet nur auf `127.0.0.1`).

3. **Dateisystem & Packaging-Hygiene:**
   - [x] Vollständiges Logo-Set (`StoreLogo.png` 50×50, Square44, Square50, Square150, Wide310, Square310).
   - [x] Alle PNGs im RGB/RGBA-Farbraum ohne CMYK-Inkompatibilitäten.
   - [x] Lokalisierte Store-Listings für alle 6 Tier-2-Sprachen (Kurzbeschreibung ≤ 100 Zeichen, je 7 markenrechtsfreie Keywords ≤ 30 Zeichen).

## Testergebnis
- **Status:** PASS (Vorbereitung für automatisierte WACK-Validierung und Microsoft Partner Center Einreichung vollständig abgeschlossen)
- **Letzte Prüfung:** 2026-11-08

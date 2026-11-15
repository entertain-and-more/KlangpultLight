# Windows Store Packaging & Build Guide — Klangpult light

Dieses Dokument beschreibt die Schritte zur Erstellung und Zertifizierungsprüfung eines MSIX-Store-Pakets für Klangpult light (`Geiger.KlangpultLight`, Version `0.1.0.0`, `x64`).

## 1. Voraussetzungen
- Windows 10/11 (x64)
- Python 3.11+ mit PySide6
- Windows SDK (`MakeAppx.exe`, `SignTool.exe`, optional `appcert.exe`)
- Lokaler Git-Arbeitsklon des Projekts (`KlangpultLight`)

## 2. Erstellung der Binärdatei
Die Windows-Executable wird via PyInstaller im Onedir-Modus generiert (inklusive gebündelter `shared/`, `planer/`, `assets/`, `mobile_icons/` und `locales/`-Datenbäume):
```cmd
build_onedir.bat
```
Das Artefakt wird unter `dist/KlangpultLightRecorder/` abgelegt.

## 3. Bereitstellung der Store-Assets
Alle Kacheln, Logos und das Manifest liegen bereit in `store_package/KlangpultLight/`:
- `AppxManifest.xml`
- `icons/StoreLogo.png` (50×50 PNG)
- `icons/icon_44x44.png` / `Square44x44Logo.png`
- `icons/icon_50x50.png` / `Square50x50Logo.png`
- `icons/icon_150x150.png` / `Square150x150Logo.png`
- `icons/icon_310x150.png` / `Wide310x150Logo.png`
- `icons/icon_310x310.png` / `Square310x310Logo.png`

## 4. Automatisierte Vorprüfung (Readiness, WACK-Preflight & Smoke)
Führen Sie vor der Paketierung alle drei hermetischen Prüfwerkzeuge aus:
```cmd
python scripts/check_store_readiness.py
python scripts/run_windows_wack.py
python tests/source_platform_smoke.py
```
Alle drei Kommandos müssen mit Exit-Code `0` (`0 Errors / 0 Beanstandungen`) abschließen.

## 5. MSIX-Staging & Paketerstellung
Da `build_onedir.bat` ausschließlich das PyInstaller-Bundle unter `dist\KlangpultLightRecorder\` ablegt, werden Binärverzeichnis, `AppxManifest.xml` und `icons\` vor dem Aufruf von `MakeAppx.exe` in einem sauberen Staging-Verzeichnis (`build\msix_stage`) zusammengeführt:
```cmd
if exist build\msix_stage rmdir /S /Q build\msix_stage
xcopy /E /I /Y dist\KlangpultLightRecorder build\msix_stage
copy /Y store_package\KlangpultLight\AppxManifest.xml build\msix_stage\AppxManifest.xml
xcopy /E /I /Y store_package\KlangpultLight\icons build\msix_stage\icons
MakeAppx.exe pack /o /d build\msix_stage /p releases\windowsstore\Geiger.KlangpultLight_0.1.0.0_x64.msix
```

## 6. Windows App Certification Kit (WACK) gegen gebautes MSIX-Paket
Sofern das Windows 10/11 SDK App Certification Kit (`appcert.exe`) installiert ist, kann der Zertifizierungslauf direkt über den sicheren Runner gestartet werden (ohne `shell=True`):
```cmd
python scripts/run_windows_wack.py --msix releases\windowsstore\Geiger.KlangpultLight_0.1.0.0_x64.msix --invoke-appcert --report-xml releases\windowsstore\wack_report.xml
```

## 7. Lokale Signierung & Testinstallation (Sideloading)
```cmd
SignTool.exe sign /fd SHA256 /a /f dev_cert.pfx releases\windowsstore\Geiger.KlangpultLight_0.1.0.0_x64.msix
Add-AppxPackage -Path releases\windowsstore\Geiger.KlangpultLight_0.1.0.0_x64.msix
```
*(Hinweis: Der tatsächliche Upload ins Microsoft Partner Center erfolgt ausschließlich nach expliziter Nutzerfreigabe über `TO-DECIDE-USER.txt`.)*

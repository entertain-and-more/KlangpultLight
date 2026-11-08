# Windows Store Packaging & Build Guide — Klangpult light

Dieses Dokument beschreibt die Schritte zur Erstellung eines zertifizierungsfähigen MSIX-Store-Pakets für Klangpult light.

## 1. Voraussetzungen
- Windows 10/11 (x64)
- Python 3.11+ mit PySide6
- Windows SDK (MakeAppx.exe, SignTool.exe)
- Lokales Code-Repository: `C:\_Local_DEV\repos\KlangpultLight`

## 2. Erstellung der Binärdatei
Die Windows-Executable wird via PyInstaller im onedir-Modus generiert:
```cmd
build_onedir.bat
```
Das Artefakt wird unter `dist/KlangpultLightRecorder/` abgelegt.

## 3. Bereitstellung der Store-Assets
Alle Kacheln, Logos und Splashscreens liegen bereit in `store_package/KlangpultLight/icons/`:
- `StoreLogo.png` (50×50 PNG)
- `icon_44x44.png` / `Square44x44Logo.png`
- `icon_50x50.png` / `Square50x50Logo.png`
- `icon_150x150.png` / `Square150x150Logo.png`
- `icon_310x150.png` / `Wide310x150Logo.png`
- `icon_310x310.png` / `Square310x310Logo.png`

## 4. Validierung vor der Paketierung
Führen Sie den Store-Readiness-Preflight-Check aus:
```cmd
python scripts/check_store_readiness.py
```
Ergebnis muss `0 Errors / 0 Warnings` sein.

## 5. MSIX-Paketerstellung
Mit dem Windows SDK `MakeAppx.exe` wird das MSIX-Paket gebaut:
```cmd
MakeAppx.exe pack /d dist\KlangpultLightRecorder /p releases\windowsstore\Geiger.KlangpultLight_0.1.0.0_x64.msix
```

## 6. Lokale Signierung & Testinstallation (Sideloading)
```cmd
SignTool.exe sign /fd SHA256 /a /f dev_cert.pfx releases\windowsstore\Geiger.KlangpultLight_0.1.0.0_x64.msix
Add-AppxPackage -Path releases\windowsstore\Geiger.KlangpultLight_0.1.0.0_x64.msix
```

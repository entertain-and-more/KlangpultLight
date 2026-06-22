# PodcastPackages

Schlanke Aufspaltung des `DEV_USBPodcastStudio` in **zwei eigenständige Tools**:

- **`Recorder/`** — PodcastRecorder, Desktop-App (Python/PySide6): aufnehmen
  (Audio + Video + gemeinsames Audio-Videoboard, Aufnahmen mit Branches,
  Quellen-Auto-Erkennung, „aufnehmen was am PC läuft", Live-Transkription als
  Motor für Monitor/Teleprompter).
- **`Planung/`** — PodcastPlaner, Web-App (später): planen (Bibliothek,
  Projektplanung, Assets/Line, KI-Monitor, Teleprompter).

**Bewusst weggelassen:** Postproduction, Cutter, Batch-Transkription (SRT/TXT-Export), OCR, Upload.

Konzept: [KONZEPT.md](./KONZEPT.md) · Umsetzungsplan: [TODO.md](./TODO.md)

## Planer — Quickstart

```powershell
# Einfachster Start (PodcastRecorder muss vorher laufen)
.\START_PLANER.bat

# Oder manuell
$env:PYTHONIOENCODING = "utf-8"
python planer/start.py

# Browser öffnet sich automatisch auf http://127.0.0.1:8770
# Ports konfigurierbar via Umgebungsvariablen:
#   PLANER_PORT=8770  LIBRARY_PORT=8767  PROJECTS_PORT=8769
```

Der Planer erfordert einen laufenden PodcastRecorder (Bridge auf Ports 8767 + 8769).
Ohne Recorder läuft er als reines Planungstool für Projekte/Episoden weiter;
die Bibliothek zeigt in diesem Fall einen Offline-Hinweis.

## Recorder — Quickstart

```powershell
# Einfachster Start
.\START_RECORDER.bat

# venv (NIEMALS in OneDrive!)
python -m venv C:\_Local_DEV\venvs\podcast_packages
C:\_Local_DEV\venvs\podcast_packages\Scripts\activate
pip install -r Recorder\requirements.txt

# App starten (flaches Layout: aus Recorder/ heraus)
cd Recorder
$env:PYTHONIOENCODING = "utf-8"
python main.py

# Headless-Selftest (kein Fenster)
$env:PODCAST_RECORDER_SELFTEST = "1"
$env:PYTHONIOENCODING = "utf-8"
python main.py

# Tests
$env:PYTHONIOENCODING = "utf-8"
python -m pytest tests -q
```

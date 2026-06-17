# PodcastPackages

Schlanke Aufspaltung des `DEV_USBPodcastStudio` in **zwei eigenständige Tools**:

- **`recorder/`** — PodcastRecorder, Desktop-App (Python/PySide6): aufnehmen
  (Audio + Video + gemeinsames Audio-Videoboard, Aufnahmen mit Branches,
  Quellen-Auto-Erkennung, „aufnehmen was am PC läuft", Live-Transkription als
  Motor für Monitor/Teleprompter).
- **`planer/`** — PodcastPlaner, Web-App (später): planen (Bibliothek,
  Projektplanung, Assets/Line, KI-Monitor, Teleprompter).

**Bewusst weggelassen:** Postproduction, Cutter, Batch-Transkription (SRT/TXT-Export), OCR, Upload.

Konzept: [KONZEPT.md](./KONZEPT.md) · Umsetzungsplan: [TODO.md](./TODO.md)

## Recorder — Quickstart

```powershell
# venv (NIEMALS in OneDrive!)
python -m venv C:\_Local_DEV\venvs\podcast_packages
C:\_Local_DEV\venvs\podcast_packages\Scripts\activate
pip install -r recorder\requirements.txt

# App starten
$env:PYTHONIOENCODING = "utf-8"
python -m recorder.main

# Headless-Selftest (kein Fenster)
$env:PODCAST_RECORDER_SELFTEST = "1"
$env:QT_QPA_PLATFORM = "offscreen"
$env:PYTHONIOENCODING = "utf-8"
python -m recorder.main

# Tests
$env:PYTHONIOENCODING = "utf-8"
python -m pytest recorder/tests -q
```

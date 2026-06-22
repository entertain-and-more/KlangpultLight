@echo off
REM PodcastPlaner starten — erfordert PodcastRecorder im Hintergrund
REM (Bridge muss auf Port 8767/8769 laufen)

set PYTHONIOENCODING=utf-8
set PLANER_PORT=8770

echo Starte PodcastPlaner auf http://127.0.0.1:%PLANER_PORT% ...
echo PodcastRecorder muss separat laufen (START_RECORDER.bat).
echo Stoppen mit Ctrl+C.
echo.

"C:\_Local_DEV\venvs\podcast_packages\Scripts\python.exe" "%~dp0planer\start.py"

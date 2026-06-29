@echo off
REM Klangpult light - Planer starten — erfordert Klangpult light - Recorder im Hintergrund
REM (Bridge muss auf Port 8767/8769 laufen)

set PYTHONIOENCODING=utf-8
set PLANER_PORT=8770

echo Starte Klangpult light - Planer auf http://127.0.0.1:%PLANER_PORT% ...
echo Klangpult light - Recorder muss separat laufen (START_RECORDER.bat).
echo Stoppen mit Ctrl+C.
echo.

"C:\_Local_DEV\venvs\klangpult_light\Scripts\python.exe" "%~dp0planer\start.py"

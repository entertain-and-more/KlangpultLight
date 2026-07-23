@echo off
REM Klangpult light - Planer starten — erfordert Klangpult light - Recorder im Hintergrund
REM (Bridge muss auf Port 8767/8769 laufen)

set PYTHONIOENCODING=utf-8
set PLANER_PORT=8770
set "VENV_PY=C:\_Local_DEV\venvs\klangpult_light\Scripts\python.exe"
if not exist "%VENV_PY%" set "VENV_PY=C:\_Local_DEV\venvs\podcast_packages\Scripts\python.exe"

if not exist "%VENV_PY%" (
  echo [FEHLER] Keine passende Python-Venv gefunden.
  echo Erwartet wurde eine dieser Venvs:
  echo   C:\_Local_DEV\venvs\klangpult_light
  echo   C:\_Local_DEV\venvs\podcast_packages
  pause
  exit /b 1
)

echo Starte Klangpult light - Planer auf http://127.0.0.1:%PLANER_PORT% ...
echo Klangpult light - Recorder muss separat laufen (START_RECORDER.bat).
echo Stoppen mit Ctrl+C.
echo.

"%VENV_PY%" "%~dp0planer\start.py"

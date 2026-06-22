@echo off
REM PodcastPackages — kombinierter Start (KONZEPT §9.2: eine zu startende Sache)
REM
REM Startet PodcastRecorder (inkl. Bridge) im Hintergrund, wartet kurz bis
REM die Bridge hochgefahren ist, dann startet PodcastPlaner und öffnet den Browser.
REM
REM Einzeln starten (für Entwicklung / Debugging):
REM   START_RECORDER.bat  — nur Recorder + Bridge
REM   START_PLANER.bat    — nur Planer (Recorder muss separat laufen)

setlocal
chcp 65001 >nul

set "VENV_PY=C:\_Local_DEV\venvs\podcast_packages\Scripts\python.exe"
set "PYTHONIOENCODING=utf-8"
set "PLANER_PORT=8770"

if not exist "%VENV_PY%" (
  echo [FEHLER] Venv fehlt: %VENV_PY%
  echo Bitte einrichten: python -m venv C:\_Local_DEV\venvs\podcast_packages
  pause
  exit /b 1
)

echo ============================================================
echo  PodcastPackages starten
echo ============================================================
echo.
echo [1/2] PodcastRecorder + Bridge starten (Hintergrund)...
start "" /B cmd /C "call ""%~dp0Recorder\START.bat"""

echo [2/2] 3 Sekunden warten bis Bridge hochgefahren...
timeout /t 3 /nobreak >nul

echo [2/2] PodcastPlaner starten auf http://127.0.0.1:%PLANER_PORT% ...
echo.
echo Beide Dienste laufen. Planer mit Ctrl+C beenden (Recorder separat schliessen).
echo.

"%VENV_PY%" "%~dp0planer\start.py"

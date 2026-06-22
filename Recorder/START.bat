@echo off
setlocal
chcp 65001 >nul

set "RECORDER_DIR=%~dp0"
set "VENV_PY=C:\_Local_DEV\venvs\podcast_packages\Scripts\python.exe"
set "PYTHONIOENCODING=utf-8"

if not exist "%VENV_PY%" (
  echo [FEHLER] Recorder-Venv fehlt:
  echo   %VENV_PY%
  echo.
  echo Bitte einmal einrichten:
  echo   python -m venv C:\_Local_DEV\venvs\podcast_packages
  echo   C:\_Local_DEV\venvs\podcast_packages\Scripts\python.exe -m pip install -r "%RECORDER_DIR%requirements.txt"
  echo.
  pause
  exit /b 1
)

"%VENV_PY%" -c "import PySide6, sounddevice, numpy, soundfile, cv2, mss, websockets, jsonschema" >nul 2>nul
if errorlevel 1 (
  echo [setup] Installiere fehlende Recorder-Abhängigkeiten...
  "%VENV_PY%" -m pip install -r "%RECORDER_DIR%requirements.txt"
  if errorlevel 1 (
    echo.
    echo [FEHLER] Abhängigkeiten konnten nicht installiert werden.
    pause
    exit /b 1
  )
)

cd /d "%RECORDER_DIR%"
"%VENV_PY%" main.py
exit /b %ERRORLEVEL%

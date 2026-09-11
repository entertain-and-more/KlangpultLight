@echo off
REM ============================================================
REM  Klangpult light - Desktop-Verknuepfung anlegen
REM ============================================================
setlocal
chcp 65001 >nul

cd /d "%~dp0"
set "PYTHONIOENCODING=utf-8"

set "PY_CMD=python"
if exist "C:\_Local_DEV\venvs\podcast_packages\Scripts\python.exe" (
  set "PY_CMD=C:\_Local_DEV\venvs\podcast_packages\Scripts\python.exe"
) else if exist "C:\_Local_DEV\venvs\klangpult_light\Scripts\python.exe" (
  set "PY_CMD=C:\_Local_DEV\venvs\klangpult_light\Scripts\python.exe"
)

"%PY_CMD%" "%~dp0scripts\create_desktop_shortcut.py"
if errorlevel 1 (
  echo [FEHLER] Desktop-Verknuepfung konnte nicht angelegt werden.
  pause
  exit /b 1
)

echo [OK] Desktop-Verknuepfung wurde auf dem Desktop eingerichtet.
pause

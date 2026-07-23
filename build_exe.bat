@echo off
REM ============================================================
REM  Klangpult light - Recorder - EXE-Build (PyInstaller onefile)
REM
REM  Ausgabe:
REM    - C:\_Local_DEV\codex_build\klangpultlight_recorder\dist\KlangpultLightRecorder.exe
REM    - %~dp0KlangpultLightRecorder.exe
REM    - %~dp0Recorder\dist\KlangpultLightRecorder.exe
REM    - %~dp0releases\v0.1.0\KlangpultLightRecorder-0.1.0-win64.exe
REM ============================================================
setlocal
chcp 65001 >nul

cd /d "%~dp0"
set "PYTHONIOENCODING=utf-8"
set "VENV_PY=C:\_Local_DEV\venvs\podcast_packages\Scripts\python.exe"
set "BUILD_ROOT=C:\_Local_DEV\codex_build\klangpultlight_recorder"
set "DIST_EXE=%BUILD_ROOT%\dist\KlangpultLightRecorder.exe"
set "ROOT_EXE=%~dp0KlangpultLightRecorder.exe"
set "RECORDER_DIST_DIR=%~dp0Recorder\dist"
set "RECORDER_DIST_EXE=%RECORDER_DIST_DIR%\KlangpultLightRecorder.exe"
set "RELEASE_DIR=%~dp0releases\v0.1.0"
set "RELEASE_EXE=%RELEASE_DIR%\KlangpultLightRecorder-0.1.0-win64.exe"
set "INTERACTIVE_PAUSE=%KLANGPULTLIGHT_INTERACTIVE%"

if not exist "%VENV_PY%" (
  echo [FEHLER] Recorder-Venv fehlt:
  echo   %VENV_PY%
  echo.
  echo Bitte einmal einrichten:
  echo   python -m venv C:\_Local_DEV\venvs\podcast_packages
  echo   C:\_Local_DEV\venvs\podcast_packages\Scripts\python.exe -m pip install -r "%~dp0Recorder\requirements.txt"
  echo.
  if /i "%INTERACTIVE_PAUSE%"=="1" pause
  exit /b 1
)

"%VENV_PY%" -c "import PyInstaller, PySide6, sounddevice, numpy, soundfile, cv2, mss, websockets, jsonschema" >nul 2>nul
if errorlevel 1 (
  echo [setup] Installiere fehlende Build-/Runtime-Abhängigkeiten...
  "%VENV_PY%" -m pip install -r "%~dp0Recorder\requirements.txt" "pyinstaller>=6.0"
  if errorlevel 1 (
    echo.
    echo [FEHLER] Abhängigkeiten konnten nicht installiert werden.
    if /i "%INTERACTIVE_PAUSE%"=="1" pause
    exit /b 1
  )
)

if not exist "%RECORDER_DIST_DIR%" mkdir "%RECORDER_DIST_DIR%" >nul 2>nul
if not exist "%RELEASE_DIR%" mkdir "%RELEASE_DIR%" >nul 2>nul

"%VENV_PY%" -m PyInstaller "%~dp0KlangpultLightRecorder.spec" --noconfirm --clean ^
  --workpath "%BUILD_ROOT%\build" ^
  --distpath "%BUILD_ROOT%\dist"
if errorlevel 1 goto fail

copy /y "%DIST_EXE%" "%ROOT_EXE%" >nul
copy /y "%DIST_EXE%" "%RECORDER_DIST_EXE%" >nul
copy /y "%DIST_EXE%" "%RELEASE_EXE%" >nul

"%VENV_PY%" -c "import hashlib, pathlib; base = pathlib.Path(r'%RELEASE_DIR%'); entries = [f'{hashlib.sha256(file.read_bytes()).hexdigest().upper()}  {file.name}' for file in sorted(base.glob('*.exe'))]; (base / 'SHA256SUMS.txt').write_text('\n'.join(entries) + '\n', encoding='utf-8')"
if errorlevel 1 goto fail

echo.
echo Build OK:
echo   %ROOT_EXE%
echo   %RECORDER_DIST_EXE%
echo   %RELEASE_EXE%
goto end

:fail
echo.
echo BUILD FEHLGESCHLAGEN
if /i "%INTERACTIVE_PAUSE%"=="1" pause
exit /b 1

:end
if /i "%INTERACTIVE_PAUSE%"=="1" pause

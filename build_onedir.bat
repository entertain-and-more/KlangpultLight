@echo off
REM ============================================================
REM  Klangpult light - Recorder - Onedir-Build (PyInstaller onedir)
REM
REM  Ausgabe:
REM    - C:\_Local_DEV\codex_build\klangpultlight_recorder_onedir\dist\KlangpultLightRecorder\
REM    - %~dp0dist\KlangpultLightRecorder\
REM    - %~dp0releases\v0.1.0\onedir\KlangpultLightRecorder\
REM ============================================================
setlocal
chcp 65001 >nul

cd /d "%~dp0"
set "PYTHONIOENCODING=utf-8"
set "VENV_PY=C:\_Local_DEV\venvs\podcast_packages\Scripts\python.exe"
set "BUILD_ROOT=C:\_Local_DEV\codex_build\klangpultlight_recorder_onedir"
set "DIST_DIR=%BUILD_ROOT%\dist\KlangpultLightRecorder"
set "DEST_DIST_DIR=%~dp0dist\KlangpultLightRecorder"
set "RELEASE_ONEDIR=%~dp0releases\v0.1.0\onedir\KlangpultLightRecorder"
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

if not exist "%~dp0dist" mkdir "%~dp0dist" >nul 2>nul
if not exist "%~dp0releases\v0.1.0\onedir" mkdir "%~dp0releases\v0.1.0\onedir" >nul 2>nul

"%VENV_PY%" -m PyInstaller "%~dp0KlangpultLightRecorderOnedir.spec" --noconfirm --clean ^
  --workpath "%BUILD_ROOT%\build" ^
  --distpath "%BUILD_ROOT%\dist"
if errorlevel 1 goto fail

if exist "%DEST_DIST_DIR%" rmdir /s /q "%DEST_DIST_DIR%" >nul 2>nul
xcopy /e /i /y "%DIST_DIR%" "%DEST_DIST_DIR%" >nul

if exist "%RELEASE_ONEDIR%" rmdir /s /q "%RELEASE_ONEDIR%" >nul 2>nul
xcopy /e /i /y "%DIST_DIR%" "%RELEASE_ONEDIR%" >nul

"%VENV_PY%" -c "import hashlib, pathlib; base = pathlib.Path(r'%~dp0releases\v0.1.0\onedir'); exe_file = base / 'KlangpultLightRecorder' / 'KlangpultLightRecorder.exe'; (base / 'SHA256SUMS.txt').write_text(f'{hashlib.sha256(exe_file.read_bytes()).hexdigest().upper()}  KlangpultLightRecorder.exe\n', encoding='utf-8') if exe_file.is_file() else None"

echo.
echo Onedir-Build OK:
echo   %DEST_DIST_DIR%\KlangpultLightRecorder.exe
echo   %RELEASE_ONEDIR%\KlangpultLightRecorder.exe
goto end

:fail
echo.
echo ONEDIR-BUILD FEHLGESCHLAGEN
if /i "%INTERACTIVE_PAUSE%"=="1" pause
exit /b 1

:end
if /i "%INTERACTIVE_PAUSE%"=="1" pause

@echo off
setlocal
chcp 65001 >nul

call "%~dp0Recorder\START.bat"
exit /b %ERRORLEVEL%

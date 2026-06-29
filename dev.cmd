@echo off
REM Double-click shim so you can run the dev build without opening a terminal.
powershell -NoProfile -ExecutionPolicy Bypass -File "%~dp0dev.ps1"
pause

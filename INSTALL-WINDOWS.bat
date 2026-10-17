@echo off
setlocal
cd /d "%~dp0"
title LibreBeacon Setup
echo LibreBeacon setup - optional accessibility notifications
 echo.
echo This software is experimental. Keep your official Libre alarms enabled.
echo.
where py >nul 2>&1
if errorlevel 1 (
 echo Python was not found. Install Python 3.11 or later from https://www.python.org/downloads/windows/
 echo Then run INSTALL-WINDOWS.bat again.
 pause
 exit /b 1
)
py -3 -c "import sys; sys.exit(0 if sys.version_info >= (3,11) else 1)"
if errorlevel 1 (
 echo Python 3.11 or later is required.
 pause
 exit /b 1
)
if not exist ".venv\Scripts\python.exe" (
 py -3 -m venv .venv
 if errorlevel 1 goto failed
)
".venv\Scripts\python.exe" -m pip install -e .
if errorlevel 1 goto failed
echo.
echo Installation complete. Double-click run-windows.bat to open settings.
pause
exit /b 0
:failed
echo.
echo Installation did not finish. Check your internet connection and Python installation.
pause
exit /b 1

@echo off
setlocal
cd /d "%~dp0"
if not exist ".venv\Scripts\python.exe" (
 echo First double-click INSTALL-WINDOWS.bat.
 pause
 exit /b 1
)
".venv\Scripts\python.exe" -m librebeacon
if errorlevel 1 pause

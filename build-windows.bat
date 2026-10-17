@echo off
setlocal
cd /d "%~dp0"
if not exist ".venv\Scripts\python.exe" (
 echo Run INSTALL-WINDOWS.bat first.
 exit /b 1
)
".venv\Scripts\python.exe" -m pip install ".[windows-build]"
if errorlevel 1 exit /b 1
".venv\Scripts\python.exe" -m PyInstaller --noconfirm --clean --onefile --windowed --name LibreBeacon --collect-all keyring librebeacon_launcher.py
if errorlevel 1 exit /b 1
echo Executable created in dist\LibreBeacon.exe. Test on Windows before distributing.

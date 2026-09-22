@echo off
cd /d "%~dp0"
if not exist "%~dp0.venv\Scripts\pythonw.exe" (
  echo Python environment is missing. Run setup.ps1 first.
  pause
  exit /b 1
)
start "" "%~dp0.venv\Scripts\pythonw.exe" -m scripts.launch %*

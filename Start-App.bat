@echo off
setlocal enabledelayedexpansion
cd /d "%~dp0"
if not exist ".venv\Scripts\python.exe" (
    echo Creating Python virtual environment...
    py -3 -m venv .venv || (echo Python launcher not found. Install Python 3.11+ and try again.& pause & exit /b 1)
)
echo Installing/refreshing dependencies...
".\.venv\Scripts\python.exe" -m pip install --upgrade pip >nul
".\.venv\Scripts\pip.exe" install -r requirements.txt
echo Launching app...
".\.venv\Scripts\python.exe" app.py
pause

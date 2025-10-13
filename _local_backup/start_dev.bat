@echo off
setlocal ENABLEDELAYEDEXPANSION

REM === NewFarmDogWalking — Windows dev starter ===
REM - Creates/activates .venv
REM - Installs deps (+ python-dotenv)
REM - Applies migrations (reads .env)
REM - Starts Django dev server (http://localhost:8000)

REM Pick Python launcher
where py >nul 2>nul
if %errorlevel%==0 (
  set PYTHON=py
) else (
  set PYTHON=python
)

REM Create venv if missing
if not exist ".venv" (
  echo [setup] Creating virtual environment .venv ...
  %PYTHON% -m venv .venv
)

REM Activate venv
call .\.venv\Scripts\activate.bat
if errorlevel 1 (
  echo [error] Could not activate .venv
  exit /b 1
)

REM Upgrade pip + install deps
echo [setup] Installing dependencies ...
python -m pip install --upgrade pip >nul
if exist requirements.txt (
  python -m pip install -r requirements.txt
) else (
  echo [warn] requirements.txt not found; continuing.
)

REM Ensure .env support
python -m pip install python-dotenv

REM Migrate with .env loaded
echo [migrate] Applying Django migrations ...
python -m dotenv run -- python manage.py migrate --noinput
if errorlevel 1 (
  echo [error] Migrations failed.
  exit /b 1
)

echo.
echo [ok] Server starting at http://localhost:8000
echo      Admin:   /admin/
echo      Portal:  /portal/
echo.

REM Run server
python -m dotenv run -- python manage.py runserver 0.0.0.0:8000

endlocal

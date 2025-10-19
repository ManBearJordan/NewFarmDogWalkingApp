@echo off
setlocal enabledelayedexpansion

REM === NewFarmDogWalking start script (Windows) ===
REM Ensures DB is migrated and static files are collected before serving.

REM Activate venv if present
if exist ".venv\Scripts\activate.bat" (
  call ".venv\Scripts\activate.bat"
)

echo.
echo [NFDW] Running migrations...
python manage.py migrate --noinput
if errorlevel 1 (
  echo [NFDW] ERROR: migrate failed. Aborting start.
  exit /b 1
)

echo [NFDW] Collecting static files...
python manage.py collectstatic --noinput
if errorlevel 1 (
  echo [NFDW] ERROR: collectstatic failed. Aborting start.
  exit /b 1
)

REM Start waitress on 127.0.0.1:8000
echo [NFDW] Starting Waitress...
python -X utf8 -m waitress --listen=127.0.0.1:8000 newfarm.wsgi:application ^
  1>logs\waitress.out.log 2>logs\waitress.err.log

REM Start Cloudflare Tunnel (assumes cloudflared is installed and configured)
echo [NFDW] Starting Cloudflare Tunnel...
cloudflared tunnel run 1>logs\cloudflared.out.log 2>logs\cloudflared.err.log

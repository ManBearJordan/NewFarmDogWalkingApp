@echo off
setlocal enabledelayedexpansion

REM === NewFarmDogWalking start script (Windows) ===
REM Ensures DB is migrated and static files are collected before serving.

REM Optional override: full path to cloudflared.exe
REM Example: set CLOUDFLARED_EXE=C:\Programs\cloudflared\cloudflared.exe
if not defined CLOUDFLARED_EXE (
  set "CLOUDFLARED_EXE="
)

REM Ensure logs directory exists
if not exist "logs" mkdir logs

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
start "NFDW Waitress" /min python -X utf8 -m waitress --listen=127.0.0.1:8000 newfarm.wsgi:application ^
  1>logs\waitress.out.log 2>logs\waitress.err.log

REM ------- Cloudflared detection / install / start -------
echo [NFDW] Locating cloudflared...

REM 1) Use explicit override if provided
if defined CLOUDFLARED_EXE if exist "%CLOUDFLARED_EXE%" goto :run_cloudflared

REM 2) Common repo-local location
if exist ".\cloudflared\cloudflared.exe" (
  set "CLOUDFLARED_EXE=.\cloudflared\cloudflared.exe"
  goto :run_cloudflared
)

REM 3) PATH lookup
where cloudflared >nul 2>&1
if %errorlevel%==0 (
  set "CLOUDFLARED_EXE=cloudflared"
  goto :run_cloudflared
)

REM 4) Not found -> attempt auto-install into .\cloudflared\
echo [NFDW] cloudflared not found. Attempting auto-install...
powershell -NoProfile -ExecutionPolicy Bypass -File "scripts\install-cloudflared.ps1"
if errorlevel 1 (
  echo [NFDW] WARNING: cloudflared could not be installed automatically.
  echo [NFDW] The site will be available locally at http://127.0.0.1:8000 only.
  echo [NFDW] To install manually, download:
  echo        https://github.com/cloudflare/cloudflared/releases/latest/download/cloudflared-windows-amd64.exe
  echo [NFDW] Save as .\cloudflared\cloudflared.exe or set CLOUDFLARED_EXE and re-run.
  goto :eof
)
set "CLOUDFLARED_EXE=.\cloudflared\cloudflared.exe"

:run_cloudflared
echo [NFDW] Starting Cloudflare Tunnel using: %CLOUDFLARED_EXE%
start "NFDW Cloudflare" /min "%CLOUDFLARED_EXE%" tunnel run nfdw-app ^
  1>logs\cloudflared.out.log 2>logs\cloudflared.err.log
goto :eof

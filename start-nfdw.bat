@echo off
setlocal enabledelayedexpansion

REM === NewFarmDogWalking start script (Windows) ===
REM Ensures DB is migrated and static files are collected before serving.

REM Optional override (set in .env or system env): full path to cloudflared.exe
REM Example: set CLOUDFLARED_EXE=C:\Programs\cloudflared\cloudflared.exe
if not defined CLOUDFLARED_EXE (
  set "CLOUDFLARED_EXE="
)

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

REM Ensure logs directory exists
if not exist "logs" mkdir logs

REM Start waitress on 127.0.0.1:8000
echo [NFDW] Starting Waitress...
start "NFDW Waitress" /min python -X utf8 -m waitress --listen=127.0.0.1:8000 newfarm.wsgi:application ^
  1>logs\waitress.out.log 2>logs\waitress.err.log

REM ------- Cloudflared detection & start -------
echo [NFDW] Locating cloudflared...

REM 1) Use explicit override if provided
if defined CLOUDFLARED_EXE if exist "%CLOUDFLARED_EXE%" goto :run_cloudflared

REM 2) Common install locations
if exist ".\cloudflared\cloudflared.exe" set "CLOUDFLARED_EXE=.\cloudflared\cloudflared.exe"
if not defined CLOUDFLARED_EXE if exist "%ProgramFiles%\Cloudflare\cloudflared\cloudflared.exe" set "CLOUDFLARED_EXE=%ProgramFiles%\Cloudflare\cloudflared\cloudflared.exe"
if not defined CLOUDFLARED_EXE if exist "%LOCALAPPDATA%\Cloudflare\cloudflared\cloudflared.exe" set "CLOUDFLARED_EXE=%LOCALAPPDATA%\Cloudflare\cloudflared\cloudflared.exe"

REM 3) PATH lookup
if not defined CLOUDFLARED_EXE (
  where cloudflared >nul 2>&1
  if %errorlevel%==0 (
    set "CLOUDFLARED_EXE=cloudflared"
  )
)

REM If we still didn't find it, warn and continue (local only)
if not defined CLOUDFLARED_EXE (
  echo [NFDW] WARNING: cloudflared not found. The site will only be available on http://127.0.0.1:8000
  echo [NFDW] To install quickly:
  echo   winget install --id Cloudflare.cloudflared -e
  echo Or set CLOUDFLARED_EXE to the full path of cloudflared.exe and re-run.
  goto :eof
)

:run_cloudflared
echo [NFDW] Starting Cloudflare Tunnel using: %CLOUDFLARED_EXE%
start "NFDW Cloudflare" /min "%CLOUDFLARED_EXE%" tunnel run ^
  1>logs\cloudflared.out.log 2>logs\cloudflared.err.log
goto :eof

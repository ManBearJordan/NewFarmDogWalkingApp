@echo off
setlocal ENABLEDELAYEDEXPANSION

REM === NewFarmDogWalking — Start Django (+ optional Celery) ===

where py >nul 2>nul
if %errorlevel%==0 (set PYTHON=py) else (set PYTHON=python)

REM Activate venv (run start_dev.bat once if it doesn't exist)
call .\.venv\Scripts\activate.bat
if errorlevel 1 (
  echo [error] Activate .venv first or run scripts\start_dev.bat once.
  exit /b 1
)

REM Start Django in its own terminal window
start "Django" cmd /k python -m dotenv run -- python manage.py runserver 0.0.0.0:8000

REM Optional: Celery (requires broker configured in .env and celery installed)
REM start "Celery Worker" cmd /k python -m dotenv run -- celery -A newfarm worker -l info
REM start "Celery Beat"   cmd /k python -m dotenv run -- celery -A newfarm beat -l info

echo [ok] Launched Django (and Celery if you uncommented those lines).
endlocal

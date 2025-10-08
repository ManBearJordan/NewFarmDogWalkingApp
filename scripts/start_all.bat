@echo off
REM Windows launcher to start Django dev server + optional Celery worker/beat

start "Django" cmd /k python -m dotenv run -- python manage.py runserver 0.0.0.0:8000

REM Start Celery worker & beat in separate terminals (uncomment if you have Redis running)
REM start "Celery Worker" cmd /k python -m dotenv run -- celery -A newfarm worker -l info
REM start "Celery Beat"   cmd /k python -m dotenv run -- celery -A newfarm beat -l info

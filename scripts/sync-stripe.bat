@echo off
REM Run Stripe sync inside the project virtualenv
REM Adjust paths only if your project directory is different

setlocal
cd /d C:\NewFarmDogWalkingApp
call .\.venv\Scripts\activate.bat
python manage.py sync_subscriptions
endlocal
exit /b 0

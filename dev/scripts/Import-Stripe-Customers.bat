@echo off
setlocal
cd /d "%~dp0"

REM Pick Python: prefer .venv, then venv, else system python
set "PYEXE="
if exist ".venv\Scripts\python.exe" set "PYEXE=.venv\Scripts\python.exe"
if not defined PYEXE if exist "venv\Scripts\python.exe" set "PYEXE=venv\Scripts\python.exe"
if not defined PYEXE set "PYEXE=python.exe"

REM If you have the helper, this sets STRIPE_API_KEY for this window
if exist "Set-Stripe-Key.bat" call "Set-Stripe-Key.bat"

echo Using: %PYEXE%
"%PYEXE%" -V
"%PYEXE%" "%~dp0Import-Stripe-Customers.py"
echo.
echo Done. If you see "Imported X, updated Y", open the app and check Clients.
pause

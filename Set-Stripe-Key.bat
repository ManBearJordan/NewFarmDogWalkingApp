@echo off
setlocal
cd /d "%~dp0"
set /p STRIPE_API_KEY=Paste your Stripe secret key (sk_test_xxx or sk_live_xxx) then press Enter: 
if "%STRIPE_API_KEY%"=="" (
  echo No key entered. You can still use the app; only Stripe features need the key.
) else (
  setx STRIPE_API_KEY "%STRIPE_API_KEY%" >nul
  echo Saved for your user account. New terminals will see it.
)
call ".\Start-App.bat"

@echo on
setlocal

REM === NewFarmDogWalking ONE-CLICK (visible) ===
REM - migrate + collectstatic
REM - start Waitress (background in THIS window)
REM - wait for /healthz
REM - run Cloudflare Tunnel "nfdw-app" (foreground so you see logs)

REM Adjust if your cloudflared.exe lives elsewhere:
set "CLOUDFLARED_EXE=.\cloudflared\cloudflared.exe"

if not exist "logs" mkdir "logs" 2>nul

REM Activate venv if present
if exist ".venv\Scripts\activate.bat" call ".venv\Scripts\activate.bat"

echo [NFDW] migrate...
python manage.py migrate --noinput || goto :fail

echo [NFDW] collectstatic...
python manage.py collectstatic --noinput || goto :fail

echo [NFDW] starting Waitress in background...
REM /B keeps it in this window; ^& to detach with start; output goes to logs
start "" /B cmd /c "python -X utf8 -m waitress --listen=127.0.0.1:8000 newfarm.wsgi:application 1>logs\waitress.out.log 2>logs\waitress.err.log"

echo [NFDW] waiting for http://127.0.0.1:8000/healthz ...
powershell -NoProfile -ExecutionPolicy Bypass -Command ^
  "$deadline=(Get-Date).AddSeconds(45);while((Get-Date)-lt$deadline){try{$r=Invoke-WebRequest 'http://127.0.0.1:8000/healthz' -UseBasicParsing -TimeoutSec 5;if($r.StatusCode -eq 200 -and $r.Content -match 'OK'){Write-Host '[NFDW] app is ready.';exit 0}}catch{};Start-Sleep -s 1};Write-Host '[NFDW] timeout waiting for app';exit 1" || goto :show_waitress_log

REM If cloudflared not in repo, try PATH
if not exist "%CLOUDFLARED_EXE%" set "CLOUDFLARED_EXE=cloudflared"

echo [NFDW] running Cloudflare Tunnel: nfdw-app
echo [NFDW] (Press CTRL+C here to stop the tunnel; use stop-nfdw.bat to stop both)
"%CLOUDFLARED_EXE%" tunnel run nfdw-app 1>logs\cloudflared.out.log 2>logs\cloudflared.err.log
goto :eof

:show_waitress_log
echo.
echo [NFDW] waitress.err.log (tail):
powershell -NoProfile -ExecutionPolicy Bypass -Command ^
  "if(Test-Path 'logs\waitress.err.log'){Get-Content 'logs\waitress.err.log' -Tail 200}else{Write-Host 'no logs\waitress.err.log yet'}"
goto :fail

:fail
echo.
echo [NFDW] FAILED. Check:
echo   logs\waitress.err.log
echo   logs\cloudflared.err.log
exit /b 1

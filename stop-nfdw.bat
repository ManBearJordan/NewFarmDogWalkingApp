@echo off
rem === NewFarmDogWalking ONE-CLICK stop ===
taskkill /fi "WINDOWTITLE eq NFDW Waitress" /f >nul 2>&1
taskkill /fi "WINDOWTITLE eq NFDW Cloudflared" /f >nul 2>&1
taskkill /im cloudflared.exe /f >nul 2>&1
rem If you run other Python apps, comment the next line:
rem taskkill /im python.exe /f >nul 2>&1
echo [NFDW] stopped.
exit /b 0

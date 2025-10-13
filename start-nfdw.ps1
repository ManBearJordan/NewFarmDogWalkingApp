# --- paths you have ---
$ProjectDir   = "C:\NewFarmDogWalkingApp"
$VenvActivate = "C:\NewFarmDogWalkingApp\.venv\Scripts\Activate.ps1"
$Cloudflared  = "C:\cloudflared\cloudflared.exe"

# --- start Django (waitress) in its own window ---
Start-Process -WindowStyle Minimized powershell.exe `
  -ArgumentList @(
    "-NoLogo","-NoProfile","-ExecutionPolicy","Bypass","-Command",
    "& {
        Set-Location '$ProjectDir';
        . '$VenvActivate';
        waitress-serve --listen=127.0.0.1:8000 --threads=8 newfarm.wsgi:application
      }"
  )

Start-Sleep -Seconds 2  # tiny buffer so app is listening

# --- start Cloudflare Tunnel in its own window ---
Start-Process -WindowStyle Minimized $Cloudflared -ArgumentList "tunnel run nfdw-tunnel"

Write-Host "NFDW: Django + Tunnel started. Open https://app.newfarmdogwalking.com.au"

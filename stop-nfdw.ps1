# stop cloudflared
Get-Process cloudflared -ErrorAction SilentlyContinue | Stop-Process -Force

# stop the python process that runs waitress in this project folder
Get-CimInstance Win32_Process |
  Where-Object {
    $_.Name -match 'python' -and $_.CommandLine -match 'newfarm\.wsgi:application'
  } | ForEach-Object { Stop-Process -Id $_.ProcessId -Force }

Write-Host "NFDW: Stopped cloudflared and Django (waitress)."

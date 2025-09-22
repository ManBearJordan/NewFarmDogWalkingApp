# PowerShell dev runner: loads .env and starts Django on PORT
Set-StrictMode -Version Latest
$ErrorActionPreference = 'Stop'

$repoRoot = Split-Path -Parent $MyInvocation.MyCommand.Path
$envPath  = Join-Path $repoRoot "..\.env"

if (Test-Path $envPath) {
  Get-Content $envPath | ForEach-Object {
    if ($_ -match '^\s*#' -or $_ -match '^\s*$') { return }
    $name, $value = $_.Split('=',2)
    if ($name -and $value) { [Environment]::SetEnvironmentVariable($name.Trim(), $value.Trim()) }
  }
} else {
  Write-Host ".env not found. Create one from config\.env.example"
}

$port = if ($env:PORT) { $env:PORT } else { "8000" }
python manage.py runserver "127.0.0.1:$port"
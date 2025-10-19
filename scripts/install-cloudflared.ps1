Param(
  [string]$TargetDir = ".\cloudflared",
  [string]$ExeName = "cloudflared.exe"
)
Set-StrictMode -Version Latest
$ErrorActionPreference = "Stop"

function Write-Info($msg) { Write-Host "[cloudflared] $msg" }
function Ensure-Dir($p) {
  if (-not (Test-Path -LiteralPath $p)) { New-Item -ItemType Directory -Path $p | Out-Null }
}

Ensure-Dir $TargetDir
$exePath = Join-Path $TargetDir $ExeName

if (Test-Path -LiteralPath $exePath) {
  Write-Info "Already present at $exePath"
  exit 0
}

Write-Info "Downloading latest cloudflared for Windows amd64..."

# Cloudflare provides a stable 'latest' URL for Windows amd64:
$url = "https://github.com/cloudflare/cloudflared/releases/latest/download/cloudflared-windows-amd64.exe"
$tmp = Join-Path $env:TEMP "cloudflared-windows-amd64.exe"

try {
  Invoke-WebRequest -Uri $url -OutFile $tmp -UseBasicParsing
} catch {
  Write-Error "Failed to download cloudflared: $($_.Exception.Message)"
  exit 1
}

try {
  Move-Item -Force -Path $tmp -Destination $exePath
} catch {
  Write-Error "Failed to move cloudflared into $exePath: $($_.Exception.Message)"
  exit 1
}

Write-Info "Installed to $exePath"
exit 0

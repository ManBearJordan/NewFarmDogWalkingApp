<#
Registers a Windows Scheduled Task to run Stripe sync every 15 minutes.
Run this file once in an elevated PowerShell (Run as Administrator).
Task name: NFDW-Stripe-Sync
#>

param(
  [string]$ProjectDir = "C:\NewFarmDogWalkingApp",
  [string]$TaskName   = "NFDW-Stripe-Sync"
)

$bat = Join-Path $ProjectDir "scripts\sync-stripe.bat"
if (-not (Test-Path $bat)) {
  Write-Error "Missing $bat — please ensure the repo path is correct."
  exit 1
}

# Create action: run the .bat via cmd.exe
$Action = New-ScheduledTaskAction `
  -Execute "C:\Windows\System32\cmd.exe" `
  -Argument "/c `"$bat`""

# Trigger: start in ~1 minute, repeat every 15 minutes indefinitely
$Trigger = New-ScheduledTaskTrigger `
  -Once -At (Get-Date).AddMinutes(1) `
  -RepetitionInterval (New-TimeSpan -Minutes 15) `
  -RepetitionDuration ([TimeSpan]::MaxValue)

# Run under current user, highest privileges, without storing password
$Principal = New-ScheduledTaskPrincipal `
  -UserId "$env:USERNAME" `
  -LogonType S4U `
  -RunLevel Highest

# If an old task exists, remove it first
try {
  if (Get-ScheduledTask -TaskName $TaskName -ErrorAction Stop) {
    Unregister-ScheduledTask -TaskName $TaskName -Confirm:$false
  }
} catch { }

Register-ScheduledTask `
  -TaskName $TaskName `
  -Action $Action `
  -Trigger $Trigger `
  -Principal $Principal `
  -Description "Sync NFDW from Stripe every 15 minutes"

Write-Host "Scheduled task '$TaskName' registered."
Write-Host "It will run once in ~1 minute and then every 15 minutes."

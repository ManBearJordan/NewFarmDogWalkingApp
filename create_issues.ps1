param([string]$JsonPath = "$(Split-Path -Parent $MyInvocation.MyCommand.Path)\issues.json")
$issues = Get-Content $JsonPath | ConvertFrom-Json
foreach ($i in $issues) { gh issue create --title $i.title --body $i.body --label ($i.labels -join ',') }

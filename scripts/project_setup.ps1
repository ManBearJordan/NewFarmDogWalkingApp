<#
.SYNOPSIS
Creates a GitHub Project (Beta) with Priority/Status fields and a Kanban view.
Requires gh >= 2.32.0

.EXAMPLE
./scripts/project_setup.ps1 -Org ManBearJordan -Name "NewFarmDogWalking Roadmap"
#>
param(
  [Parameter(Mandatory=$true)][string]$Org,
  [string]$Name = "NewFarmDogWalking Roadmap"
)

$proj = gh project create --owner $Org --title $Name --format json | ConvertFrom-Json
$pid = $proj.id
Write-Host "Project ID: $pid"

gh project field-create $pid --name "Priority" --data-type SINGLE_SELECT --options "P0,P1,P2,P3"
gh project field-create $pid --name "Status"   --data-type SINGLE_SELECT --options "To Do,In Progress,Review,Done"
gh project view-create  $pid --title "Kanban"  --layout board --group-by "Status" --sort "Priority"

Write-Host "Open in browser..."
gh project view $pid --web

Write-Host @'
NEXT STEPS
1) In repo Settings → Secrets and variables → Actions, add:
   - GH_PAT_FOR_PROJECT : classic token with project/repo/issues write
   - NFDW_PROJECT_URL   : paste the Project URL opened above
2) Commit & push .github/workflows/add-to-project.yml
3) Create issues (templates) or bulk import via issues.json
'@

#!/usr/bin/env bash
# Creates a GitHub Project (Beta) with Priority/Status fields and a Kanban view.
# Requires: gh >= 2.32.0 and jq
# Usage:
#   GH_ORG=ManBearJordan GH_REPO=NewFarmDogWalkingApp ./scripts/project_setup.sh
set -euo pipefail

if ! command -v gh >/dev/null 2>&1; then
  echo "GitHub CLI (gh) is required. https://cli.github.com/"
  exit 1
fi
if ! command -v jq >/dev/null 2>&1; then
  echo "jq is required. https://stedolan.github.io/jq/"
  exit 1
fi

ORG="${GH_ORG:-}"
REPO="${GH_REPO:-}"
NAME="${PROJECT_NAME:-NewFarmDogWalking Roadmap}"

if [ -z "$ORG" ]; then echo "Set GH_ORG"; exit 1; fi

echo "Creating GitHub Project in org $ORG: $NAME"
PID=$(gh project create --owner "$ORG" --title "$NAME" --format json | jq -r '.id')
echo "Project ID: $PID"

echo "Creating fields (Priority, Status)"
gh project field-create "$PID" --name "Priority" --data-type SINGLE_SELECT --options "P0,P1,P2,P3"
gh project field-create "$PID" --name "Status" --data-type SINGLE_SELECT --options "To Do,In Progress,Review,Done"

echo "Creating views"
gh project view-create "$PID" --title "Kanban" --layout board --group-by "Status" --sort "Priority"

echo "Done. Project URL:"
gh project view "$PID" --web

cat <<EOF

NEXT STEPS
1) In your repo settings, add two Actions secrets:
   - GH_PAT_FOR_PROJECT : Classic token with 'project', 'repo', 'issues' write
   - NFDW_PROJECT_URL   : Paste the Project URL opened above
2) Commit and push .github/workflows/add-to-project.yml
3) Create issues normally (or bulk via issues.json) — they auto-land on the board.

EOF

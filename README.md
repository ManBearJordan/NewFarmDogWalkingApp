# NewFarmDogWalking — GitHub Project Kit (Verbose)

This kit bootstraps:
- **Issue templates** so new tasks are consistent and labeled.
- **Workflow** to auto-add issues/PRs to a GitHub Project and apply area labels.
- **Project setup scripts** to create a Project with **Priority** and **Status** and a Kanban view.
- **Labels seed script** to create the standard label set used in our spec.

## Files
- `.github/ISSUE_TEMPLATE/*.yml` — Templates for Spec Task, Feature, Bug.
- `.github/workflows/add-to-project.yml` — Automation to intake items into the Project.
- `scripts/project_setup.ps1` / `.sh` — Create the Project and fields.
- `scripts/labels_setup.ps1` — Seed labels.

## One-time Setup
1. **Copy this folder** into your repo and commit/push.
2. **Create labels** (run once):
   ```powershell
   ./scripts/labels_setup.ps1
   ```
3. **Create a Project** (org-level):
   ```powershell
   ./scripts/project_setup.ps1 -Org ManBearJordan
   ```
   Copy the Project URL.
4. **Add repository secrets** (Settings → Secrets and variables → Actions):
   - `GH_PAT_FOR_PROJECT` — classic token with project/repo/issues write.
   - `NFDW_PROJECT_URL` — the Project URL (copied above).
5. **Push** the `.github/workflows/add-to-project.yml` so automation is live.

## Daily Usage
- File a **Spec Task** using the template (title starts with `[Spec]`).
- Or bulk-create tasks from `issues.json` using PowerShell:
  ```powershell
  Get-Content .\issues.json | ConvertFrom-Json | ForEach-Object {
    gh issue create --title $_.title --body $_.body --label ($_.labels -join ",")
  }
  ```
- New items auto-land on the Project board and get area labels based on keywords in the title/body.

## Notes
- The workflow uses `actions/add-to-project` which requires an org-level Project (Beta).
- Secret `GH_PAT_FOR_PROJECT` is used to mutate the Project and labels (fine-grained tokens don’t yet fully work for Projects).

Happy shipping!

## Tests
Run tests with coverage (writes `coverage.xml`):

```bash
pytest --maxfail=1 --disable-warnings -q
```

The CI-ready coverage report is written to `coverage.xml`. You can add a badge later via Shields.io/CI.

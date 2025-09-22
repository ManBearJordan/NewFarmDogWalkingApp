#!/usr/bin/env bash
set -euo pipefail
jq -c '.[]' issues.json | while read -r item; do
  title=$(echo "$item" | jq -r '.title')
  body=$(echo  "$item" | jq -r '.body')
  labels=$(echo "$item" | jq -r '.labels | join(",")')
  gh issue create --title "$title" --body "$body" --label "$labels"
 done

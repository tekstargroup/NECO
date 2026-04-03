#!/usr/bin/env bash
# Create named branches at integration tip (same SHA) for PR targeting.
# Splitting into different SHAs requires interactive staging per docs/pr/MERGE_STRATEGY.md
set -euo pipefail
ROOT="$(cd "$(dirname "$0")/../.." && pwd)"
cd "$ROOT"
TIP="${1:-integration/patches-complete}"
for b in patch-b-d-foundation patch-c-e-f-reasoning patch-a-memo-alignment; do
  git branch -f "$b" "$TIP" 2>/dev/null || git branch "$b" "$TIP"
  echo "branch $b -> $TIP"
done

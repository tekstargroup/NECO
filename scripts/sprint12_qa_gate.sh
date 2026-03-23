#!/usr/bin/env bash

set -euo pipefail

ROOT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
FRONTEND_DIR="${ROOT_DIR}/frontend"
OUTPUT_DIR="${ROOT_DIR}/output"

BASE_URL="${BASE_URL:-http://localhost:9001}"
FRONTEND_BASE_URL="${FRONTEND_BASE_URL:-http://localhost:3001}"
USE_DEV_AUTH="${USE_DEV_AUTH:-0}"
RUN_UI="${RUN_UI:-1}"

if [[ "${USE_DEV_AUTH}" == "1" ]]; then
  PLAYWRIGHT_STORAGE_STATE="${PLAYWRIGHT_STORAGE_STATE:-${FRONTEND_DIR}/.auth/dev-auth-state.json}"
else
  PLAYWRIGHT_STORAGE_STATE="${PLAYWRIGHT_STORAGE_STATE:-${FRONTEND_DIR}/.auth/clerk-state.json}"
fi

RUN_TS="$(date -u +"%Y-%m-%dT%H:%M:%SZ")"
GATE_REPORT_MD="${OUTPUT_DIR}/sprint12_qa_gate_report.md"
GATE_REPORT_JSON="${OUTPUT_DIR}/sprint12_qa_gate_report.json"

mkdir -p "${OUTPUT_DIR}"

api_status="PASS"
ui_status="SKIPPED"
api_exit=0
ui_exit=0

normalize_storage_state() {
  local source_state="$1"
  local frontend_base_url="$2"
  local output_state="$3"

  python3 - "$source_state" "$frontend_base_url" "$output_state" <<'PY'
import json
import sys
from urllib.parse import urlparse

source_state, frontend_base_url, output_state = sys.argv[1:4]

try:
    with open(source_state, "r", encoding="utf-8") as f:
        data = json.load(f)
except Exception as exc:
    print(f"invalid Playwright storage state ({exc})", file=sys.stderr)
    raise SystemExit(1)

target = urlparse(frontend_base_url)
if not target.scheme or not target.netloc:
    print(f"invalid FRONTEND_BASE_URL: {frontend_base_url}", file=sys.stderr)
    raise SystemExit(1)

target_origin = f"{target.scheme}://{target.netloc}"
origins = data.get("origins")
if not isinstance(origins, list):
    print("Playwright storage state missing origins[]", file=sys.stderr)
    raise SystemExit(1)

origin_rewrites = {}
for entry in origins:
    origin = entry.get("origin")
    if not isinstance(origin, str):
        continue
    parsed = urlparse(origin)
    if parsed.scheme == target.scheme and parsed.hostname == target.hostname and parsed.netloc != target.netloc:
        origin_rewrites[f"{parsed.scheme}://{parsed.netloc}"] = target_origin

rewritten_origins = 0
rewritten_values = 0
for entry in origins:
    origin = entry.get("origin")
    if isinstance(origin, str) and origin in origin_rewrites:
        entry["origin"] = origin_rewrites[origin]
        rewritten_origins += 1

    storage = entry.get("localStorage")
    if not isinstance(storage, list):
        continue
    for item in storage:
        value = item.get("value")
        if not isinstance(value, str):
            continue
        new_value = value
        for old_origin, new_origin in origin_rewrites.items():
            new_value = new_value.replace(old_origin, new_origin)
        if new_value != value:
            item["value"] = new_value
            rewritten_values += 1

with open(output_state, "w", encoding="utf-8") as f:
    json.dump(data, f, indent=2)

print(f"storage_state_normalized origins={rewritten_origins} values={rewritten_values}")
PY
}

echo "Sprint 12 QA gate started @ ${RUN_TS}"
echo "API base: ${BASE_URL}"
echo "Frontend base: ${FRONTEND_BASE_URL}"
[[ "${USE_DEV_AUTH}" == "1" ]] && echo "Dev auth: enabled (USE_DEV_AUTH=1)"

set +e
BASE_URL="${BASE_URL}" "${ROOT_DIR}/scripts/sprint12_loop.sh"
api_exit=$?
set -e
if [[ "${api_exit}" -ne 0 ]]; then
  api_status="FAIL"
fi

if [[ "${RUN_UI}" == "1" ]]; then
  ui_status="PASS"

  if [[ "${USE_DEV_AUTH}" == "1" ]]; then
    FRONTEND_HEALTH_URL="${FRONTEND_BASE_URL}/dev-login"
  else
    FRONTEND_HEALTH_URL="${FRONTEND_BASE_URL}/sign-in"
  fi
  FRONTEND_HEALTH_CODE="$(curl -sS -o /dev/null -w "%{http_code}" "${FRONTEND_HEALTH_URL}" || true)"
  if [[ "${FRONTEND_HEALTH_CODE}" != "200" && "${FRONTEND_HEALTH_CODE}" != "301" && "${FRONTEND_HEALTH_CODE}" != "302" && "${FRONTEND_HEALTH_CODE}" != "307" && "${FRONTEND_HEALTH_CODE}" != "308" ]]; then
    echo "Frontend is not reachable at ${FRONTEND_HEALTH_URL} (http=${FRONTEND_HEALTH_CODE})." >&2
    if [[ "${USE_DEV_AUTH}" == "1" ]]; then
      echo "Start frontend with NEXT_PUBLIC_DEV_AUTH=true." >&2
    else
      echo "Start the frontend on port 3001 or override FRONTEND_BASE_URL." >&2
    fi
    ui_status="FAIL"
    ui_exit=11
  fi

  if [[ "${USE_DEV_AUTH}" == "1" ]]; then
    echo "Running dev-auth setup..."
    if ! FRONTEND_BASE_URL="${FRONTEND_BASE_URL}" OUTPUT_PATH="${PLAYWRIGHT_STORAGE_STATE}" "${ROOT_DIR}/scripts/playwright_dev_auth_setup.sh"; then
      echo "Dev-auth setup failed." >&2
      ui_status="FAIL"
      ui_exit=10
    fi
  fi

  if [[ ! -f "${PLAYWRIGHT_STORAGE_STATE}" ]]; then
    echo "Missing Playwright storage state: ${PLAYWRIGHT_STORAGE_STATE}" >&2
    if [[ "${USE_DEV_AUTH}" == "1" ]]; then
      echo "Dev-auth setup should have created it. Check backend is running." >&2
    else
      echo "Create it once by signing in manually and saving storage state." >&2
    fi
    ui_status="FAIL"
    ui_exit=10
  elif [[ "${ui_status}" == "PASS" ]]; then
    NORMALIZED_STORAGE_STATE="${OUTPUT_DIR}/playwright-storage-state.normalized.json"
    if ! normalize_storage_state "${PLAYWRIGHT_STORAGE_STATE}" "${FRONTEND_BASE_URL}" "${NORMALIZED_STORAGE_STATE}"; then
      echo "Failed to normalize Playwright storage state for ${FRONTEND_BASE_URL}." >&2
      ui_status="FAIL"
      ui_exit=12
    fi
  fi

  if [[ "${ui_status}" == "PASS" ]]; then
    set +e
    (
      cd "${FRONTEND_DIR}"
      FRONTEND_BASE_URL="${FRONTEND_BASE_URL}" \
      PLAYWRIGHT_STORAGE_STATE="${NORMALIZED_STORAGE_STATE}" \
      npm run qa:ui
    )
    ui_exit=$?
    set -e
    if [[ "${ui_exit}" -ne 0 ]]; then
      ui_status="FAIL"
    fi
  fi
fi

python3 - "${GATE_REPORT_JSON}" "${RUN_TS}" "${BASE_URL}" "${FRONTEND_BASE_URL}" "${api_status}" "${ui_status}" "${api_exit}" "${ui_exit}" <<'PY'
import json
import sys
from pathlib import Path

report_path, run_ts, base_url, frontend_base_url, api_status, ui_status, api_exit, ui_exit = sys.argv[1:9]
payload = {
    "run_timestamp_utc": run_ts,
    "api_base_url": base_url,
    "frontend_base_url": frontend_base_url,
    "summary": {
        "api_status": api_status,
        "ui_status": ui_status,
        "api_exit_code": int(api_exit),
        "ui_exit_code": int(ui_exit),
    },
}
Path(report_path).write_text(json.dumps(payload, indent=2), encoding="utf-8")
PY

{
  echo "# Sprint 12 QA Gate Report"
  echo ""
  echo "- Run Timestamp (UTC): ${RUN_TS}"
  echo "- API Base URL: ${BASE_URL}"
  echo "- Frontend Base URL: ${FRONTEND_BASE_URL}"
  echo "- API Status: ${api_status} (exit=${api_exit})"
  echo "- UI Status: ${ui_status} (exit=${ui_exit})"
  echo ""
  echo "## Artifacts"
  echo "- /Users/stevenbigio/Cursor Projects/NECO/output/sprint12_loop_report.md"
  echo "- /Users/stevenbigio/Cursor Projects/NECO/output/sprint12_loop_report.json"
  echo "- /Users/stevenbigio/Cursor Projects/NECO/output/playwright-report/index.html"
  echo "- /Users/stevenbigio/Cursor Projects/NECO/output/sprint12_qa_gate_report.json"
} > "${GATE_REPORT_MD}"

echo "Gate report: ${GATE_REPORT_MD}"
echo "Gate report JSON: ${GATE_REPORT_JSON}"

if [[ "${api_status}" == "PASS" && ( "${ui_status}" == "PASS" || "${ui_status}" == "SKIPPED" ) ]]; then
  echo "Sprint 12 QA gate PASSED."
  exit 0
fi

if [[ "${api_status}" == "FAIL" && "${ui_status}" == "FAIL" ]]; then
  echo "Sprint 12 QA gate FAILED (API and UI)." >&2
  exit 4
fi

if [[ "${api_status}" == "FAIL" ]]; then
  echo "Sprint 12 QA gate FAILED (API)." >&2
  exit 2
fi

echo "Sprint 12 QA gate FAILED (UI)." >&2
exit 3

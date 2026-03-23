#!/usr/bin/env bash

set -euo pipefail

ROOT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
OUTPUT_DIR="${ROOT_DIR}/output"
GATE_SCRIPT="${ROOT_DIR}/scripts/sprint12_qa_gate.sh"

BASE_URL="${BASE_URL:-http://localhost:9001}"
FRONTEND_BASE_URL="${FRONTEND_BASE_URL:-http://localhost:3001}"
RUN_UI="${RUN_UI:-1}"
RUNS="${RUNS:-2}"

RUN_TS="$(date -u +"%Y-%m-%dT%H:%M:%SZ")"
RUN_ID="$(date -u +"%Y%m%d%H%M%S")"
SESSION_DIR="${OUTPUT_DIR}/sprint2_daily/${RUN_ID}"
REPORT_MD="${SESSION_DIR}/sprint2_daily_qa_report.md"
REPORT_JSON="${SESSION_DIR}/sprint2_daily_qa_report.json"

mkdir -p "${SESSION_DIR}"

if [[ ! -x "${GATE_SCRIPT}" ]]; then
  echo "Missing executable gate script: ${GATE_SCRIPT}" >&2
  exit 1
fi

echo "Sprint 2 hardening run started @ ${RUN_TS}"
echo "Session dir: ${SESSION_DIR}"
echo "Base URL: ${BASE_URL}"
echo "Frontend URL: ${FRONTEND_BASE_URL}"
echo "Runs: ${RUNS}"

for run_idx in $(seq 1 "${RUNS}"); do
  run_dir="${SESSION_DIR}/run${run_idx}"
  mkdir -p "${run_dir}"

  set +e
  BASE_URL="${BASE_URL}" \
  FRONTEND_BASE_URL="${FRONTEND_BASE_URL}" \
  RUN_UI="${RUN_UI}" \
  "${GATE_SCRIPT}" >"${run_dir}/gate.stdout.log" 2>"${run_dir}/gate.stderr.log"
  gate_exit=$?
  set -e

  printf '%s\n' "${gate_exit}" > "${run_dir}/gate_exit_code.txt"

  if [[ -f "${OUTPUT_DIR}/sprint12_qa_gate_report.json" ]]; then
    cp "${OUTPUT_DIR}/sprint12_qa_gate_report.json" "${run_dir}/sprint12_qa_gate_report.json"
  fi
  if [[ -f "${OUTPUT_DIR}/sprint12_qa_gate_report.md" ]]; then
    cp "${OUTPUT_DIR}/sprint12_qa_gate_report.md" "${run_dir}/sprint12_qa_gate_report.md"
  fi
  if [[ -f "${OUTPUT_DIR}/sprint12_loop_report.json" ]]; then
    cp "${OUTPUT_DIR}/sprint12_loop_report.json" "${run_dir}/sprint12_loop_report.json"
  fi
  if [[ -f "${OUTPUT_DIR}/sprint12_loop_report.md" ]]; then
    cp "${OUTPUT_DIR}/sprint12_loop_report.md" "${run_dir}/sprint12_loop_report.md"
  fi
done

python3 - "${SESSION_DIR}" "${REPORT_MD}" "${REPORT_JSON}" "${RUN_TS}" "${BASE_URL}" "${FRONTEND_BASE_URL}" "${RUNS}" <<'PY'
import json
import sys
from pathlib import Path
from collections import defaultdict

session_dir, report_md, report_json, run_ts, base_url, frontend_base_url, runs = sys.argv[1:8]
runs = int(runs)

api_endpoint_map = {
    "health": "/health",
    "seed_data": "postgres: seed org/user/membership",
    "strict_missing_user": "POST /api/v1/shipments",
    "create_shipment": "POST /api/v1/shipments",
    "org_mismatch": "GET /api/v1/shipments",
    "missing_org_header": "GET /api/v1/shipments",
    "list_shipments": "GET /api/v1/shipments",
    "analyze_shipment": "POST /api/v1/shipments/{shipment_id}/analyze",
}

api_step_name_map = {
    "health": "Health",
    "seed_data": "Seed Data",
    "strict_missing_user": "Strict Missing User",
    "create_shipment": "Create Shipment",
    "org_mismatch": "Org Mismatch",
    "missing_org_header": "Missing Org Header",
    "list_shipments": "List Shipments",
    "analyze_shipment": "Analyze Shipment",
}

api_blocker_map = {
    "health": "QA-API-001",
    "seed_data": "QA-API-002",
    "strict_missing_user": "QA-AUTH-001",
    "create_shipment": "QA-API-003",
    "org_mismatch": "QA-AUTH-002",
    "missing_org_header": "QA-AUTH-003",
    "list_shipments": "QA-API-004",
    "analyze_shipment": "QA-API-005",
}

def load_json(path: Path, default):
    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except Exception:
        return default

def classify_ui_failure(ui_exit_code: int, stderr_text: str):
    if ui_exit_code == 0:
        return ("NONE", "ui_pass")
    if ui_exit_code == 10 or "Missing Playwright storage state" in stderr_text:
        return ("QA-UI-001", "missing_playwright_storage_state")
    if "ERR_CONNECTION_REFUSED" in stderr_text or "ECONNREFUSED" in stderr_text:
        return ("QA-UI-002", "frontend_unreachable")
    return ("QA-UI-999", "ui_test_failure")

rows = []
run_summaries = []
failure_groups = defaultdict(list)

for run_idx in range(1, runs + 1):
    run_dir = Path(session_dir) / f"run{run_idx}"
    gate = load_json(run_dir / "sprint12_qa_gate_report.json", {})
    loop = load_json(run_dir / "sprint12_loop_report.json", {})
    try:
        stderr_text = (run_dir / "gate.stderr.log").read_text(encoding="utf-8", errors="ignore")
    except Exception:
        stderr_text = ""

    try:
        gate_exit_code = int((run_dir / "gate_exit_code.txt").read_text(encoding="utf-8").strip())
    except Exception:
        gate_exit_code = -1

    gate_summary = gate.get("summary", {})
    loop_summary = loop.get("summary", {})
    results = loop.get("results", [])

    run_summaries.append(
        {
            "run": run_idx,
            "gate_exit_code": gate_exit_code,
            "api_status": gate_summary.get("api_status", "UNKNOWN"),
            "ui_status": gate_summary.get("ui_status", "UNKNOWN"),
            "api_exit_code": int(gate_summary.get("api_exit_code", -1)),
            "ui_exit_code": int(gate_summary.get("ui_exit_code", -1)),
            "api_passed": int(loop_summary.get("passed", 0)),
            "api_failed": int(loop_summary.get("failed", 0)),
        }
    )

    for item in results:
        check = item.get("check", "unknown")
        status = item.get("status", "FAIL")
        working = "Working" if status == "PASS" else "Broken"
        blocker = "NONE" if status == "PASS" else api_blocker_map.get(check, "QA-API-999")

        row = {
            "run": run_idx,
            "step_key": check,
            "step": f"Run {run_idx} - {api_step_name_map.get(check, check)}",
            "endpoint": api_endpoint_map.get(check, "unknown"),
            "http": str(item.get("actual", "")),
            "key_fields": item.get("details", ""),
            "status": working,
            "blocker": blocker,
            "failure_type": "",
        }
        rows.append(row)
        if working == "Broken":
            failure_groups[check].append(row)

    ui_status = gate_summary.get("ui_status", "UNKNOWN")
    ui_exit = int(gate_summary.get("ui_exit_code", -1))
    ui_blocker_id, ui_reason = classify_ui_failure(ui_exit, stderr_text)
    ui_working = "Working" if ui_status in {"PASS", "SKIPPED"} else "Broken"
    ui_row = {
        "run": run_idx,
        "step_key": "ui_gate",
        "step": f"Run {run_idx} - UI Smoke Gate",
        "endpoint": "frontend/tests/smoke/sprint12.spec.ts",
        "http": str(ui_exit),
        "key_fields": f"ui_status={ui_status}; reason={ui_reason}; gate_exit={gate_exit_code}; frontend={frontend_base_url}",
        "status": ui_working,
        "blocker": "NONE" if ui_working == "Working" else ui_blocker_id,
        "failure_type": "",
    }
    rows.append(ui_row)
    if ui_working == "Broken":
        failure_groups["ui_gate"].append(ui_row)

deterministic = set()
flaky = set()

for step_key, failed_rows in failure_groups.items():
    failed_runs = {row["run"] for row in failed_rows}
    if len(failed_runs) == runs:
        http_codes = {row["http"] for row in failed_rows}
        blockers = {row["blocker"] for row in failed_rows}
        if len(http_codes) == 1 and len(blockers) == 1:
            deterministic.add(step_key)
        else:
            flaky.add(step_key)
    else:
        flaky.add(step_key)

for row in rows:
    if row["status"] == "Broken":
        if row["step_key"] in deterministic:
            row["failure_type"] = "deterministic"
        elif row["step_key"] in flaky:
            row["failure_type"] = "flaky"
        else:
            row["failure_type"] = "unknown"
        row["blocker"] = f'{row["blocker"]} ({row["failure_type"]})'

total_working = sum(1 for row in rows if row["status"] == "Working")
total_broken = sum(1 for row in rows if row["status"] == "Broken")

summary = {
    "run_timestamp_utc": run_ts,
    "base_url": base_url,
    "frontend_base_url": frontend_base_url,
    "runs": run_summaries,
    "totals": {
        "working": total_working,
        "broken": total_broken,
    },
    "failure_tracking": {
        "deterministic_steps": sorted(deterministic),
        "flaky_steps": sorted(flaky),
    },
    "gate_recommendation": "GO" if total_broken == 0 else "NO-GO",
    "table_rows": rows,
}

Path(report_json).write_text(json.dumps(summary, indent=2), encoding="utf-8")

with open(report_md, "w", encoding="utf-8") as f:
    f.write("# Sprint 2 Daily QA Hardening Report\n\n")
    f.write(f"- Run Timestamp (UTC): {run_ts}\n")
    f.write(f"- API Base URL: {base_url}\n")
    f.write(f"- Frontend Base URL: {frontend_base_url}\n")
    f.write(f"- Runs: {runs}\n")
    f.write(f"- Working: {total_working}\n")
    f.write(f"- Broken: {total_broken}\n")
    f.write(f"- Deterministic failures: {len(deterministic)}\n")
    f.write(f"- Flaky failures: {len(flaky)}\n")
    f.write(f"- Recommendation: {summary['gate_recommendation']}\n\n")
    f.write("Step | Endpoint | HTTP | Key fields | Working/Broken | Blocker ID\n")
    f.write("--- | --- | --- | --- | --- | ---\n")
    for row in rows:
        step = row["step"].replace("|", "/")
        endpoint = row["endpoint"].replace("|", "/")
        http = row["http"].replace("|", "/")
        key_fields = row["key_fields"].replace("|", "/")
        status = row["status"]
        blocker = row["blocker"]
        f.write(f"{step} | {endpoint} | {http} | {key_fields} | {status} | {blocker}\n")

print(json.dumps({
    "working": total_working,
    "broken": total_broken,
    "deterministic": len(deterministic),
    "flaky": len(flaky),
    "recommendation": summary["gate_recommendation"],
}))
PY

python3 - "${REPORT_JSON}" <<'PY'
import json
import sys
from pathlib import Path

report = json.loads(Path(sys.argv[1]).read_text(encoding="utf-8"))
broken = int(report["totals"]["broken"])
deterministic = len(report["failure_tracking"]["deterministic_steps"])
flaky = len(report["failure_tracking"]["flaky_steps"])

print(f"Report MD: {Path(sys.argv[1]).with_suffix('.md')}")
print(f"Report JSON: {sys.argv[1]}")
print(f"Working={report['totals']['working']} Broken={broken} Deterministic={deterministic} Flaky={flaky}")
print(f"Recommendation={report['gate_recommendation']}")

if broken == 0:
    raise SystemExit(0)
if deterministic > 0 and flaky == 0:
    raise SystemExit(2)
if flaky > 0 and deterministic == 0:
    raise SystemExit(3)
raise SystemExit(4)
PY

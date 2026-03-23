#!/usr/bin/env bash

set -euo pipefail

ROOT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
BASE_URL="${BASE_URL:-http://localhost:9001}"
PG_CONTAINER="${PG_CONTAINER:-neco_postgres}"
OUTPUT_DIR="${ROOT_DIR}/output"
RUN_TS="$(date -u +"%Y-%m-%dT%H:%M:%SZ")"
RUN_ID="$(date -u +"%Y%m%d%H%M%S")"
TMP_DIR="$(mktemp -d)"
RESULTS_TSV="${TMP_DIR}/results.tsv"
REPORT_MD="${OUTPUT_DIR}/sprint12_loop_report.md"
REPORT_JSON="${OUTPUT_DIR}/sprint12_loop_report.json"

LOOP_ORG_ID="org_s12_loop"
LOOP_ORG_NAME="Sprint 12 Loop Org"
LOOP_ORG_SLUG="s12-loop-org"
LOOP_USER_SUB="user_s12_loop_provisioned"
LOOP_USER_EMAIL="qa-sprint12-loop@example.com"
LOOP_USER_NAME="Sprint12 Loop User"
MISSING_USER_SUB="user_s12_loop_missing"

PASS_COUNT=0
FAIL_COUNT=0

cleanup() {
  rm -rf "${TMP_DIR}"
}
trap cleanup EXIT

record_result() {
  local check_name="$1"
  local status="$2"
  local expected="$3"
  local actual="$4"
  local details="$5"

  if [[ "${status}" == "PASS" ]]; then
    PASS_COUNT=$((PASS_COUNT + 1))
  else
    FAIL_COUNT=$((FAIL_COUNT + 1))
  fi

  printf '%s\t%s\t%s\t%s\t%s\n' "${check_name}" "${status}" "${expected}" "${actual}" "${details}" >> "${RESULTS_TSV}"
}

assert_command() {
  local cmd="$1"
  local message="$2"
  if ! command -v "${cmd}" >/dev/null 2>&1; then
    echo "Missing required command: ${cmd} (${message})" >&2
    exit 1
  fi
}

http_status() {
  local method="$1"
  local url="$2"
  local body_file="$3"
  shift 3
  curl -sS -o "${body_file}" -w "%{http_code}" -X "${method}" "$url" "$@"
}

extract_json_field() {
  local file="$1"
  local field="$2"
  python3 - "$file" "$field" <<'PY'
import json
import sys
path = sys.argv[1]
field = sys.argv[2]
try:
    with open(path, 'r', encoding='utf-8') as f:
        data = json.load(f)
    value = data.get(field, "")
    if value is None:
        value = ""
    print(value)
except Exception:
    print("")
PY
}

seed_test_data() {
  docker exec -i "${PG_CONTAINER}" psql -v ON_ERROR_STOP=1 -U neco -d neco <<SQL >/dev/null
INSERT INTO organizations (clerk_org_id, name, slug)
VALUES ('${LOOP_ORG_ID}', '${LOOP_ORG_NAME}', '${LOOP_ORG_SLUG}')
ON CONFLICT (clerk_org_id) DO UPDATE SET name = EXCLUDED.name;

INSERT INTO users (id, clerk_user_id, email, full_name, is_active, is_admin, created_at)
VALUES (
  (
    substr(md5('${LOOP_USER_SUB}'),1,8) || '-' ||
    substr(md5('${LOOP_USER_SUB}'),9,4) || '-' ||
    substr(md5('${LOOP_USER_SUB}'),13,4) || '-' ||
    substr(md5('${LOOP_USER_SUB}'),17,4) || '-' ||
    substr(md5('${LOOP_USER_SUB}'),21,12)
  )::uuid,
  '${LOOP_USER_SUB}',
  '${LOOP_USER_EMAIL}',
  '${LOOP_USER_NAME}',
  true,
  false,
  now()
)
ON CONFLICT (clerk_user_id) DO UPDATE SET
  email = EXCLUDED.email,
  full_name = EXCLUDED.full_name,
  is_active = true;

INSERT INTO memberships (user_id, organization_id, role, created_at)
SELECT u.id, o.id, 'ADMIN'::userrole, now()
FROM users u
JOIN organizations o ON o.clerk_org_id = '${LOOP_ORG_ID}'
WHERE u.clerk_user_id = '${LOOP_USER_SUB}'
ON CONFLICT (user_id, organization_id) DO NOTHING;

INSERT INTO entitlements (user_id, period_start, shipments_used, shipments_limit, created_at)
SELECT
  u.id,
  date_trunc('month', timezone('America/New_York', now()))::date,
  0,
  15,
  now()
FROM users u
WHERE u.clerk_user_id = '${LOOP_USER_SUB}'
ON CONFLICT (user_id, period_start) DO UPDATE SET
  shipments_used = 0,
  shipments_limit = 15;
SQL
}

generate_token() {
  local sub="$1"
  local email="$2"
  "${ROOT_DIR}/backend/venv/bin/python" - "$sub" "$email" <<'PY'
from jose import jwt
import sys
sub = sys.argv[1]
email = sys.argv[2]
claims = {"sub": sub}
if email:
    claims["email"] = email
print(jwt.encode(claims, "dev", algorithm="HS256"))
PY
}

generate_reports() {
  mkdir -p "${OUTPUT_DIR}"

  {
    echo "# Sprint 12 Loop Report"
    echo ""
    echo "- Run Timestamp (UTC): ${RUN_TS}"
    echo "- Base URL: ${BASE_URL}"
    echo "- Postgres Container: ${PG_CONTAINER}"
    echo "- Passed: ${PASS_COUNT}"
    echo "- Failed: ${FAIL_COUNT}"
    echo ""
    echo "| Check | Result | Expected | Actual | Details |"
    echo "|---|---|---|---|---|"
    while IFS=$'\t' read -r check_name status expected actual details; do
      printf '| %s | %s | %s | %s | %s |\n' "${check_name}" "${status}" "${expected}" "${actual}" "${details}"
    done < "${RESULTS_TSV}"
  } > "${REPORT_MD}"

  python3 - "${RESULTS_TSV}" "${REPORT_JSON}" "${RUN_TS}" "${BASE_URL}" "${PASS_COUNT}" "${FAIL_COUNT}" <<'PY'
import json
import sys
from pathlib import Path

results_tsv, report_json, run_ts, base_url, passed, failed = sys.argv[1:7]
items = []
with open(results_tsv, "r", encoding="utf-8") as f:
    for line in f:
        line = line.rstrip("\n")
        if not line:
            continue
        check_name, status, expected, actual, details = line.split("\t", 4)
        items.append(
            {
                "check": check_name,
                "status": status,
                "expected": expected,
                "actual": actual,
                "details": details,
            }
        )

payload = {
    "run_timestamp_utc": run_ts,
    "base_url": base_url,
    "summary": {"passed": int(passed), "failed": int(failed)},
    "results": items,
}
Path(report_json).write_text(json.dumps(payload, indent=2), encoding="utf-8")
PY
}

main() {
  assert_command curl "HTTP checks"
  assert_command docker "DB seed checks"
  assert_command python3 "report generation"

  if [[ ! -x "${ROOT_DIR}/backend/venv/bin/python" ]]; then
    echo "Missing backend venv python: ${ROOT_DIR}/backend/venv/bin/python" >&2
    exit 1
  fi

  echo "Running Sprint 12 loop against ${BASE_URL}"

  # 1) Health
  HEALTH_BODY="${TMP_DIR}/health.json"
  HEALTH_CODE="$(http_status GET "${BASE_URL}/health" "${HEALTH_BODY}")"
  if [[ "${HEALTH_CODE}" == "200" ]]; then
    record_result "health" "PASS" "200" "${HEALTH_CODE}" "backend reachable"
  else
    record_result "health" "FAIL" "200" "${HEALTH_CODE}" "backend not reachable"
    generate_reports
    echo "Health check failed. See ${REPORT_MD}" >&2
    exit 1
  fi

  # 2) Seed deterministic org/user/membership
  if seed_test_data; then
    record_result "seed_data" "PASS" "org/user/membership present" "ok" "seeded ${LOOP_USER_SUB} in ${LOOP_ORG_ID}"
  else
    record_result "seed_data" "FAIL" "org/user/membership present" "error" "failed to seed data"
    generate_reports
    echo "Seed failed. See ${REPORT_MD}" >&2
    exit 1
  fi

  TOKEN_PROVISIONED="$(generate_token "${LOOP_USER_SUB}" "${LOOP_USER_EMAIL}")"
  TOKEN_MISSING="$(generate_token "${MISSING_USER_SUB}" "")"

  # 3) Missing user strict branch -> 403
  MISSING_BODY="${TMP_DIR}/missing_user.json"
  MISSING_CODE="$(http_status POST "${BASE_URL}/api/v1/shipments" "${MISSING_BODY}" \
    -H "Authorization: Bearer ${TOKEN_MISSING}" \
    -H "X-Clerk-Org-Id: ${LOOP_ORG_ID}" \
    -H "Content-Type: application/json" \
    -d '{"name":"S12 Loop Missing User"}')"
  if [[ "${MISSING_CODE}" == "403" ]]; then
    record_result "strict_missing_user" "PASS" "403" "${MISSING_CODE}" "controlled denial"
  else
    record_result "strict_missing_user" "FAIL" "403" "${MISSING_CODE}" "unexpected response"
  fi

  # 4) Provisioned user create -> 201
  CREATE_NAME="S12 Loop ${RUN_ID}"
  CREATE_BODY="${TMP_DIR}/create.json"
  CREATE_CODE="$(http_status POST "${BASE_URL}/api/v1/shipments" "${CREATE_BODY}" \
    -H "Authorization: Bearer ${TOKEN_PROVISIONED}" \
    -H "X-Clerk-Org-Id: ${LOOP_ORG_ID}" \
    -H "Content-Type: application/json" \
    -d "{\"name\":\"${CREATE_NAME}\",\"references\":[{\"key\":\"PO\",\"value\":\"PO-${RUN_ID}\"}],\"items\":[]}")"
  SHIPMENT_ID="$(extract_json_field "${CREATE_BODY}" "shipment_id")"
  if [[ "${CREATE_CODE}" == "201" && -n "${SHIPMENT_ID}" ]]; then
    record_result "create_shipment" "PASS" "201 + shipment_id" "${CREATE_CODE}" "shipment_id=${SHIPMENT_ID}"
  else
    record_result "create_shipment" "FAIL" "201 + shipment_id" "${CREATE_CODE}" "response missing expected payload"
  fi

  # 5) Org mismatch -> 403
  MISMATCH_BODY="${TMP_DIR}/org_mismatch.json"
  MISMATCH_CODE="$(http_status GET "${BASE_URL}/api/v1/shipments" "${MISMATCH_BODY}" \
    -H "Authorization: Bearer ${TOKEN_PROVISIONED}" \
    -H "X-Clerk-Org-Id: org_s12_loop_other")"
  if [[ "${MISMATCH_CODE}" == "403" ]]; then
    record_result "org_mismatch" "PASS" "403" "${MISMATCH_CODE}" "org scope enforced"
  else
    record_result "org_mismatch" "FAIL" "403" "${MISMATCH_CODE}" "unexpected response"
  fi

  # 6) Missing org header -> 403
  NOORG_BODY="${TMP_DIR}/no_org.json"
  NOORG_CODE="$(http_status GET "${BASE_URL}/api/v1/shipments" "${NOORG_BODY}" \
    -H "Authorization: Bearer ${TOKEN_PROVISIONED}")"
  if [[ "${NOORG_CODE}" == "403" ]]; then
    record_result "missing_org_header" "PASS" "403" "${NOORG_CODE}" "header required"
  else
    record_result "missing_org_header" "FAIL" "403" "${NOORG_CODE}" "unexpected response"
  fi

  # 7) List shipments -> 200 and includes created id
  LIST_BODY="${TMP_DIR}/list.json"
  LIST_CODE="$(http_status GET "${BASE_URL}/api/v1/shipments" "${LIST_BODY}" \
    -H "Authorization: Bearer ${TOKEN_PROVISIONED}" \
    -H "X-Clerk-Org-Id: ${LOOP_ORG_ID}")"

  if [[ "${LIST_CODE}" == "200" ]]; then
    if python3 - "${LIST_BODY}" "${SHIPMENT_ID}" <<'PY'
import json
import sys
path, shipment_id = sys.argv[1], sys.argv[2]
try:
    data = json.load(open(path, 'r', encoding='utf-8'))
    found = any(item.get('shipment_id') == shipment_id for item in data)
    raise SystemExit(0 if found else 1)
except Exception:
    raise SystemExit(1)
PY
    then
      record_result "list_shipments" "PASS" "200 + includes created shipment" "${LIST_CODE}" "shipment visible"
    else
      record_result "list_shipments" "FAIL" "200 + includes created shipment" "${LIST_CODE}" "created shipment not found"
    fi
  else
    record_result "list_shipments" "FAIL" "200" "${LIST_CODE}" "unexpected response"
  fi

  # 8) Analyze -> 202 (if shipment created)
  if [[ -n "${SHIPMENT_ID}" ]]; then
    ANALYZE_BODY="${TMP_DIR}/analyze.json"
    ANALYZE_CODE="$(http_status POST "${BASE_URL}/api/v1/shipments/${SHIPMENT_ID}/analyze" "${ANALYZE_BODY}" \
      -H "Authorization: Bearer ${TOKEN_PROVISIONED}" \
      -H "X-Clerk-Org-Id: ${LOOP_ORG_ID}")"
    if [[ "${ANALYZE_CODE}" == "202" ]]; then
      record_result "analyze_shipment" "PASS" "202" "${ANALYZE_CODE}" "analysis accepted"
    else
      record_result "analyze_shipment" "FAIL" "202" "${ANALYZE_CODE}" "unexpected response"
    fi
  else
    record_result "analyze_shipment" "FAIL" "202" "skipped" "shipment creation failed"
  fi

  generate_reports

  echo "Report written: ${REPORT_MD}"
  echo "Report written: ${REPORT_JSON}"

  if [[ "${FAIL_COUNT}" -gt 0 ]]; then
    echo "Sprint 12 loop completed with failures: ${FAIL_COUNT}" >&2
    exit 2
  fi

  echo "Sprint 12 loop completed successfully (${PASS_COUNT} checks)."
}

main "$@"

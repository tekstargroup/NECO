#!/usr/bin/env bash
# Run dev-login flow and save Playwright storage state.
# Requires: Frontend on FRONTEND_BASE_URL with NEXT_PUBLIC_DEV_AUTH=true,
#           Backend running (for /api/v1/auth/dev-token).
set -euo pipefail

ROOT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
FRONTEND_DIR="${ROOT_DIR}/frontend"
FRONTEND_BASE_URL="${FRONTEND_BASE_URL:-http://localhost:3001}"
OUTPUT_PATH="${OUTPUT_PATH:-${FRONTEND_DIR}/.auth/dev-auth-state.json}"

mkdir -p "$(dirname "${OUTPUT_PATH}")"

# Quick health check
HTTP_CODE="$(curl -sS -o /dev/null -w "%{http_code}" "${FRONTEND_BASE_URL}/dev-login" || true)"
if [[ "${HTTP_CODE}" != "200" ]]; then
  echo "Frontend not reachable at ${FRONTEND_BASE_URL}/dev-login (http=${HTTP_CODE})." >&2
  echo "Start frontend with NEXT_PUBLIC_DEV_AUTH=true." >&2
  exit 1
fi

cd "${FRONTEND_DIR}"
FRONTEND_BASE_URL="${FRONTEND_BASE_URL}" OUTPUT_PATH="${OUTPUT_PATH}" HEADLESS="${HEADLESS:-1}" \
  node scripts/dev-auth-setup.mjs

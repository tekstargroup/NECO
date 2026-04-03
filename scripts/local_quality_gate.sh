#!/usr/bin/env bash
# Repeatable local checks: backend unit/integration tests + frontend lint + production build.
# Optional: UI smoke via Playwright when RUN_PLAYWRIGHT=1 (requires API + Next + seed + dev auth).
#
# Usage:
#   ./scripts/local_quality_gate.sh              # pytest + lint + build
#   RUN_PLAYWRIGHT=1 ./scripts/local_quality_gate.sh   # also Playwright (see below)
#
# Playwright prerequisites:
#   cd frontend && npx playwright install chromium   # once per machine
#   Backend on NEXT_PUBLIC_API_URL, Next with NEXT_PUBLIC_DEV_AUTH=true, Sprint 12 seed applied
#   FRONTEND_BASE_URL=http://localhost:3000 npm run qa:ui:dev   # or set env to match your dev port

set -euo pipefail

ROOT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
cd "${ROOT_DIR}"

echo "=== NECO local quality gate ==="

echo ""
echo "== Backend: pytest tests/ (needs DATABASE_URL in backend/.env) =="
cd "${ROOT_DIR}/backend"
if [[ -x venv/bin/python ]]; then
  PY="venv/bin/python"
else
  PY="python3"
  echo "Warning: backend/venv not found; using ${PY}" >&2
fi
"${PY}" -m pytest tests/ -q

echo ""
echo "== Frontend: lint + production build =="
cd "${ROOT_DIR}/frontend"
npm run qa:static

echo ""
echo "=== Static gate passed ==="

if [[ "${RUN_PLAYWRIGHT:-0}" == "1" ]]; then
  echo ""
  echo "== Playwright smoke (RUN_PLAYWRIGHT=1) =="
  npm run qa:ui:dev
  echo "HTML report (if generated): ${ROOT_DIR}/output/playwright-report/index.html"
fi

if [[ "${RUN_PLAYWRIGHT:-0}" != "1" ]]; then
  echo ""
  echo "Tip: With stack running, UI smoke:  cd frontend && npm run qa:ui:dev"
  echo "     Or:  RUN_PLAYWRIGHT=1 ./scripts/local_quality_gate.sh"
fi

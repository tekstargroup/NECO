# Sprint 12 QA Gate

## Repeatable “did we break anything?” (local)

From repo root (Postgres + `backend/.env` required for pytest):

```bash
./scripts/local_quality_gate.sh
```

This runs **backend `pytest tests/`**, then **frontend `lint` + `production build`**. To also run **Playwright** smoke after the static gate (API + Next must be up, seed + dev auth configured):

```bash
RUN_PLAYWRIGHT=1 ./scripts/local_quality_gate.sh
```

Playwright is already wired (`frontend/playwright.config.ts`, `frontend/tests/smoke/`). One-time browser install: `cd frontend && npm run qa:playwright:install`.

## One-time setup

1. Install frontend dependencies:
   ```bash
   cd /Users/stevenbigio/Cursor\ Projects/NECO/frontend
   npm install
   npx playwright install chromium
   ```

2. **Auth for UI tests** – choose one:

   **Option A: Dev auth (recommended for local QA)** – no manual Clerk sign-in:
   - Frontend must run with `NEXT_PUBLIC_DEV_AUTH=true` in `.env.local`
   - Run gate with `USE_DEV_AUTH=1`; it will auto-create storage state via `/dev-login`

   **Option B: Clerk auth** – manual one-time setup:
   ```bash
   cd /Users/stevenbigio/Cursor\ Projects/NECO/frontend
   mkdir -p .auth
   npx playwright codegen http://localhost:3001/sign-in --save-storage=.auth/clerk-state.json
   ```
   Sign in, select the correct org, then close the codegen browser.

## Run gate

```bash
cd /Users/stevenbigio/Cursor\ Projects/NECO
./scripts/sprint12_qa_gate.sh
```

**Quick dev iteration** – run only Playwright UI tests (backend + frontend must be running):

```bash
cd /Users/stevenbigio/Cursor\ Projects/NECO/frontend
npm run qa:ui:dev
```

This runs dev-auth setup, then the smoke tests. Use after code changes to verify UI without the full gate.

## Sprint 2 reliability hardening (daily x2 full gates)

```bash
cd /Users/stevenbigio/Cursor\ Projects/NECO
BASE_URL=http://localhost:9001 FRONTEND_BASE_URL=http://localhost:3001 RUN_UI=1 ./scripts/sprint2_daily_qa_hardening.sh
```

This runs two consecutive full gates and publishes:

- Deterministic failures (same step broken in both runs)
- Flaky failures (step broken in only one run, or mismatched failure signals)
- Strict table format:
  `Step | Endpoint | HTTP | Key fields | Working/Broken | Blocker ID`

## Useful options

- API on a different port:
  ```bash
  BASE_URL=http://localhost:9001 ./scripts/sprint12_qa_gate.sh
  ```

- Frontend on a different port:
  ```bash
  FRONTEND_BASE_URL=http://localhost:3001 ./scripts/sprint12_qa_gate.sh
  ```

- Skip UI and run API-only gate:
  ```bash
  RUN_UI=0 ./scripts/sprint12_qa_gate.sh
  ```

- Custom storage state path:
  ```bash
  PLAYWRIGHT_STORAGE_STATE=/absolute/path/to/state.json ./scripts/sprint12_qa_gate.sh
  ```

- **Dev auth** (no Clerk codegen; frontend must have `NEXT_PUBLIC_DEV_AUTH=true`):
  ```bash
  USE_DEV_AUTH=1 ./scripts/sprint12_qa_gate.sh
  ```

## Outputs

- `/Users/stevenbigio/Cursor Projects/NECO/output/sprint12_loop_report.md`
- `/Users/stevenbigio/Cursor Projects/NECO/output/sprint12_loop_report.json`
- `/Users/stevenbigio/Cursor Projects/NECO/output/playwright-report/index.html`
- `/Users/stevenbigio/Cursor Projects/NECO/output/sprint12_qa_gate_report.md`
- `/Users/stevenbigio/Cursor Projects/NECO/output/sprint12_qa_gate_report.json`

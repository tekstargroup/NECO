# Phase 6 manual testing + QA harness (single reference)

Use this file as your **one place** for: what to test manually (Phase 6), what to run before hands-on testing, and what engineering added so you can repeat checks reliably.

**Printable PDF:** from repo root run `python scripts/generate_phase6_qa_pdf.py` → `output/PHASE6_QA_Harness_NECO.pdf` (regenerate after edits).

The Phase 6 body below matches [`USER_TESTING_PHASE6.md`](USER_TESTING_PHASE6.md); keep them in sync when you edit.

---

## A. Before you test manually (pre-flight)

Do these so login and API calls work; otherwise you’ll chase ghosts.

| Step | What to do |
|------|------------|
| 1 | Backend running; API matches `NEXT_PUBLIC_API_URL` in `frontend/.env.local` (often `http://localhost:9001`). |
| 2 | Frontend: `NEXT_PUBLIC_DEV_AUTH=true` if using `/dev-login` instead of Clerk. |
| 3 | Backend `ENVIRONMENT` is `development`, `dev`, or `local` so `/api/v1/auth/dev-token` exists (not 404). |
| 4 | **Sprint 12 seed** in the **same database** the API uses: `./scripts/sprint12_loop.sh` (Docker Postgres), **or** `cd backend && python scripts/seed_sprint12_dev_login.py`. |
| 5 | (Optional) Automated sanity: from repo root `./scripts/local_quality_gate.sh` — backend tests + frontend lint + production build. |

---

## B. Automated checks (robots — not a substitute for Phase 6)

| Command | What it proves |
|---------|----------------|
| `./scripts/local_quality_gate.sh` | Backend `pytest tests/` + frontend `lint` + `next build`. Needs Postgres + `backend/.env`. |
| `RUN_PLAYWRIGHT=1 ./scripts/local_quality_gate.sh` | Same, then **Playwright** smoke (needs stack up + seed + dev auth). |
| `cd frontend && npm run qa:ui:dev` | Playwright only: dev-login flow + shipments smoke. |
| `cd frontend && npm run qa:playwright:install` | One-time browser install for Playwright. |

**CI:** Pushes/PRs touching `frontend/` run lint + build via [`.github/workflows/frontend-quality.yml`](../.github/workflows/frontend-quality.yml).

---

## C. Phase 6 — Pre-launch smoke checklist and user test script

Run **6A smoke** before external user sessions. Use **6B** during sessions. If you hit a P0 trust break, stop and fix before continuing.

**Local dev-login prerequisite:** With `NEXT_PUBLIC_DEV_AUTH=true`, `NEXT_PUBLIC_API_URL` must point at your running API (see `frontend/.env.example`). Backend `ENVIRONMENT` must be `development`, `dev`, or `local` so `/api/v1/auth/dev-token` exists. Seed the Sprint 12 dev user/org (`./scripts/sprint12_loop.sh` with Docker, or `backend/scripts/seed_sprint12_dev_login.py`) or authenticated calls after login will return 403.

### 6A — Trust-focused smoke pass (operators)

Check each item and note pass/fail.

1. **Snapshot vs Reviews**  
   Upload docs → run analysis → open **Reviews**. Confirm line items come from the review **snapshot** (`snapshot_json`), not live analysis. If you re-ran analysis after the review was created, confirm a drift warning appears when applicable.

2. **Accept → knowledge**  
   Accept a review. Confirm the path goes through the API (no silent local-only state). Optionally verify a `product_hts_map` row or server logs for knowledge recording.

3. **422 not 500**  
   Trigger a known client/validation failure on analyze (e.g. missing required preconditions your API documents). Response must be **422** (or appropriate 4xx), not **500**.

4. **No `dev_context` in non-local**  
   On staging/production (or any `ENVIRONMENT` outside `development`/`dev`/`local`), inspect analysis status JSON in the network tab: **`dev_context` must be absent**.

5. **Duplicate analyze (optional)**  
   While analysis is **RUNNING**, confirm the UI does not start a second overlapping run without an explicit re-run.

6. **Export parity**  
   After accept, generate an **export** (audit pack / broker prep as you use). Open JSON and/or CSV. Confirm review state and line-level outcomes **match** what the Reviews tab showed (HTS, outcomes, counts—no cross-surface drift).

### 6B — User test script (5–8 tasks)

Adapt filenames and org to your pilot.

1. Create a shipment and upload a **commercial invoice** (and any second doc your flow expects).  
2. Run **analysis**; wait until complete. Note anything confusing in progress or errors.  
3. Open **Analysis** tab: scan classification, duty, regulatory cards for one “hard” line. Open the detail drawer if present.  
4. Open **Reviews** tab: confirm items match what you expect from analysis; note any mismatch.  
5. Make **per-line review decisions** (accept/override as supported), then **accept** the review at shipment level.  
6. Download or open an **export**; confirm it matches Reviews (Phase 6A item 6).  
7. (Optional) **Re-run analysis** on the same shipment; return to Reviews and confirm snapshot vs live behavior matches your expectations.  
8. (Optional) **Second user / second org** (if multi-tenant): repeat sign-in and confirm org scoping.

### Observation log (template)

| Time | Task # | Quote or behavior | Severity (P0–P3) | Hypothesis |
|------|--------|-------------------|------------------|------------|
|      |        |                   |                  |            |

**P0 trust breaks (stop testing):** snapshot vs export mismatch; accept not persisted; auth bypass; data from another org visible.

### Stop rule

If any **P0** appears, **stop sessions**, fix, re-run **6A smoke**, then resume user tests.

---

## D. What we implemented for QA / dev experience (inventory)

Engineering additions so you can **re-run the same checks** and **unblock local testing** (not product features):

| Area | What | Where |
|------|------|--------|
| One-command local gate | Backend pytest + frontend lint + production build | [`scripts/local_quality_gate.sh`](../scripts/local_quality_gate.sh) |
| Frontend shortcuts | `npm run qa:static`, `npm run qa:playwright:install` | [`frontend/package.json`](../frontend/package.json) |
| Dev-login seed (no Docker `exec`) | Idempotent SQL via app `DATABASE_URL` | [`backend/scripts/seed_sprint12_dev_login.py`](../backend/scripts/seed_sprint12_dev_login.py) |
| Frontend env template | `NEXT_PUBLIC_API_URL`, `NEXT_PUBLIC_DEV_AUTH`, etc. | [`frontend/.env.example`](../frontend/.env.example) |
| Shared DB fixture for tests | Async `db_session` for integration-style tests | [`backend/tests/conftest.py`](../backend/tests/conftest.py) |
| Test fixes | Audit pack version expectation, review RBAC test, Sprint 4.2 paths, golden HTS fixture dedup, review mock | `backend/tests/test_*.py` |
| Docs | QA loop points to local gate; README “Quality gates” | [`scripts/QA_LOOP.md`](../scripts/QA_LOOP.md), [`frontend/README.md`](../frontend/README.md) |
| Playwright | Already wired: smoke tests, dev-auth setup, HTML report under `output/playwright-report` | [`frontend/playwright.config.ts`](../frontend/playwright.config.ts), [`frontend/tests/smoke/`](../frontend/tests/smoke/) |
| CI | Frontend lint + build on push/PR | [`.github/workflows/frontend-quality.yml`](../.github/workflows/frontend-quality.yml) |

**Still manual / product:** Clerk JWT hardening for production, full backend CI with Postgres, and your Phase 6 business validation — those are separate from this harness.

---

## E. AI-assisted manual testing (optional)

Use any chat model as a **session planner**: paste **Section C** and ask for expanded steps, edge cases, or a filled observation log template. It does not replace your eyes on trust and compliance.

---

*Last consolidated for NECO Phase 6 prep and QA harness documentation.*

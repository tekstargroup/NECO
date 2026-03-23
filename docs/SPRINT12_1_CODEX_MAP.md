# Sprint 12.1 – Codex Phase Map

**Scope:** Work completed during the Codex phase. Complements Sprint 12 (shipments, org-scoped auth) with QA infrastructure, backend fixes, and discovery.

---

## 1. Where Everything Is Stored

### QA / Gate Scripts (Dean-heavy)

| File | Purpose |
|------|---------|
| `scripts/sprint12_loop.sh` | API checks: health, seed, create/list/analyze shipment, org enforcement |
| `scripts/sprint12_qa_gate.sh` | Full gate: API + optional UI (Playwright) |
| `scripts/sprint2_daily_qa_hardening.sh` | Run gate 2x for deterministic vs flaky failure detection |
| `scripts/QA_LOOP.md` | How to run gates, options, outputs |

### QA Outputs / Reports

| Location | Contents |
|----------|----------|
| `output/sprint12_loop_report.md` | API check results |
| `output/sprint12_loop_report.json` | API results (machine-readable) |
| `output/sprint12_qa_gate_report.md` | Full gate summary |
| `output/sprint12_qa_gate_report.json` | Gate summary (machine-readable) |
| `output/sprint2_daily/<timestamp>/` | Timestamped hardening sessions (run1, run2) |
| `output/playwright-report/` | Playwright HTML report |

### Frontend Smoke Tests

| File | Purpose |
|------|---------|
| `frontend/tests/smoke/sprint12.spec.ts` | Shipments list, create shipment |
| `frontend/playwright.config.ts` | Playwright config, storage state path |
| `frontend/test-results/` | Playwright artifacts |

**Note:** `frontend/.auth/clerk-state.json` is required for UI tests (or use dev-auth setup when available).

### Backend Implementation (Oliver-heavy)

| File | Purpose |
|------|---------|
| `backend/app/api/v1/shipments.py` | Shipments CRUD, analyze |
| `backend/app/api/v1/shipment_documents.py` | Presign, confirm, list |
| `backend/app/api/v1/reviews.py` | Review get, list, override |
| `backend/app/api/v1/exports.py` | Audit pack, broker prep export |
| `backend/app/services/analysis_orchestration_service.py` | Analysis job orchestration |
| `backend/app/models/analysis.py` | Analysis model |
| `backend/app/core/config.py` | Settings (SPRINT12_* flags) |

### Backend Regression Tests

| File | Purpose |
|------|---------|
| `backend/tests/test_shipments_validation.py` | Shipment validation |
| `backend/tests/test_s3_upload_service.py` | S3 upload service |
| `backend/tests/test_export_service_org_scope.py` | Export org-scope enforcement |

### Strategy / Archive Docs

| File | Purpose |
|------|---------|
| `docs/archive/SPRINT0_CHARTER.md` | Charter (archived) |
| `PROJECT_STATUS.md` | Current status |
| `SPRINT12_STATUS.md` | Sprint 12 progress tracker |

### Discovery (Phil)

| Location | Purpose |
|----------|---------|
| `discovery/sprint1/` | Interview guides, evidence, KPI recommendations |

---

## 2. Role Definitions (Codex)

| Role | Owner | Scope |
|------|-------|-------|
| **Ben** | You / Codex partner | Technical coordinator, blocker triage, execution plan, cross-agent handoffs, root-cause consolidation, final next-step decisions |
| **Dean** | QA / reliability | Run gates, reproduce failures, produce pass/fail artifacts and blocker IDs |
| **Oliver** | Implementation | Code patches, regression tests, endpoint-level proof after fixes (primarily backend) |
| **Phil** | Discovery / GTM | Interview execution, quote-backed pain/objection evidence, contradiction matrix, KPI-linked recommendations |

---

## 3. Sprint 12.1 vs Sprint 12

| Aspect | Sprint 12 | Sprint 12.1 (Codex) |
|--------|------------|---------------------|
| **Focus** | Shipments API, org-scoped auth, frontend shell | QA infrastructure, backend fixes, regression tests, discovery |
| **Deliverables** | Models, endpoints, UI pages | Gate scripts, Playwright specs, test coverage, discovery artifacts |
| **Baseline** | What "working" means | How we verify and harden it |

---

## 4. Current Gaps

- **Clerk storage state** – `frontend/.auth/clerk-state.json` missing; UI gate fails without it (or use dev-auth setup)
- **Dev-auth UI path** – Proposed in BASELINE_AND_MVP_ROADMAP.md to unblock UI tests without Clerk

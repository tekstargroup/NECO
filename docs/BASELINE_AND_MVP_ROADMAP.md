# NECO Baseline Sprint and MVP Roadmap

**Last Updated:** February 24, 2026

---

## Reference Documents

| Document | Purpose |
|---------|---------|
| **[docs/COMPLETE_PROJECT_HISTORY.md](COMPLETE_PROJECT_HISTORY.md)** | Everything built so far (Sprint 12 + analysis pipeline fixes + supporting docs) |
| **[docs/SPRINT_ROADMAP_LOCKED.md](SPRINT_ROADMAP_LOCKED.md)** | Canonical sprint map with success criteria and completion gates for Sprints 13–20 |

---

## 1. Current Baseline: Sprint 12

**Sprint 12** is the established baseline. It defines what "working" means today.

### Baseline Scope

| Area | What's In Scope |
|------|-----------------|
| **Backend** | Shipments API (create, list, analyze), org-scoped auth, dev-token |
| **Frontend** | Next.js 14, Clerk + dev auth bypass, shipments list/new/detail |
| **Auth** | Clerk (production path) + dev-token (local testing) |
| **Data** | Seeded org `org_s12_loop`, user `user_s12_loop_provisioned` |

### Baseline QA Gate

The gate is `./scripts/sprint12_qa_gate.sh`:

**API checks (sprint12_loop.sh):**
1. Health – backend reachable
2. Seed data – org/user/membership in Postgres
3. Strict missing user – 403 for unprovisioned user
4. Create shipment – 201 + shipment_id
5. Org mismatch – 403 when org doesn't match
6. Missing org header – 403 when X-Clerk-Org-Id absent
7. List shipments – 200 + created shipment visible
8. Analyze shipment – 202 accepted

**UI checks (optional, RUN_UI=1):**
- Shipments list loads
- Create shipment redirects to detail

**Current blocker:** UI tests require `PLAYWRIGHT_STORAGE_STATE` (Clerk session). With dev auth, we can add a dev-login-based storage state.

---

## 2. How to Test the Baseline

### Prerequisites Running

```bash
# Terminal 1: Docker + Backend
docker-compose up -d
sleep 5
./start_neco.sh

# Terminal 2: Frontend (for UI tests)
cd frontend && npm run dev
```

### Run API-Only Gate

```bash
RUN_UI=0 ./scripts/sprint12_qa_gate.sh
```

**Expected:** Exit 0, all 8 API checks PASS.

### Run Full Gate (API + UI)

**Option A – Clerk (manual setup):**
```bash
cd frontend
mkdir -p .auth
npx playwright codegen http://localhost:3001/sign-in --save-storage=.auth/clerk-state.json
# Sign in, select org, close browser

cd ..
./scripts/sprint12_qa_gate.sh
```

**Option B – Dev auth (proposed):** Add a setup script that uses Playwright to visit `/dev-login`, click the button, and save storage state. Then UI tests run without Clerk.

---

## 3. Missing Steps to Reach Baseline

| Step | Status | Action |
|------|--------|--------|
| Docker running | ? | `docker-compose up -d` |
| Migrations applied | ? | `cd backend && alembic upgrade head` |
| Sprint 12 seed | ? | `./scripts/sprint12_loop.sh` (run by gate) |
| Backend on 9001 | ? | `./start_neco.sh` |
| Frontend .env.local | ? | Clerk keys + `NEXT_PUBLIC_API_URL` |
| UI storage state | Blocked | Clerk codegen or dev-auth setup |

---

## 4. MVP Definition

**MVP = Core happy path in < 5 minutes**

A compliance director can:
1. **Log in** (Clerk or dev auth)
2. **Create a shipment** (or upload CI)
3. **See analysis** (HTS, duty, PSC flags, money impact)
4. **Review** (accept/reject classification)
5. **Export** filing-prep bundle for broker

---

## 5. MVP Gap Analysis

### Built (Sprint 12 + prior)

| Component | Status |
|-----------|--------|
| Auth (Clerk + dev bypass) | Done |
| Shipments CRUD | Done |
| Shipment analyze (202) | Done |
| Classification engine | Done |
| PSC Radar | Done |
| Broker filing-prep API | Done |
| Review/override API | Done |
| Frontend: list, new, detail | Done |
| Dev auth bypass | Done |

### Missing for MVP

| Gap | Priority | Effort |
|-----|----------|--------|
| **Shipment detail: Analysis view** | Critical | 2–3 days |
| **Document upload** (CI) in UI | Critical | 1–2 days |
| **Review/override UI** | High | 1–2 days |
| **Export button + download** | High | 0.5–1 day |
| **UI QA gate with dev auth** | Medium | 0.5 day |
| **Clerk JWT validation** (pre-pilot) | Medium | 1 day |

### Analysis View (8 sections from Sprint 11)

The shipment detail page needs to show:
1. Outcome Summary
2. Money Impact
3. Risk Summary
4. Structural Analysis
5. PSC Radar
6. Enrichment Evidence
7. Review Status
8. Audit Trail

Backend already returns this via analysis/review APIs. Frontend needs to fetch and render it.

---

## 6. Recommended Next Sprints

For full success criteria and completion gates, see **[docs/SPRINT_ROADMAP_LOCKED.md](SPRINT_ROADMAP_LOCKED.md)**.

### Sprint 13: Analysis View (MVP critical path)

**Goal:** Shipment detail shows full analysis after "Analyze" runs.

**Deliverables:**
- Fetch analysis result from backend
- Render 8 sections (or minimal subset)
- Loading/error states
- Link from shipments list to detail

**Success:** Create shipment → Analyze → See analysis on detail page.

**Estimate:** 2–3 days

---

### Sprint 14: Document Upload + Export

**Goal:** Upload CI, extract fields, and export filing-prep.

**Deliverables:**
- Document upload on shipment (presign flow)
- Extract fields integration
- Export button → download filing-prep bundle
- Block export if REVIEW_REQUIRED

**Estimate:** 1–2 days

---

### Sprint 15: Review UI + Polish

**Goal:** Review/override workflow and MVP polish.

**Deliverables:**
- Review status display
- Accept/reject with notes
- Override UI (with audit warning)
- Error handling, empty states

**Estimate:** 1–2 days

---

## 7. Quick Win: Dev-Auth UI Tests

To unblock the UI gate without Clerk:

1. **Add `scripts/playwright_dev_auth_setup.sh`** that:
   - Starts Playwright (or uses existing)
   - Goes to `FRONTEND_BASE_URL/dev-login`
   - Clicks "Login as test user"
   - Waits for redirect to `/app/shipments`
   - Saves storage state to `frontend/.auth/dev-auth-state.json`

2. **Update `sprint12_qa_gate.sh`** to accept `USE_DEV_AUTH=1`:
   - When set, run dev-auth setup (or use pre-generated state)
   - Set `PLAYWRIGHT_STORAGE_STATE` to dev-auth state
   - Require `NEXT_PUBLIC_DEV_AUTH=true` on frontend

3. **Frontend** must be built/run with `NEXT_PUBLIC_DEV_AUTH=true` for this path.

**Estimate:** 0.5 day

---

## 8. Summary

| Item | Status |
|------|--------|
| **Baseline** | Sprint 12 (shipments, org-scoped, dev auth) |
| **Baseline test** | `./scripts/sprint12_qa_gate.sh` (API: 8 checks) |
| **API gate** | Passes when Docker + backend running |
| **UI gate** | Blocked on Clerk storage state (or dev-auth setup) |
| **MVP distance** | ~5–7 days (Analysis view, upload, export, review UI) |
| **First MVP milestone** | Sprint 13: Analysis view on shipment detail |
| **Sprint map** | See [docs/SPRINT_ROADMAP_LOCKED.md](SPRINT_ROADMAP_LOCKED.md) for full sprint definitions and completion gates |

---

## 9. Post-MVP Sprints (17–20)

After MVP hardening (Sprint 16), the roadmap extends with:

| Sprint | Focus |
|--------|-------|
| **17** | User-Selectable Analysis Preferences (psc_threshold, resource_mode, analyze_coo/duty/hs_code) |
| **18** | Bulk Import (zip upload, create shipments, enqueue analyses) |
| **19** | Duty Rates Accuracy + Section 301 Overlay |
| **20** | Compliance Signal Engine (regulatory monitoring, signal classification, PSC Radar alerts) |

See **[docs/SPRINT17_PLUS_BACKLOG.md](SPRINT17_PLUS_BACKLOG.md)** for full breakdown. Compliance Signal Engine: [docs/COMPLIANCE_SIGNAL_ENGINE.md](COMPLIANCE_SIGNAL_ENGINE.md), [docs/REGULATORY_MONITORING.md](REGULATORY_MONITORING.md).

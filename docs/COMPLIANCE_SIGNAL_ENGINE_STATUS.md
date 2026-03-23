# Compliance Signal Engine — Status & Execution Guide

**Purpose:** Clear split of what is done, what you run, and what the AI executes. This is the MOAT — compliance intelligence from external signals.

**Last updated:** March 17, 2026

---

## 1. Where We Are Right Now

### Sprint 20 (Compliance Signal Engine) — IMPLEMENTED

The full pipeline is in the codebase:

| Component | Status | Location |
|-----------|--------|----------|
| **Database schema** | Done | Migration 011 applied; tables exist |
| **Models** | Done | `raw_signal`, `normalized_signal`, `signal_classification`, `signal_score`, `psc_alert`, `importer_hts_usage` |
| **Sources config** | Done | `backend/config/sources_config.json` |
| **Feed poller** | Done | `backend/app/services/regulatory_feed_poller.py` (all tiers) |
| **Classification engine** | Done | `backend/app/engines/signal_classification.py` (LLM + rules) |
| **Scoring service** | Done | `backend/app/services/signal_scoring_service.py` |
| **PSC alert service** | Done | `backend/app/services/psc_alert_service.py` |
| **Importer HTS usage** | Done | `backend/app/services/importer_hts_usage_service.py` (Tier 8) |
| **Celery tasks** | Done | `poll_regulatory_feeds`, `process_regulatory_signals`, `refresh_importer_hts_usage` |
| **APIs** | Done | `GET/POST /api/v1/regulatory-updates`, `POST /regulatory-updates/refresh-hts-usage`, `GET/PATCH /api/v1/psc-radar/alerts` |
| **Frontend** | Done | PSC Radar page at `/app/psc-radar`, nav link, Analysis tab link |

### Data Sources (All Tiers Implemented)

| Tier | Source | Type | Status |
|------|--------|------|--------|
| **1** | CBP CSMS, ACE, Duty Rates, Legal Decisions | RSS | ✅ |
| **1** | Federal Register | API | ✅ |
| **1** | USITC HTS (diff-based) | API | ✅ |
| **1** | USTR News, Press | RSS | ✅ |
| **1** | CBP CROSS rulings | Scrape | ✅ |
| **2** | OFAC Recent Actions | Scrape | ✅ |
| **2** | FDA Import Alerts | Scrape | ✅ |
| **2** | USDA FSIS | RSS | ✅ |
| **2** | BIS Federal Register | API | ✅ |
| **2** | ITA AD/CVD | RSS | ✅ |
| **3** | WTO News | RSS | ✅ |
| **3** | EU TAXUD | RSS | ✅ |
| **3** | WCO News | Scrape | ✅ |
| **4** | White House Briefing | RSS | ✅ |
| **4** | Congress.gov | API | ✅ (requires CONGRESS_API_KEY) |
| **5** | CBP Quota, UBR | RSS | ✅ |
| **6** | FreightWaves, JOC, SupplyChainDive, Flexport | RSS | ✅ |
| **7** | CBP CROSS vectorization | — | Pending (enhancement) |
| **8** | Importer HTS usage (internal) | Job | ✅ |

### What the AI Has Already Executed (No Action Needed)

- Created all docs, models, services, APIs, and UI
- Ran migration 011 (tables exist)
- Stamped alembic version 011
- Added `feedparser` to requirements.txt

---

## 2. What YOU Need to Execute (Your Side)

**Full MVP run:** See [docs/MVP_RUN_GUIDE.md](MVP_RUN_GUIDE.md) for starting all services (backend, frontend, Celery worker, Celery beat) and keeping them running.

### One-Time Setup

```bash
# 1. Install feedparser (if not already)
cd backend && pip install feedparser==6.0.11

# 2. Verify migration (should already be at 011)
alembic current
# Expected: 011 (head)
```

### To Run the Signal Engine

**Option A: Manual trigger (no Celery)**

1. Start backend: `./start_neco.sh`
2. Start frontend: `cd frontend && npm run dev`
3. Log in (dev auth or Clerk)
4. **Poll feeds:** Call `POST /api/v1/regulatory-updates/process` with your org header — or run the Celery task once (see Option B)
5. **Process signals:** Same endpoint — it processes unprocessed raw signals for your org
6. View alerts: Go to `/app/psc-radar`

**Option B: Scheduled (Celery Beat)**

```bash
# Terminal 1: Celery worker
cd backend && celery -A app.core.celery_app worker -l info

# Terminal 2: Celery beat (schedules poll + process hourly)
cd backend && celery -A app.core.celery_app beat -l info
```

- **Poll:** Every hour — fetches all 24 sources (Tiers 1–6), inserts into `raw_signals`
- **Process:** Every hour + 100s — normalizes, classifies, scores, creates `psc_alerts` when score > 70
- **Refresh HTS usage:** Daily — populates `importer_hts_usage` from ShipmentItem (Tier 8)

### To Populate Data (First Run)

If you have no raw signals yet:

```bash
# Trigger poll manually (requires Celery worker running)
celery -A app.core.celery_app call app.tasks.regulatory.poll_regulatory_feeds

# Then trigger process (or wait for beat)
celery -A app.core.celery_app call app.tasks.regulatory.process_regulatory_signals --kwargs='{"limit": 50}'
```

Or use the API (with auth headers):

```bash
# Process (also works if poller has already run and inserted raw signals)
curl -X POST "http://localhost:9001/api/v1/regulatory-updates/process?limit=20" \
  -H "Authorization: Bearer YOUR_TOKEN" \
  -H "X-Clerk-Org-Id: YOUR_ORG_ID"
```

---

## 3. What the AI Will Execute Directly (When You Ask)

When you say "implement X" or "fix Y", the AI will:

- Edit code (Python, TypeScript, migrations, config)
- Create/update docs
- Run read-only commands (grep, search, read files)
- **Not** run long-lived processes (backend, Celery, frontend dev server)
- **Not** commit to git (unless you ask)
- **Not** deploy to production

### What the AI Cannot Do For You

- Start/stop Docker, backend, frontend, Celery
- Sign in to Clerk or create real user sessions
- Hit external URLs (CBP, Federal Register) — that happens when *you* run the poller
- Verify end-to-end in a live browser — that’s your manual check

---

## 4. Pipeline Flow (Reference)

```
[You run: Celery Beat + Worker]
        │
        ▼
┌───────────────────┐
│ poll_regulatory_  │  ← Fetches all tiers (CBP, FR, USITC, USTR, CROSS, OFAC, FDA, etc.)
│ feeds (hourly)    │     Inserts into raw_signals
└─────────┬─────────┘
         │
         ▼
┌───────────────────┐
│ process_regulatory│  ← For each org: normalize → classify → score
│ signals (hourly)  │     Creates psc_alerts when final_score > 70
└─────────┬─────────┘
         │
         ▼
┌───────────────────┐
│ PSC Radar UI      │  ← You visit /app/psc-radar
│ /api/v1/psc-radar │     GET alerts, PATCH status (reviewed/dismissed)
└───────────────────┘
```

---

## 5. Quick Verification Checklist

| Step | You Run | Expected |
|------|---------|----------|
| 1 | `alembic current` | `011` |
| 2 | `./start_neco.sh` | Backend on 9001 |
| 3 | Visit http://localhost:9001/docs | Swagger loads |
| 4 | GET /api/v1/regulatory-updates | 200 (may be empty) |
| 5 | GET /api/v1/psc-radar/alerts | 200 (may be empty) |
| 6 | Visit /app/psc-radar (logged in) | PSC Radar page loads |
| 7 | Run poll + process (Celery or API) | raw_signals and psc_alerts get rows |
| 8 | POST /regulatory-updates/refresh-hts-usage | Refreshes importer HTS (Tier 8) |

---

## 6. If Something Breaks

- **Migration fails:** DB may be in a bad state. Share the error; AI can adjust migration or suggest fixes.
- **Poller returns 0 signals:** CBP/USTR URLs can block or change. AI can update `sources_config.json` or add retries.
- **No alerts in PSC Radar:** Need raw signals first (run poll), then process. Scoring depends on org HTS usage; new orgs may score low.
- **Celery not running:** You must start worker + beat. AI cannot start processes for you.

---

## 7. Gaps & Priorities (Pinned Backlog)

See **[docs/COMPLIANCE_SIGNAL_ENGINE_GAPS.md](COMPLIANCE_SIGNAL_ENGINE_GAPS.md)** for:

- Pinned previous priorities (link alerts to shipments, verify CBP CROSS, per-source scheduling, etc.)
- GAP 1–10: Quota engine, Tariff mapping, FDA admissibility, CBP CROSS, Real-time signals, HTS filtering, Importer-aware mapping, Financial impact, Output structure, Success criteria

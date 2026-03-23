# NECO Project Status

**Last Updated:** February 24, 2026

---

## 1. What NECO Is

**NECO** (Next-Gen Compliance Engine) is an AI-powered customs compliance platform for U.S. importers. It automates HS classification, surfaces PSC (Post Summary Correction) opportunities, processes trade documents, and helps identify duty savings.

**Target use case:** Process 25+ AURA shipments to find duty savings through better HTS classification and PSC filings.

---

## 2. What's Built (Current State)

### Backend (FastAPI)

| Router | Prefix | Purpose |
|--------|--------|---------|
| auth | `/api/v1/auth` | Login, register, me |
| documents | `/api/v1/documents` | Legacy document upload (deprecated) |
| health | `/api/v1/health` | Health check, knowledge-base metrics |
| classification | `/api/v1/classification` | Generate alternatives, get by SKU |
| compliance | `/api/v1/compliance` | Dashboard, reports, audit-pack, drilldown |
| broker | `/api/v1/broker` | Filing prep bundle |
| enrichment | `/api/v1/enrichment` | Document ingest, extract |
| shipments | `/api/v1/shipments` | Create, list, analyze shipments |
| shipment_documents | `/api/v1/shipment-documents` | Presign, confirm, list |
| reviews | `/api/v1/reviews` | Get review, list by shipment, override |
| exports | `/api/v1/exports` | Audit pack, broker prep export |

### Engines

- **Classification Engine** – Generates alternative HTS codes using text similarity, context builder, product analysis, duty selection by COO
- **PSC Radar** – Read-only intelligence for classification-driven risk signals
- **Ingestion** – PDF extraction, Excel parsing, Claude AI field detection, OCR, Vision API
- **Regulatory Applicability** – Side Sprint A evaluations

### Frontend (Next.js 14)

- **Auth:** Clerk (sign-in, sign-up)
- **Pages:** Organizations (select, new, [id]), Shipments (list, new, [shipmentId])
- **Stack:** TypeScript, Tailwind, Radix UI, Playwright for tests

### Data

- **HTS:** ~19K codes from 2025HTS.pdf, duty rates (general, special, column 2)
- **CFR:** 360 regulation sections
- **Entry Summary Guide:** 39 fields
- **HTS Headings:** 34 headings
- **ACE:** 25 sections

---

## 3. Architecture: Two Workflows

| Feature | Legacy (Entry) | Sprint 12 (Shipment) |
|---------|----------------|----------------------|
| Tenant | `client_id` | `organization_id` (Clerk) |
| Storage | Local (UPLOAD_DIR) | S3 (presigned) |
| Endpoints | `/api/v1/documents` | `/api/v1/shipments`, `/api/v1/shipment-documents` |
| Status | Deprecated | Active |

See [backend/app/models/LEGACY_DOCUMENTS_DEPRECATION.md](backend/app/models/LEGACY_DOCUMENTS_DEPRECATION.md) for details.

---

## 4. What Remains to Build

### MVP Blockers

- [ ] **UI QA gate** – Playwright requires Clerk-authenticated storage state (`PLAYWRIGHT_STORAGE_STATE`). See [scripts/QA_LOOP.md](scripts/QA_LOOP.md).
- [ ] **Clerk JWT validation** – Backend currently trusts `X-Clerk-User-Id` and `X-Clerk-Org-Id` headers for dev; must validate Clerk JWT before pilot.

### Post-MVP

- [ ] Full migration from legacy documents to Sprint 12 workflow
- [ ] Deployment / production infrastructure
- [ ] CROSS rulings integration

---

## 5. How to Run

### Prerequisites

- Docker (PostgreSQL + Redis)
- Python 3.9+
- Node.js (for frontend)

### Quick Start

```bash
# 1. Start Docker services
docker-compose up -d

# 2. Run migrations and seed (once)
cd backend && alembic upgrade head && cd ..
./scripts/sprint12_loop.sh

# 3. Start all MVP services (backend, frontend, Celery worker, Celery beat)
./scripts/start_mvp_all.sh
```

Or start manually in 4 terminals — see [docs/MVP_RUN_GUIDE.md](docs/MVP_RUN_GUIDE.md).

**Stop all:** `./scripts/stop_mvp_all.sh`

See [docs/STARTUP_CHECKLIST.md](docs/STARTUP_CHECKLIST.md) for full steps.

### Dev Auth Bypass

To skip Clerk sign-in when testing locally:

1. Add `NEXT_PUBLIC_DEV_AUTH=true` to `frontend/.env.local`
2. Visit http://localhost:3001/dev-login
3. Click "Login as test user (dev only)"

Requires Sprint 12 seed data (`./scripts/sprint12_loop.sh`). Token lasts 7 days.

### API

- **API Base:** http://localhost:9001 (configurable)
- **Swagger UI:** http://localhost:9001/docs
- **Health:** http://localhost:9001/health

### QA Gate

```bash
./scripts/sprint12_qa_gate.sh
# With UI: BASE_URL=http://localhost:9001 FRONTEND_BASE_URL=http://localhost:3001 RUN_UI=1 ./scripts/sprint2_daily_qa_hardening.sh
```

---

## 6. Key Docs

| Doc | Purpose |
|-----|---------|
| [README.md](README.md) | Quick start |
| [HOW_TO_RUN.md](HOW_TO_RUN.md) | Classification engine API details |
| [SPRINT12_STATUS.md](SPRINT12_STATUS.md) | Sprint 12 progress tracker |
| [scripts/QA_LOOP.md](scripts/QA_LOOP.md) | QA gate instructions |
| [backend/DUTY_DATA_MODEL_README.md](backend/DUTY_DATA_MODEL_README.md) | Duty rate model |
| [backend/RUN_MIGRATION.md](backend/RUN_MIGRATION.md) | Database migrations |
| [backend/app/engines/PSC_RADAR_DOCUMENTATION.md](backend/app/engines/PSC_RADAR_DOCUMENTATION.md) | PSC Radar behavior |
| [backend/app/models/LEGACY_DOCUMENTS_DEPRECATION.md](backend/app/models/LEGACY_DOCUMENTS_DEPRECATION.md) | Legacy vs Sprint 12 |
| [docs/archive/](docs/archive/) | Historical sprint docs |
| [docs/STARTUP_CHECKLIST.md](docs/STARTUP_CHECKLIST.md) | Full startup steps |
| [docs/BASELINE_AND_MVP_ROADMAP.md](docs/BASELINE_AND_MVP_ROADMAP.md) | Baseline sprint, MVP gap, next steps |

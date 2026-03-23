# NECO MVP — Full Run Guide

**Purpose:** Run the complete MVP with all services. All four services must stay running for the full experience (shipments, analysis, PSC Radar, regulatory signals).

**Last updated:** March 17, 2026

---

## Services Required (All Must Run)

| # | Service | Purpose | Port |
|---|---------|---------|------|
| 1 | **Docker** (Postgres + Redis) | Database and Celery broker | 5432, 6379 |
| 2 | **Backend** (FastAPI) | API, analysis orchestration | 9001 |
| 3 | **Frontend** (Next.js) | Web UI | 3001 |
| 4 | **Celery Worker** | Runs analysis tasks, regulatory poll/process | — |
| 5 | **Celery Beat** | Schedules regulatory poll + process hourly | — |

---

## Prerequisites (One-Time)

```bash
# 1. Docker running
docker-compose up -d

# 2. Migrations
cd backend
source venv/bin/activate   # or: source ../venv_neco/bin/activate
alembic upgrade head

# 3. Seed data (for dev auth)
cd ..
./scripts/sprint12_loop.sh

# 4. Frontend env
# Create frontend/.env.local with NEXT_PUBLIC_API_URL=http://localhost:9001
# Add NEXT_PUBLIC_DEV_AUTH=true for dev login bypass
```

---

## Start All Services (4 Terminals)

**Terminal 1 — Backend**
```bash
cd /Users/stevenbigio/Cursor\ Projects/NECO
./start_neco.sh
```
Leave running. Backend: http://localhost:9001

---

**Terminal 2 — Frontend**
```bash
cd /Users/stevenbigio/Cursor\ Projects/NECO/frontend
npm run dev
```
Leave running. Frontend: http://localhost:3001

---

**Terminal 3 — Celery Worker**
```bash
cd /Users/stevenbigio/Cursor\ Projects/NECO/backend
source venv/bin/activate
celery -A app.core.celery_app worker -l info
```
Leave running. Handles: shipment analysis, regulatory poll, regulatory process.

---

**Terminal 4 — Celery Beat**
```bash
cd /Users/stevenbigio/Cursor\ Projects/NECO/backend
source venv/bin/activate
celery -A app.core.celery_app beat -l info
```
Leave running. Schedules: poll_regulatory_feeds (hourly), process_regulatory_signals (hourly + 100s).

---

## Run in Background (Optional)

To avoid keeping 4 terminals open:

```bash
cd /Users/stevenbigio/Cursor\ Projects/NECO

# Backend
./start_neco.sh > logs/backend.log 2>&1 &

# Frontend
cd frontend && npm run dev > ../logs/frontend.log 2>&1 &

# Celery worker
cd backend && source venv/bin/activate && celery -A app.core.celery_app worker -l info > ../logs/celery-worker.log 2>&1 &

# Celery beat
cd backend && source venv/bin/activate && celery -A app.core.celery_app beat -l info > ../logs/celery-beat.log 2>&1 &
```

Create logs dir first: `mkdir -p logs`

To stop background processes:
```bash
pkill -f "uvicorn app.main"
pkill -f "next-server"
pkill -f "celery.*worker"
pkill -f "celery.*beat"
```

---

## One-Command Startup Script

Use the provided script to start all services in background:

```bash
./scripts/start_mvp_all.sh
```

See [scripts/start_mvp_all.sh](../scripts/start_mvp_all.sh) for details.

---

## Verify All Services

| Check | URL | Expected |
|-------|-----|----------|
| Backend | http://localhost:9001/health | `{"status":"healthy"}` |
| API docs | http://localhost:9001/docs | Swagger UI |
| Frontend | http://localhost:3001 | App loads |
| Dev login | http://localhost:3001/dev-login | Login as test user |
| PSC Radar | http://localhost:3001/app/psc-radar | After login |

---

## What Happens When Running

- **Backend:** Serves API; triggers Celery for analysis when user clicks "Analyze"
- **Frontend:** Web UI for shipments, analysis, PSC Radar
- **Celery Worker:** Runs `run_shipment_analysis`, `poll_regulatory_feeds`, `process_regulatory_signals`
- **Celery Beat:** Sends poll + process tasks to worker every hour

---

## Troubleshooting

| Issue | Fix |
|-------|-----|
| Port 9001 in use | `lsof -i :9001` then `kill -9 <PID>` |
| Port 3001 in use | `lsof -i :3001` then `kill -9 <PID>` |
| Celery "Connection refused" | Ensure Redis is running: `docker ps` |
| Analysis never completes | Celery worker must be running |
| PSC Radar empty | Run poll + process (Celery or API); wait for hourly beat |
| No venv in backend | Use `venv_neco` at project root: `source venv_neco/bin/activate` |

---

## Related Docs

- [docs/STARTUP_CHECKLIST.md](STARTUP_CHECKLIST.md) — Prerequisites, migrations, seed
- [docs/COMPLIANCE_SIGNAL_ENGINE_STATUS.md](COMPLIANCE_SIGNAL_ENGINE_STATUS.md) — Signal engine details
- [docs/SPRINT_ROADMAP_LOCKED.md](SPRINT_ROADMAP_LOCKED.md) — Sprint definitions

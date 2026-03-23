# NECO Startup Checklist

## Prerequisites

- Docker (PostgreSQL + Redis)
- Python 3.9+
- Node.js 18+ (for frontend)

## Full MVP Run (All Services)

**For the complete MVP including PSC Radar and regulatory signals, all 5 services must run:**

1. Docker (Postgres + Redis)
2. Backend (FastAPI)
3. Frontend (Next.js)
4. Celery Worker (analysis + regulatory tasks)
5. Celery Beat (schedules regulatory poll/process hourly)

**Quick start:** See [docs/MVP_RUN_GUIDE.md](MVP_RUN_GUIDE.md) for the full guide.

**One-command start (background):**
```bash
./scripts/start_mvp_all.sh
```

**Stop all:**
```bash
./scripts/stop_mvp_all.sh
```

---

## Step-by-Step Startup

### 1. Start Docker Services

```bash
cd /path/to/NECO
docker-compose up -d
```

Wait a few seconds for Postgres to initialize.

### 2. Run Database Migrations

```bash
cd backend
source ../venv_neco/bin/activate  # or: venv_neco/bin/activate
alembic upgrade head
cd ..
```

### 3. Seed Sprint 12 Test Data (Required for Shipments)

```bash
./scripts/sprint12_loop.sh
```

This seeds organizations, users, and memberships. Run once per environment.

### 4. Start Backend

```bash
./start_neco.sh
```

Backend runs on **http://localhost:9001**

- API docs: http://localhost:9001/docs
- Health: http://localhost:9001/health

### 5. Configure Frontend Environment

Create `frontend/.env.local`:

```
NEXT_PUBLIC_CLERK_PUBLISHABLE_KEY=pk_...
NEXT_PUBLIC_API_URL=http://localhost:9001
```

For **dev auth bypass** (skip Clerk sign-in when testing):

```
NEXT_PUBLIC_DEV_AUTH=true
```

### 6. Start Frontend

```bash
cd frontend
npm install
npm run dev
```

Frontend runs on **http://localhost:3001**

### 6b. Start Celery Worker and Beat (Required for Analysis + PSC Radar)

For shipment analysis and the Compliance Signal Engine (PSC Radar, regulatory alerts):

```bash
# Terminal 3: Celery worker
cd backend
source venv/bin/activate   # or: source ../venv_neco/bin/activate
celery -A app.core.celery_app worker -l info

# Terminal 4: Celery beat (in a separate terminal)
cd backend
source venv/bin/activate
celery -A app.core.celery_app beat -l info
```

Both must stay running. Without the worker, analysis tasks will not complete. Without beat, regulatory signals will not be polled/processed on a schedule.

### 7. Access the App

- **With Clerk:** http://localhost:3001 → sign in
- **With dev auth:** http://localhost:3001/dev-login → click "Login as test user"

### 8. Run QA Gate (Optional)

With backend and frontend running (and `NEXT_PUBLIC_DEV_AUTH=true` for dev auth):

```bash
USE_DEV_AUTH=1 ./scripts/sprint12_qa_gate.sh
```

See [scripts/QA_LOOP.md](../scripts/QA_LOOP.md) for options.

## Root .env

Ensure project root `.env` has:

- `ANTHROPIC_API_KEY` – for classification
- `SECRET_KEY` – for JWT signing
- `DATABASE_URL` – Postgres connection string

**For unlimited analyses during dev/debug** (avoids "15 of 15 analyses used"):

- `ENTITLEMENT_UNLIMITED_EMAILS=qa-sprint12-loop@example.com` – dev login user gets unlimited analyses

## Restart backend

After changing `backend/.env` or code, stop the backend (Ctrl+C in its terminal), then from project root:

```bash
./start_neco.sh
```

Or without Docker startup (backend only):

```bash
source venv_neco/bin/activate && cd backend && python -m uvicorn app.main:app --host 0.0.0.0 --port 9001 --reload
```

## Analysis duration

- **Typical run:** 1–3 minutes (sync dev mode).
- Progress tracker shows 6 steps; step 6 **Completed** means results are ready to view. If the request times out or is cancelled, use **Check for results** or **Re-run** as needed.

## Troubleshooting

| Issue | Fix |
|-------|-----|
| Port 9001 in use | `lsof -i :9001` then `kill -9 <PID>` |
| Database connection failed | Ensure Docker is running, `docker ps` |
| Dev login fails | Run `./scripts/sprint12_loop.sh` to seed test data |
| Frontend 401 | Check `NEXT_PUBLIC_API_URL` matches backend port |

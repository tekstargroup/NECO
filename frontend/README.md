# NECO Frontend - Sprint 12

## Quick Start

### 1. Install Dependencies

```bash
cd frontend
npm install
```

### 2. Configure Environment

Create `frontend/.env.local` (see `.env.example` for all flags):
```
NEXT_PUBLIC_CLERK_PUBLISHABLE_KEY=pk_...
NEXT_PUBLIC_API_URL=http://localhost:9001
```

`NEXT_PUBLIC_API_URL` must match wherever the FastAPI process is listening (default in this repo is **9001**). If the backend runs on another port (for example 8000), set this to that origin and restart `npm run dev` so the dev-login page and API client use the same URL.

**Important**: Do NOT put `CLERK_SECRET_KEY` in frontend `.env.local`. It's a server-side secret and should only be in the backend environment if needed.

### 3. Start Dev Server

```bash
npm run dev
```

Frontend will run on `http://localhost:3001`

## Testing

See `TEST_EXECUTION_GUIDE.md` for detailed test instructions.

### Quality gates (re-run after big changes)

| Command | What it checks |
|--------|----------------|
| Repo root: `./scripts/local_quality_gate.sh` | Backend `pytest tests/`, then `npm run qa:static` (lint + production build). Needs `DATABASE_URL` in `backend/.env`. |
| `npm run qa:static` | Frontend only: lint + `next build`. |
| `npm run qa:ui:dev` | **Playwright** smoke (shipments list + create flow) using dev login. Requires API + Next running, `NEXT_PUBLIC_DEV_AUTH=true`, Sprint 12 seed, and `FRONTEND_BASE_URL` matching your dev server (often `http://localhost:3000`). |
| `RUN_PLAYWRIGHT=1 ./scripts/local_quality_gate.sh` | Static gate, then same Playwright path as `qa:ui:dev`. |

**Playwright:** already set up (`@playwright/test`, `tests/smoke/sprint12.spec.ts`). Install browsers once: `npm run qa:playwright:install`. Config defaults to `http://localhost:3001`; override with `FRONTEND_BASE_URL` if you use port 3000.

## Backend Prerequisites

- Backend API on `http://localhost:9001`
- PostgreSQL running
- Redis running  
- Celery worker running

## Dev Auth Bypass

To skip Clerk sign-in when testing locally:

1. Add to `frontend/.env.local`:
   ```
   NEXT_PUBLIC_DEV_AUTH=true
   ```

2. Visit http://localhost:3001/dev-login

3. Click "Login as test user (dev only)"

Requires Sprint 12 seed data in the **same database** the API uses:

- **Docker Postgres** (container name `neco_postgres` by default): `./scripts/sprint12_loop.sh` (set `BASE_URL` and `PG_CONTAINER` if needed).
- **Any Postgres** (no Docker `exec`): from `backend/`, `python scripts/seed_sprint12_dev_login.py`.

Backend must expose `/api/v1/auth/dev-token` (`ENVIRONMENT=development`, `dev`, or `local`). If the button shows **Not found** (404), fix backend `ENVIRONMENT`. If it shows a **network** error, fix `NEXT_PUBLIC_API_URL` and ensure the API is running.

Token lasts 7 days. Use "Dev Logout" in the app header to clear and return to dev-login.

## Architecture Notes

### Auth Headers (Development Only)

The frontend currently sends `X-Clerk-User-Id` and `X-Clerk-Org-Id` headers for development/testing.

**TODO**: Backend must validate Clerk JWT tokens for authority before any pilot. Headers are not trusted in production.

See `backend/app/api/dependencies_sprint12.py` for the TODO comments.

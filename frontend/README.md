# NECO Frontend - Sprint 12

## Quick Start

### 1. Install Dependencies

```bash
cd frontend
npm install
```

### 2. Configure Environment

Create `frontend/.env.local`:
```
NEXT_PUBLIC_CLERK_PUBLISHABLE_KEY=pk_...
NEXT_PUBLIC_API_URL=http://localhost:9001
```

**Important**: Do NOT put `CLERK_SECRET_KEY` in frontend `.env.local`. It's a server-side secret and should only be in the backend environment if needed.

### 3. Start Dev Server

```bash
npm run dev
```

Frontend will run on `http://localhost:3001`

## Testing

See `TEST_EXECUTION_GUIDE.md` for detailed test instructions.

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

Requires Sprint 12 seed data (`./scripts/sprint12_loop.sh`). Token lasts 7 days. Use "Dev Logout" in the app header to clear and return to dev-login.

## Architecture Notes

### Auth Headers (Development Only)

The frontend currently sends `X-Clerk-User-Id` and `X-Clerk-Org-Id` headers for development/testing.

**TODO**: Backend must validate Clerk JWT tokens for authority before any pilot. Headers are not trusted in production.

See `backend/app/api/dependencies_sprint12.py` for the TODO comments.

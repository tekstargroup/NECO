# Frontend Setup Required

## Current Status

❌ **Node.js/npm not found in shell PATH**

The test execution requires Node.js and npm to be installed and available in your system PATH.

## Quick Setup

### 1. Install Node.js (if needed)

**macOS (Homebrew)**:
```bash
brew install node
```

**Or download from**: https://nodejs.org (LTS version recommended)

**Verify**:
```bash
node --version  # Should be v18+ or v20+
npm --version   # Should be 9+
```

### 2. Install Frontend Dependencies

```bash
cd "/Users/stevenbigio/Cursor Projects/NECO/frontend"
npm install
```

### 3. Configure Environment

Create `frontend/.env.local`:
```
NEXT_PUBLIC_CLERK_PUBLISHABLE_KEY=pk_...
NEXT_PUBLIC_API_URL=http://localhost:9001
```

**Note**: `CLERK_SECRET_KEY` should NOT be in the frontend `.env.local`. It's a server-side secret and should only be in the backend environment if needed for server routes.

### 4. Start Frontend Dev Server

```bash
cd "/Users/stevenbigio/Cursor Projects/NECO/frontend"
npm run dev
```

Frontend will run on `http://localhost:3001`

## Backend Prerequisites

Verify these are running:
- ✅ Backend API on `http://localhost:9001`
- ✅ PostgreSQL running (Docker)
- ✅ Redis running (Docker)
- ✅ Celery worker running

## Next Steps

Once Node.js is installed and frontend is running:

1. Follow `TEST_EXECUTION_GUIDE.md` for manual test execution
2. Record results in test execution guide
3. Report any failures with API responses and backend logs

# Analysis pipeline: should this work?

**Yes.** After the fixes below, the pipeline is designed to either **complete with results** or **return a clear error** (never hang with "nothing").

## What was fixed

1. **Blocking the event loop** – Document processing (Claude extraction) was synchronous and blocked the async server. It now runs in a **thread pool** (`run_in_executor`), so the 4‑minute timeout can fire and the server stays responsive.

2. **Per-document timeout** – Each document has a **90-second** limit. If one file hangs, it’s skipped with a warning and the rest of the run continues.

3. **Endpoint always responds** – The `POST /analyze` handler is wrapped in try/except. If anything in orchestration raises, the API still returns **200** with `status: "FAILED"` and `error_message`, so the UI can show an error instead of "nothing."

4. **Request logging** – When you hit Analyze, the backend logs:  
   `POST /analyze shipment_id=... force_new=...`  
   so you can confirm the request reaches the server.

## How to verify

1. **Restart the backend** from the project root so it loads the latest code:
   ```bash
   cd /path/to/NECO
   ./start_neco.sh
   ```
   Or: `source venv_neco/bin/activate && cd backend && python -m uvicorn app.main:app --host 0.0.0.0 --port 9001 --reload`

2. **Watch the backend terminal** when you click **Analyze** or **Re-run (start fresh)**. You should see:
   - `POST /analyze shipment_id=... force_new=...`
   - Then either:
     - `Analysis start shipment_id=... INLINE_DEV=True SYNC_DEV=True ...`
     - `Running analysis synchronously ...`
     - Then either completion or a traceback

3. **If you see no log at all** – The request isn’t reaching the backend. Common cause: **proxy**. In `frontend/.env.local` set:
   - `NEXT_PUBLIC_USE_API_PROXY=false`
   - `NEXT_PUBLIC_API_URL=http://localhost:9001`
   Then restart the frontend (`npm run dev`). The browser will send API requests straight to the backend (port 9001). Try Analyze again and watch the backend terminal for `POST /analyze`.

4. **If you see the log but still no result in the UI** – Check for a traceback in the backend logs. The endpoint catch-all should then return 200 with `status: "FAILED"` and an `error_message`; the UI should show that. If the UI still shows "RUNNING" or nothing, the frontend may not be handling that payload (e.g. missing `analysis_id`).

5. **If analysis runs but takes a long time** – With `SPRINT12_FAST_ANALYSIS_DEV=True`, after document extraction the run uses the fast path (no full classification LLM). Document extraction can take tens of seconds per document (Claude). After at most 4 minutes the sync timeout fires and you get a FAILED response with a timeout message.

## Config that affects behavior

In `backend/.env`:

- `ENVIRONMENT=development` – Required for inline/sync and fast path.
- `SPRINT12_INLINE_ANALYSIS_DEV=True` – Run analysis in-process (no Celery).
- `SPRINT12_SYNC_ANALYSIS_DEV=True` – Wait for analysis in the request and return full status (so you get a response).
- `SPRINT12_FAST_ANALYSIS_DEV=True` – After document extraction, skip full classification/duty/PSC and return quickly.
- `SPRINT12_INSTANT_ANALYSIS_DEV=False` – Use the real pipeline (not the instant fake result).

If "still nothing" after a restart, the next step is to capture what appears in the **backend terminal** when you click Analyze (first few log lines and any traceback) and use that to see whether the request is received, which path runs, and where it fails.

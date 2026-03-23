# Analysis Pipeline: Debugging History and Fixes

**Last updated:** 2026-02-24  
**Context:** Multi-hour debugging session for analysis "completing" without results, Re-run button disabled, and disconnect between frontend, backend, and document storage.

**Bugs fixed this session:** (1) Document files not on disk → `files_not_found` flag, LOCAL_UPLOAD_BASE_URL. (2) Re-run disabled when shipment stuck ANALYZING → clear status on timeout, remove frontend check. (3) InvalidTextRepresentationError on ReviewRecord flush → sanitize object_snapshot and result_json for JSONB (NaN, numpy). (4) Failed-task cleanup used rolled-back session → use fresh session. (5) Circular JSON in debug logs → serialize primitives only, arrow wrappers on handlers. (6) "Taking longer" message at 1 min → moved to 4 min.

---

## For new agents: read these first

Before working on analysis or related features, read in this order:

| Doc | Purpose |
|-----|---------|
| **This file** (`docs/ANALYSIS_DEBUGGING_AND_FIXES.md`) | Architecture, fixes applied, open issues, troubleshooting |
| **`docs/NECO_ANALYSIS_PIPELINE.md`** | End-to-end flow, config, how each step works, "No line items – what to check" |

---

## Executive Summary

The analysis flow had several interconnected issues:

1. **Document files not on disk** – Uploads were not landing in `backend/data/mock_uploads`, so the analysis pipeline could not find files even though documents existed in the DB.
2. **Re-run button disabled** – `shipment.status` could stay `ANALYZING` when sync timed out (task cancelled before updating status), and the frontend disabled Re-run when `shipment.status === "ANALYZING"`.
3. **"Completed" without results** – UI showed "Analysis complete" with `result_json` but empty `items` (no line items), because document files were missing.
4. **Circular JSON in debug logs** – Instrumentation passed non-serializable values (e.g. React event) to `JSON.stringify`, causing runtime errors.

---

## Architecture Overview

```
┌─────────────────┐     POST /analyze      ┌─────────────────────┐
│   Frontend      │ ───────────────────►  │   Backend (FastAPI)  │
│   (Next.js)     │                       │   Port 9001          │
└────────┬────────┘                       └──────────┬──────────┘
         │                                            │
         │ NEXT_PUBLIC_USE_API_PROXY=false             │ Sync mode: runs pipeline
         │ → direct to localhost:9001                  │ in request, returns 200
         │                                             │ with full status
         │                                             ▼
         │                                    ┌─────────────────────┐
         │                                    │ ShipmentAnalysis    │
         │                                    │ Service             │
         │                                    │ - Parse documents   │
         │                                    │ - Import line items │
         │                                    │ - Build result_json │
         │                                    └──────────┬──────────┘
         │                                               │
         │                                               │ Looks for files in:
         │                                               │ backend/data/mock_uploads
         │                                               │ (when S3 not configured)
         │                                               ▼
         │                                    ┌─────────────────────┐
         │                                    │ DocumentProcessor   │
         │                                    │ - PDF/Excel extract  │
         │                                    │ - Line items from CI │
         │                                    └─────────────────────┘
         │
         │  Upload flow (Documents tab):
         │  presign → PUT mock-upload (with X-S3-Key) → confirm
         │  Files stored at: MOCK_UPLOADS_DIR / (s3_key with / → _)
         ▼
```

---

## Key Configuration

| Variable | Location | Purpose |
|----------|----------|---------|
| `NEXT_PUBLIC_USE_API_PROXY` | `frontend/.env.local` | `false` = API calls go directly to backend (localhost:9001). `true` = via Next.js proxy. |
| `NEXT_PUBLIC_API_URL` | `frontend/.env.local` | Backend base URL, e.g. `http://localhost:9001` |
| `LOCAL_UPLOAD_BASE_URL` | `backend/.env` | Forces presign to return upload URL that hits your backend. Use `http://localhost:9001` when behind proxy. |
| `SPRINT12_INLINE_ANALYSIS_DEV` | `backend/.env` | `true` = run analysis in-process (no Celery) |
| `SPRINT12_SYNC_ANALYSIS_DEV` | `backend/.env` | `true` = block until analysis completes, return 200 with full result |
| `SPRINT12_INSTANT_ANALYSIS_DEV` | `backend/.env` | `false` = run real pipeline. `true` = return minimal COMPLETE immediately (placeholder). |
| `SPRINT12_FAST_ANALYSIS_DEV` | `backend/.env` | `true` = fast path: ES duty, origin mismatch, PSC for high-duty items. `false` = full classification, duty resolver, PSC, regulatory (slower, complete analysis). |
| `PSC_DUTY_THRESHOLD` | `backend/.env` | Min duty (USD) to run PSC Radar in fast path. Default 1000; set lower (e.g. 100) for more coverage. |
| `MOCK_UPLOADS_DIR` | `backend/app/core/config.py` | Path to local uploads: `backend/data/mock_uploads` |

---

## Document Upload and Analysis Path Resolution

1. **Presign** – Backend returns `upload_url` and `s3_key`. When S3 is not configured, `upload_url` points to `{LOCAL_UPLOAD_BASE_URL}/api/v1/shipment-documents/mock-upload/{token}`.
2. **Mock upload** – Frontend PUTs file with `X-S3-Key` header. Backend stores at `MOCK_UPLOADS_DIR / safe_name` where `safe_name = s3_key.replace("/", "_")`.
3. **Confirm** – Creates `ShipmentDocument` with `s3_key`.
4. **Analysis** – For each document, resolves path: `MOCK_UPLOADS_DIR / safe_name`. If not found, tries legacy paths and filename fallback.

**Critical:** If `mock_uploads` is empty but documents exist in DB, analysis will run but produce no line items. The UI will show "No line items" or "files_not_found" hint.

**For real analysis (classification, duty alternatives, PSC):** Set `SPRINT12_FAST_ANALYSIS_DEV=False` in `backend/.env` and restart the backend. The fast path still surfaces ES duty, origin mismatch, and PSC for high-duty items; the full path runs the complete classification engine and regulatory evaluation.

---

## Fixes Applied

### 1. Backend: Clear `shipment.status` on sync timeout/exception

**File:** `backend/app/services/analysis_orchestration_service.py`

When sync analysis times out (4 min) or throws, the task is cancelled. It never reaches the code that sets `shipment.status = COMPLETE` or `FAILED`. The orchestration now explicitly sets `shipment.status = FAILED` when handling timeout or exception, so Re-run is not blocked.

### 2. Frontend: Stop disabling Re-run based on `shipment.status`

**File:** `frontend/src/components/shipment-tabs/analysis-tab.tsx`

Re-run was disabled when `shipment.status === "ANALYZING"`. Because that status could be stuck, Re-run stayed disabled. The condition was removed; Re-run is now disabled only when `analyzing === true` (request in flight).

### 3. Backend: `files_not_found` flag in evidence map

**File:** `backend/app/services/shipment_analysis_service.py`

When a document file is not on disk, `evidence_map["files_not_found"] = True` is set. Both fast and full analysis paths use this (plus warning message checks) to set `no_items_hint = "files_not_found"`, so the UI can show the "Re-upload your Entry Summary and Commercial Invoice" message instead of generic "No line items".

### 4. Backend: Configurable upload base URL

**File:** `backend/app/core/config.py`, `backend/app/services/s3_upload_service.py`, `backend/.env`

Added `LOCAL_UPLOAD_BASE_URL`. When set (e.g. `http://localhost:9001`), presign uses it for the mock upload URL instead of `request.base_url`, which can be wrong behind a proxy.

### 5. Frontend: "Taking longer than expected" at 4 minutes, not 1

**File:** `frontend/src/components/shipment-tabs/analysis-tab.tsx`

The warning appeared after 1 minute, but typical analysis is 1–3 minutes. Users saw it while the run was still in progress. Threshold changed from `60 * 1000` to `4 * 60 * 1000` ms. Message text updated to "4 minutes."

### 6. Backend: Sanitize review_snapshot and result_json for JSONB (InvalidTextRepresentationError)

**File:** `backend/app/tasks/analysis.py`

The pipeline completed (parse → import → fast analysis) but failed when persisting ReviewRecord. `object_snapshot` and `result_json` (both JSONB columns) contained non-JSON-serializable values: `float('nan')`, `float('inf')`, and numpy types (e.g. `numpy.float64`) from Excel/pandas extraction. PostgreSQL rejects these for JSONB. Added `_sanitize_for_jsonb()` to recursively convert NaN/inf to None, numpy scalars to Python types, and ensure JSON-serializability. Applied to both `object_snapshot` (ReviewRecord) and `result_json` (Analysis).

### 7. Backend: Use fresh session when marking analysis failed

**File:** `backend/app/tasks/analysis.py`

When the task throws, the task's db session is in a rolled-back state. Calling `_mark_analysis_failed_internal(db, ...)` with that session would fail (e.g. "Session's transaction has been rolled back"). Changed to use `_mark_analysis_failed(shipment_id, str(e))` which creates a fresh session, so the analysis and shipment can be correctly marked FAILED.

### 8. Frontend: Fix circular JSON in debug instrumentation

**File:** `frontend/src/components/shipment-tabs/analysis-tab.tsx`

When `handleAnalyze` was called as `onClick={handleAnalyze}` (no arrow), the first argument was the React event. Passing it to `JSON.stringify` caused "Converting circular structure to JSON". Two fixes: (a) All log payloads now use only serializable primitives (`String()`, `Boolean()`, `Number()`). (b) All button handlers now use arrow wrappers, e.g. `onClick={() => void handleAnalyze(true)}`, so the event is never passed.


---

## Debug Instrumentation (Optional)

Instrumentation was added for a debug session. It sends logs to `http://127.0.0.1:7656/ingest/...` (requires debug server) and writes backend logs to `logs/debug_analysis_aa7c8f.log`.

**Frontend logs:**
- `handleAnalyze:entry` – Analyze clicked
- `handleAnalyze:syncResponse` – Sync response received (status, hasResultJson, itemsCount)
- `handleAnalyze:catch` – Request failed
- `handleAnalyze:2minFallback` – 2-min fallback fired
- `NoLineItemsCard:render` – No-line-items card shown

**Backend logs:**
- `shipments.py:analyze:entry` – Analyze endpoint hit
- `shipments.py:analyze:result` – Orchestration result
- `shipments.py:analyze:exception` – Endpoint exception
- `shipment_analysis_service.py:parse_done` – Documents parsed
- `shipment_analysis_service.py:file_not_found` – Document file not on disk

To remove instrumentation: search for `#region agent log` and delete those blocks.

---

## Timing: "Taking longer than expected" message

The warning "Analysis is taking longer than expected. If it's been more than 4 minutes, the server may be stuck" appears only after **4 minutes** of run time. Typical analysis is 1–3 minutes, so showing this at 1 minute caused users to think the server was stuck when it was still running. Threshold: `4 * 60 * 1000` ms in `analysis-tab.tsx`.

---

## Open issue: Analysis not completing

**Status (as of 2026-02-24):** Analysis often does not complete within 4+ minutes. After 10+ tests over 2+ hours, results have not been obtained. The pipeline runs (documents parsed, etc.) but the sync response never returns with COMPLETE and result_json. Possible causes under investigation:

- Document processing (Claude extraction) timing out or hanging
- Sync timeout (4 min) being hit before pipeline finishes
- Backend not returning 200 with full result to frontend
- File path issues (mock_uploads empty) causing pipeline to run but produce no items, then stall

**Root cause (2026-02-24):** Logs showed pipeline completed (parse_done → after_import → fast_done) but `orchestration:sync_exception` with `InvalidTextRepresentationError` during ReviewRecord flush. The `object_snapshot` (review_snapshot) contained non-JSON-serializable values—likely `float('nan')` from Excel extraction—which PostgreSQL JSONB rejects.

**Fix applied:** `_sanitize_for_jsonb()` in `app/tasks/analysis.py` recursively converts NaN/inf to None and ensures all values are JSON-serializable before passing to ReviewRecord.

---

## Pre-flight audit (2026-02-24)

Before running again, the following were verified or fixed:

| Area | Check | Result |
|------|-------|--------|
| **result_json JSONB** | Same NaN/numpy issue as object_snapshot | **Fixed** – now sanitized before `analysis.result_json = ...` |
| **numpy types** | Excel/pandas produces numpy.int64, numpy.float64 | **Fixed** – _sanitize_for_jsonb handles numpy scalars |
| **Failed-task session** | _mark_analysis_failed_internal used rolled-back session | **Fixed** – use _mark_analysis_failed (fresh session) |
| **regulatory_evaluations** | Fast local has empty list; loop could KeyError on malformed data | **OK** – empty for fast path; full path would need valid enum values |
| **Enum values** | Regulator, RegulatoryOutcome, ConditionState | **OK** – fast path skips; full path validates |
| **hts_version_id** | String UUID format | **OK** – AUTHORITATIVE_HTS_VERSION_ID is valid |
| **Session isolation** | Task uses own AsyncSessionLocal | **OK** – separate from request session |

---

## Troubleshooting Checklist

| Symptom | Check |
|---------|-------|
| "No line items" after analysis | 1. `backend/data/mock_uploads` – are files there? 2. Document types set (Entry Summary, Commercial Invoice)? 3. Re-upload with `LOCAL_UPLOAD_BASE_URL` set |
| Re-run button disabled | 1. Is `analyzing` stuck true? 2. Refresh page. 3. Backend fix: shipment.status cleared on timeout |
| Analysis "completes" but times out | 1. Sync timeout is 4 min. 2. Document processing has 90s per doc. 3. Check backend logs for errors |
| Request never reaches backend | 1. `NEXT_PUBLIC_USE_API_PROXY=false` 2. Backend running on 9001 3. CORS if frontend on different origin |
| Circular JSON error | Ensure all values passed to `JSON.stringify` are primitives or plain objects (no DOM nodes, events, or React internals) |

---

## Key File Paths

| Path | Purpose |
|------|---------|
| `frontend/src/components/shipment-tabs/analysis-tab.tsx` | Analysis UI, handleAnalyze, Re-run, NoLineItemsCard |
| `frontend/src/components/analysis-progress-tracker.tsx` | Progress bar (steps 1–6), serverStatus caps "Completed" until COMPLETE |
| `frontend/src/lib/api-client-client.ts` | API client, API_BASE_URL, apiPost |
| `backend/app/api/v1/shipments.py` | POST /analyze, GET analysis-status |
| `backend/app/services/analysis_orchestration_service.py` | start_analysis, sync timeout, shipment.status cleanup |
| `backend/app/services/shipment_analysis_service.py` | run_full_shipment_analysis, _parse_documents_and_build_evidence_map |
| `backend/app/api/v1/shipment_documents.py` | presign, mock-upload, confirm |
| `backend/app/engines/ingestion/document_processor.py` | process_document, Excel/PDF extraction |
| `docs/NECO_ANALYSIS_PIPELINE.md` | Pipeline flow and config |

---

## Reproduction Steps (Verification)

1. Restart backend: `./start_neco.sh` or `cd backend && python -m uvicorn app.main:app --host 0.0.0.0 --port 9001 --reload`
2. Ensure `LOCAL_UPLOAD_BASE_URL=http://localhost:9001` in `backend/.env`
3. In Documents tab: upload Entry Summary (PDF) and Commercial Invoice (Excel/CSV), set each file's type
4. In Analysis tab: click Analyze Shipment or Re-run
5. Verify: either line items appear, or "Re-upload your Entry Summary and Commercial Invoice" if files not on disk

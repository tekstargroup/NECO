# Sprint 12: Document-Driven Analysis – Wrap

**Closed:** March 2026

This document captures the scope, behavior, and how to test the document-driven analysis flow added in Sprint 12.

---

## Scope (what we tested)

1. **Upload-only flow** – User uploads Entry Summary (PDF) and Commercial Invoice (XLSX) via the Documents tab. In local dev, no S3 is required; files are stored under `backend/data/mock_uploads` (keyed by `s3_key`).

2. **Extraction and import** – When analysis runs, the backend:
   - Loads documents from mock_uploads (when S3 is not configured)
   - Runs the document processor (Claude Haiku) to extract structured data and `line_items` (HTS, description, value, quantity, etc.)
   - Imports line items into the shipment **only when the shipment has no items** (idempotent). Entry Summary is preferred for HTS codes; Commercial Invoice supplements description/value.

3. **Full analysis** – With `SPRINT12_FAST_ANALYSIS_DEV=false` (set in `backend/.env`), analysis runs classification, duty resolver, PSC Radar, and regulatory evaluation on the imported line items. The Analysis tab shows the 8-section result: outcome summary, money impact, risk summary, structural analysis, PSC Radar, enrichment evidence, review status, audit trail.

4. **UX and resilience**
   - **Re-run analysis** when status is FAILED (header “Re-run analysis” + Re-analyze on Analysis tab; Overview hint when failed).
   - **Dev login** – With `NEXT_PUBLIC_DEV_AUTH=true`, unauthenticated visits to `/` or `/app` redirect to `/dev-login` so testers avoid Google/Clerk during local testing.
   - **Progress tracker** – While status is QUEUED/RUNNING, a Domino’s-style tracker shows three phases (Analyzing documents → Classifying products & duties → Checking compliance & risk) and an “About M:SS remaining” countdown.

---

## Local testing (no S3)

- Backend reads uploads from `backend/data/mock_uploads`. Files are stored by the mock-upload endpoint using the `X-S3-Key` header (path derived from `s3_key`).
- Use dev login: set `NEXT_PUBLIC_DEV_AUTH=true` in `frontend/.env.local`; go to the app and complete one “Login as test user” on `/dev-login`.
- For full analysis results (not just placeholders), set `SPRINT12_FAST_ANALYSIS_DEV=False` in `backend/.env` and restart the backend.

---

## Manual test checklist

| Step | How to verify |
|------|----------------|
| Dev login | Open app → redirect to `/dev-login` → click “Login as test user” → land on shipments (no Google). |
| Upload | Create shipment → Documents tab → upload Entry Summary (PDF) + Commercial Invoice (XLSX) with correct types. |
| Analyze | Click “Analyze Shipment” (or “Re-run analysis” if previously FAILED) → progress tracker shows 3 phases + countdown → status becomes COMPLETE. |
| Results | Analysis tab shows line items and real duty/classification/PSC/risk content (not all “No material duty” / “No risk flags” when data exists). |
| Re-run | On a FAILED shipment, use “Re-run analysis” in header or “Re-analyze” on Analysis tab → new run starts; no need to re-upload documents. |

---

## Known limits

- **Progress is estimated** – The tracker advances by elapsed time vs. an estimated total (derived from doc/item counts). The backend does not emit phase events; when the job finishes, the UI switches to the result.
- **Line item import is one-time** – Import runs only when `shipment.items` is empty. Re-running analysis does not re-import or merge; it reuses existing items.
- **Rate limiting** – Extraction uses Claude Haiku and truncates input (12k chars) to stay under org rate limits; large documents may have truncated content.

---

## QA gate

Baseline API checks (no document flow): run from repo root with backend on 9001 and Docker/Postgres up:

```bash
RUN_UI=0 ./scripts/sprint12_qa_gate.sh
```

Expected: 8 checks PASS (health, seed, create shipment, org enforcement, list, analyze 202). Document upload and extraction are not covered by this gate; use the manual checklist above.

---

## Next: Sprint 13

See [BASELINE_AND_MVP_ROADMAP.md](BASELINE_AND_MVP_ROADMAP.md) § Sprint 13: Analysis View. Focus is polishing the analysis experience and MVP critical path (fetch/display, loading/error states, link from list to detail). Much of the 8-section analysis view is already in place from this sprint.

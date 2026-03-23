# NECO Analysis Pipeline – The Heart of the Tool

This doc describes how NECO processes documents and produces analysis results. Use it to evaluate whether each step works and where to fix.

**Related:** See [ANALYSIS_DEBUGGING_AND_FIXES.md](./ANALYSIS_DEBUGGING_AND_FIXES.md) for debugging history, fixes for "no line items", Re-run disabled, and document file path issues.

---

## End-to-end flow

```
1. User uploads documents (Documents tab)
   → Files stored (local or S3), ShipmentDocument records created
   → User sets document type per file: Entry Summary, Commercial Invoice, etc.

2. User clicks "Analyze" or "Re-run (start fresh)" (Analysis tab)
   → POST /api/v1/shipments/{id}/analyze (optionally ?force_new=1)
   → Backend: eligibility check → entitlement → create Analysis record → run pipeline

3. Pipeline (run_full_shipment_analysis)
   a) Load shipment + documents + items (DB)
   b) Parse documents & build evidence map
      - For each document: resolve file path (local or S3) → process_document(path)
      - process_document: PDF/Excel/DOCX extraction → FieldDetector (Claude) for type + structured data (line items, etc.)
      - Evidence map = { documents: [...], extraction_errors, warnings }
   c) Import line items (if shipment has none)
      - From structured_data.line_items (Entry Summary + Commercial Invoice)
      - Merge by line number, create ShipmentItem records
   d) Analysis branch
      - If SPRINT12_FAST_ANALYSIS_DEV: build fast local result (no LLM classification/duty/PSC) → result_json
      - Else: for each item run Classification, Duty, PSC, Regulatory → build result_json
   e) Create ReviewRecord, persist regulatory rows, set analysis COMPLETE + result_json

4. Frontend receives 200 + result (or polls until status COMPLETE) → shows Analysis results (8 sections)
```

---

## What each step does

| Step | Where in code | What it does |
|------|----------------|--------------|
| **Eligibility** | `ShipmentEligibilityService` | Ensures shipment has required doc types (e.g. Entry Summary + Commercial Invoice). |
| **Document parsing** | `ShipmentAnalysisService._parse_documents_and_build_evidence_map` | For each doc: get file path → `DocumentProcessor.process_document(path)` → extracted text + structured_data (e.g. line_items). |
| **process_document** | `DocumentProcessor` (engines/ingestion) | PDF/Excel/DOCX extraction; then `FieldDetector` (Claude) for document type and structured extraction (e.g. commercial_invoice → line items). |
| **Line item import** | `_import_line_items_from_documents` | Reads structured_data.line_items from docs, merges, creates `ShipmentItem` rows. |
| **Fast analysis** | `_build_fast_local_analysis` | Builds result_json from shipment items + evidence_map; no classification/duty/PSC. |
| **Full analysis** | Loop over items + ClassificationEngine, resolve_duty, PSCRadar, RegulatoryApplicabilityEngine | LLM classification, duty resolution, PSC, regulatory → result_json. |
| **Persist** | `_run_analysis_async` (tasks/analysis) | ReviewRecord + regulatory rows; analysis.status = COMPLETE; analysis.result_json = result_json. |

---

## Config that affects the pipeline

| Env var | Effect |
|---------|--------|
| `SPRINT12_INSTANT_ANALYSIS_DEV=true` | **Skips** the pipeline; returns minimal COMPLETE result (no parsing, no real analysis). Use only to unblock UI. |
| `SPRINT12_FAST_ANALYSIS_DEV=true` | After document parsing + import, **skips** classification/duty/PSC/regulatory; builds result from items + evidence. |
| `SPRINT12_INLINE_ANALYSIS_DEV=true` | Run analysis in the API process (no Celery). |
| `SPRINT12_SYNC_ANALYSIS_DEV=true` | Wait for pipeline in the request and return 200 with full result (so UI gets result without polling). |
| `ENVIRONMENT=development` | Required for inline/sync/fast to apply. |

For **real** analysis (documents processed, line items extracted, and either fast or full result):

- `SPRINT12_INSTANT_ANALYSIS_DEV=false`
- `SPRINT12_FAST_ANALYSIS_DEV=true` (faster) or `false` (full classification/duty/PSC)
- `SPRINT12_INLINE_ANALYSIS_DEV=true`, `SPRINT12_SYNC_ANALYSIS_DEV=true`

---

## How to evaluate

1. **Documents** – Upload at least one Entry Summary (PDF) and one Commercial Invoice (Excel/CSV). Set each file’s type in the Documents tab.
2. **Backend logs** – When you click Analyze, watch for:
   - `Analysis start ... INSTANT_DEV=False` (so the real pipeline runs)
   - `run_full_shipment_analysis: parsing documents for shipment ...`
   - `run_full_shipment_analysis: documents parsed, importing line items ...`
   - `run_full_shipment_analysis: using fast local analysis` (if FAST_DEV) or `running classification/duty/PSC`
   - `Analysis completed for shipment ...` or a traceback
3. **Result** – Either COMPLETE with result_json (sections populated from evidence + items) or FAILED with error_message. No infinite RUNNING.
4. **Fixes already in place** – Document processing runs in a thread (so it doesn’t block the event loop); 90s timeout per document; 4 min sync timeout; force_new so Re-run starts a fresh run.

If the pipeline still hangs or returns 202 and never completes, the next step is to capture the exact backend log (and any traceback) from one Analyze click and fix the step where it stops.

---

## How to test the real pipeline

1. **Config** – In `backend/.env` set:
   - `SPRINT12_INSTANT_ANALYSIS_DEV=False`
   - `SPRINT12_FAST_ANALYSIS_DEV=True` (for faster runs; set `False` for full classification/duty/PSC)
   - `ENVIRONMENT=development`
   - `SPRINT12_INLINE_ANALYSIS_DEV=True`, `SPRINT12_SYNC_ANALYSIS_DEV=True`

2. **Restart backend** from project root so it loads `.env` and runs from `backend/` (so `backend/data/mock_uploads` and `.env` are correct).

3. **Data** – Use a shipment that has at least one document (Entry Summary or Commercial Invoice). Files should be under `backend/data/mock_uploads` (or the path your upload flow uses). Set each document’s type in the Documents tab.

4. **Run** – Click **Re-run (start fresh)** on the Analysis tab. Watch the **backend terminal**. You should see, in order:
   - `Analysis start ... INSTANT_DEV=False`
   - `run_full_shipment_analysis: parsing N document(s) ...`
   - `run_full_shipment_analysis: documents parsed ... importing line items`
   - `run_full_shipment_analysis: using fast local analysis ... (M items)`
   - `run_full_shipment_analysis: fast local analysis done ...`
   - `Analysis completed for shipment ...`
   Then the request returns 200 and the UI shows results (from evidence + items).

5. **If it stops** – Note the last log line. If you see a traceback, that’s the failing step. Common cases:
   - **File not found** – Docs reference files that aren’t in `backend/data/mock_uploads` (or the path we resolve). Fix upload path or add a fallback.
   - **Timeout** – One document takes >90s (e.g. slow Claude call). You’ll see "Document processing timed out (90s)" and the rest of the pipeline continues.
   - **Sync timeout** – Whole pipeline >4 min → we return 200 with status FAILED and a timeout message.

---

## "No line items" – what to check

When analysis completes but the UI says "No line items in this analysis":

1. **Documents tab** – The shipment must have at least one document. Each file must have its **type** set (e.g. **Entry Summary** or **Commercial Invoice**). Use the type dropdown and save.
2. **Commercial Invoice for Excel/CSV** – Line items are extracted from Entry Summary and **Commercial Invoice**. If you uploaded an Excel or CSV invoice, set its type to **Commercial Invoice** so the backend runs the right extraction and can show a "Use selected rows" table if auto-extract finds no rows.
3. **File location** – In local dev, files must be under `backend/data/mock_uploads` (or the path your upload API uses). If the backend can’t find the file, you’ll get warnings in the evidence map and no line items.
4. **Re-run after fixing** – After uploading or fixing document types, click **Re-run** on the Analysis tab so the pipeline runs again with the updated data.
5. **Table with checkboxes** – If you see a table of rows from your document, use "Use selected rows" to pick which rows are line items, then Re-run to run analysis on those items.
6. **Files not on disk** – In local dev, uploads go to `backend/data/mock_uploads`. If that folder is empty but you see documents in the UI, the upload may have gone to a different backend (e.g. behind proxy). Set `LOCAL_UPLOAD_BASE_URL=http://localhost:9001` in `backend/.env` so the presign returns a URL that hits your backend, then **re-upload** the documents.

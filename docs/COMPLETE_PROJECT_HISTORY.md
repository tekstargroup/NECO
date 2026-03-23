# NECO Complete Project History

**Purpose:** Master record of everything built so far. Use this as the single source of truth for "what we've done."

**Last updated:** February 24, 2026

---

## 1. Sprint 12 Baseline (Closed March 2026)

Sprint 12 established the document-driven analysis flow and is the current baseline.

### Scope

- **Document-driven analysis:** Upload Entry Summary (PDF) + Commercial Invoice (XLSX) → extract line items → import into shipment → full analysis
- **Backend:** Shipments API (create, list, analyze), org-scoped auth, dev-token
- **Frontend:** Next.js 14, Clerk + dev auth bypass, shipments list/new/detail with tabs (Overview, Documents, Analysis, Reviews, Exports)
- **Auth:** Clerk (production path) + dev-token (local testing)
- **Data:** Seeded org `org_s12_loop`, user `user_s12_loop_provisioned`

### Key Deliverables

| Area | What Was Built |
|------|----------------|
| **Upload flow** | Presign → mock upload (or S3) → confirm; files stored in `backend/data/mock_uploads` when S3 not configured |
| **Document processor** | Claude Haiku extraction of structured data and `line_items` (HTS, description, value, quantity, etc.) from ES/CI |
| **Line item import** | Idempotent import when shipment has no items; Entry Summary preferred for HTS; Commercial Invoice supplements description/value |
| **Analysis** | Classification, duty resolver, PSC Radar, regulatory evaluation → 8-section result (Outcome Summary, Money Impact, Risk Summary, Structural Analysis, PSC Radar, Enrichment Evidence, Review Status, Audit Trail) |
| **UX** | Re-run analysis when FAILED; dev-login redirect; progress tracker (3 phases + countdown) |
| **QA gate** | `./scripts/sprint12_qa_gate.sh` — 8 API checks; UI optional with `RUN_UI=1` |

### Reference

- [docs/SPRINT12_DOCUMENT_ANALYSIS_WRAP.md](SPRINT12_DOCUMENT_ANALYSIS_WRAP.md) — scope, local testing, manual checklist, known limits

---

## 2. Analysis Pipeline Fixes (Post-Sprint 12)

Improvements made after Sprint 12 closed to address phantom line items, poor analysis quality, and reliability.

### 2.1 Phantom Line Items (Excel Extraction)

**Problem:** Excel extraction produced 7 line items instead of 1 (header rows and empty rows treated as data).

**File:** `backend/app/engines/ingestion/document_processor.py`

**Changes:**
- `_looks_like_header()` — filter rows whose cell values match header keywords (qty, description, unit price, etc.)
- `_has_numeric()` — skip rows without numeric qty/value
- Fallback: `_build_line_items_from_unnamed_header()` when first pass yields nothing (handles "Unnamed: 0" columns)
- Result: 1 line item from CI instead of 7 phantom rows

### 2.2 Origin Comparison and Fast-Path Enrichment

**Problem:** No CI vs ES origin comparison; no duty from Entry Summary; no COO confirmation prompt for high-duty items.

**File:** `backend/app/services/shipment_analysis_service.py`

**Changes:**
- `_normalize_coo_for_comparison()` — normalize country names for comparison
- `_detect_origin_mismatches_from_evidence()` — compare CI vs ES COO per line; detect mismatches
- `_get_es_duty_per_line()` — extract duty from Entry Summary per line
- `_build_fast_local_analysis()` extended to:
  - Attach `duty_from_entry_summary` from Entry Summary
  - Detect CI vs ES origin mismatches and add dollar framing to blockers
  - Add `coo_confirmation_prompt` when duty is high or origin mismatches exist
  - Run PSC Radar for items with duty > threshold (configurable)
  - Add `clarification_questions` for high-duty items

### 2.3 Frontend Analysis Tab

**File:** `frontend/src/components/shipment-tabs/analysis-tab.tsx`

**Changes:**
- Display ES duty (`duty_from_entry_summary`)
- Display Section 301 when present
- Display COO confirmation prompt when present
- Display origin mismatch with dollar framing (ci_country vs es_country, duty_paid)
- Display PSC alternatives
- Display clarification questions
- Duty disclaimer: "Duty rates are derived from HTS and Entry Summary data. Verify with CBP or your broker before filing."

### 2.4 Configurable PSC Threshold

**File:** `backend/app/core/config.py`, `backend/.env`

Added `PSC_DUTY_THRESHOLD` (default 1000, env-configurable). Minimum duty (USD) to run PSC Radar in fast path. Set lower (e.g. 100) for more coverage.

---

## 3. Debugging and Resilience Fixes

**File:** [docs/ANALYSIS_DEBUGGING_AND_FIXES.md](ANALYSIS_DEBUGGING_AND_FIXES.md)

Fixes applied during multi-hour debugging sessions:

| Fix | Description |
|-----|-------------|
| **files_not_found** | When documents not on disk, `evidence_map["files_not_found"] = True`; UI shows "Re-upload your Entry Summary and Commercial Invoice" |
| **Re-run enabled** | Clear `shipment.status` on sync timeout/exception; no longer disable Re-run when stuck ANALYZING |
| **JSONB sanitization** | `_sanitize_for_jsonb()` — convert NaN/inf to None, numpy scalars to Python types; fixes InvalidTextRepresentationError on ReviewRecord flush |
| **Failed-task cleanup** | Use fresh session when marking analysis failed (not rolled-back session) |
| **Circular JSON** | Serialize primitives only in debug logs; arrow wrappers on handlers so event not passed |
| **"Taking longer"** | Moved from 1 min to 4 min threshold |
| **LOCAL_UPLOAD_BASE_URL** | Config for proxy scenarios; presign returns correct upload URL |

---

## 4. Supporting Documentation and Assets

| Asset | Purpose |
|-------|---------|
| [docs/HTS_DATA_SOURCE.md](HTS_DATA_SOURCE.md) | HTS data source, extraction flow, what is/isn't included (Section 301, etc.) |
| [docs/BULK_IMPORT_GUIDE.md](BULK_IMPORT_GUIDE.md) | User guide for bulk import structure |
| [docs/bulk_import_template/](bulk_import_template/) | Template folder + README.txt with folder structure |

---

## 5. Key File Paths

| Path | Purpose |
|------|---------|
| `backend/app/engines/ingestion/document_processor.py` | Excel/PDF extraction, line item filtering |
| `backend/app/services/shipment_analysis_service.py` | Fast-path enrichment, origin comparison, PSC threshold |
| `frontend/src/components/shipment-tabs/analysis-tab.tsx` | Analysis UI, duty disclaimer |
| `backend/app/core/config.py` | `PSC_DUTY_THRESHOLD` |
| `backend/app/tasks/analysis.py` | `_sanitize_for_jsonb`, failed-task cleanup |
| `backend/app/services/analysis_orchestration_service.py` | Sync timeout, status cleanup |

---

## 6. How to Test

**API gate:** `RUN_UI=0 ./scripts/sprint12_qa_gate.sh` — 8 checks PASS

**Manual flow:** Dev login → create shipment → upload ES (PDF) + CI (XLSX) → Analyze → verify 1 line item, ES duty, origin mismatch, COO prompt when applicable

---

## 7. Next: Sprint 13

See [docs/SPRINT_ROADMAP_LOCKED.md](SPRINT_ROADMAP_LOCKED.md) for the full sprint map and next steps.

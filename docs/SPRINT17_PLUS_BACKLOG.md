# Sprints 17–20 – Post-MVP Backlog

**Purpose:** Extends beyond Sprint 16 (MVP hardening). Includes user preferences, bulk import, duty accuracy, and the Compliance Signal Engine.

**Reference:** [docs/COMPLIANCE_SIGNAL_ENGINE.md](COMPLIANCE_SIGNAL_ENGINE.md), [docs/REGULATORY_MONITORING.md](REGULATORY_MONITORING.md)

---

## Sprint 17: User-Selectable Analysis Preferences

**Goal:** Let users choose what to analyze and at what value thresholds (COO, Duty, HS Code alternatives) based on compute/token budget.

**Deliverables:**
- **Backend:** Add `analysis_preferences` to org or user settings (or per-shipment override):
  - `psc_threshold_min` (e.g. 100, 1000, 10000)
  - `psc_threshold_max` (optional cap)
  - `analyze_coo` (boolean)
  - `analyze_duty` (boolean)
  - `analyze_hs_code` (boolean)
  - `resource_mode`: "light" | "standard" | "full"
- **Backend:** Pass preferences into `_build_fast_local_analysis` and full pipeline; gate PSC by threshold and mode.
- **Frontend:** Settings/Preferences UI (e.g. in Analysis tab or org settings):
  - Checkboxes: COO comparison, Duty impact, HS code alternatives (PSC)
  - Value thresholds: All > $100, $100–$1K, $1K–$10K, > $10K (multi-select or range)
  - Resource mode dropdown: Light / Standard / Full
- **API:** `GET/PATCH /api/v1/organizations/{id}/analysis-preferences` or equivalent.

**Files to touch:** `backend/app/services/shipment_analysis_service.py`, new preferences model/API, `frontend/src/components/shipment-tabs/analysis-tab.tsx` or settings page.

---

## Sprint 18: Bulk Import (Folder/Zip)

**Goal:** User uploads a zip or folder; NECO creates one shipment per document group and analyzes all.

**Deliverables:**
- **Backend:** `POST /api/v1/shipments/bulk-import` accepting multipart zip upload.
- **Backend:** Unzip, detect document types (ES, CI), group by shipment (PO, entry number, or folder structure).
- **Backend:** Create shipments, attach documents, enqueue analyses (or run inline with progress).
- **Frontend:** Bulk import UI: drag-drop zip or folder picker; progress; summary list of created shipments with links.
- **Template:** Downloadable example zip with structure:
  - `shipment_1/ES_561056.pdf`, `shipment_1/CI_241211.xlsx`
  - `shipment_2/ES_561057.pdf`, `shipment_2/CI_241212.xlsx`
  - `README.txt` with naming/folder rules
- **Docs:** User guide: how to structure files, naming conventions, how shipments are inferred.

**Files to touch:** New bulk-import API, document processor for batch, frontend bulk-import page/modal.

---

## Sprint 19: Duty Rates Accuracy and Section 301 Overlay

**Goal:** Ensure NECO duty data is current and add Section 301 (9903) overlay for China-origin goods.

**Deliverables:**
- **Document HTS source:** Add `docs/HTS_DATA_SOURCE.md` — which HTS PDF/edition, extraction date, refresh process.
- **Section 301 overlay:** Integrate USTR/CBP Section 301 data (9903.88.xx, etc.); apply when COO = China.
- **Duty resolution:** Extend `resolve_duty` or add overlay step to combine general + Section 301 when applicable.
- **Versioning:** Define HTS version refresh cadence (e.g. quarterly); add `effective_date` or version metadata to `hts_versions`.
- **Disclaimer:** Add UI disclaimer: "Duty rates are derived from HTS and Section 301 data. Verify with CBP/broker before filing."

**Files to touch:** `backend/scripts/duty_resolution.py`, new Section 301 data/loader, `backend/app/core/hts_constants.py`, docs.

---

## Sprint 20: Compliance Signal Engine

**Goal:** NECO becomes a compliance intelligence system. Ingest external signals (CBP, Federal Register, USTR, CROSS rulings), classify and score them, map to HTS/products, and produce actionable PSC Radar alerts.

**Deliverables:** See [docs/COMPLIANCE_SIGNAL_ENGINE.md](COMPLIANCE_SIGNAL_ENGINE.md) and [docs/REGULATORY_MONITORING.md](REGULATORY_MONITORING.md).

**Summary:**
- **Ingestion:** Feed poller for RSS/API sources; `raw_signals` table
- **Pipeline:** Normalize → Classify → Score → PSC alerts
- **Scoring:** HTS match, country match, importer history, financial impact (weighted)
- **PSC Radar:** Alerts when `final_score > 70`; explainability layer
- **UI:** PSC Radar page; shipment detail integration; signal detail view

---

## Implementation Order

| Order | Sprint | Focus |
|-------|--------|-------|
| 1 | **17** | User-Selectable Analysis Preferences |
| 2 | **18** | Bulk Import |
| 3 | **19** | Duty Rates + Section 301 |
| 4 | **20** | Compliance Signal Engine |

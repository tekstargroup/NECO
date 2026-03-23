# HTS Data Source and Duty Resolution

**Last updated:** February 2026

## Overview

NECO uses Harmonized Tariff Schedule (HTS) data for duty resolution and classification. This document describes the data source, extraction process, and limitations.

---

## Data Flow

```
HTS PDF (USITC/USCBP) → PDF Extraction → hts_versions / hts_nodes → resolve_duty() → Analysis
```

1. **Source:** HTS PDF (U.S. International Trade Commission / CBP publication)
2. **Extraction:** `regenerate_structured_hts_codes_v2.py` — pdfplumber-based extraction of 10-digit codes, duty text, descriptions
3. **Storage:** `hts_versions` (legacy), `hts_nodes` (multi-level hierarchy: 6, 8, 10-digit)
4. **Resolution:** `scripts/duty_resolution.py` — walks tree upward, resolves general/special/column2 duty

---

## Authoritative HTS Version

- **Version ID:** `792bb867-c549-4769-80ca-d9d1adc883a3` (see `backend/app/core/hts_constants.py`)
- **Effective:** Set at extraction/backfill time; no automatic refresh

---

## What NECO Includes

| Data | Source | Notes |
|------|--------|-------|
| General (MFN) duty | hts_versions / hts_nodes | Extracted from HTS PDF tariff tables |
| Special duty | hts_versions / hts_nodes | FTA rates when present |
| Column 2 duty | hts_versions / hts_nodes | When present |

---

## What NECO Does NOT Include (As of Today)

| Data | Status | Notes |
|------|--------|------|
| **Section 301 (9903.88.xx)** | Not in duty resolution | 9903 codes excluded from backfill; Section 301 amounts come from Entry Summary when user uploads |
| **Section 201** | Not modeled | Would require separate overlay |
| **Trump tariffs / Supreme Court changes** | Not modeled | HTS PDF is the source; if PDF is outdated, rates may not reflect recent changes |
| **Quotas** | Not modeled | |
| **Trade programs (GSP, etc.)** | Not modeled | |

---

## Refresh Process

1. Obtain updated HTS PDF from USITC/CBP
2. Run extraction: `regenerate_structured_hts_codes_v2.py`
3. Load to `hts_nodes`: `load_structured_codes_to_hts_nodes.py`
4. Backfill duty rates: `backfill_duty_rates.py`, `backfill_parent_duties.py`
5. Update `AUTHORITATIVE_HTS_VERSION_ID` in `hts_constants.py` if using a new version

**Recommended cadence:** Quarterly or when CBP publishes significant HTS updates.

---

## Section 301 and Launch Readiness

For launch, consider:

1. **Integrate Section 301 overlay** — USTR/CBP publish Section 301 rates (e.g. 9903.88.02 for China). Add a separate data source and apply when COO = China.
2. **Document PDF version** — Record which HTS PDF edition and date was used for the current `hts_versions` / `hts_nodes` data.
3. **Disclaimer** — NECO surfaces duty from HTS and, when available, from the user's Entry Summary. Users should verify with CBP/broker before filing.

---

## Related Files

- `backend/app/core/hts_constants.py` — Authoritative version ID
- `backend/scripts/duty_resolution.py` — Duty resolver
- `backend/scripts/regenerate_structured_hts_codes_v2.py` — PDF extractor
- `backend/scripts/backfill_hts_nodes.py` — Populate hts_nodes
- `backend/scripts/backfill_duty_rates.py` — Populate duty_rates

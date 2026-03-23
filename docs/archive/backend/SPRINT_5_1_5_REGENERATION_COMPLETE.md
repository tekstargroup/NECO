# Sprint 5.1.5: Structured HTS Codes Regeneration Complete

**Date:** January 1, 2025  
**Status:** ✅ Regeneration and persistence complete

---

## What Was Done

### 1. Created Regeneration Script
- **Script:** `backend/scripts/regenerate_structured_hts_codes.py`
- **Purpose:** Re-extract structured HTS codes from PDF and persist to JSONL
- **Output:** `data/hts_tariff/structured_hts_codes.jsonl`

### 2. Created Loader Script
- **Script:** `backend/scripts/load_structured_codes_to_hts_nodes.py`
- **Purpose:** Load JSONL file into `hts_nodes` table
- **Features:** Batch upserts, dry-run mode, progress reporting

### 3. Regenerated Structured Codes
- **Source:** `CBP Docs/2025HTS.pdf` (4,402 pages)
- **Output:** `data/hts_tariff/structured_hts_codes.jsonl`
- **Total Codes Extracted:** 19,329 codes

---

## File Location

**Permanent Storage:**
```
data/hts_tariff/structured_hts_codes.jsonl
```

This file is now part of the repository and should be committed to version control. It contains all extracted structured codes with:
- Code normalized (digits only)
- Code display (with dots)
- Level (6, 8, or 10)
- Parent code relationships
- Descriptions (short and long)
- Duty text (general, special, column2)
- Source lineage (page, table, row)

---

## Usage

### Regenerate (if needed):
```bash
cd backend
python scripts/regenerate_structured_hts_codes.py \
  --pdf-path "../CBP Docs/2025HTS.pdf" \
  --output "../data/hts_tariff/structured_hts_codes.jsonl"
```

### Load into hts_nodes:
```bash
cd backend
python scripts/load_structured_codes_to_hts_nodes.py \
  --jsonl "../data/hts_tariff/structured_hts_codes.jsonl" \
  --batch-size 1000
```

### Dry run (verify before loading):
```bash
python scripts/load_structured_codes_to_hts_nodes.py \
  --jsonl "../data/hts_tariff/structured_hts_codes.jsonl" \
  --dry-run
```

---

## Next Steps

1. **Load into hts_nodes:**
   ```bash
   python scripts/load_structured_codes_to_hts_nodes.py \
     --jsonl "../data/hts_tariff/structured_hts_codes.jsonl"
   ```

2. **Verify duty text population:**
   - Check that 6-digit and 8-digit nodes now have duty text
   - Run duty backfill for all levels

3. **Run duty backfill for all levels:**
   ```bash
   python scripts/backfill_duty_rates.py --levels 10,8,6 --duty-column general
   python scripts/backfill_duty_rates.py --levels 10,8,6 --duty-column special
   python scripts/backfill_duty_rates.py --levels 10,8,6 --duty-column column2
   ```

---

## Important Notes

1. **Simplified Extractor:** The current extractor uses basic table parsing. For production accuracy, you may want to enhance it with:
   - Better table structure detection
   - LLM/Claude integration for complex parsing
   - Validation against known HTS code patterns

2. **Data Persistence:** The JSONL file is now the source of truth. Always commit it to version control.

3. **Incremental Updates:** If the PDF changes, regenerate the JSONL and reload. The upsert logic will update existing nodes.

---

## Files Created

- ✅ `backend/scripts/regenerate_structured_hts_codes.py`
- ✅ `backend/scripts/load_structured_codes_to_hts_nodes.py`
- ✅ `data/hts_tariff/structured_hts_codes.jsonl` (persisted output)

# HTS Extraction Diagnosis - Critical Issues Found

**Date:** January 1, 2025  
**Status:** ⚠️ **EXTRACTION BROKEN - DO NOT PROCEED**  
**Root Cause:** ✅ **CONFIRMED - Row Reconstruction Issue**

---

## Findings

### PDF Location
- **File:** `CBP Docs/2025HTS.pdf`
- **Size:** 19 MB
- **Format:** PDF version 1.4
- **Pages:** 4,402

### Current Extraction Method
- **Tool:** `pdfplumber` (Python library)
- **Method:** Text extraction via `page.extract_text()` (NOT OCR)
- **Table Extraction:** `page.extract_tables()` (not working properly)

### Critical Problem

**Current extraction results:**
- Level 6: 3,864 codes ✅
- Level 8: 15,464 codes (2,067 with duty text) ✅
- Level 10: **1 code** ❌ **CRITICAL FAILURE**

**Expected:** ~19,000+ 10-digit codes (based on original extraction: 69,430 total codes)

---

## Root Cause Analysis

### ✅ **CONFIRMED: Row Reconstruction Issue (NOT OCR)**

**Diagnosis from pages 2196-2198:**
- `extract_text()`: **0 ten-digit codes found**
- `extract_words()`: **Multiple ten-digit codes PRESENT**:
  - "6112.19.10" (word 39, page 2196)
  - "6112.19.40" (word 75, page 2196)
  - "6112.19.80" (word 40, page 2197)
  - "6112.20.10" (word 38, page 2198)
  - "6112.20.20" (word 90, page 2198)

**Conclusion:** The 10-digit codes exist in the PDF words, but `pdfplumber.extract_text()` is losing them during row reconstruction. This is a **text reconstruction problem**, not OCR or missing data.

### Evidence

**Page 2196 sample:**
```
Word 39: "6112.19.10" (47.8, 0.0, 89.9, 0.0)  ← 10-digit code EXISTS
Word 75: "6112.19.40" (47.8, 0.0, 89.9, 0.0)  ← 10-digit code EXISTS
```

But `extract_text()` shows:
- 10-digit codes (with dots): 0
- 10-digit codes (no dots): 0

**The codes are being lost during text reconstruction!**

---

## Required Fixes

### 1. **DO NOT PROCEED** with:
- ❌ Loading structured codes into `hts_nodes`
- ❌ Populating duty text from broken extraction
- ❌ Running duty backfill for 6/8-digit levels
- ❌ Implementing Phase 3 inheritance

### 2. **MUST FIX** before proceeding:
- ✅ **Use `extract_words()` instead of `extract_text()`** for code extraction
- ✅ **Reconstruct rows from word coordinates** (group words by y-coordinate/row)
- ✅ **Extract codes directly from words** before text reconstruction
- ✅ Fix regex to handle codes with/without dots
- ✅ Extract 10-digit codes properly (target: ~19,000+ codes)

### 3. **Solution Approach:**
Instead of relying on `extract_text()` which loses codes during reconstruction:

1. **Use `extract_words()`** to get individual words with coordinates
2. **Group words by row** (y-coordinate clustering with tolerance)
3. **Extract HTS codes directly from word sequences** (look for patterns like "6112.19.10")
4. **Reconstruct table rows** from word groups
5. **Extract duty columns** from properly reconstructed rows

### 4. **Implementation Strategy:**
```python
# Pseudo-code approach:
words = page.extract_words()
rows = group_words_by_y_coordinate(words, tolerance=5)
for row in rows:
    row_text = ' '.join([w['text'] for w in row])
    # Extract codes from row_text or directly from word sequence
    codes = extract_hts_codes_from_row(row)
```

---

## Next Steps

1. **Rewrite extraction script** to use `extract_words()`:
   - Group words by y-coordinate to reconstruct rows
   - Extract codes directly from word sequences
   - Reconstruct table structure from word positions

2. **Test extraction:**
   - Verify 10-digit code count matches expectations (~19,000+)
   - Verify duty text extraction for all levels
   - Compare against original 69,430 code count

3. **Only after extraction is fixed:**
   - Load structured codes into `hts_nodes`
   - Populate duty text
   - Run duty backfill for all levels
   - Implement Phase 3 inheritance

---

## Current Status

**EXTRACTION BROKEN - DO NOT USE**

The current `regenerate_structured_hts_codes.py` script produces invalid results:
- Only 1 ten-digit code (should be ~19,000+)
- Cannot be used for duty text population
- Cannot be used for inheritance logic

**Root Cause:** Row reconstruction in `extract_text()` is breaking up 10-digit codes.

**Solution:** Use `extract_words()` and reconstruct rows manually from coordinates.

**Action Required:** Fix extraction before proceeding with Sprint 5.1.5.

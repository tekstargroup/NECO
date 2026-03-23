# Sprint 5.3 Fix Summary: Corrected Synthetic Code Detection

## Critical Correction

**Issue**: Previous fix incorrectly rejected ALL codes ending in "00", but many legitimate HTS codes have "00" as their statistical suffix.

**Correct Fix**: Only reject SYNTHETIC codes (emitted without real suffix token), not codes ending in "00".

## Changes Made

### 1. Extractor Fix (`regenerate_structured_hts_codes_v2.py`)

**Removed**: Explicit rejection of suffix == "00"

**Kept**: Single invariant that prevents synthetic children:
- No 10-digit emission unless `suffix_token` exists AND `suffix_token.band == "SUFFIX_BAND"`

**Added**: Debug gate - all 10-digit codes must have:
- `suffix_token_text` in component_parts
- `suffix_token_band == "SUFFIX_BAND"`  
- `suffix_provenance` with token_text, token_band, row_id

**Location**: Lines 914-979

### 2. Cleanup Script Fix (`cleanup_bogus_00_codes.py`)

**Changed**: Function renamed from `find_bogus_00_codes` to `find_synthetic_10_digit_codes`

**Old Query** (WRONG):
```python
# Find all 10-digit codes ending in "00"
query = select(HTSNode).where(
    HTSNode.level == 10,
    HTSNode.code_normalized.like("%00")  # ❌ Too broad
)
```

**New Query** (CORRECT):
```python
# Find ALL 10-digit codes
query = select(HTSNode).where(
    HTSNode.level == 10  # ✅ Check all, not just .00
)
```

**Detection Criteria** (CORRECT):
A code is synthetic if ANY of:
- `suffix_token_text` is missing/null in component_parts
- `suffix_token_band != "SUFFIX_BAND"`
- Missing `suffix_provenance` AND incomplete component_parts
- No `source_lineage` at all (old extractor)

**Valid .00 Codes**: Codes ending in "00" are VALID if:
- `suffix_token_text == "00"` AND
- `suffix_token_band == "SUFFIX_BAND"`

### 3. Resolver/Backfill Filtering

Updated to filter nodes where `source_lineage.is_valid == False` (synthetic codes).

## Example: Valid .00 Code Lineage

A legitimate .00 code would have source_lineage like:
```json
{
  "component_parts": {
    "base": "6112.20.10",
    "suffix": "00",
    "suffix_token_text": "00",  // ✅ Present
    "suffix_token_band": "SUFFIX_BAND",  // ✅ Correct band
    "reconstructed_code": "6112.20.10.00"
  },
  "suffix_provenance": {
    "token_text": "00",
    "token_band": "SUFFIX_BAND",
    "row_id": 12345
  }
}
```

## Page 2198 Golden Results

**Expected**: No .00 children (because Page 2198 has no "00" suffix tokens)

**After Fix**: 
- Extractor will NOT emit .00 codes for Page 2198 (no suffix token "00" in SUFFIX_BAND)
- Existing .00 codes from old extractor will be marked invalid
- Valid .00 codes from other pages will remain valid

## Validation

The fix ensures:
1. ✅ No synthetic codes created (invariant: suffix_token must exist AND be in SUFFIX_BAND)
2. ✅ Valid .00 codes preserved (if suffix_token_text="00" and band=SUFFIX_BAND)
3. ✅ Page 2198 has no .00 children (correct - none exist on that page)
4. ✅ Old synthetic codes marked invalid (missing suffix_token evidence)

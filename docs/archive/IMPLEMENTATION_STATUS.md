# Classification Engine Fixes - Implementation Status

**Date:** January 8, 2026

---

## ✅ Completed (Steps 1-5)

### Step 1: Candidate Retrieval Hard Exclusions ✅
- **Location:** `backend/app/engines/classification/engine.py` - `_generate_candidates()`
- **Changes:**
  - Added `tariff_text NOT ILIKE '%9903.%'` exclusion
  - Added `tariff_text_short NOT ILIKE '%9903.%'` exclusion
  - Added `hts_code NOT LIKE '98%'` exclusion
  - Added `hts_code NOT LIKE '99%'` exclusion
  - All exclusions at database query level, before scoring

### Step 2: Noise Filters ✅
- **Location:** `backend/app/engines/classification/engine.py` - `_is_noisy_description()`
- **Filters implemented:**
  - Too short: fewer than 4 meaningful tokens
  - Numeric density > 0.25
  - Punctuation density > 0.20
  - Low alpha ratio < 0.50
- **Applied:** After database query, before scoring
- **Logging:** Counts logged (pre_filter, post_filter, noisy_excluded)

### Step 3: Confidence Gating ✅
- **Location:** `backend/app/engines/classification/engine.py` - `generate_alternatives()`
- **Implementation:**
  - If `best_similarity < 0.18`, return `NO_CONFIDENT_MATCH`
  - Returns top 5 candidates as "untrusted" for human review
  - Does NOT force output
- **Audit fields:**
  - `similarity_top`: Best similarity score
  - `threshold_used`: "0.18"
  - `reason_code`: "LOW_SIMILARITY_GATE"
  - `status`: "NO_CONFIDENT_MATCH"

### Step 4: Audit Replayability Upgrades ✅
- **Location:** `backend/app/models/classification_audit.py`
- **New fields added:**
  - `applied_filters`: JSONB array of filter names
  - `candidate_counts`: JSONB with pre_filter_count, post_filter_count, post_score_count
  - `similarity_top`: String (best similarity score)
  - `threshold_used`: String (confidence threshold)
  - `reason_code`: String (rejection reason)
  - `status`: String (SUCCESS, NO_CONFIDENT_MATCH, NO_GOOD_MATCH)
- **Migration:** `003_add_audit_replayability_fields.py` created
- **API updates:** All audit records now include these fields

### Step 5: Smoke Test Updates ✅
- **Location:** `backend/scripts/smoke_test_classification.py`
- **Updated test cases:**
  1. **Earbuds:** "Wireless Bluetooth earbuds with rechargeable battery, noise cancellation, and microphone for hands-free communication"
  2. **Water bottle:** "Stainless steel insulated water bottle with double-wall vacuum insulation, 32 ounce capacity, for personal use"
  3. **T-shirt:** "Men's cotton t-shirt, knit fabric, short sleeves, 100% cotton, weight 180 gsm, for retail sale"
- **Expected outcomes:**
  - Fewer absurd cross-chapter results
  - Some NO_CONFIDENT_MATCH outputs (this is good)
  - Stable candidate sets

---

## ⏳ Pending (Step 6 - After Smoke Tests Pass)

### Step 6: Store "Free" as First-Class Duty Data
**Status:** Waiting for smoke test validation

**Planned changes:**
1. Add `duty_rate_general_text` (or `duty_rate_general_raw`) column to `hts_versions`
2. Add `is_free` boolean column to `hts_versions`
3. Backfill from `tariff_text` parse for "Free"
4. Update duty availability scoring to treat `is_free` as present

**Files to modify:**
- Database migration (new)
- `backend/app/engines/classification/engine.py` - duty rate selection logic
- Backfill script

---

## 🧪 Next Steps

1. **Run migration:**
   ```bash
   cd backend
   alembic upgrade head
   ```

2. **Run smoke tests:**
   ```bash
   python backend/scripts/smoke_test_classification.py
   ```

3. **Verify:**
   - ✅ Fewer absurd cross-chapter results
   - ✅ Some NO_CONFIDENT_MATCH outputs appear
   - ✅ Candidate sets are stable
   - ✅ No earbuds matching wood plywood (Ch. 44)

4. **After smoke tests pass:** Implement Step 6 (Store "Free" rates)

---

## 📊 Expected Improvements

### Before Fixes
- ❌ Earbuds matching wood plywood (HTS 4412513121)
- ❌ All candidates with similarity 0.053 (effectively random)
- ❌ 10,461 codes with 9903 contamination in search results
- ❌ No confidence gating

### After Fixes
- ✅ 9903 contamination excluded (10,461 rows filtered)
- ✅ Noise descriptions filtered out
- ✅ Confidence gating prevents low-quality matches
- ✅ Full audit trail for replayability
- ✅ Richer test cases for validation

---

## 🔍 Key Changes Summary

1. **Hard exclusions:** 9903 text, chapters 98/99 at DB level
2. **Noise filters:** Remove low-quality descriptions before scoring
3. **Confidence gating:** Don't force output if similarity < 0.18
4. **Audit trail:** Complete replayability with filter counts and reasons
5. **Better tests:** Richer product descriptions for validation

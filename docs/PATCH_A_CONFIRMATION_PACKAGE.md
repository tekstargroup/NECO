# Patch A — Confirmation Package (Status & Similarity Cleanup)

**Goal:** Similarity is **supportive** (retrieval ranking), not **decisive** (SUCCESS / REVIEW / reporting).

---

## 1. Files touched

| File | Role |
|------|------|
| `backend/app/engines/classification/status_model.py` | `determine_status` no longer takes `best_similarity`; added `competitive_ambiguity_requires_review`, constants `MIN_TOP_CANDIDATE_SCORE_FOR_SUCCESS`, `MIN_ANALYSIS_CONFIDENCE_FOR_SUCCESS`. |
| `backend/app/engines/classification/engine.py` | Family gate uses multiple 8518 **subheadings**, not `best_8518_similarity >= 0.16`. `_review_ambiguity_notes()` for REVIEW copy. `determine_status(..., ambiguity_requires_review=...)`. Metadata `threshold_used`: `outcome_based` (quality gate still documents `0.20` where applicable). |
| `backend/app/engines/classification/review_explanation.py` | No 0.18 / 0.25 **lexical similarity band** explanations; reasons tied to combined score, analysis confidence, ambiguity notes, 8518 multi-subheading logic. |
| `backend/app/services/reporting_service.py` | Classification risk buckets use `output.status`, not `metadata.best_similarity` bands. |
| `backend/tests/test_patch_a_status_model.py` | **New** — unit tests for status model + review explanation invariants. |
| `backend/tests/test_reporting_service.py` | **Extended** — `test_classification_risk_report_buckets_by_status_not_similarity`. |

---

## 2. Exact code changes (summary)

### `status_model.py`

- **Removed:** `determine_status(..., best_similarity: float, ...)` and all branches that compared `best_similarity` to 0.18 / 0.25 for SUCCESS / REVIEW.
- **Added:** `competitive_ambiguity_requires_review(final_candidates, score_gap=0.08)` — uses `final_score` on the top two candidates only.
- **SUCCESS** requires (when `missing_required_attributes` is empty and `candidates_exist`):

  - `top_candidate_score >= 0.20`
  - `analysis_confidence >= 0.7`
  - `not ambiguity_requires_review`

- **Otherwise** (with candidates): **REVIEW_REQUIRED**. **No candidates:** **NO_CONFIDENT_MATCH**. **Missing attrs:** **CLARIFICATION_REQUIRED**.

### `engine.py`

- **Family-aware path:** `audio_devices` + clarification + ≥2 candidates in 8518 + **more than one distinct 6-digit subheading** → `REVIEW_REQUIRED`, `reason_code=FAMILY_AWARE_GATE_8518`. Else standard `determine_status` with `ambiguity_requires_review=competitive_ambiguity_requires_review(final_candidates)`.
- **REVIEW_REQUIRED** early return: `ambiguity_reason` from `_review_ambiguity_notes(...)` (competitive scores, analysis confidence, top combined score vs 0.20, family note) — **not** lexical similarity bands.
- **Success path** final `determine_status` uses the same `ambiguity_requires_review` flag (no `best_similarity`).
- **Metadata:** `threshold_used` = `"outcome_based"` for normal classification responses; **NO_GOOD_MATCH** path still exposes `quality_gate_threshold: 0.20` (combined score floor, not pg_trgm).
- **Empty-candidate** default `reason_code` default label: `NO_CANDIDATES_GATE` (replaces misleading `LOW_SIMILARITY_GATE`).

### `review_explanation.py`

- `best_similarity` / `best_8518_similarity` retained in signature for callers but **not** used to build “threshold band” sentences.
- Primary reasons emphasize **combined score**, **analysis confidence (0.70)**, **multi-candidate / 8518** ambiguity, and engine-provided `ambiguity_reason` lines.

### `reporting_service.py`

- **Before:** Low / medium / high mixed `status` with `similarity < 0.18` and `0.18 ≤ similarity < 0.25`.
- **After:** Buckets driven only by `output.status` (see matrix below).

---

## 3. Before / after decision matrix

### A. Core `determine_status` (no engine family override)

Assumptions: `missing_required_attributes == []`, `candidates_exist == True`, unless noted.

| analysis_confidence | top_candidate_score | ambiguity_requires_review | Before (old similarity-based) | After (Patch A) |
|---------------------|----------------------|---------------------------|-----------------------------|-----------------|
| ≥ 0.7 | ≥ 0.20 | False | SUCCESS if `best_similarity ≥ 0.25` **and** same score/confidence gates; else often REVIEW if `0.18 ≤ sim < 0.25` or sim &lt; 0.18 with candidates | **SUCCESS** |
| ≥ 0.7 | ≥ 0.20 | True | Could be REVIEW (similarity bands) | **REVIEW_REQUIRED** |
| &lt; 0.7 | ≥ 0.20 | False | REVIEW if similarity in “review band” or confidence &lt; 0.7 | **REVIEW_REQUIRED** |
| ≥ 0.7 | &lt; 0.20 | False | Mixed with similarity | **REVIEW_REQUIRED** |
| — | — | — | `candidates_exist == False` | **NO_CONFIDENT_MATCH** (unchanged intent) |
| — | — | — | `missing_required` non-empty | **CLARIFICATION_REQUIRED** (unchanged) |

**Key behavioral shift:** A case with **high lexical similarity** but **low `analysis_confidence`** or **competitive top-two scores** no longer sneaks to SUCCESS because similarity looked “good”; it follows confidence / score / ambiguity only.

### B. Classification risk report buckets (`generate_classification_risk_report`)

| `output.status` | Before (similarity in snapshot) | After |
|-------------------|----------------------------------|--------|
| `SUCCESS` | High if similarity high enough even without checking status consistently | **high_confidence** |
| `REVIEW_REQUIRED` | Often medium via similarity band | **medium_confidence** |
| `NO_CONFIDENT_MATCH`, `NO_GOOD_MATCH`, `CLARIFICATION_REQUIRED` | Often low via similarity &lt; 0.18 | **low_confidence** |
| Missing / other | Fell through to high if similarity ≥ 0.25 | **medium_confidence** |

---

## 4. Tests

### Added / updated

- `backend/tests/test_patch_a_status_model.py` — `determine_status`, `competitive_ambiguity_requires_review`, and `generate_review_explanation` invariants (no legacy similarity-band phrasing).
- `backend/tests/test_reporting_service.py` — `test_classification_risk_report_buckets_by_status_not_similarity` (high `best_similarity` does not move a `REVIEW_REQUIRED` row to “high”).

### Command

```bash
cd backend
python3 -m pytest tests/test_patch_a_status_model.py tests/test_reporting_service.py -q
```

(Requires project deps: `pytest`, `pytest-asyncio`, `asyncpg`, and app settings so `conftest` can import the DB layer.)

---

## 5. API / metadata / DB notes

- **API responses:** `metadata.best_similarity` may still be present for **diagnostics** (max similarity among final candidates). It must not be interpreted as “the model understood the product.”
- **`metadata.threshold_used`:** `"outcome_based"` for paths that no longer encode a lexical cutoff; **NO_GOOD_MATCH** still carries an explicit **combined-score** quality threshold (`0.20`) in metadata where applicable.
- **`metadata.reason_code`:** `FAMILY_AWARE_GATE_8518` when multiple 8518 subheadings apply; `NO_CANDIDATES_GATE` when no scored candidates (renamed from similarity-flavored default).
- **DB:** No migration; **ReviewRecord** snapshots continue to store `output.status` and `metadata`; reporting now keys off **status** for risk buckets.
- **Logs:** Engine may still log `best_similarity` as informational; classification outcome is not decided by that number alone.

---

## 6. Retrieval

- SQL / `pg_trgm` **ordering** of candidates is **unchanged**; similarity remains a **ranking** signal only.

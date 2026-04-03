# PR3 — `patch-a-memo-alignment` (Patch A + engine follow-up)

**Base:** merge **PR2** (or apply after B–D–C–E–F stack).

## Scope

- **Patch A:** `classification_memo.py` (strict vs legacy alignment with engine `status`), `build_classification_memo` / `stable_classification_outcome` imported from orchestration; `CLASSIFICATION_MEMO_STRICT_STATUS_ALIGNMENT` config; consumers updated (`export_service`, `reporting_service`, benchmarks, tests).
- **Patch A follow-up:** `engine.py` quality gate: `best_similarity` (not undefined `best_similarity_for_gate`) in `NO_GOOD_MATCH` metadata; comment that SUCCESS paths should not hit `top_score < 0.20` gate.

## Exact files

| Area | Paths |
|------|--------|
| Memo | `backend/app/services/classification_memo.py` |
| Engine | `backend/app/engines/classification/engine.py`, `backend/app/engines/classification/status_model.py` |
| Config | `backend/app/core/config.py` (`CLASSIFICATION_MEMO_STRICT_*`) |
| Callers | `backend/app/services/shipment_analysis_service.py` (imports memo), `backend/app/services/export_service.py`, `backend/app/services/reporting_service.py`, `backend/run_benchmark.py` |
| Tests | `backend/tests/test_classification_memo_strict.py`, `backend/tests/test_patch_a_status_model.py`, `backend/tests/test_trust_benchmark.py`, `backend/tests/test_sprint_4_2_invariants.py`, `backend/tests/test_review_service.py`, `backend/tests/test_reporting_service.py`, `backend/tests/test_audit_pack_service.py`, golden HTS tests if touched |

## Migration steps

None.

## Flags

| Flag | Default | Purpose |
|------|---------|---------|
| `CLASSIFICATION_MEMO_STRICT_STATUS_ALIGNMENT` | env-dependent | Memo `support_level` tracks engine `status`, not raw similarity alone |

## Tests to run

```bash
cd backend
python3 -m pytest tests/test_classification_memo_strict.py tests/test_patch_a_status_model.py \
  tests/test_trust_benchmark.py tests/test_sprint_4_2_invariants.py -v --tb=short
```

## Known limitations

- Strict memo assumes engine `status` is authoritative; mismatched engine versions can still confuse UX.
- Quality-gate branch for `NO_GOOD_MATCH` should be rare when `determine_status` yields SUCCESS (comment documents intent).

## Rollback

Revert PR3 commit(s). Toggle strict flag off in env if hotfix needed without full revert.

## Confirmation package

| Check | Expect |
|-------|--------|
| `NO_GOOD_MATCH` metadata | `best_similarity` key present (no NameError) |
| Strict memo | `SUCCESS` / `REVIEW_REQUIRED` consistent with `status_model` docs |

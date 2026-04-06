# PR: Phase 1 & Phase 2 — Canonical artifact completion

**Scope:** Phase 1 (execution integrity, pipeline stages, trust semantics) and **Phase 2 (canonical, analysis-scoped, replayable artifacts)** are **complete** on this branch. **Phase 3 (e.g. decision engine) has not started** and is out of scope for this PR.

---

## Deploy note

**Run Alembic through migration `026` before deploy.**

---

## Summary

This PR completes **Phase 2: Canonical Artifact Completion** (building on Phase 1 closeout).

### Key outcomes

- All core analysis artifacts are now canonical and analysis-scoped where defined
- Reasoning traces persisted in DB (`analysis_item_reasoning_traces`)
- Regulatory artifacts aligned to `analysis_id`
- Provenance snapshot model introduced (`analysis_line_provenance_snapshots`)
- Canonical DB-first loader implemented (`load_canonical_analysis_artifacts`, etc.)
- Review/object snapshot derived from canonical artifacts (not parallel truth)
- Trust contract upgraded to **`phase2_v3`** with full artifact matrix

### System guarantees after merge

- Analysis results are reconstructable from DB state alone (canonical dimensions)
- Same-analysis retries are idempotent for canonical artifact writes
- `TRUSTED` reflects explicit artifact-level guarantees via `trust_contract`
- Provenance is frozen per analysis for audit consistency (`analysis_line_provenance_snapshots`)

### Deferred (explicitly not in this PR)

- Duty/PSC remain advisory (not in TRUSTED)
- Full integration tests with seeded DB
- Full surface migration to canonical loader (incremental)
- **Phase 3** work (decision engine and downstream) — not started

This PR establishes the baseline required before Phase 3.

# Phase 2 — Canonical Artifact Completion

This document defines **data model**, **artifact contracts**, **migrations**, **services**, **trust contract**, **stages**, **tests**, **hard recommendations**, and **Phase 3 readiness**.

---

## Hard recommendations (decisions)

### 1. Reasoning trace: normalized tables vs typed JSON column?

**Recommendation: single table with JSONB `trace_json` + constraints, keyed by `(analysis_id, shipment_item_id)`.**

- **Why not fully normalized:** Heading reasoning is a structured tree that evolves with the engine; normalizing into dozens of tables adds migration churn and weakens replay fidelity without LLM involvement.
- **Why JSONB in DB (not only `result_json`):** Gives a **canonical, queryable, upsertable** row per analysis run and line, auditable independently of review snapshot or API payload shape.
- **Schema discipline:** `schema_version` column (e.g. `1`) + optional JSON Schema checksum in `trust_contract`; reject or warn on unknown schema in strict mode.

### 2. Canonical provenance contract (line / document → item)

**Recommendation (minimum coherent model):**

| Layer | Canonical | Role |
|-------|-----------|------|
| `shipment_documents` | Document bytes + extraction | Source documents |
| `shipment_item_line_provenance` | `(shipment_item_id, shipment_document_id, line_index, …)` | **Line-level** ES/CI linkage (already exists) |
| **`analysis_id` on provenance (Phase 2)** | Optional FK `analysis_id → analyses.id` | **Which analysis run** materialized or validated this linkage for replay |
| Classification facts | `shipment_item_classification_facts` | Product facts used for classification |
| **No duplicate “truth”** | Snapshot JSON | **Derived** projection for UI/export, rebuilt from DB where possible |

**Contract:** For a given `analysis_id`, reproducible story is: documents + per-analysis provenance rows (where `analysis_id` set) + facts + regulatory + reasoning traces. Legacy rows with `analysis_id IS NULL` remain shipment-scoped until backfilled.

### 3. Regulatory: review-linked vs analysis-scoped?

**Recommendation: move **canonical** regulatory rows to **`analysis_id` + `shipment_item_id`** (or evaluation keyed by analysis), with **`review_id` nullable or derived**.**

- **Short term (Phase 2a):** Keep `regulatory_evaluations.review_id` FK; add **`analysis_id`** on `regulatory_evaluations` (NOT NULL for new rows), unique constraints where appropriate; review record still points at analysis for workflow.
- **Phase 2b:** Exports and trust gate read regulatory by **`analysis_id`**, not by walking review-only.
- **Rationale:** Review is a **workflow** object; analysis is the **run**; compliance replay should not depend on review row shape.

### 4. Duty / PSC: advisory vs canonical in Phase 2?

**Recommendation: keep **advisory by default** for Phase 2; add **optional** canonical snapshots table only if product commits to filing-grade duty.**

- **`analysis_item_duty_psc_snapshots`** (optional migration): `analysis_id`, `shipment_item_id`, `duty_json`, `psc_json`, `schema_version`, `computed_at`, upsert on retry. **Not** in TRUSTED mandatory unless explicitly promoted.
- **TRUSTED** continues to mean “pipeline stages + facts + regulatory + reasoning DB + …” per matrix; duty/PSC stay **`in_trusted_contract: false`** until Phase 2.2+ product decision.

### 5. Minimum Phase 2 completion bar before Phase 3

Phase 3 (e.g. broader decision intelligence, retrieval tuning) may start only when:

1. **Reasoning trace** persisted per `(analysis_id, shipment_item_id)` with idempotent upsert; **result_json** trace is **derived or verified** against DB for new runs.
2. **Provenance** either analysis-scoped (`analysis_id` on line provenance) or a documented replay rule from shipment-scoped rows + analysis version.
3. **Regulatory** rows addressable by `analysis_id` for export/chat/replay without relying on review snapshot alone.
4. **`trust_contract` version ≥ `phase2_v3`** (regulatory + snapshot derivation + line provenance snapshots + canonical loader) with updated **artifact_matrix** and explicit TRUSTED implications.
5. **Tests:** idempotent retry + at least one reconstruction test from DB-only inputs.

---

## 1. Proposed data model / schema changes

### A. `analysis_item_reasoning_traces` (implemented in migration `023`)

| Column | Type | Notes |
|--------|------|--------|
| `id` | UUID PK | |
| `analysis_id` | UUID FK `analyses.id` ON DELETE CASCADE | |
| `shipment_id` | UUID FK | Denormalized for org queries |
| `organization_id` | UUID FK | |
| `shipment_item_id` | UUID FK `shipment_items.id` | |
| `trace_json` | JSONB NOT NULL | Canonical structured trace |
| `schema_version` | TEXT NOT NULL DEFAULT `'1'` | |
| `created_at` / `updated_at` | timestamptz | |

**Constraints:** `UNIQUE (analysis_id, shipment_item_id)` — upsert target for retries.

**Indexes:** `(analysis_id)`, `(shipment_item_id)`, `(organization_id, analysis_id)`.

### B. `regulatory_evaluations.analysis_id` + `shipment_item_id` (migration `024`)

| Column | Type | Notes |
|--------|------|--------|
| `analysis_id` | UUID FK `analyses.id` ON DELETE CASCADE **NOT NULL** | Primary access key for loads; backfilled from `review_records` |
| `shipment_item_id` | UUID FK `shipment_items.id` ON DELETE SET NULL nullable | Per-line linkage when engine emits `item_id` |

Orphan rows without resolvable `analysis_id` are **deleted** during upgrade (cannot be replayed safely).

### C. `shipment_item_line_provenance.analysis_id` (migration `025`)

| Column | Type | Notes |
|--------|------|--------|
| `analysis_id` | UUID FK `analyses.id` ON DELETE SET NULL nullable | Optional audit alignment; backfilled from `shipment_items.active_analysis_id` where set |

### D. `analysis_item_duty_psc_snapshots` (optional Phase 2.2)

Same pattern as reasoning: JSONB + upsert; **advisory** until promoted in trust matrix.

---

## 2. Artifact-by-artifact canonical contract

| Artifact | Canonical source | Retry policy | In TRUSTED? | Stage / dependency | result_json role |
|----------|------------------|--------------|-------------|-------------------|------------------|
| Classification output | Engine + `classification_results` → JSON | Per run | Yes (via stages) | CLASSIFICATION | Derived |
| Classification facts | `shipment_item_classification_facts` | Upsert | Yes | FACT_PERSIST | Derived |
| Reasoning trace | **`analysis_item_reasoning_traces.trace_json`** | Upsert | **Phase 2.1+ when flag on** | REASONING_TRACE_PERSIST | **Derived** from DB for new runs |
| Line provenance | `shipment_item_line_provenance` (+ optional `analysis_id`) | Insert/replace rules TBD | Phase 2 when scoped | DOCUMENT_EVIDENCE / import | Derived |
| Regulatory | `regulatory_evaluations` + conditions | Replace-with-review or by-analysis | Yes | REGULATORY + persist | Derived |
| Review snapshot | `review_records.object_snapshot` | Replace per analysis | Yes | REVIEW_REGULATORY_PERSIST | **Derived** aggregate (long-term) |
| Duty / PSC | Advisory JSON or optional snapshot table | Upsert if snapshotted | **No** (default) | DUTY_PSC_ADVISORY | Advisory |

---

## 3. Migration plan

| Order | Migration | Purpose |
|-------|-----------|---------|
| 023 | `analysis_item_reasoning_traces` | Create reasoning table + indexes |
| 024 | `shipment_item_line_provenance.analysis_id` | Analysis-scoped provenance |
| 025 | `regulatory_evaluations.analysis_id` | Analysis-first regulatory |
| 026 | Optional duty/PSC snapshot table | If product promotes |

**Backfill:**  
- **Reasoning:** Script reads `analyses.result_json` → INSERT … ON CONFLICT for historical COMPLETE rows (batch).  
- **Provenance:** Set `analysis_id` from `shipment_items.active_analysis_id` or latest analysis for shipment.  
- **Regulatory:** Join `review_records.analysis_id` → UPDATE `regulatory_evaluations`.

**Mixed read strategy:**  
- API builds `result_json.items[].heading_reasoning_trace` from **DB first** if `analysis_id` present and row exists; else fall back to embedded JSON (legacy).

**Shim removal:** After backfill + one release, drop JSON-only path for reasoning in new analyses (feature flag).

---

## 4. Service-layer changes

| Area | Behavior |
|------|----------|
| **Writes** | After item payloads built, `upsert_analysis_item_reasoning_trace(...)` for each item when `analysis_id` set. |
| **Retries** | Same upsert key → replace `trace_json` + `updated_at`. |
| **Exports/chat** | Load trace from DB when serving authoritative analysis; merge into snapshot for export consistency. |
| **Pipeline stage** | `REASONING_TRACE_PERSIST`: RUNNING → per-item upserts → SUCCEEDED / FAILED |

---

## 5. Trust contract updates (`phase2_v3` current)

- **`version`** **`phase2_v3`** — regulatory primary key + materialized review snapshot + `analysis_line_provenance_snapshots` + expanded artifact matrix (`regulatory_conditions_db`, `line_provenance_snapshot`, `line_provenance_live_import`).
- **`artifact_matrix`:** `heading_reasoning_trace` row: `canonical_source: analysis_item_reasoning_traces`, `in_trusted_contract: true` **when** `PHASE2_REASONING_TRACE_TRUSTED_REQUIRED=true`.
- **`trusted_implies` / `trusted_does_not_imply`:** align with matrix.
- Keep **duty/PSC** excluded unless promoted.

---

## 6. Stage model (recommended)

| Stage | Required for TRUSTED (Phase 2.1) |
|-------|-------------------------------|
| `REASONING_TRACE_PERSIST` | Yes, **when** settings flag enables Phase 2 trust bar |

Until flag is on, stage is **tracked** but not in `MANDATORY_STAGES_FOR_TRUSTED`.

---

## 7. Tests required

- **Idempotent upsert** for reasoning trace (same analysis retry).
- **Reconstruction:** Build item DTO from DB rows only (mock).
- **Migration compatibility:** Old analysis without table row still loads from JSON fallback.
- **Consumer contract:** `artifact_in_trusted_contract` matches matrix after version bump.

---

## Critical vs structural vs defer

### Critical (Phase 2 core)

- Reasoning trace DB + upsert + read path preference.
- Trust contract + matrix updates.
- Regulatory `analysis_id` (if exports must not depend on review alone).

### Structural (good if low-risk)

- `analysis_id` on line provenance.
- Review snapshot builder from DB projections.

### Non-critical / defer

- Full normalization of reasoning trace.
- Duty/PSC canonical promotion.
- LLM or ontology layers.

---

## Implementation status (repo)

### Done (Phase 2a — reasoning trace)

- **Migration `023_analysis_item_reasoning_traces`:** table + indexes + `UNIQUE (analysis_id, shipment_item_id)`.
- **Model:** `app/models/analysis_item_reasoning_trace.py` (`AnalysisItemReasoningTrace`).
- **Persistence:** `app/services/reasoning_trace_persistence.py` — `upsert_analysis_item_reasoning_trace`, `persist_reasoning_traces_from_result_items`, `merge_reasoning_traces_into_result_json`.
- **Pipeline:** `ShipmentAnalysisService._persist_reasoning_traces_phase2` after full and fast-local `result_json` build; stage **`REASONING_TRACE_PERSIST`** (ordinal 32) RUNNING → SUCCEEDED/FAILED.
- **Read path:** `AnalysisOrchestrationService.get_analysis_status` deep-copies `result_json` and merges DB traces over `items[].heading_reasoning_trace` when rows exist.
- **Config:** `PHASE2_REASONING_TRACE_TRUSTED_REQUIRED` (default **False**). When **True**, `mandatory_stages_for_trusted()` includes `REASONING_TRACE_PERSIST` and `all_mandatory_stages_succeeded()` enforces it; `artifact_matrix` marks `heading_reasoning_trace` **in_trusted_contract** accordingly.
- **Trust contract:** reasoning-trace gating via `phase2_reasoning_trace_trusted_gate_enabled` (overall contract version **`phase2_v2`** after Phase 2b ships).
- **Tests:** `tests/test_pipeline_stages.py`, `tests/test_trust_contract_consumer.py` (gate on/off).

### Done (Phase 2b — regulatory + derived review snapshot)

- **Migration `024_regulatory_evaluations_analysis_scope`:** `analysis_id` (NOT NULL), `shipment_item_id`, indexes; backfill + delete orphans; model + `Analysis.regulatory_evaluations`.
- **Migration `025_line_provenance_analysis_id`:** nullable `analysis_id` on `shipment_item_line_provenance` + index; backfill from `active_analysis_id`.

### Done (Phase 2c — analysis-scoped provenance freeze + canonical loader)

- **Migration `026_analysis_line_provenance_snapshots`:** `analysis_line_provenance_snapshots` table; unique `(analysis_id, shipment_item_id, shipment_document_id, line_index)`; replaces-on-retry semantics via delete-all-then-insert in `replace_line_provenance_snapshots_for_analysis`.
- **Pipeline:** after regulatory persist, **freeze** live line provenance into snapshots, then `materialize_review_object_snapshot` reads snapshots first (falls back to live `shipment_item_line_provenance` if no rows — legacy).
- **Loader:** `app/services/canonical_analysis_artifacts.py` — `load_canonical_analysis_artifacts`, `build_analysis_snapshot_from_canonical_artifacts`.
- **Trust contract:** **`phase2_v3`** with `line_provenance_snapshot`, `regulatory_conditions_db`, `line_provenance_live_import`, loader pointer metadata.
- **Writes:** `delete_regulatory_evaluations_for_analysis` before insert; `RegulatoryEvaluation` rows include `analysis_id`, `review_id` (workflow), `shipment_item_id` when present.
- **Reads:** `regulatory_select_for_review` / `fetch_regulatory_evaluations_engine_json` — primary path `analysis_id`; `review_id` only for legacy rows without `review.analysis_id`.
- **Review snapshot:** `materialize_review_object_snapshot` in `review_snapshot_derivation.py` — **materialized** after persist; overlays facts, reasoning, regulatory, line provenance from DB + advisory fields from engine JSON; sets `_snapshot_derivation`.
- **Pipeline:** `execute_shipment_analysis_pipeline` finalizes `review_records.object_snapshot` from materializer (not raw `deepcopy(result_json)` as source of truth).
- **Trust contract:** **`phase2_v2`**; `phase2b_regulatory_primary_key`, `phase2b_review_snapshot_derivation`; matrix rows for `regulatory_evaluations_db`, `review_snapshot_db`, `line_provenance` updated.
- **Tests:** `tests/test_phase2b_canonical.py` (contract + materialize smoke + regulatory select); existing trust/pipeline tests updated for `phase2_v2`.

**Phase 2b guarantees (this slice):**

- Regulatory compliance data for an analysis is **addressable by `regulatory_evaluations.analysis_id`**; exports and review API prefer loading by that key.
- Line provenance remains **shipment-scoped** canonical rows; optional `analysis_id` is **supporting metadata** for audit alignment (not a second line-level truth).
- `review_records.object_snapshot` is a **denormalized, materialized projection** built after canonical DB writes (not an independent source of truth for regulatory/facts/reasoning/provenance).
- Duty/PSC remain **advisory** (`outputs_advisory_only`); not promoted into TRUSTED.

### Deferred

- Optional **026** duty/PSC snapshot table if promoted
- JSON backfill script for historical `result_json` → `analysis_item_reasoning_traces` where gaps exist
- Full **Postgres integration** tests behind `RUN_PHASE2_INTEGRATION_TESTS=1` (fixture graph TBD)

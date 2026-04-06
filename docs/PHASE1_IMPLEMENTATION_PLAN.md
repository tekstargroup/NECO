# Phase 1 — Decision integrity: implementation plan

This document turns Phase 1 principles into **constraints**, **schemas**, **state machines**, **breaking-change boundaries**, and a **migration path**. It is grounded in the current NECO codebase (Sprint 12 `analyses`, Patch D facts, regulatory rows on `review_records`, etc.).

---

## 1. Current snapshot (repo state)

| Area | Status |
|------|--------|
| `analyses.id` | Primary key (treat as `analysis_id` in APIs) |
| Execution enum | `AnalysisStatus`: `QUEUED`, `RUNNING`, `COMPLETE`, `FAILED`, `REFUSED` |
| Decision enum | `DecisionStatus`: `TRUSTED`, `REVIEW_REQUIRED`, `INSUFFICIENT_DATA`, `DEGRADED`, `BLOCKED` (column exists post-migration) |
| Versioning | `analyses.version` (monotonic per shipment) — populated on new rows in orchestration |
| Active pointer | `analyses.is_active` + `shipment_items.active_analysis_id` — promoted per **gated** rules (`maybe_promote_analysis_after_success`: TRUSTED auto; REVIEW_REQUIRED if `ANALYSIS_PROMOTE_REVIEW_REQUIRED`; DEGRADED only if `ANALYSIS_ALLOW_DEGRADED_PROMOTION` + local dev) |
| Display resolution | `resolve_display_analysis()` — **no `created_at` authority**; order: in-flight (QUEUED/RUNNING) by `version` → `is_active` → terminal fallback by **`version` only**. Raises `AnalysisIntegrityError` if **multiple** `is_active` rows (should be impossible with index `019`). |
| TRUSTED derivation | **Gated** via `trust_gate_allows_trusted_status` (no blockers, non-degraded mode, facts row per item, no `critical_pipeline_errors`) — not “COMPLETE + empty blockers”. |
| Pipeline entry | `execute_shipment_analysis_pipeline(..., analysis_id=...)` — no “latest row by time” inside the pipeline |
| Still “latest by time” | Idempotency guard in `AnalysisOrchestrationService`, task bootstrap in `tasks/analysis.py`, `_mark_analysis_failed`, `shipment_eligibility_service.py`, scripts |

**Gap vs full Phase 1 spec:** canonical JSON as *render-only*, structured regulatory/duty keyed by `analysis_id`, per-fact uniqueness, transactional stage ledger, and elimination of silent `except` paths are **not** fully implemented; they belong in later slices below.

---

## 2. Database schema changes

### 2.1 Already introduced (Alembic `018_phase1_analysis_identity`)

| Object | Definition |
|--------|-------------|
| **ENUM** `decisionstatus` | `TRUSTED`, `REVIEW_REQUIRED`, `INSUFFICIENT_DATA`, `DEGRADED`, `BLOCKED` |
| **`analyses.version`** | `INTEGER NOT NULL`, default `1` |
| **`analyses.decision_status`** | `decisionstatus NULL` (set when execution is terminal success, or `BLOCKED` on refusal paths where implemented) |
| **`analyses.supersedes_analysis_id`** | `UUID NULL` → `analyses(id)` `ON DELETE SET NULL` |
| **`analyses.is_active`** | `BOOLEAN NOT NULL DEFAULT false` |
| **`shipment_items.active_analysis_id`** | `UUID NULL` → `analyses(id)` `ON DELETE SET NULL` |
| **Indexes** | `(shipment_id, is_active)` on `analyses`; `active_analysis_id` on `shipment_items` |

### 2.2 Alembic `019_phase1_active_integrity`

| Object | Definition |
|--------|------------|
| **Backfill** | Exactly one `COMPLETE` row per shipment (highest `version`, then `completed_at`) is `is_active`; all `shipment_items.active_analysis_id` updated. *(One-time SQL may use `completed_at` for tie-break only — not a runtime contract.)* |
| **Index** | `uq_analyses_one_active_per_shipment` — `UNIQUE (shipment_id) WHERE is_active = true` |

### 2.3 Recommended next migrations (to match full Phase 1 spec)

| Change | Purpose |
|--------|---------|
| ~~**Partial unique index**~~ | **Done in 019** |
| **`analyses.pipeline_errors`** | `JSONB` default `[]` or separate child table `analysis_pipeline_stage_runs` | Typed stage failures; no silent drop |
| **`analyses.execution_checkpoint`** | `JSONB` nullable OR stage table | Resume/idempotency metadata (optional) |
| **`shipment_item_classification_facts`** | Evolve uniqueness to `(analysis_id, shipment_item_id, fact_type)` **or** keep one JSON row but add **generated** uniqueness via normalized child table `classification_fact_rows` | Matches “artifact uniqueness” principle |
| **`regulatory_results` / `duty_results` (new)** | `analysis_id`, `shipment_item_id`, stable keys (`rule_id`, etc.), `UNIQUE` per spec | DB as source of truth; `result_json` becomes projection |
| **FK from existing regulatory rows** | Today: `regulatory_evaluations.review_id` → `review_records`. Target: also link or migrate to **`analysis_id`** for replay without walking review | Larger refactor; see §7 |

**Existing related constraints (reference):**

- `shipment_item_classification_facts`: `UNIQUE (analysis_id, shipment_item_id)` — one facts bundle per item per run today.
- `regulatory_evaluations` / `regulatory_conditions`: tied to `review_records`, not `analyses` directly.

---

## 3. Analysis lifecycle: two orthogonal state machines

Phase 1 requires **separating**:

1. **Execution** — job/process state (`analyses.status`).
2. **Decision** — outcome semantics for trust/review (`analyses.decision_status`).

They are **not** the same enum. `REFUSED` is an execution terminal state; `BLOCKED` is the decision label for “cannot proceed / gated.”

### Phase 1 scope — shipment-wide snapshot (explicit invariant)

In Phase 1, each `Analysis` row is an **immutable snapshot of the entire shipment** (all line items) for that version. **Per-item divergent active analyses are out of scope** until a future phase defines partial re-runs. Promotion is intentionally **shipment-wide**: one `is_active` analysis per shipment; every `shipment_item.active_analysis_id` matches that row.

### 3.1 Execution state machine (`analyses.status`)

| State | Meaning |
|-------|---------|
| `QUEUED` | Row created; worker not started or not yet RUNNING |
| `RUNNING` | Pipeline executing |
| `COMPLETE` | Pipeline finished without uncaught failure; persisted success path |
| `FAILED` | Pipeline or infrastructure error; **no promotion** to active |
| `REFUSED` | Pre-pipeline gate (eligibility, entitlement) — **no pipeline run** |

**Allowed transitions (intended):**

```
QUEUED → RUNNING → COMPLETE
QUEUED → RUNNING → FAILED
QUEUED → FAILED        (e.g. superseded, stale RUNNING cleanup)
REFUSED  (terminal; created directly)
```

**Invariants**

- `RUNNING` implies `started_at` set.
- `COMPLETE` implies `completed_at` set and **promotion** may run (if business rules say this run is displayable).
- `FAILED` implies `failed_at` set; `is_active` must not be set for this row by promotion.
- `REFUSED` — no `result_json` from engines; decision may be `BLOCKED` (or leave `decision_status` null if you want refusal-only semantics).

**Invariant (Phase 1 hard rule):** **Superseded analyses are immutable** — once a newer run is promoted, older rows are never updated in place for “current truth” (only audit/correction flows if ever added). **DB:** partial unique index prevents two `is_active` rows per shipment. **App:** do not mutate `result_json` on rows with `status=COMPLETE` when `is_active=false` except explicit admin tooling.

**Supersession:** `supersedes_analysis_id` records lineage; a **failed** run must not clear a **trusted active** analysis without an explicit transition (orchestration `force_new` marks the stale row `FAILED` — promotion of the new row still follows gated promotion rules).

### 3.2 Decision state machine (`analyses.decision_status`)

Set when execution reaches a **decision-relevant** terminal state (primarily `COMPLETE`; `REFUSED` may use `BLOCKED`).

| State | Meaning |
|-------|---------|
| `TRUSTED` | Full success path per policy; no review-forcing blockers |
| `REVIEW_REQUIRED` | Human review needed (e.g. pipeline blockers) |
| `INSUFFICIENT_DATA` | Deterministic insufficient evidence / facts |
| `DEGRADED` | Complete but dev shortcut / fast path / known reduced fidelity |
| `BLOCKED` | Gated (refusal, hard block) |

**Compatibility rule (from spec):**

- `COMPLETE` + `DEGRADED` **allowed** (e.g. instant/fast dev modes).
- `COMPLETE` + `TRUSTED` **only** when policy says “full pipeline success” (no degraded modes, no unresolved blockers).

**Invariants**

- If `status != COMPLETE`, typically `decision_status` is `NULL` (except explicit `BLOCKED` on refusal rows if you standardize that).
- UI and API should prefer **`decision_status` + `status`** together, not `created_at`.

---

## 4. Required code changes by component

### 4.1 Pipeline (`app/services/analysis_pipeline.py`, `shipment_analysis_service.py`)

| Task | Priority |
|------|----------|
| Keep **`analysis_id`** as the only identity for loads inside `execute_shipment_analysis_pipeline` | Done |
| **Single transaction** boundary: review record + regulatory rows + facts + `result_json` + promotion — either all commit or rollback | Partial — expand to explicit stages + errors |
| **Derive `decision_status`** from structured signals (blockers, mode flags), not ad hoc | Partial (`derive_decision_status`) |
| **Replace silent `try/except: continue`** with recorded stage errors + `FAILED` or `decision_status` | **Refactor first** in hot paths |
| **Projection builder**: assemble API/view JSON **from DB rows** (facts, duty, regulatory) with `result_json` as cache or phased removal | Future |

### 4.2 Workers (`app/tasks/analysis.py`, Celery)

| Task | Priority |
|------|----------|
| Load **`Analysis` by `analysis.id`** after creation (task id often equals analysis id) — **stop** using `ORDER BY created_at` for the running row | **Shim OK**: pass `analysis_id` into `_run_analysis_async` explicitly (string in task args) |
| Failure handler **`_mark_analysis_failed`** must target **the same `analysis_id`**, not latest row | **Breaking** if multiple rows exist and wrong row is failed |
| Retries: either **same `analysis_id`** (idempotent writes) or **new row** (new version) — policy in §5 | Must be explicit |

### 4.3 Orchestration (`analysis_orchestration_service.py`)

| Task | Priority |
|------|----------|
| Idempotency guard (`QUEUED`/`RUNNING`) — still uses `created_at` ordering | **Refactor**: scope by `version` or “no concurrent RUNNING” with row lock |
| **`force_new` / supersede** — set `supersedes_analysis_id` on the new row | Shim until UI/API documents supersession |
| Refusal paths — **`version` + `decision_status`** | Partial |

### 4.4 API (`app/api/v1/shipments.py`, analysis endpoints)

| Task | Priority |
|------|----------|
| List/detail: **display analysis** via `resolve_display_analysis` | Partial |
| Any endpoint that still assumes “newest analysis” | **Audit** (`grep Analysis.created_at`, `latest`) |
| Expose `analysis_id`, `version`, `decision_status`, `is_active` consistently | Partial (`get_analysis_status`) |

### 4.5 Other services (must converge)

| File | Issue |
|------|--------|
| `shipment_eligibility_service.py` | Uses latest analysis by `created_at` — should use **`resolve_display_analysis`** or “active + completeness” rules |
| Scripts (`verify_analysis_*.py`) | OK for dev; label as legacy ordering or update |

### 4.6 Frontend

| Task | Priority |
|------|----------|
| Use API fields for “current run” instead of inferring from timestamps | When API stable |
| Show **execution** vs **decision** separately where trust UX matters | Product-dependent |

---

## 5. Idempotency strategy (retries)

### 5.1 Principles

| Principle | Implementation choice |
|-----------|-------------------------|
| One **analysis row** = one **execution attempt** (logical run) | Already aligned |
| **Retries must not corrupt** uniqueness constraints | Use **upsert** or **delete-then-insert** per `(analysis_id, …)` or create **new analysis row** (bump `version`) |
| **Same Celery retry** hitting the same `analysis_id` twice | Writes must be **idempotent**: `ON CONFLICT DO UPDATE` or “if row exists for stage, skip” |

### 5.2 Current artifacts

| Artifact | Current constraint | Retry behavior |
|----------|-------------------|----------------|
| `shipment_item_classification_facts` | `UNIQUE (analysis_id, shipment_item_id)` | Second insert for same pair **fails** — retry must replace facts or use new `analysis_id` |
| Regulatory rows | Linked to `review_record` created in pipeline | Re-run same `analysis_id` risks **duplicate review/regulatory** unless pipeline is idempotent |
| `result_json` | Last write wins | Dangerous if partial writes — prefer single commit at end or clear failure |

### 5.3 Recommended policy (explicit)

1. **Preferred:** Celery **retries** = same `analysis_id` **only if** pipeline stages are idempotent (upsert facts, single review record per analysis enforced by unique constraint on `analysis_id` if added).
2. **Alternative:** Any ambiguous retry → **new `Analysis` row** (`version++`, `supersedes_analysis_id`), **never** reuse half-written rows.
3. **Must add:** either **`UNIQUE (analysis_id)` on `review_records`** (if 1:1) or store `review_record_id` only after full success and use transactional outbox pattern — today review is created **inside** the same transaction as completion; duplicate risk is on **retry after commit** partial failure (monitor and add idempotency keys).

---

## 6. Migration plan: current system → target system

### Phase A — **Done / in progress** (identity)

1. Deploy migration `018`.
2. Backfill active analysis + item pointers (included in migration).
3. Route “what we show” through `resolve_display_analysis` for key APIs + trust workflow.
4. Pipeline loads by `analysis_id`.

### Phase B — **Eliminate `created_at` as truth** (short)

1. Replace remaining queries in **eligibility**, **failure marking**, **task bootstrap** with **`analysis_id` pass-through** or `resolve_display_analysis`.
2. Add **DB partial unique index** on active analysis if desired.

### Phase C — **Structured artifacts** (medium)

1. Add `regulatory_results` / `duty_results` (or extend existing tables) keyed by `analysis_id` + item + rule keys.
2. Migrate writers in `analysis_pipeline` / `ShipmentAnalysisService` to **DB first**, JSON second.
3. Deprecate dual-write paths.

### Phase D — **Failure transparency** (medium)

1. Add `pipeline_errors` or stage table.
2. Remove bare `except` patterns in `shipment_analysis_service.py` systematically (grep-driven).

### Phase E — **Dev isolation** (ongoing)

1. Ensure `SPRINT12_*` and similar flags **cannot** change schema or enum semantics in production (`ENVIRONMENT` gate + config validation at startup — extend `docs/DEPLOYMENT.md` patterns).

---

## 7. What breaks

| Change | Risk |
|--------|------|
| Stricter **UNIQUE** constraints on facts/regulatory/duty | **Concurrent or retried** pipeline runs against same `analysis_id` **fail** or need upsert |
| **DB-enforced** single `is_active` | Invalid promotion logic causes **commit errors** |
| Removing **`result_json`** as authority | **Frontend** breaks until projection API matches fields |
| Celery task args change (explicit `analysis_id`) | Old workers vs new code **version skew** during deploy — use **compatible** task signature or queue drain |
| `decision_status` required non-null for `COMPLETE` | Legacy rows / partial migrations → **NULL** until backfill |

---

## 8. What must be refactored first

1. **Worker + failure path identity** — `_mark_analysis_failed` and task entry **must** use the same `analysis_id` as the run (no `ORDER BY created_at`).
2. **Eligibility / “latest analysis”** — `shipment_eligibility_service.py` should align with **active** or **explicit** policy.
3. **Review + regulatory idempotency** — define **one review per analysis** constraint or explicit idempotency token before adding hard uniqueness everywhere.

---

## 9. What can be shimmed temporarily

| Shim | Tradeoff |
|------|----------|
| `resolve_display_analysis` **fallback** to `created_at` when no `is_active` | Hides bugs where promotion failed; **remove** once all paths promote or set active |
| `decision_status` derived only from blockers + `mode` | **INSUFFICIENT_DATA** underused until signals exist |
| `result_json` still full payload while DB tables grow | **Dual-write** — acceptable short term if labeled and tested |
| `supersedes_analysis_id` unset on `force_new` | Audit trail incomplete until wired |

---

## 10. Success criteria checklist (Phase 1 exit)

- [ ] **Replay:** Given `analysis_id`, all persisted artifacts are reachable without `result_json`.
- [ ] **“Which run?”** — Answer is always `analyses.id` + `version`, not timestamp.
- [ ] **No silent degradation** — stage failures recorded; no bare `except` in pipeline hot path.
- [ ] **DB/UI agreement** — same resolution path for trust UI and APIs (`resolve_display_analysis` + projections).
- [ ] **Retries safe** — documented policy + constraints + tests for duplicate insert prevention.

---

## 11. Appendix: file index (implementation touchpoints)

| Concern | Primary files |
|---------|----------------|
| Schema | `backend/alembic/versions/018_*.py`, future `019+` |
| Identity / promotion | `backend/app/services/analysis_identity_service.py` |
| Pipeline | `backend/app/services/analysis_pipeline.py`, `shipment_analysis_service.py` |
| Workers | `backend/app/tasks/analysis.py` |
| Orchestration | `backend/app/services/analysis_orchestration_service.py` |
| API | `backend/app/api/v1/shipments.py`, analysis routes |
| Trust / readiness | `backend/app/services/trust_workflow_service.py` |
| Eligibility | `backend/app/services/shipment_eligibility_service.py` |

This plan should be updated when each migration lands so **breaking changes** and **shims** stay accurate for deploy notes and QA.

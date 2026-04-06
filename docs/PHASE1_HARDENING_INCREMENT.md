# Phase 1 — Next hardening increment (spec)

This document defines the **next** increment after the current foundation slice: it names **exact** schema migrations, **code touchpoints**, **invariants** (DB vs service), **retry policy**, **breaking changes**, and **shims to delete**.

Foundation already in place (reference only): `018`/`019`, `analysis_identity_service.py`, `resolve_display_analysis` (no `created_at` in resolver), `execute_shipment_analysis_pipeline(..., analysis_id=...)`, gated promotion, gated `TRUSTED` via `trust_gate_allows_trusted_status`.

---

## 1. Goals of this increment

| Goal | Outcome |
|------|---------|
| A. No remaining **`created_at` authority** for choosing an `Analysis` row | Every query uses **`analysis_id`**, **`version`**, **`status`**, **`is_active`**, or **`celery_task_id` ↔ analysis id** |
| B. **Stage-level** persistence | Rows or normalized JSON for each pipeline stage: status + errors |
| C. **`TRUSTED` is non-residual** | Granted only when **required stages succeeded** and **required artifacts** exist + trust gate |
| D. **DB-backed** active uniqueness + safe supersession | Already partially in `019`; extend with CHECKs / triggers if needed |
| E. **One retry policy per pathway** | Worker retry = same `analysis_id` + idempotent writes; user rerun = new row |

---

## 2. Migration order (strict)

| Order | Revision id (proposed) | Purpose |
|-------|------------------------|---------|
| After `019` | **`020_pipeline_stages_and_errors`** | New table(s) + enums for stage runs and/or aggregate columns on `analyses` |
| After `020` | **`021_analysis_idempotent_constraints`** | Uniqueness helpers for retry path (e.g. `review_records` 1:1 `analysis_id` if adopted) + facts upsert support |
| After `021` | **`022_optional_immutability_trigger`** | Optional: `BEFORE UPDATE` on `analyses` blocking mutation of `result_json` when `status=COMPLETE` and row is not active admin path — **only if** product accepts operational complexity |

**Rule:** ship **`020` before** changing worker identity loading, so stage rows exist when tightening `TRUSTED`.

---

## 3. Schema changes (exact)

### 3.1 New ENUM: `pipelinestagestatus` (Postgres)

Suggested values (adjust names to match code enums):

| Value | Meaning |
|-------|---------|
| `PENDING` | Not started |
| `RUNNING` | In progress |
| `SUCCEEDED` | Stage completed without blocking error |
| `FAILED` | Stage failed; pipeline should fail or mark non-TRUSTED |
| `SKIPPED` | Explicitly skipped (document reason in row) |

### 3.2 New ENUM: `pipelinestagename` (or `VARCHAR` with CHECK)

Stable identifiers used in code (single source of truth in Python `enum`):

Examples: `EVIDENCE`, `CLASSIFICATION`, `DUTY`, `PSC`, `REGULATORY`, `REVIEW_RECORD`, `FACTS_PERSISTENCE`, `RESULT_ASSEMBLY`.

### 3.3 New table: `analysis_pipeline_stages`

| Column | Type | Notes |
|--------|------|--------|
| `id` | `UUID` PK | `gen_random_uuid()` |
| `analysis_id` | `UUID` NOT NULL FK `analyses(id)` `ON DELETE CASCADE` | |
| `shipment_id` | `UUID` NOT NULL FK `shipments(id)` | Denormalized for tenant queries (optional but useful) |
| `organization_id` | `UUID` NOT NULL FK `organizations(id)` | |
| `stage` | `pipelinestagename` NOT NULL | |
| `status` | `pipelinestagestatus` NOT NULL | |
| `error_code` | `TEXT` NULL | Machine-readable |
| `error_message` | `TEXT` NULL | Human-readable |
| `error_details` | `JSONB` NULL | Stack/context (internal) |
| `started_at` | `TIMESTAMPTZ` NULL | |
| `completed_at` | `TIMESTAMPTZ` NULL | |
| `ordinal` | `INT` NOT NULL | Order within run (1..N) |

**Constraints**

- `UNIQUE (analysis_id, stage)` — one row per stage per analysis run (idempotent upsert key for retries).

**Indexes**

- `(analysis_id)`  
- `(shipment_id, stage)` (optional)

### 3.4 `analyses` table additions (aggregate mirror, optional but useful)

| Column | Type | Purpose |
|--------|------|---------|
| `pipeline_aggregate_status` | `ENUM` or `TEXT` | e.g. `ALL_SUCCEEDED` \| `HAS_FAILURES` \| `IN_PROGRESS` — **derived** from stage rows in same transaction as `COMPLETE` |
| `pipeline_errors_summary` | `JSONB` DEFAULT `'[]'` | Redundant compact list for API (optional; can be view-only from stages) |

**Invariant:** If `pipeline_aggregate_status != ALL_SUCCEEDED`, **`decision_status` MUST NOT be `TRUSTED`** (enforced in service; optional CHECK via trigger in `022`).

### 3.5 DB constraints already present / reinforced

| Invariant | Enforcement |
|-----------|-------------|
| At most one `is_active` per `shipment_id` | **DB:** partial unique index `uq_analyses_one_active_per_shipment` (`019`) — **keep** |
| Facts per item per run | **DB:** `UNIQUE (analysis_id, shipment_item_id)` on `shipment_item_classification_facts` — **keep** |
| Promotion does not create second active | **DB:** partial unique index + transactional promotion — **keep** |

### 3.6 Optional (retry idempotency): `review_records.analysis_id`

If review is **1:1** with analysis:

- Add nullable `analysis_id UUID UNIQUE` FK → `analyses(id)`  
- Backfill from `analyses.review_record_id`  
- Later: make `review_record_id` on `analyses` redundant or keep as dual pointer with sync rule  

**Breaking:** migration scripts that insert duplicate reviews per analysis must be fixed.

---

## 4. Removing all remaining `created_at` fallback authority (exact code)

**Current violations (grep: `Analysis.created_at`):**

| File | Lines (approx.) | Required change |
|------|-----------------|-----------------|
| `backend/app/tasks/analysis.py` | ~98, ~147 | Load analysis by **`analysis_id == UUID(celery_task_id)`** when `celery_task_id` is the canonical task id (`019` pattern: `task_id=str(analysis.id)`). For `inline-{uuid}` / `instant-{uuid}`, parse suffix UUID or pass **`analysis_id` in task kwargs** explicitly. **Never** `order_by(created_at)`. |
| `backend/app/services/analysis_orchestration_service.py` | ~156 | Idempotency guard for QUEUED/RUNNING: use **`version`** + **`status`**, or **`SELECT ... WHERE id = ?`** if keyed by client; if “find in-flight row”, use **`WHERE status IN (QUEUED,RUNNING)`** + **`ORDER BY version DESC LIMIT 1`**. |
| `backend/app/services/shipment_eligibility_service.py` | ~39 | Replace “latest analysis” with **`resolve_display_analysis`** or explicit **`active_analysis_id`** join on items — **no `created_at`**. |
| `backend/scripts/verify_analysis_*.py` | various | Scripts: use **`version DESC`** or **`analysis_id` argument**; document that scripts are not API authority. |

**Invariant after change:** No production code path uses `Analysis.created_at` for **selection** or **ordering** of “which analysis row.” (`created_at` may remain for **audit display** only.)

---

## 5. Stage-level errors + stage status (exact code)

### 5.1 New module

`backend/app/services/analysis_pipeline_stages.py` (or `analysis_stage_registry.py`):

- `PIPELINE_STAGES: tuple[pipelinestagename, ...]` — ordered list of **required** stages for a **full** trust run.
- `async def upsert_stage(db, analysis_id, stage, status, error=...)`
- `async def all_required_stages_succeeded(db, analysis_id) -> bool`

### 5.2 Pipeline orchestration

`backend/app/services/analysis_pipeline.py`:

- At start of `execute_shipment_analysis_pipeline`: insert `PENDING` or `RUNNING` rows for required stages (or lazily per stage).
- Around each major call into `ShipmentAnalysisService`: update stage to `SUCCEEDED` or `FAILED` with error payload.
- On success: set `pipeline_aggregate_status` / mirror JSON.
- On uncaught exception: mark current stage `FAILED`, propagate; `analysis.status = FAILED` as today.

### 5.3 Shipment analysis service

`backend/app/services/shipment_analysis_service.py`:

- Replace **silent** `except Exception` on mandatory paths with: record stage failure → re-raise or return structured error to pipeline — **targeted increment** (file is large); minimum: **classification + regulatory + facts** paths.

---

## 6. Redefining `decision_status = TRUSTED` (exact predicate)

**TRUSTED** is granted **only if all** hold (service-layer; optional DB mirror via aggregate flag):

1. `execution_status == COMPLETE`.
2. **No** business `blockers` (existing list).
3. **No** degraded mode in `result_json.mode` (`INSTANT_DEV`, `FAST_LOCAL_DEV`, any future `*_DEV` — centralize in one helper).
4. `trust_gate_allows_trusted_status(...)` passes **today’s** checks (facts rows, no `critical_pipeline_errors` in JSON).
5. **`all_required_stages_succeeded(analysis_id)`** is **True** (new — reads `analysis_pipeline_stages`).
6. **Required artifacts** for TRUSTED (configurable list), minimum Phase 1 hardening:
   - `shipment_item_classification_facts`: `COUNT(*) >= shipment_item_count` when item count > 0.
   - Regulatory stage: `SUCCEEDED` (or explicitly `SKIPPED` with allowed reason enum — product decision).
   - Review record created: stage `REVIEW_RECORD` = `SUCCEEDED`.

**Implementation:** extend `trust_gate_allows_trusted_status` to accept `db` and call `all_required_stages_succeeded`, **or** fold stage check into a single `compute_trust_eligibility(db, analysis_id, ...)` returning `{trusted: bool, reasons: [...]}`.

**If any condition fails:** `decision_status` ∈ `{REVIEW_REQUIRED, DEGRADED, INSUFFICIENT_DATA}` — **never** TRUSTED.

---

## 7. Promotion / supersession (DB vs service)

| Rule | Enforced by |
|------|-------------|
| ≤1 `is_active` per shipment | **DB** — partial unique index (`019`) |
| Promotion clears other `is_active` in same transaction | **Service** — `promote_analysis_to_active` + transaction boundary in pipeline |
| `supersedes_analysis_id` set on **new** row when `force_new` kills QUEUED/RUNNING | **Service** — orchestration (not yet everywhere): **add** on new `Analysis` row |
| Failed run does not delete prior active without explicit policy | **Service** — `_mark_analysis_failed` must target **specific `analysis_id`** (see §8), not “latest” |

**Optional DB (022):** `CHECK` that `is_active = true` ⇒ `status = COMPLETE` (or product allows ACTIVE+REVIEW states — align before adding).

---

## 8. Retry policy — one pathway, no hybrid

### 8.1 Pathway A — Celery / worker **retry** (same logical job)

**Definition:** Same worker invocation retries after transient failure **without** user clicking “Re-run.”

**Invariant**

- **Same `analysis_id`** for the entire attempt.
- **Idempotent writes:** `INSERT ... ON CONFLICT (analysis_id, stage)` **or** `UPDATE` stage rows; facts `ON CONFLICT DO UPDATE` **or** delete facts for `analysis_id` in transaction before insert (pick one strategy per table).

**Exact code change**

- `run_shipment_analysis` receives `self.request.id`. When `send_task(..., task_id=str(analysis.id))`, **`self.request.id == str(analysis.id)`**.
- **Load analysis:** `select(Analysis).where(Analysis.id == UUID(self.request.id))` — **remove** `order_by(created_at)`.
- `_mark_analysis_failed(shipment_id, ...)` → **`_mark_analysis_failed(analysis_id: UUID, ...)`** — mark **that** row failed.

**Breaking:** Any code assuming “latest by time” for failure marking will break — **intended**.

### 8.2 Pathway B — User-triggered **rerun** (`force_new` or new analyze after terminal)

**Invariant**

- **New `Analysis` row** (`version = next`), optional `supersedes_analysis_id` pointing to prior run.
- Old row: `FAILED` or left terminal; **promotion** moves to new row only when pipeline completes and promotion rules pass.

**Exact code:** already partially in `AnalysisOrchestrationService` for `force_new` — ensure **every** new run gets a new row and **never** reuses QUEUED row for a different logical rerun without clearing state.

### 8.3 Forbidden hybrid

- Worker retry **must not** create a second QUEUED row for the same user intent.
- User rerun **must not** mutate the previous `analysis_id` row’s `result_json` in place.

---

## 9. Transitional shims to **delete** after this increment

| Shim | Location | Action |
|------|----------|--------|
| `ORDER BY created_at` for `Analysis` | `tasks/analysis.py`, orchestration, eligibility | **Remove** — replaced by id + version |
| Trust based partly on `result_json.get("critical_pipeline_errors")` alone | `trust_gate_allows_trusted_status` | **Tighten** — primary source = **`analysis_pipeline_stages`** failures |
| Duplicate “terminal fallback” without active | `resolve_display_analysis` step 4 | Re-evaluate: if **production** requires active for COMPLETE, enforce via migration + promotion; else document **version-only** display as **non-authoritative** |

---

## 10. Breaking changes (explicit)

| Change | Impact |
|--------|--------|
| Celery task loads by `analysis_id` only | Misconfigured task ids (not equal to `analysis.id`) **fail fast** — verify `send_task(task_id=str(analysis.id))` everywhere |
| `_mark_analysis_failed` signature | All callers must pass **`analysis_id`** |
| Stricter TRUSTED | More runs end as **REVIEW_REQUIRED** until stages are wired — **UX/copy** may need updates |
| Stage table + unique (analysis_id, stage) | Retry mid-stage must use **upsert**, not blind insert |
| Optional `review_records.analysis_id` UNIQUE | Duplicate review inserts **fail** — fix tests |

---

## 11. Invariant matrix: DB-enforced vs service-enforced

| Invariant | DB | Service |
|-----------|----|---------|
| One active analysis per shipment | ✅ Partial unique index (`019`) | Clear siblings before set active |
| One stage row per (analysis, stage name) | ✅ `UNIQUE(analysis_id, stage)` | Upsert on retry |
| TRUSTED implies stages + artifacts | ⚪ Optional CHECK/trigger (`022`) | ✅ `trust_gate` + `derive_decision_status` |
| No `created_at` selection | ❌ | ✅ Code review / lint rule |
| Celery retry = same `analysis_id` | ❌ | ✅ Task loader + idempotent writes |
| User rerun = new version | ❌ | ✅ Orchestration |
| Immutable completed superseded snapshot | ⚪ Optional trigger | ✅ Document + no updates in app paths |

---

## 12. Suggested implementation order (engineering)

**Resolution contract:** Display vs authoritative analysis is documented in
`docs/PHASE1_RESOLUTION_CONTRACT.md` (`resolve_display_analysis` is not equivalent to
`resolve_authoritative_analysis`).

**Order inside remaining Phase 1 (recommended):**

1. **Stage ledger + typed errors** — and eliminate silent `except` on mandatory stages (highest risk).
2. **Retry semantics** — same `analysis_id` + upserts; user rerun = new version (operationally closed).
3. **Canonical regulatory** (DB-first, `analysis_id`-scoped).
4. **Canonical duty**.
5. **Reasoning / provenance / review** — derive projections; JSON not authoritative.

**Engineering checklist for the same increment:**

1. Land **`020`** + SQLAlchemy models for `AnalysisPipelineStage`.
2. Fix **`tasks/analysis.py`** and **`_mark_analysis_failed`** to use **`analysis_id`** (Pathway A).
3. Wire **stage upserts** in `execute_shipment_analysis_pipeline` + narrow silent `except` in critical subpaths.
4. Extend **`trust_gate`** + **`derive_decision_status`** to require **stage success**.
5. Replace **`shipment_eligibility_service`** and **orchestration** `created_at` queries.
6. Add **integration tests:** Celery retry double-invoke does not duplicate stage rows / facts; `force_new` creates new `analysis_id`.

---

## 13. Files expected to change (checklist)

- `backend/alembic/versions/020_*.py`, `021_*.py` (and optional `022_*.py`)
- `backend/app/models/analysis.py` (+ new `analysis_pipeline_stage.py`)
- `backend/app/services/analysis_pipeline.py`
- `backend/app/services/analysis_identity_service.py` (`trust_gate`, `derive_decision_status`)
- `backend/app/tasks/analysis.py`
- `backend/app/services/analysis_orchestration_service.py`
- `backend/app/services/shipment_eligibility_service.py`
- `backend/app/services/shipment_analysis_service.py` (exceptions + stage hooks)
- `backend/tests/test_analysis_pipeline_stages.py` (new), extend `test_analysis_identity.py`

This document is the contract for the **next** increment; update it when migrations are renamed or scope is split across PRs.

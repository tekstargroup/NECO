# Phase 1 — Stage truth & trust increment (implemented)

## DB

- **`020_analysis_pipeline_stages`**: one row per **`(analysis_id, stage)`** (unique constraint).
- **`021_review_records_analysis_id`**: optional **`review_records.analysis_id`** → **`analyses.id`**, unique when set (idempotent review + regulatory replace on same-analysis retry).
- Enum **`pipelinestagestatus`**: `PENDING`, `RUNNING`, `SUCCEEDED`, `FAILED`, `SKIPPED`.
- Stage ids are **strings** (see `PipelineStageName` in `app/models/analysis_pipeline_stage.py`).

## Mandatory vs optional (TRUSTED)

| Stage | Mandatory for TRUSTED | Notes |
|-------|----------------------|--------|
| `DOCUMENT_EVIDENCE` | Yes | Document parse / evidence map in `run_full_shipment_analysis`. |
| `LINE_ITEM_IMPORT` | Yes | Entry summary / CI line import; raises on failure. |
| `CLASSIFICATION` | Yes | Per-item classification engine + rule bias; `classification_results` only (no facts DB write). |
| `FACT_PERSIST` | Yes | Per-item `ShipmentItemClassificationFacts` upsert from classification output. |
| `REGULATORY_ENGINE` | Yes | Regulatory applicability evaluation; raises on failure. |
| `REVIEW_REGULATORY_PERSIST` | Yes | `ReviewRecord` (by `analysis_id`) + regulatory rows in `analysis_pipeline.py`. |
| `DUTY_PSC_ADVISORY` | **No** (tracked) | Ledger shows whether any item duty/PSC JSON has `"error"`; does not block TRUSTED. |
| Product knowledge lookup | **No** | Failures recorded in `prior_knowledge_lookup_errors` (no silent pass). |

Legacy ledger value **`CORE_ANALYSIS`** may exist on old rows; new runs use the fine-grained stages above.

See **`docs/PHASE1_TRUSTED_SEMANTICS.md`** for the full TRUSTED / non-TRUSTED boundary and **`result_json.trust_contract`**.

## Failure → execution / decision mapping

| Situation | `analysis.status` | `decision_status` (if COMPLETE) |
|-----------|-------------------|----------------------------------|
| Exception in a mandatory stage inside `run_full_shipment_analysis` | **FAILED** (task handler) | n/a |
| Exception in `REVIEW_REGULATORY_PERSIST` | **FAILED** | n/a |
| Success path, blockers present | **COMPLETE** | `REVIEW_REQUIRED` |
| Success path, trust gate fails (including **any** mandatory stage not `SUCCEEDED`) | **COMPLETE** | `REVIEW_REQUIRED` (not `TRUSTED`) |
| Full success + trust gate | **COMPLETE** | `TRUSTED` (if not degraded mode) |

## Worker retries

- Celery **`task_id`** = **`str(analysis.id)`** — loads **`Analysis.id`** directly (no `created_at`).
- Classification **facts** — **`INSERT ... ON CONFLICT DO UPDATE`** on `uq_classification_facts_analysis_item`.
- **Review + regulatory** — same `ReviewRecord` for `analysis_id` when present; regulatory children deleted and reinserted from latest snapshot.

## Breaking changes (historical)

- Line item import / classification / regulatory failures: **raise** (no silent soft placeholders for those mandatory paths).
- **`TRUSTED`** requires **`analysis_pipeline_stages`** rows for **all** mandatory stages — run **`alembic upgrade head`** through **`021`**.

## Tests

- `tests/test_pipeline_stages.py` — mandatory stage list + task id parsing.

## Remaining (later phases)

- Canonical DB persistence for reasoning traces, duty summaries, and full provenance contract.
- Optional: promote duty/PSC into mandatory stages when the product promises them as authoritative.

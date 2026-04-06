# Phase 1 — `decision_status=TRUSTED` semantics

This document fixes the **meaning** of `TRUSTED` for the current Phase 1 hardening slice. It applies to API payloads that include `result_json.trust_contract` (see `build_trust_contract_metadata()` in `app/services/pipeline_stage_service.py`, version `phase1_v4` and `stage_ledger_schema_version`). Integrations should use `app.services.trust_contract_consumer` for per-artifact checks.

## What TRUSTED means (mandatory slice)

`TRUSTED` is assigned only when **all** of the following hold:

1. **Execution:** `Analysis.status == COMPLETE`, no review blockers, no `critical_pipeline_errors` in `result_json`, and not a dev-degraded mode (`INSTANT_DEV` / `FAST_LOCAL_DEV` fail the trust gate).
2. **Classification facts:** one `ShipmentItemClassificationFacts` row per line item for this `analysis_id` (worker retries use upsert on that table).
3. **Mandatory pipeline stages** (rows in `analysis_pipeline_stages`) are all `SUCCEEDED`:
   - `DOCUMENT_EVIDENCE`
   - `LINE_ITEM_IMPORT`
   - `CLASSIFICATION` (engine output, before facts DB)
   - `FACT_PERSIST` (classification facts upsert per line)
   - `REGULATORY_ENGINE`
   - `REVIEW_REGULATORY_PERSIST`

So TRUSTED means: **document handling and line import completed, classification succeeded, facts rows persisted, regulatory evaluation ran, and the review snapshot + regulatory rows for this analysis were persisted successfully.**

Legacy ledger value **`CLASSIFICATION_AND_FACTS`** may exist on old runs; new runs use **`CLASSIFICATION`** + **`FACT_PERSIST`**. See `docs/PHASE1_CLOSEOUT.md`.

## What TRUSTED does **not** imply

Unless separately stage-tracked and added to the mandatory list, TRUSTED does **not** guarantee:

- Correct or complete **duty** resolution (per-item duty may contain `"error"` in JSON).
- Successful **PSC** analysis.
- **Product knowledge** lookups or suggestions (failures appear in `prior_knowledge_lookup_errors`).
- **Provenance** completeness for every line or document.
- **Reasoning trace** persistence to a canonical DB table (`heading_reasoning_trace` is JSON on the analysis payload only in this phase).
- Absence of advisory-stage failures (e.g. `DUTY_PSC_ADVISORY` may be `FAILED` while TRUSTED remains possible).

Those outputs remain **advisory** or **best-effort** unless the product promotes them into mandatory stages later.

## Advisory stages (tracked, non-blocking)

- **`DUTY_PSC_ADVISORY`:** Ledger reflects whether any item’s duty or PSC payload contains an `"error"` key. Failure here is visible in `analysis_pipeline_stages` but does **not** block TRUSTED.

## Same-analysis retry / idempotency (Phase 1)

| Artifact | Behavior |
|----------|----------|
| `ShipmentItemClassificationFacts` | Upsert on `(analysis_id, shipment_item_id)` |
| `ReviewRecord` | One row per `analysis_id` (unique); snapshot replaced on retry |
| `RegulatoryEvaluation` / `RegulatoryCondition` | Deleted and reinserted from latest snapshot for that review |
| `Analysis.result_json` | Replaced on successful complete commit |

Still **not** fully canonical / retry-specified for: duty DB rows, reasoning trace DB, PSC DB, and other optional engines.

## User-facing guidance

Surfaces that show duty, PSC, or product-knowledge hints must treat them as **advisory** unless the trust contract version bumps and mandatory stages explicitly cover them. Use `result_json.trust_contract` for the machine-readable boundary.

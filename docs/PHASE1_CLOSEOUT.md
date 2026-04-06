# Phase 1 — Closeout slice (classification vs facts, artifact matrix, surfaces)

This document defines what was implemented in the **closeout** increment and what remains **Phase 1 blockers** vs **safe to defer to Phase 2**.

## Stage split: `CLASSIFICATION` vs `FACT_PERSIST`

Replaces the former single combined stage `CLASSIFICATION_AND_FACTS` (legacy string may still appear on old ledger rows).

| Stage | Ordinal | Meaning |
|-------|---------|--------|
| `CLASSIFICATION` | 30 | Engine + rule bias + `classification_results` (including `CLARIFICATION_REQUIRED` mutation). No DB facts write. |
| `FACT_PERSIST` | 31 | `ShipmentItemClassificationFacts` upsert per line from `_product_analysis_for_classification_facts`. |

Duty/PSC remain **after** both stages, then `DUTY_PSC_ADVISORY` (tracked, non-mandatory for TRUSTED).

## Artifact matrix (authoritative for closeout planning)

The machine-readable copy lives in `result_json.trust_contract.artifact_matrix` (see `build_trust_contract_metadata()` in `app/services/pipeline_stage_service.py`, version `phase1_v3`).

| Artifact | Canonical source | Retry policy | In TRUSTED contract? | Phase 2 if… |
|----------|------------------|--------------|----------------------|-------------|
| Classification output | `result_json.items[].classification` | Recomputed each run | Yes (via `CLASSIFICATION` stage) | — |
| Classification facts DB | `shipment_item_classification_facts` | Upsert per `(analysis_id, item)` | Yes (`FACT_PERSIST`) | — |
| Review + regulatory DB | `review_records` + `regulatory_*` | One review per `analysis_id`; replace regulatory children | Yes | — |
| Duty / PSC JSON | `result_json.items[]` | JSON only; errors allowed | **No** | DB persistence promised |
| Heading reasoning trace | JSON on item | Not persisted as canonical DB row | **No** | Audit-grade trace DB |
| Line provenance | JSON + `shipment_item_line_provenance` | Partial | **No** | Evidence defensibility promise |

## Review record uniqueness (`review_records.analysis_id`)

- **Intent:** At most **one** review row per analysis when `analysis_id` is set (unique constraint).
- **Nullable:** Legacy or unusual paths may still have `analysis_id IS NULL`; pipeline **creates** new rows with `analysis_id=analysis.id` for normal completes.
- **Migration 021** backfills `analysis_id` from `analyses.review_record_id` where possible.
- **Ambiguity:** Rows with null `analysis_id` after backfill are orphaned from the new idempotent path until reconciled — acceptable for Phase 1 if those rows are not on active shipments.

## Surfaces audited for TRUSTED overread (this increment)

| Surface | Change / note |
|---------|----------------|
| `GET .../analysis-status` | Exposes top-level **`trust_contract`** (copy from `result_json`) when present, plus `decision_status` and `result_json`. |
| Analysis tab UI | Trusted banner + import/provenance supporting-evidence note. |
| Grounded chat | Duty/PSC advisory subtitle; answers that cite **routing / document evidence / missing facts** prepend **reasoning & provenance supporting-only** notice. |
| Exports (`export_service`) | Every audit pack / broker prep JSON includes **`trust_contract`**, **`export_advisory_notice`**, **`reasoning_and_provenance_notice`** via `trust_contract_consumer.export_supplement_from_snapshot`. |
| Filing prep service | Module doc states duty resolution is **not** implied by analysis TRUSTED alone. |
| Programmatic API | Use `app.services.trust_contract_consumer` (`artifact_in_trusted_contract`, `classify_artifact_scope`, `get_trust_contract`) for integrations. |

**Required invariant (all consumers):** Do not equate **Trusted** with duty/PSC/reasoning/provenance guarantees; use `trust_contract.consumer_invariant`, `artifact_matrix`, or `trust_contract_consumer`.

## Legacy stage rows (`CLASSIFICATION_AND_FACTS`)

- **Trust gate:** `all_mandatory_stages_succeeded` treats a **SUCCEEDED** `CLASSIFICATION_AND_FACTS` row as satisfying **both** `CLASSIFICATION` and `FACT_PERSIST` for older analyses.
- **Metadata:** `trust_contract.stage_ledger_schema_version`, `deprecated_stage_ids`, `legacy_stage_equivalence` (see `build_trust_contract_metadata()` v `phase1_v4`).
- **DB migration `022`:** backfills `CLASSIFICATION` + `FACT_PERSIST` rows from legacy `CLASSIFICATION_AND_FACTS` **SUCCEEDED** rows so tooling can prefer new stage ids only after upgrade.

## Phase 1 blockers vs defer

**Blockers to call Phase 1 “closed” for *trust honesty* (current codebase target):**

- [x] Fine-grained mandatory stages including split **CLASSIFICATION** / **FACT_PERSIST**
- [x] `trust_contract` with artifact matrix + `consumer_invariant`
- [x] Review/regulatory idempotent persist by `analysis_id`
- [x] At least one UI surface reminding users Trusted ≠ duty/PSC authority

**Safe to defer to Phase 2 (unless product promise changes):**

- Reasoning trace **DB** persistence as canonical audit artifact
- Full **provenance completeness** as a trust gate
- Duty/PSC **DB** canonical rows (if they stay advisory-only, JSON may remain non-blocking indefinitely)
- Export PDF wording / filing bundle disclaimers (product copy)

## Reasoning trace: Phase 1 vs 2

- **Today:** `heading_reasoning_trace` is **JSON on the analysis result** only — not a separate durable audit table.
- **Phase 1 close** for NECO can treat it as **explanatory, not independently auditable** unless you add DB persistence.
- **Move to Phase 2** if reviewers or compliance workflows **formally rely** on trace immutability across retries and years.

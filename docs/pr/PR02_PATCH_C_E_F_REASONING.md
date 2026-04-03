# PR2 — `patch-c-e-f-reasoning` (Patch C + E + F + follow-ups)

**Base:** merge **PR1** first (or `integration/patches-complete` as monolith).

## Scope

- **Patch C:** `select_product_family` / `FamilySelection`, `family_router.py` + `_get_critical_missing` when `CLASSIFICATION_FAMILY_ROUTER_ENABLED`, `product_analysis` UNKNOWN confidence cap, family-specific clarification overrides; **transmitter phrase follow-up** + backlog comment on Ch.90 vs interim `ELECTRONICS`.
- **Patch E:** `build_heading_reasoning_trace`, attached per item in full + fast paths.
- **Patch E follow-up:** Pass `None` into `build_heading_reasoning_trace` when `suppress_alternatives` so trace aligns with hidden `classification`; early exit still attaches `evidence_used` / `line_provenance`.
- **Patch F:** `grounded_classification_chat_service` + `POST .../grounded-chat`.
- **Patch F follow-up:** Empty `rejected_alternatives` → `refusal: true`; optional `scope: shipment_not_line` on shipment-level doc citation.

## Exact files

| Area | Paths |
|------|--------|
| Classification | `backend/app/engines/classification/required_attributes.py`, `backend/app/engines/classification/family_router.py`, `backend/app/engines/classification/product_analysis.py`, `backend/app/engines/classification/chapter_clusters.py`, `backend/app/engines/classification/attribute_maps.py`, `backend/app/engines/classification/review_explanation.py` (if C-related) |
| Trace | `backend/app/engines/classification/heading_reasoning_trace.py` |
| Chat | `backend/app/services/grounded_classification_chat_service.py` |
| Orchestration | `backend/app/services/shipment_analysis_service.py` (C/E trace + fast path + suppress), `backend/app/services/analysis_pipeline.py` |
| API | `backend/app/api/v1/shipments.py` (grounded-chat route) |
| Config | `backend/app/core/config.py` (`CLASSIFICATION_FAMILY_ROUTER_*`) |
| Frontend | `frontend/src/components/grounded-chat-bar.tsx`, `frontend/src/components/shipment-tabs/analysis-tab.tsx` (GroundedChatBar) |
| Tests | `backend/tests/test_product_family_router.py`, `backend/tests/test_family_router.py`, `backend/tests/test_product_analysis_unknown_confidence.py`, `backend/tests/test_heading_reasoning_trace.py`, `backend/tests/test_grounded_classification_chat.py` |

## Migration steps

None beyond PR1 (no new Alembic in typical C/E/F).

## Flags

| Flag | Default | Purpose |
|------|---------|---------|
| `CLASSIFICATION_FAMILY_ROUTER_ENABLED` | `false` | Use `family_router.critical_missing_for_family` in `_get_critical_missing` |

## Tests to run

```bash
cd backend
python3 -m pytest tests/test_product_family_router.py tests/test_family_router.py \
  tests/test_product_analysis_unknown_confidence.py tests/test_heading_reasoning_trace.py \
  tests/test_grounded_classification_chat.py -v --tb=short
```

Frontend: smoke analysis tab + grounded chat bar if enabled.

## Known limitations

- **Patch C:** Family routing is heuristic; **interim** `ELECTRONICS` for industrial instruments — not a final Ch.85/Ch.90 legal model.
- **Patch E:** Trace withheld entirely when suppress + `classification=None` (aligned); tariff `provenance` not in trace when `classification_result` is `None`.
- **Patch F:** Intent detection is keyword-based; edge phrasing may hit `unsupported`.

## Rollback

Revert PR2 commit(s). No DB migration rollback. Restore previous `required_attributes` / trace / chat behavior.

## Confirmation package

| Check | Expect |
|-------|--------|
| `select_product_family("industrial pressure transmitter …")` | `ELECTRONICS`, `rule_industrial_sensor` |
| `suppress_alternatives` true | `heading_candidates` empty in trace, `classification` null |
| Grounded chat “rejected” with empty list | `refusal: true` |
| API | `POST /shipments/{id}/grounded-chat` returns citations / refusal |

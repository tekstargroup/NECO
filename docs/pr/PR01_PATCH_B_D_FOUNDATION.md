# PR1 — `patch-b-d-foundation` (Patch B + Patch D + follow-ups)

## Scope

- **Patch B:** Authoritative line provenance (CI/ES), optional provenance on selection/manual flows, AUTO item–document links.
- **Patch B follow-up:** `import_summary.provenance_skipped` on HTS conflict + `logger.warning`; UI surfacing on analysis tab.
- **Patch D:** Persisted `ShipmentItemClassificationFacts` per `(analysis_id, shipment_item_id)`, `build_classification_facts_payload`, wiring in full + fast analysis paths.
- **Patch D follow-up:** Doc comments on facts cardinality / `analysis_id` retry behavior (`analysis_pipeline` + model).

## Exact files (from integration branch; `shipment_analysis_service.py` is shared)

| Area | Paths |
|------|--------|
| Migrations | `backend/alembic/versions/016_shipment_item_line_provenance.py`, `backend/alembic/versions/017_shipment_item_classification_facts.py` |
| Models | `backend/app/models/shipment_item_line_provenance.py`, `backend/app/models/shipment_item_classification_facts.py`, `backend/app/models/analysis.py`, `backend/app/models/shipment.py`, `backend/app/models/__init__.py`, `backend/app/models/shipment_document.py` (if touched) |
| Services | `backend/app/services/shipment_item_provenance_service.py`, `backend/app/services/shipment_analysis_service.py` (B+D portions + facts persist + import merge + `provenance_skipped` + `_auto_link_*`), `backend/app/services/analysis_pipeline.py` |
| Engine payload | `backend/app/engines/classification/classification_facts.py` |
| API | `backend/app/api/v1/shipments.py` (provenance-related endpoints; split from grounded-chat if needed) |
| Config | `backend/app/core/config.py` (provenance flags) |
| Env | `backend/.env.example` |
| Frontend | `frontend/src/components/shipment-tabs/analysis-tab.tsx` (`import_summary` + `provenance_skipped` UI), optionally `documents-tab.tsx` |
| Tests | Any backend tests tied only to provenance/facts if present |

## Migration steps

```bash
cd backend
alembic upgrade 016_line_provenance   # revision id from 016 file
alembic upgrade 017_classification_facts
```

Order: **016 before 017** (017 may depend on analyses/shipments already present).

## Flags

| Flag | Default | Purpose |
|------|---------|---------|
| `PROVENANCE_ON_SELECTION_LINE_ITEMS` | typically `true` | Provenance when creating line items from table selection |
| `PROVENANCE_ON_MANUAL_ITEM_PROVENANCE` | env-specific | Manual item provenance API path |

See `backend/.env.example`.

## Tests to run

```bash
cd backend
python3 -m pytest tests/ -q -k "provenance or classification_facts or audit" --tb=no 2>/dev/null || true
# Broad:
python3 -m pytest backend/tests/test_audit_pack_service.py backend/tests/test_review_service.py -q --tb=short
```

Add/adjust targeted tests when B/D-only test files exist.

## Known limitations

- **HTS conflict** lines skip merge → no structured provenance row; surfaced via `provenance_skipped` + UI.
- **Facts** unique on `(analysis_id, shipment_item_id)` — retry same `analysis_id` without delete → DB error (documented in model/pipeline comments).
- **Monolithic service file:** other patches may touch the same file; merge conflicts possible if splitting PRs manually.

## Rollback

```bash
alembic downgrade -1  # repeat to before 016 if needed; confirm revision chain
```

Revert PR commit on `main`. Drop `shipment_item_line_provenance` / `shipment_item_classification_facts` tables only after downgrade (or restore from backup).

## Confirmation package

| Check | Expect |
|-------|--------|
| Migrations apply cleanly on empty DB | 016 → 017 |
| `import_summary` | includes `provenance_skipped: []` or populated on conflict |
| `result_json.items[].classification_facts` | present when analysis ran with facts layer |
| UI | Import banner shows conflicts + provenance-skipped details when non-empty |

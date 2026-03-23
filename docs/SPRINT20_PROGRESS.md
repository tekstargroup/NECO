# Sprint 20: Compliance Signal Engine — Progress Log

**Sprint:** 20 (Post-MVP)  
**Status:** In progress — not complete  
**Last updated:** March 18, 2026

**Sprint timeline note:** Only Sprint 13 is currently running (separate agent). Sprints 14–19 are not yet executed. This doc covers Sprint 20 only.

---

## Sprint 20 Goal (from roadmap)

> NECO ingests external signals (CBP, Federal Register, USTR, CROSS), classifies/scores, produces PSC Radar alerts.

**Success definition:** (1) Poller ingests Tier 1 sources; (2) Pipeline: raw → normalized → classified → scored; (3) psc_alerts table populated; (4) PSC Radar UI shows alerts.

---

## What’s Been Done (So Far)

### Phase 1: Base Pipeline (Sprint 20 core)

| Item | Status | Notes |
|------|--------|------|
| Database schema (migration 011) | Done | raw_signals, normalized_signals, signal_classifications, signal_scores, psc_alerts, importer_hts_usage |
| Sources config | Done | 25 sources across Tiers 1–6 |
| Feed poller | Done | RSS, API, scrape handlers for all source types |
| Classification engine | Done | LLM + rules hybrid |
| Scoring service | Done | Weighted formula (HTS, country, history, financial) |
| PSC alert service | Done | Creates alerts when score > 70 |
| Celery tasks | Done | poll_regulatory_feeds, process_regulatory_signals |
| APIs | Done | GET/POST regulatory-updates, GET/PATCH psc-radar/alerts |
| PSC Radar UI | Done | /app/psc-radar page, nav link |
| **Signal Health dashboard** | Done | /app/signal-health — manager visibility on feeds, pipeline, alerts |
| Importer HTS usage | Done | Service + daily refresh task |

### Phase 2: All Tiers (1–8)

| Tier | Sources | Status |
|------|---------|--------|
| 1 | CBP CSMS, ACE, Duty, Legal, Federal Register, USITC HTS, USTR, CBP CROSS | Done |
| 2 | OFAC, FDA, USDA, BIS, ITA AD/CVD | Done |
| 3 | WTO, EU TAXUD, WCO | Done |
| 4 | White House, Congress | Done |
| 5 | CBP Quota, UBR | Done |
| 6 | FreightWaves, JOC, SupplyChainDive, Flexport | Done |
| 7 | CBP CROSS vectorization | Pending |
| 8 | Importer HTS usage (internal) | Done |

### Phase 3: GAPs 1–10 (from COMPLIANCE_SIGNAL_ENGINE_GAPS.md)

| GAP | Description | Status |
|-----|-------------|--------|
| 1 | Quota Intelligence Engine | Done — quota_status table, fill rate, QUOTA_RISK alerts |
| 2 | Tariff → HTS Mapping Engine | Done — duty delta, shipment linkage |
| 3 | FDA / Admissibility Engine | Done — import_restrictions table, FDA_RISK alerts |
| 4 | CBP CROSS Rulings | Done — cbp_rulings table, ingestion |
| 5 | Real-Time Signal Engine | Done — per-source Celery schedules (5m/15m/1h/6h/1d) |
| 6 | HTS-Centric Filtering | Done — suppress signals without HTS |
| 7 | Importer-Aware Mapping | Done — signal → shipment matching |
| 8 | Financial Impact Layer | Done — duty_delta_estimate on alerts |
| 9 | Final Output Structure | Done — shipment_id, confidence_score, signal_source, priority |
| 10 | Shipment Detail Integration | Done — PSC alerts per shipment, API filter |

### Phase 4: Database (migration 012)

| Table / Change | Status |
|----------------|--------|
| quota_status | Done |
| import_restrictions | Done |
| cbp_rulings | Done |
| product_hts_map | Done |
| normalized_signals: duty_rate_change, affected_hts_codes, quota_limit, quota_used, old_duty_rate, new_duty_rate | Done |
| psc_alerts: confidence_score, priority, signal_source | Done |

### Phase 5: Pinned Priorities (Addressed)

| Priority | Status |
|----------|--------|
| Link PSC alerts to shipments | Done |
| Verify CBP CROSS | Partial — ingestion in place; validate if raw_signals populated |
| Add per-source scheduling | Done |
| Compute duty delta | Done |
| Add product_hts_map | Done |
| Shipment detail integration | Done |

---

## Remaining / Not Done

| Item | Notes |
|------|------|
| **Source validation** | Many sources return empty. See [SPRINT20_SOURCE_SETUP_GUIDE.md](SPRINT20_SOURCE_SETUP_GUIDE.md) for API keys, URL fixes, research tasks. |
| **CBP CROSS validation** | Confirm CBP_CROSS raw_signals populate; if empty, fix scraper |
| **CBP CROSS vectorization** | Tier 7 — vectorize rulings, map to HTS suggestions |
| **GAP 10 success criteria** | End-to-end: tariff change → mapped → shipment → impact; quota fill → alert; FDA alert → product flag; CBP ruling → reclassification |
| **Manual acceptance** | Full path: poll → process → PSC Radar alerts visible |
| **Sprint 20 mark complete** | Per roadmap: (1) Poller ingests Tier 1; (2) Pipeline works; (3) psc_alerts populated; (4) PSC Radar UI shows alerts |

---

## Files Touched (Sprint 20)

### Backend
- `alembic/versions/011_compliance_signal_engine.py`
- `alembic/versions/012_compliance_signal_engine_gaps.py`
- `config/sources_config.json`
- `app/core/sources_config.py`
- `app/core/celery_app.py`
- `app/core/config.py`
- `app/models/` — raw_signal, normalized_signal, signal_classification, signal_score, psc_alert, importer_hts_usage, quota_status, import_restriction, cbp_ruling, product_hts_map
- `app/services/regulatory_feed_poller.py`
- `app/services/psc_alert_service.py`
- `app/services/importer_hts_usage_service.py`
- `app/services/signal_scoring_service.py`
- `app/engines/signal_classification.py`
- `app/tasks/regulatory.py`
- `app/api/v1/regulatory.py`
- `app/api/v1/psc_radar.py`

### Frontend
- `frontend/src/app/app/psc-radar/page.tsx`
- `frontend/src/app/app/signal-health/page.tsx`
- `frontend/src/components/shipment-tabs/analysis-tab.tsx`
- `frontend/src/components/app-shell.tsx`

### Docs
- `docs/COMPLIANCE_SIGNAL_ENGINE.md`
- `docs/COMPLIANCE_SIGNAL_ENGINE_STATUS.md`
- `docs/COMPLIANCE_SIGNAL_ENGINE_GAPS.md` (created, then executed)

---

## How to Run

```bash
cd /Users/stevenbigio/Cursor\ Projects/NECO
./scripts/start_mvp_all.sh
```

Or manually: Docker, backend, frontend, Celery worker, Celery beat. See [MVP_RUN_GUIDE.md](MVP_RUN_GUIDE.md).

---

## Related

- [SPRINT_ROADMAP_LOCKED.md](SPRINT_ROADMAP_LOCKED.md) — Sprint 20 definition
- [COMPLIANCE_SIGNAL_ENGINE_STATUS.md](COMPLIANCE_SIGNAL_ENGINE_STATUS.md) — Execution guide
- [COMPLIANCE_SIGNAL_ENGINE_GAPS.md](COMPLIANCE_SIGNAL_ENGINE_GAPS.md) — GAPs backlog (executed)

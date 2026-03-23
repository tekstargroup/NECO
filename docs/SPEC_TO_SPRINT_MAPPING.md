# Spec-to-Sprint Mapping: Money + Risk + Decision System

**Purpose:** Map the "Transform NECO from signal+alerts → money+risk+decision" spec to Sprints 13–19 (not yet implemented) vs Sprint 20 (current).

**Last updated:** March 17, 2026

---

## TL;DR

| Spec Section | Sprints 13–19 | Sprint 20 (Current) |
|--------------|---------------|---------------------|
| **0. Objective** | — | Full (money + risk + decision) — all in Sprint 20 |
| **1. Core concept** (Shipment, Product, Portfolio) | Shipment only | Shipment + Product + Portfolio |
| **2. Product Intelligence Engine** | — | **Sprint 20** (to do) |
| **3. Importer Portfolio Intelligence** | — | **Sprint 20** (to do) |
| **4. HTS Intelligence Layer** | — | **Sprint 20** (to do) |
| **5. Rulings Intelligence Engine** | — | Partial → full in Sprint 20 |
| **6. Quota Forecasting Engine** | — | Partial → full in Sprint 20 |
| **7. Financial Intelligence Layer** | — | Partial → full in Sprint 20 |
| **8. Human-readable explanations** | Optional (Sprint 13) | Sprint 20 (to do) |
| **9. Prioritization Engine** | — | Partial → full in Sprint 20 |
| **10. UI requirements** | — | PSC Radar, Signal Health done; Product/HTS/Portfolio to do |
| **11. Success criteria** | — | Full in Sprint 20 |

---

## Sprints 13–19 (Not Yet Implemented)

**Current roadmap scope** — these sprints are already defined and do **not** include the spec’s Product/Portfolio/HTS layers:

| Sprint | Roadmap Scope | Spec Overlap |
|--------|---------------|--------------|
| **13** | Analysis view polish, 8 sections, loading/error states | Section 8 (explanations) could improve analysis copy — optional |
| **14** | Upload + Export | None |
| **15** | Review UI (Accept/Reject/Override) | None |
| **16** | MVP hardening, edge states, language | None |
| **17** | User preferences (PSC threshold, COO/Duty/HS toggles) | None |
| **18** | Bulk import (zip → shipments) | None |
| **19** | Duty accuracy + Section 301 overlay | Section 7 (financial) — 19 focuses on duty correctness, not cumulative impact |

**Recommendation:** Keep Sprints 13–19 as defined. The spec’s Product/Portfolio/HTS/Financial layers are **not** part of 13–19; they belong in Sprint 20/21.

### Can any Sprint 21+ items fit into Sprints 13–19?

| Spec item | Could fit in | Rationale |
|-----------|--------------|-----------|
| **Section 8 (Human-readable explanations)** | Sprint 13 | Analysis polish includes “clear copy”; improving alert/analysis explanations aligns with “outcome clarity” |
| **Section 7 (Financial: historical + annualized)** | Sprint 19 | Duty + Section 301 already touches duty resolution; adding `historical_impact` / `projected_annual_impact` is a natural extension when duty data is current |
| **Portfolio summary (lightweight)** | Sprint 16 | MVP hardening could add a simple “exec summary” card: total imports, total duties from existing `ShipmentItem` data — no new tables, just aggregate |
| **Product/HTS/Portfolio full layers** | No | Require new tables (`product_intelligence`, `importer_intelligence`, `hts_intelligence`) and aggregation jobs; too large for 13–19’s focused scope |

**Optimization suggestions:**
- **Sprint 13:** Add “structured explanations” (what changed, why it matters) to analysis output.
- **Sprint 16:** Add lightweight “Portfolio summary” (total value, duties) if time permits.
- **Sprint 19:** Add `historical_impact` / `projected_annual_impact` to duty-related signals when Section 301 is integrated.

---

## Sprint 20 (Current — Compliance Signal Engine)

**What Sprint 20 is:** Ingest external signals → classify → score → PSC Radar alerts.

**What we’ve built (Sprint 20):**

| Spec Section | Sprint 20 Status |
|--------------|------------------|
| **5. Rulings** | Partial — CBP CROSS ingestion, `cbp_rulings` table, `product_hts_map`. Missing: match by keyword similarity, score relevance, attach to alerts, influence HTS suggestions (Tier 7 vectorization) |
| **6. Quota** | Partial — `quota_status`, fill rate, QUOTA_RISK when fill > 90%. Missing: velocity, `days_to_fill` forecast, “Quota likely filled in X days” alert |
| **7. Financial** | Partial — `duty_delta_estimate` on alerts. Missing: historical_impact (30/60/90d), projected_annual_impact |
| **8. Explanations** | Partial — alert text exists. Missing: structured “what changed / why it matters / why it applies to this importer” |
| **9. Prioritization** | Partial — `priority`, thresholds. Missing: sort by financial impact, confidence, urgency |
| **10. UI** | PSC Radar page, shipment Analysis tab alerts. Missing: Product page, HTS page, Portfolio dashboard |

**Sprint 20 full scope (all spec items to be executed in Sprint 20):**

| Spec Section | Sprint 20 Scope | Status |
|--------------|-----------------|--------|
| **2. Product Intelligence Engine** | `product_intelligence` table, aggregate by product, consistency score, estimated_duty_savings, product-level alerts | To do |
| **3. Importer Portfolio Intelligence** | `importer_intelligence` table, total value/duties/savings, top risks, exposure metrics | To do |
| **4. HTS Intelligence Layer** | `hts_intelligence` table, aggregate by HTS, rank by savings/risk/usage | To do |
| **5. Rulings (full)** | Match rulings to product/HTS, score relevance, attach to alerts, influence HTS suggestions (Tier 7) | Partial |
| **6. Quota (full)** | Velocity, `days_to_fill`, “filled in X days” alert | Partial |
| **7. Financial (full)** | `historical_impact`, `projected_annual_impact` on signals/alerts | Partial |
| **8. Explanations** | Structured “what / why / why you” for each alert | Partial |
| **9. Prioritization** | Sort by financial impact, confidence, urgency | Partial |
| **10. UI** | Product Intelligence page, HTS Intelligence page, Portfolio dashboard, **Signal Health dashboard** | PSC Radar done; Signal Health done; Product/HTS/Portfolio to do |

**Sprint 20 remainder (to execute):**

1. CBP CROSS validation (confirm raw_signals populate)
2. Tier 7: CBP CROSS vectorization → match rulings to HTS, attach to alerts
3. Quota: add velocity + `days_to_fill` forecast (Section 6)
4. Explanations: structured “what / why / why you” (Section 8)
5. Prioritization: sort by financial impact (Section 9)
6. **Product Intelligence Engine** (Section 2): table, aggregation, product-level alerts
7. **Importer Portfolio Intelligence** (Section 3): table, aggregation, exposure metrics
8. **HTS Intelligence Layer** (Section 4): table, aggregation, ranking
9. **Financial (full)** (Section 7): historical_impact, projected_annual_impact
10. **UI** (Section 10): Product page, HTS page, Portfolio dashboard
11. Manual acceptance: full path works

---

## Sprint 21+ (Post–Sprint 20)

Any remaining enhancements after Sprint 20 closes. Sprint 20 now includes the full spec scope above.

---

## Summary: What Goes Where

| Item | Sprint 13–19 | Sprint 20 |
|------|--------------|----------|
| Analysis polish, Upload, Review, Bulk import, Duty+301, Preferences | ✅ | |
| Signal ingestion, classification, scoring | | ✅ |
| PSC Radar, shipment alerts, **Signal Health dashboard** | | ✅ |
| Quota (fill rate, basic alerts) | | ✅ |
| Tariff mapping, duty_delta | | ✅ |
| FDA, CBP CROSS ingestion | | ✅ |
| product_hts_map | | ✅ |
| CBP CROSS vectorization, rulings matching | | In progress |
| Quota velocity, days_to_fill | | To do |
| Financial: historical + annualized | | To do |
| product_intelligence table | | To do |
| importer_intelligence table | | To do |
| hts_intelligence table | | To do |
| Product Intelligence page | | To do |
| HTS Intelligence page | | To do |
| Portfolio dashboard | | To do |

---

## How to Triple-Check Compliance Is Working

### 1. Signal pipeline health

| Check | How |
|-------|-----|
| Feeds polled | `raw_signals` has recent rows; `source` in (CBP_CSMS, FEDERAL_REGISTER, etc.) |
| Signals processed | `normalized_signals` and `signal_classifications` populated |
| Alerts created | `psc_alerts` has rows with `final_score > 70` |
| Importer HTS usage | `importer_hts_usage` has rows for org’s HTS codes |

```sql
SELECT source, COUNT(*), MAX(created_at) FROM raw_signals GROUP BY source;
SELECT COUNT(*) FROM psc_alerts WHERE created_at > NOW() - INTERVAL '7 days';
```

### 2. End-to-end validation

| Step | Action |
|------|--------|
| 1 | `POST /api/v1/regulatory-updates/refresh-hts-usage` |
| 2 | `POST /api/v1/regulatory-updates/process?limit=100` |
| 3 | Open `/app/psc-radar` — see alerts |
| 4 | Open a shipment with matching HTS → Analysis tab shows PSC alerts |
| 5 | Re-run shipment analysis → alerts still linked |

### 3. Coverage metrics

| Metric | Target | How to measure |
|--------|--------|----------------|
| Sources with data | ≥ 5 of Tier 1 | Count distinct `source` in `raw_signals` |
| Alerts per org | > 0 when HTS usage exists | `SELECT COUNT(*) FROM psc_alerts WHERE org_id = ?` |
| Shipment–alert linkage | Alerts show on shipment detail | UI: shipment Analysis tab |
| Quota alerts | When fill > 90% | `psc_alerts` with `alert_type = 'QUOTA_RISK'` |
| Duty delta | On tariff-change alerts | `psc_alerts.duty_delta_estimate` not null |

### 4. Regression tests (optional)

- Unit: classification output shape, scoring formula
- Integration: poll → normalize → classify → score → alert
- E2E: refresh HTS → process → PSC Radar shows alerts

### 5. Signal Health dashboard (manager visibility)

**Location:** `/app/signal-health`

The Signal Health dashboard provides manager visibility on:

- **Overall status:** ok / warning / critical
- **Per-source status:** Each RSS/API/scrape feed shows count, last ingested, status (ok / stale / no_data)
- **Pipeline totals:** Raw signals, normalized signals, alerts (24h, 7d)
- **Celery schedule:** What Celery Beat is supposed to run (poll 5m/15m/1h/6h/1d, process hourly, refresh HTS daily)

**How it works:** The API `GET /api/v1/compliance/signal-health` queries `raw_signals` grouped by source. A source is “ok” if it has data within 2× its poll frequency; “stale” if older; “no_data” if never ingested. No Celery task is needed — the dashboard queries the DB on page load.

**Red flags:**
- `overall: critical` — no sources with recent data; Celery may not be running
- Many `stale` sources — poller may be failing or feeds changed
- `alerts_last_24h: 0` when `importer_hts_usage` has data — process task may not be running or no matching signals

### 6. Manual acceptance checklist

- [ ] Poll runs without errors
- [ ] Process runs without errors
- [ ] PSC Radar loads and shows alerts (or clear empty state)
- [ ] Shipment detail Analysis tab shows linked alerts
- [ ] Alert copy is readable (“what changed, why it matters”)
- [ ] Priority (HIGH/CRITICAL) visible
- [ ] Re-run shipment produces new analysis; alerts still applicable
- [ ] **Signal Health dashboard loads; sources show ok/stale; pipeline totals visible**

---

## Related

- [SPRINT_ROADMAP_LOCKED.md](SPRINT_ROADMAP_LOCKED.md)
- [SPRINT20_PROGRESS.md](SPRINT20_PROGRESS.md)
- [COMPLIANCE_SIGNAL_ENGINE_STATUS.md](COMPLIANCE_SIGNAL_ENGINE_STATUS.md)

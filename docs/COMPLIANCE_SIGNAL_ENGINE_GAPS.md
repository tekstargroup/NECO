# Compliance Signal Engine — Gaps & Priorities

**Purpose:** Pinned backlog of gaps to close. Execute in order when ready.

**Related:** [COMPLIANCE_SIGNAL_ENGINE_STATUS.md](COMPLIANCE_SIGNAL_ENGINE_STATUS.md), [COMPLIANCE_SIGNAL_ENGINE.md](COMPLIANCE_SIGNAL_ENGINE.md)

**Last executed:** March 17, 2026 — GAPs 1–10 implemented (migration 012, services, UI).

---

## Pinned: Previous Suggested Priorities

*Return to these after GAP 1–10.*

1. **Link PSC alerts to shipments** — Match alerts to shipments by HTS and org, set `shipment_id` / `shipment_item_id` when creating alerts.
2. **Verify CBP CROSS** — Run poller, inspect `raw_signals` for CBP_CROSS; if empty, investigate rulings.cbp.gov structure and adjust scraper/API usage.
3. **Add per-source scheduling** — Use `frequency` from config to drive separate Celery schedules (e.g. CSMS 5 min, FR 15 min).
4. **Compute duty delta** — Use duty resolution to estimate duty change and populate `duty_delta_estimate`.
5. **Add product_hts_map** — If products exist, add table and logic to map signals to products.
6. **Shipment detail integration** — Show relevant PSC alerts in the shipment/entry detail view.

---

## GAP 1 – Quota Intelligence Engine

**Objective:** Turn quota mentions into structured, trackable, actionable quota data.

### Step 1 – Add new table

Create table `quota_status` with fields:

| Column | Type | Description |
|--------|------|-------------|
| id | UUID | Primary key |
| hts_code | text | HTS subject to quota |
| country | text | Country of origin |
| quota_type | text | Type of quota |
| quota_limit | numeric | Limit quantity |
| quantity_used | numeric | Used so far |
| fill_rate | numeric | quantity_used / quota_limit |
| status | text | `open`, `near_limit`, `filled` |
| effective_date | date | When quota applies |
| last_updated | timestamp | Last refresh |

### Step 2 – Extract quota signals

Update classification output to include:

- `category` = `QUOTA_UPDATE`
- `hts_codes` (array)
- `country`
- `quota_limit`
- `quantity_used`

### Step 3 – Compute fill rate

```
fill_rate = quantity_used / quota_limit
```

### Step 4 – Add quota alert logic

If `fill_rate > 0.9`:

Create PSC alert with:

- `alert_type` = `QUOTA_RISK`
- `reason` = "Quota nearly filled"
- `priority` = HIGH

### Step 5 – UI requirement

In PSC Radar, add:

- **Fill %**
- **Status** (Open / Near / Closed)

---

## GAP 2 – Tariff → HTS Mapping Engine

**Objective:** Convert tariff changes into importer-specific impact.

### Step 1 – Extend normalized_signals

Add fields:

- `duty_rate_change` (numeric)
- `affected_hts_codes` (array of text)

### Step 2 – Parse tariff signals

When `category` = `TARIFF_CHANGE`, extract:

- HTS codes
- `old_rate`
- `new_rate`

### Step 3 – Map to importer

For each HTS in signal:

If HTS exists in `importer_hts_usage`:

→ Fetch shipments using that HTS.

### Step 4 – Compute impact

```
duty_delta = (new_rate - old_rate) * shipment.customs_value
```

### Step 5 – Create alert

Create PSC alert with:

- `shipment_id`
- `hts_code`
- `duty_delta_estimate`
- `reason` = "Tariff change affects this HTS"

---

## GAP 3 – FDA / Admissibility Engine

**Objective:** Move from informational alerts to shipment-level risk.

### Step 1 – Add table

Create table `import_restrictions` with:

| Column | Type |
|--------|------|
| id | UUID |
| agency | text |
| product_keywords | array |
| hts_codes | array |
| country | text |
| severity | text |
| description | text |

### Step 2 – Match against shipment items

For each shipment item:

- If HTS matches restriction HTS → flag
- Else if product description matches keywords → flag

### Step 3 – Create alert

Create PSC alert with:

- `alert_type` = `FDA_RISK`
- `shipment_id`
- `hts_code`
- `reason` = "FDA import alert applies to this product"

### Step 4 – Severity scoring

High severity if:

- HTS match
- Same country
- Active enforcement

---

## GAP 4 – CBP CROSS Rulings (CRITICAL)

**Objective:** Ensure rulings ingestion is real, complete, and usable.

### Step 1 – Validate ingestion

Query `raw_signals` where `source` = `CBP_CROSS`.

If results are low or zero → fix immediately.

### Step 2 – Improve ingestion

If the site is dynamic:

- Use Playwright (headless browser)
- Or inspect network calls and replicate API
- Or scrape structured search results

### Step 3 – Add rulings table

Create table `cbp_rulings` with:

| Column | Type |
|--------|------|
| id | UUID |
| ruling_number | text |
| hts_codes | array |
| description | text |
| full_text | text |
| ruling_date | date |

### Step 4 – Link rulings to importer HTS

If any ruling HTS matches `importer_hts_usage`:

→ Attach ruling to alert.

### Step 5 – Use rulings in PSC alerts

Create PSC alert with:

- `reason` = "CBP ruling suggests alternative classification"
- `evidence_links` including ruling source

---

## GAP 5 – Real-Time Signal Engine

**Objective:** Move from hourly batch to priority-based ingestion.

### Step 1 – Add scheduling config

Define:

| Source | Frequency |
|--------|-----------|
| CBP_CSMS | 5 minutes |
| FEDERAL_REGISTER | 15 minutes |
| CBP_CROSS | 60 minutes |
| USITC_HTS | daily |

### Step 2 – Split Celery tasks

Create separate tasks:

- `poll_csms_feed`
- `poll_federal_register`
- `poll_cross_rulings`
- `poll_hts_updates`

Each runs at its own frequency.

### Step 3 – Prioritize processing

- If signal source = `CBP_CSMS` → process immediately
- Else → batch process

---

## GAP 6 – HTS-Centric Filtering (MANDATORY)

**Objective:** Ensure every signal maps to HTS or gets suppressed.

### Step 1 – Enforce rule

If signal has no HTS codes:

→ **Suppress it.**

### Step 2 – Fallback extraction

If HTS not found:

- Extract via keywords
- Infer via rulings
- Map via similarity

---

## GAP 7 – Importer-Aware Mapping

**Objective:** Make signals specific to each importer.

### Step 1 – Match signals

If signal HTS intersects `importer_hts_usage`:

→ Mark as relevant.

### Step 2 – Add explanation

Each alert must include:

- `reason` = "Importer used this HTS recently"
- `country_match` (true/false)
- `historical_usage` (true/false)

---

## GAP 8 – Financial Impact Layer (CRITICAL)

**Objective:** Every alert must quantify money.

### Step 1 – Compute duty impact

```
duty_delta = (alt_rate - declared_rate) * customs_value
```

### Step 2 – Store in alerts

Add/use field in `psc_alerts`:

- `duty_delta_estimate`

### Step 3 – Add UI fields

Display:

- Estimated savings in dollars
- Percentage change
- Confidence

---

## GAP 9 – Final Output Structure

**Objective:** Standardize PSC alert shape.

Each PSC alert must contain:

| Field | Required |
|-------|----------|
| shipment_id | Yes |
| hts_code | Yes |
| signal_source | Yes |
| reason | Yes |
| duty_delta_estimate | Yes |
| confidence_score | Yes |
| explanation | Yes |
| evidence_links | Yes |

---

## GAP 10 – Success Criteria

**System is complete when:**

1. A tariff change happens → NECO maps it to HTS → links to shipment → calculates impact
2. A quota fills → NECO flags affected shipments
3. FDA alert appears → NECO flags specific products
4. CBP ruling updates → NECO suggests reclassification

---

## Final Reality Check

**If you execute this correctly, NECO becomes:**

- A compliance intelligence system
- A money-saving engine
- A decision tool

**If you don’t, it becomes:**

- A signal aggregator
- Noisy
- Ignored

---

## Suggested Execution Order

| Order | Gap | Rationale |
|-------|-----|-----------|
| 1 | GAP 4 (CBP CROSS) | Critical; validate/fix ingestion first |
| 2 | GAP 5 (Real-time) | Per-source scheduling enables better signal flow |
| 3 | GAP 6 (HTS filtering) | Reduces noise; mandatory rule |
| 4 | GAP 8 (Financial impact) | Critical; every alert must quantify money |
| 5 | GAP 2 (Tariff mapping) | Links tariff changes to shipments |
| 6 | GAP 1 (Quota) | Structured quota intelligence |
| 7 | GAP 3 (FDA) | Shipment-level admissibility risk |
| 8 | GAP 7 (Importer-aware) | Already partially done; enhance |
| 9 | GAP 9 (Output structure) | Standardize; may overlap with prior gaps |

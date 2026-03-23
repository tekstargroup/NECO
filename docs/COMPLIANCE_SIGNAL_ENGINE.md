# Compliance Signal Engine

**Purpose:** Full spec for NECO's compliance intelligence pipeline — ingest, classify, score, and produce actionable PSC Radar alerts.

**Related:** [docs/REGULATORY_MONITORING.md](REGULATORY_MONITORING.md), [docs/SPRINT17_PLUS_BACKLOG.md](SPRINT17_PLUS_BACKLOG.md)

---

## Objective

Build a system that:
- Ingests all relevant trade and compliance signals
- Classifies and scores them
- Maps them to HTS, products, and entries/shipments
- Produces actionable, explainable alerts (PSC Radar)

Output must be:
- Low noise
- High financial relevance
- Fully traceable

---

## Database Schema

### raw_signals

Stores raw ingestion.

| Column | Type | Description |
|--------|------|-------------|
| id | UUID | Primary key |
| source | String | Source name (e.g. CBP_DUTY_RATES) |
| title | String | Item title |
| content | Text | Raw content |
| url | String | Source URL (dedupe key) |
| published_at | DateTime | Publication date |
| ingested_at | DateTime | When ingested |

### normalized_signals

| Column | Type | Description |
|--------|------|-------------|
| id | UUID | Primary key |
| raw_signal_id | UUID | FK to raw_signals |
| summary | Text | Extracted summary |
| full_text | Text | Normalized text |
| signal_type | String | Type classification |
| countries | JSONB | Affected countries |
| hts_codes | JSONB | Mentioned HTS codes |
| keywords | JSONB | Extracted keywords |
| effective_date | Date | When signal takes effect |
| confidence | Float | 0–1 |

### signal_classifications

| Column | Type | Description |
|--------|------|-------------|
| id | UUID | Primary key |
| signal_id | UUID | FK to normalized_signals |
| category | Enum | TARIFF_CHANGE, HTS_UPDATE, QUOTA_UPDATE, SANCTION, IMPORT_RESTRICTION, RULING, TRADE_ACTION, DOCUMENTATION_RULE |
| impact_type | String | duty_increase, duty_decrease, compliance_risk, documentation |
| affected_entities | JSONB | country, product, hts |

### signal_scores

| Column | Type | Description |
|--------|------|-------------|
| id | UUID | Primary key |
| signal_id | UUID | FK to normalized_signals |
| relevance_score | Integer | 0–100 |
| financial_impact_score | Integer | 0–100 |
| urgency_score | Integer | 0–100 |
| confidence_score | Integer | 0–100 |
| final_score | Float | Weighted |

### psc_alerts

| Column | Type | Description |
|--------|------|-------------|
| id | UUID | Primary key |
| signal_id | UUID | FK to normalized_signals |
| shipment_id | UUID | Nullable |
| shipment_item_id | UUID | Nullable |
| entry_id | UUID | Nullable |
| line_item_id | UUID | Nullable |
| hts_code | String | Affected HTS |
| alert_type | String | Type of alert |
| duty_delta_estimate | String | Estimated duty change |
| reason | Text | Human-readable reason |
| evidence_links | JSONB | Source links |
| status | Enum | new, reviewed, dismissed |
| explanation | JSONB | hts_match, country_match, historical_usage, source |
| created_at | DateTime | When created |

### importer_hts_usage

For scoring — derived from ShipmentItem or LineItem.

| Column | Type | Description |
|--------|------|-------------|
| organization_id | UUID | FK to organizations |
| hts_code | String | HTS used |
| frequency | Integer | Count of uses |
| total_value | Numeric | Total value |

---

## Classification Categories (Enum)

- TARIFF_CHANGE
- HTS_UPDATE
- QUOTA_UPDATE
- SANCTION
- IMPORT_RESTRICTION
- RULING
- TRADE_ACTION
- DOCUMENTATION_RULE

---

## Relevance Scoring Formula

```
FINAL_SCORE = (HTS_MATCH * 0.35) + (COUNTRY_MATCH * 0.20) + (IMPORTER_HISTORY * 0.25) + (FINANCIAL_IMPACT * 0.20)
```

**Inputs:**
- **HTS_MATCH:** Does signal mention HTS used by importer?
- **COUNTRY_MATCH:** Does it affect importer's countries?
- **IMPORTER_HISTORY:** Has this importer used affected HTS before?
- **FINANCIAL_IMPACT:** Estimate based on duty delta potential.

---

## PSC Alert Triggers

Create alert when:
1. Alternative HTS has lower duty
2. New ruling contradicts current classification
3. Tariff change impacts existing imports
4. Historical mismatch detected

**Threshold:** `final_score > 70`

---

## Priority Tiers

| Tier | Score | Visibility |
|------|-------|------------|
| CRITICAL | > 85 | Always show |
| HIGH | 70–85 | Always show |
| MEDIUM | 50–70 | Show when expanded |
| LOW | < 50 | Hidden by default |

---

## Explainability Layer

Every alert must include:

```json
{
  "explanation": {
    "hts_match": true,
    "country_match": true,
    "historical_usage": true,
    "source": "CBP ruling HQ123456"
  }
}
```

Every alert must answer:
- Why was this triggered?
- What data supports it?
- What is the financial impact?
- What is the confidence?

---

## Critical Rules

1. No black box outputs
2. Every alert must link to a source
3. Suppress low relevance signals (score < 50 hidden by default)
4. Prioritize money impact over volume
5. Always show evidence

---

## API Endpoints

| Endpoint | Purpose |
|----------|---------|
| GET /api/v1/regulatory-updates | List signals, filter by tag, date range |
| GET /api/v1/psc-radar/alerts | List psc_alerts for org, filter by status |
| PATCH /api/v1/psc-radar/alerts/{id} | Update status (reviewed/dismissed) |

---

## UI Components

- **PSC Radar page:** Table — Entry/Shipment | HTS | Signal | Duty Delta | Score | Status
- **Shipment detail integration:** Show relevant signals in Analysis tab Section 5 (PSC Radar)
- **Signal detail view:** Original source link, summary, why it matters, linked HTS/products

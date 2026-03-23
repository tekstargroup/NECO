# Sprint 8 - Enterprise Controls & Reporting (Audit Readiness)

## Overview

Sprint 8 provides compliance visibility and audit readiness capabilities. This sprint is **read-only, aggregated, explainable, and exportable**.

**Key Principle**: Visibility and defensibility, not new logic. No changes to Sprint 5, 6, or 7.

## Core Components

### 1. Compliance Summary Dashboard

**Read-only aggregations** for management visibility.

**Metrics:**
- Total classifications
- % auto-resolved vs REVIEW_REQUIRED
- % reviewed vs overridden
- PSC flags count
- High-duty-delta cases (count + total $ exposure)
- Open vs closed review items

**Groupable by:**
- Time range
- HTS chapter
- Reviewer
- Object type (classification vs PSC)

**Endpoint:** `GET /api/v1/compliance/dashboard/summary`

### 2. Risk & Exposure Reports

**Structured, deterministic, reproducible reports:**

1. **Classification Risk Report**
   - Low/medium/high confidence buckets
   - Counts and record IDs

2. **PSC Exposure Report**
   - Duty deltas (aggregate + per case)
   - Total exposure USD
   - Cases with exposure

3. **Review Activity Report**
   - Accepted/rejected/overridden counts
   - Detailed review records
   - Reviewer activity

4. **Unresolved Risk Report**
   - REVIEW_REQUIRED items still open
   - Days open
   - Snapshot summaries

**Endpoints:**
- `GET /api/v1/compliance/reports/classification-risk`
- `GET /api/v1/compliance/reports/psc-exposure`
- `GET /api/v1/compliance/reports/review-activity`
- `GET /api/v1/compliance/reports/unresolved-risk`

### 3. Audit Pack Generator (Critical)

**Most valuable feature in Sprint 8.**

For a selected time range or case set, generates complete audit pack containing:
- Inputs
- Outputs
- Review records
- Overrides
- Audit replay results
- HTS version used
- Disclaimer text

**Export formats:**
- **JSON** (canonical) - Authoritative source
- **PDF/TXT** (human-readable) - Simple text format
- **ZIP bundle** - Complete package with JSON, TXT, and README

**Endpoint:** `GET /api/v1/compliance/audit-pack`

**Parameters:**
- `review_ids` (optional): Specific review IDs
- `time_range_start` (optional): Start of time range
- `time_range_end` (optional): End of time range
- `include_audit_replay` (default: true): Include audit replay results
- `format` (default: json): Export format (json, pdf, zip)

### 4. Read-Only Drilldown Views

Given a report row, links to:
- Classification/PSC snapshot
- Review/override history
- Audit replay output

**Read-only**: No edits, re-review, or overrides allowed.

**Endpoint:** `GET /api/v1/compliance/drilldown/{review_id}`

## Example: Compliance Dashboard Summary

```json
{
  "time_range": {
    "start": "2024-01-01T00:00:00Z",
    "end": "2024-01-31T23:59:59Z"
  },
  "filters": {
    "hts_chapter": null,
    "reviewer": null,
    "object_type": null
  },
  "metrics": {
    "total_classifications": 1250,
    "auto_resolved": {
      "count": 1000,
      "percentage": 80.0
    },
    "review_required": {
      "count": 250,
      "percentage": 20.0
    },
    "reviewed": 200,
    "overridden": 5,
    "psc_flags_count": 45,
    "high_duty_delta_cases": 12,
    "open_reviews": 50,
    "closed_reviews": 1200
  }
}
```

## Example: PSC Exposure Report

```json
{
  "report_type": "PSC_EXPOSURE",
  "time_range": {
    "start": "2024-01-01T00:00:00Z",
    "end": "2024-01-31T23:59:59Z"
  },
  "exposure_metrics": {
    "total_exposure_usd": 125000.50,
    "cases_with_exposure": 12,
    "average_exposure_per_case": 10416.71
  },
  "cases": [
    {
      "review_id": "550e8400-e29b-41d4-a716-446655440000",
      "declared_hts": "6112.20.20.30",
      "alternative_hts": "6112.20.10.10",
      "delta_amount": 9500.00,
      "delta_percent": 19.9
    }
  ]
}
```

## Example: Audit Pack (JSON)

```json
{
  "audit_pack_version": "1.0",
  "generated_at": "2024-01-31T15:30:00Z",
  "hts_version_id": "792bb867-c549-4769-80ca-d9d1adc883a3",
  "disclaimer": "AUDIT PACK DISCLAIMER...",
  "summary": {
    "total_records": 10,
    "time_range": {
      "start": "2024-01-01T00:00:00Z",
      "end": "2024-01-31T23:59:59Z"
    }
  },
  "review_records": [
    {
      "review_id": "550e8400-e29b-41d4-a716-446655440000",
      "object_type": "CLASSIFICATION",
      "status": "REVIEWED_ACCEPTED",
      "object_snapshot": {
        "inputs": {...},
        "output": {...}
      }
    }
  ],
  "audit_replay_results": [
    {
      "review_id": "550e8400-e29b-41d4-a716-446655440000",
      "replay_result": {
        "matches": true,
        "flags": []
      }
    }
  ]
}
```

## Compliance Director Use Cases

### Use Case 1: "What risks exist?"

**Answer:** Open Unresolved Risk Report
```
GET /api/v1/compliance/reports/unresolved-risk?time_range_start=2024-01-01
```

Shows all REVIEW_REQUIRED items still open, with days open and snapshot summaries.

### Use Case 2: "What decisions were made?"

**Answer:** Open Review Activity Report
```
GET /api/v1/compliance/reports/review-activity?reviewer=reviewer_1
```

Shows all accepted/rejected/overridden decisions with reviewer, timestamps, and reasons.

### Use Case 3: "Who approved them?"

**Answer:** Drilldown to review record
```
GET /api/v1/compliance/drilldown/{review_id}
```

Shows complete review history, including who created, who reviewed, when, and why.

### Use Case 4: "What is our exposure?"

**Answer:** Open PSC Exposure Report
```
GET /api/v1/compliance/reports/psc-exposure
```

Shows total exposure USD, cases with exposure, and per-case details.

### Use Case 5: "CBP Audit Request"

**Answer:** Generate Audit Pack
```
GET /api/v1/compliance/audit-pack?time_range_start=2024-01-01&format=zip
```

Downloads complete ZIP bundle with all inputs, outputs, reviews, overrides, and audit replay results.

## Hard Rules

1. **Read-only**: No mutations, no edits, no workflows
2. **Aggregated**: Metrics only, no drill-down logic changes
3. **Explainable**: Every metric has clear source
4. **Exportable**: JSON canonical, PDF/TXT human-readable, ZIP bundle
5. **Deterministic**: Same inputs = same outputs
6. **Reproducible**: Can regenerate any report

## Files Created

- `backend/app/services/compliance_dashboard_service.py`: Dashboard aggregations
- `backend/app/services/reporting_service.py`: Report generation
- `backend/app/services/audit_pack_service.py`: Audit pack generation
- `backend/app/api/v1/compliance.py`: API endpoints
- `backend/tests/test_compliance_dashboard.py`: Dashboard tests
- `backend/tests/test_reporting_service.py`: Reporting tests
- `backend/tests/test_audit_pack_service.py`: Audit pack tests

## Exit Criteria Met

✅ Compliance director can open dashboard  
✅ Compliance director can export audit pack  
✅ Compliance director can answer CBP-style questions  
✅ Compliance director can explain decisions without engineers  
✅ "This is something I would trust in an audit"  

**Sprint 8 is CLOSED. NECO is audit-ready.**

# Sprint 9 - Broker Filing Prep (No Automation)

## Overview

Sprint 9 produces broker-ready outputs that can be handed off safely and confidently. This sprint is **formatting, validation, and handoff, not decision-making**.

**Key Principle**: "Can a broker use this immediately without re-doing the work or assuming liability?"

**No filing. No transmission. No ACE. No recommendations.**

## Core Principles

- **Read-only intelligence**: No mutations
- **Explicit blockers**: Hard gates, no soft warnings
- **Conservative defaults**: Human review required
- **Safety first**: If unsafe, NECO blocks and explains why

## Core Components

### 1. FilingPrepBundle (Canonical)

Single source of truth for all broker exports.

**Fields:**
- Declared HTS code (10-digit)
- Duty breakdown (general, special, column2)
- Quantity and UOM
- Customs value
- Country of origin (context only)
- Review status
- PSC flags (if any)
- HTS version ID
- Disclaimers
- Export blockers and reasons

### 2. Pre-Submission Validation (Hard Gates)

**Export blocked if:**
- `REVIEW_REQUIRED` present
- Missing quantity
- Missing value
- Missing duty fields
- Unresolved PSC flags (configurable, default block)

**Explicit error messages:**
- "Export blocked: classification not reviewed"
- "Export blocked: missing quantity"
- "Export blocked: missing customs value"
- "Export blocked: missing duty fields"
- "Export blocked: unresolved PSC risk"

### 3. Broker Export Formats

**JSON (canonical)**
- Complete FilingPrepBundle structure
- Machine-readable
- Authoritative source

**CSV (broker-friendly)**
- Field-value pairs
- Easy to import into broker systems
- Includes disclaimers and broker notes

**PDF Summary (human-readable)**
- Simple text format
- Clear sections: Classification, Duties, Quantity/Value, Review Status, PSC Flags, Broker Notes, Disclaimers
- No styling beyond clarity

### 4. Broker Handoff Notes

Structured notes explaining:
- **What was reviewed**: Review history, reviewer, notes
- **What was overridden**: Override justifications
- **What risks were flagged**: PSC Radar flags
- **What NECO did NOT evaluate**: Trade programs, quotas, Section 301/232, ADD/CVD, legal interpretation

### 5. Read-Only Broker View

Broker can see:
- Filing-prep bundle
- Review trail
- Audit replay snapshot

Broker cannot:
- Edit
- Approve
- Override

This is consumption, not collaboration.

## API Endpoints

### Get Filing Prep Bundle
```
GET /api/v1/broker/filing-prep
```

**Parameters:**
- `declared_hts_code` (required): 10-digit HTS code
- `quantity` (optional): Product quantity
- `unit_of_measure` (optional): Unit of measure
- `customs_value` (optional): Customs value
- `country_of_origin` (optional): Country of origin (context only)
- `product_description` (optional): Product description (for PSC Radar)
- `review_id` (optional): Review record ID (if already reviewed)
- `block_on_unresolved_psc` (default: true): Block export if unresolved PSC flags

**Returns:** FilingPrepBundle JSON

### Export Filing Prep
```
GET /api/v1/broker/filing-prep/export
```

**Parameters:** Same as above, plus:
- `format` (default: json): Export format (json, csv, pdf)

**Returns:** Export file (JSON, CSV, or PDF)

**Error Response (if blocked):**
```json
{
  "export_blocked": true,
  "errors": [
    "Export blocked: classification not reviewed"
  ],
  "bundle": { ... }
}
```

### Get Broker View
```
GET /api/v1/broker/filing-prep/view/{review_id}
```

**Returns:** Read-only view with bundle, review trail, and audit replay

## Example: FilingPrepBundle JSON

```json
{
  "declared_hts_code": "6112.20.20.30",
  "duty_breakdown": {
    "general_duty": "8.3%",
    "special_duty": "Free(AU,BH,CL,CO,E*,IL,JO,KR,MA,OM,P,PA,PE,S,SG)",
    "column2_duty": "90%"
  },
  "quantity": 100.0,
  "unit_of_measure": "PCS",
  "customs_value": 5000.0,
  "country_of_origin": "CN",
  "review_status": "REVIEWED_ACCEPTED",
  "psc_flags": [],
  "hts_version_id": "792bb867-c549-4769-80ca-d9d1adc883a3",
  "review_id": "550e8400-e29b-41d4-a716-446655440000",
  "reviewed_by": "reviewer_1",
  "reviewed_at": "2024-01-31T15:30:00Z",
  "review_notes": "Classification verified against HTSUS",
  "is_override": false,
  "override_of_review_id": null,
  "override_justification": null,
  "disclaimers": [
    "This is not a filing. Broker review required before submission.",
    "NECO does not provide legal advice or filing recommendations.",
    "Duty rates are based on general/special/column2 only. Trade programs, quotas, and other measures not evaluated.",
    "Country of origin is provided for context only. NECO does not evaluate origin rules or preferences.",
    "PSC Radar flags indicate potential risks but do not constitute filing advice.",
    "All classifications should be verified against current HTSUS and applicable rulings.",
    "Broker assumes full responsibility for final classification and filing decisions."
  ],
  "export_blocked": false,
  "export_block_reasons": [],
  "broker_notes": {
    "what_was_reviewed": [
      "Classification reviewed by reviewer_1 on 2024-01-31T15:30:00Z",
      "Review notes: Classification verified against HTSUS"
    ],
    "what_was_overridden": [],
    "what_risks_were_flagged": [],
    "what_neco_did_not_evaluate": [
      "Trade program eligibility (GSP, AGOA, etc.)",
      "Country-specific duty rates beyond general/special/column2",
      "Quota or safeguard measures",
      "Section 301/232 applicability",
      "ADD/CVD orders",
      "PSC filing eligibility or timelines",
      "Legal interpretation of HTS notes or rulings"
    ]
  }
}
```

## Example: Blocked Export Error

```json
{
  "detail": {
    "export_blocked": true,
    "errors": [
      "Export blocked: classification not reviewed"
    ],
    "bundle": {
      "declared_hts_code": "6112.20.20.30",
      "review_status": "REVIEW_REQUIRED",
      "export_blocked": true,
      "export_block_reasons": ["REVIEW_REQUIRED"],
      ...
    }
  }
}
```

## Example: Broker PDF Summary

```
================================================================================
NECO FILING PREP SUMMARY
================================================================================

Generated: 2024-01-31T15:30:00Z

✓ Export Ready (Broker Review Still Required)

--------------------------------------------------------------------------------
CLASSIFICATION & DUTIES
--------------------------------------------------------------------------------
Declared HTS Code: 6112.20.20.30
General Duty: 8.3%
Special Duty: Free(AU,BH,CL,CO,E*,IL,JO,KR,MA,OM,P,PA,PE,S,SG)
Column 2 Duty: 90%
HTS Version: 792bb867-c549-4769-80ca-d9d1adc883a3

--------------------------------------------------------------------------------
QUANTITY & VALUE
--------------------------------------------------------------------------------
Quantity: 100.0
Unit of Measure: PCS
Customs Value: $5,000.00
Country of Origin: CN

--------------------------------------------------------------------------------
REVIEW STATUS
--------------------------------------------------------------------------------
Status: REVIEWED_ACCEPTED
Reviewed By: reviewer_1
Reviewed At: 2024-01-31T15:30:00Z
Review Notes: Classification verified against HTSUS

--------------------------------------------------------------------------------
BROKER NOTES
--------------------------------------------------------------------------------
What Was Reviewed:
  • Classification reviewed by reviewer_1 on 2024-01-31T15:30:00Z
  • Review notes: Classification verified against HTSUS

What NECO Did NOT Evaluate:
  • Trade program eligibility (GSP, AGOA, etc.)
  • Country-specific duty rates beyond general/special/column2
  • Quota or safeguard measures
  • Section 301/232 applicability
  • ADD/CVD orders
  • PSC filing eligibility or timelines
  • Legal interpretation of HTS notes or rulings

================================================================================
DISCLAIMERS
================================================================================
This is not a filing. Broker review required before submission.

NECO does not provide legal advice or filing recommendations.

Duty rates are based on general/special/column2 only. Trade programs, quotas, and other measures not evaluated.

Country of origin is provided for context only. NECO does not evaluate origin rules or preferences.

PSC Radar flags indicate potential risks but do not constitute filing advice.

All classifications should be verified against current HTSUS and applicable rulings.

Broker assumes full responsibility for final classification and filing decisions.

================================================================================
END OF FILING PREP SUMMARY
================================================================================
```

## Broker Use Cases

### Use Case 1: Get Filing Prep Bundle
```
GET /api/v1/broker/filing-prep?declared_hts_code=6112.20.20.30&quantity=100&customs_value=5000
```

Returns complete bundle with validation and blockers.

### Use Case 2: Export for Broker System
```
GET /api/v1/broker/filing-prep/export?declared_hts_code=6112.20.20.30&quantity=100&customs_value=5000&format=csv
```

Downloads CSV file ready for import into broker system.

### Use Case 3: Human Review
```
GET /api/v1/broker/filing-prep/export?declared_hts_code=6112.20.20.30&quantity=100&customs_value=5000&format=pdf
```

Downloads PDF summary for human review.

### Use Case 4: View Review History
```
GET /api/v1/broker/filing-prep/view/{review_id}
```

Read-only view of review record with full history and audit replay.

## Hard Rules

1. **Read-only**: No mutations, no edits, no approvals
2. **Explicit blockers**: Hard gates, no soft warnings
3. **Conservative defaults**: Human review required
4. **Disclaimers always present**: Every export includes disclaimers
5. **No filing**: No ACE integration, no transmission, no automation

## Files Created

- `backend/app/models/filing_prep_bundle.py`: FilingPrepBundle model
- `backend/app/services/filing_prep_service.py`: Filing prep service
- `backend/app/services/broker_export_service.py`: Export generators
- `backend/app/api/v1/broker.py`: Broker API endpoints
- `backend/tests/test_filing_prep.py`: Tests

## Exit Criteria Met

✅ Broker can receive the export  
✅ Broker can understand it without explanation  
✅ Broker can trust that NECO did not overstep  
✅ Broker can use it as a starting point, not a liability  
✅ "This saves me time and doesn't put me at risk."  

**Sprint 9 is CLOSED. NECO is broker-ready.**

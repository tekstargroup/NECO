# Sprint 10 - Enrichment (Document Ingestion + Attribute Extraction)

## Overview

Sprint 10 provides document enrichment to reduce clarification burden and increase defensibility by extracting structured attributes from importer documents, while maintaining zero-hallucination behavior.

**Key Principle**: Extract facts present in documents only. Never infer missing facts.

**No new conclusions. No HTS decisions. No classification recommendations.**

## Core Principles

- **Extract facts present in documents only**
- **Attach evidence pointers everywhere**
- **Never infer missing facts**
- **Handle conflicts explicitly**
- **Maintain replayability**

## Core Components

### 1. EnrichmentBundle (Canonical)

Single source of truth for extracted fields.

**Fields:**
- Document metadata (document_id, document_type, document_hash, parser_version)
- Extracted fields (with evidence, confidence, warnings)
- Line items (for invoices/packing lists)
- Aggregated values (if unambiguous)
- Missing required fields
- Warnings
- Conflicts

### 2. Document Ingestion Pipeline

**Read-only document ingestion:**
- Accept PDF (and images if supported)
- Parse via OCR/token system
- Create DocumentRecord with:
  - document_id
  - document_type (CI, PL, TDS)
  - filename
  - hash (SHA256 for deduplication)
  - uploaded_at, parsed_at
  - page_count
  - tokenized_content, text_spans

### 3. Field Extractors (Deterministic, Evidence-backed)

**Phase 1 fields:**
- Seller name
- Buyer name
- Invoice number
- Invoice date
- Currency
- Line items (description, quantity, UOM, unit price, line value)
- Total value
- Country of origin (only if explicitly present)
- Material composition (only if explicitly present)
- Brand/model identifiers (only if explicitly present)

**Rules:**
- Every extracted field includes evidence (document_id, page_number, bbox/line_span, raw_text_snippet)
- If multiple conflicting values exist: store all candidates, flag CONFLICT, do not choose one

### 4. Canonical Normalization Layer (Safe)

**Normalize formats without changing meaning:**
- Dates to ISO (if parseable)
- Currency codes
- Quantity numeric parsing
- UOM normalization to controlled vocabulary (retain raw value too)

**Never normalize by guessing.**

### 5. Integration Points (Non-invasive)

**Integrate EnrichmentBundle into:**
- Classification input payload (as additional evidence)
- PSC Radar input payload (as additional evidence)
- FilingPrepBundle generation (populate quantity/value if extracted and unambiguous)

**Hard gate:** If enrichment is ambiguous or conflicting, do not auto-populate final fields used for export. Keep blockers.

### 6. Auditability

**Persist EnrichmentBundle snapshots linked to:**
- classification review_id
- PSC review_id
- filing-prep review_id

**Enrichment must be replayable:**
- Same document hash + same parser version = same extracted fields

## API Endpoints

### Ingest Document
```
POST /api/v1/enrichment/documents/ingest
```

**Parameters:**
- `file`: PDF file (multipart/form-data)
- `document_type`: COMMERCIAL_INVOICE, PACKING_LIST, or TECHNICAL_SPEC

**Returns:** DocumentRecord with document_id

### Extract Fields
```
POST /api/v1/enrichment/documents/{document_id}/extract
```

**Returns:** EnrichmentBundle with extracted fields and evidence

### Get Enrichment Snapshot
```
GET /api/v1/enrichment/enrichment/{enrichment_id}
```

**Returns:** EnrichmentAuditRecord

### Get Enrichments for Review
```
GET /api/v1/enrichment/enrichment/review/{review_id}
```

**Returns:** List of enrichment snapshots linked to review

## Example: EnrichmentBundle JSON

```json
{
  "document_id": "CI_20240101_12345678",
  "document_type": "COMMERCIAL_INVOICE",
  "document_hash": "abc123def456...",
  "parser_version": "1.0",
  "extracted_fields": [
    {
      "field_name": "invoice_number",
      "value": "INV-12345",
      "raw_value": "Invoice No: INV-12345",
      "evidence": [
        {
          "document_id": "CI_20240101_12345678",
          "page_number": 1,
          "bbox": null,
          "line_span": {"start_line": 5, "end_line": 5},
          "raw_text_snippet": "Invoice No: INV-12345"
        }
      ],
      "confidence": "HIGH",
      "warnings": []
    },
    {
      "field_name": "invoice_date",
      "value": "2024-01-15T00:00:00",
      "raw_value": "01/15/2024",
      "evidence": [
        {
          "document_id": "CI_20240101_12345678",
          "page_number": 1,
          "raw_text_snippet": "Date: 01/15/2024"
        }
      ],
      "confidence": "HIGH",
      "warnings": []
    },
    {
      "field_name": "currency",
      "value": "USD",
      "raw_value": "USD",
      "evidence": [
        {
          "document_id": "CI_20240101_12345678",
          "page_number": 1,
          "raw_text_snippet": "Currency: USD"
        }
      ],
      "confidence": "HIGH",
      "warnings": []
    },
    {
      "field_name": "total_value",
      "value": 5000.0,
      "raw_value": "$5,000.00",
      "evidence": [
        {
          "document_id": "CI_20240101_12345678",
          "page_number": 1,
          "raw_text_snippet": "Total: $5,000.00"
        }
      ],
      "confidence": "HIGH",
      "warnings": []
    }
  ],
  "line_items": [
    {
      "item_number": null,
      "description": null,
      "quantity": 100.0,
      "unit_of_measure": "PCS",
      "unit_price": null,
      "line_value": null,
      "country_of_origin": null,
      "material_composition": null,
      "brand_model": null,
      "evidence": [
        {
          "document_id": "CI_20240101_12345678",
          "page_number": 1,
          "raw_text_snippet": "Qty: 100"
        }
      ]
    }
  ],
  "total_quantity": 100.0,
  "total_value": 5000.0,
  "currency": "USD",
  "missing_required_fields": [],
  "warnings": [],
  "conflicts": [],
  "extracted_at": "2024-01-31T15:30:00Z"
}
```

## Example: Conflict Case Output

```json
{
  "document_id": "CI_CONFLICT_123",
  "document_type": "COMMERCIAL_INVOICE",
  "document_hash": "conflict123",
  "parser_version": "1.0",
  "extracted_fields": [],
  "line_items": [],
  "total_quantity": null,
  "total_value": null,
  "currency": null,
  "missing_required_fields": [],
  "warnings": [
    "Multiple conflicting countries of origin detected: CN, US"
  ],
  "conflicts": [
    {
      "field": "country_of_origin",
      "values": ["CN", "US"],
      "evidence": [
        {
          "document_id": "CI_CONFLICT_123",
          "page_number": 1,
          "raw_text_snippet": "Country of Origin: CN"
        },
        {
          "document_id": "CI_CONFLICT_123",
          "page_number": 2,
          "raw_text_snippet": "Origin: US"
        }
      ]
    }
  ],
  "extracted_at": "2024-01-31T15:30:00Z"
}
```

## Example: Filing-Prep with Enrichment

**Scenario:** Clean document with unambiguous extraction

**EnrichmentBundle:**
- total_value: 5000.0 (unambiguous)
- total_quantity: 100.0 (unambiguous)
- currency: USD (unambiguous)
- No conflicts

**FilingPrepBundle Result:**
```json
{
  "declared_hts_code": "6112.20.20.30",
  "quantity": 100.0,
  "customs_value": 5000.0,
  "currency": "USD",
  "review_status": "REVIEWED_ACCEPTED",
  "export_blocked": false,
  "broker_notes": {
    "enrichment_source": {
      "document_id": "CI_20240101_12345678",
      "document_type": "COMMERCIAL_INVOICE",
      "extracted_at": "2024-01-31T15:30:00Z"
    }
  }
}
```

**Note:** Export is still blocked if REVIEW_REQUIRED, even with unambiguous enrichment. Enrichment helps but does not remove blockers.

## Hard Rules

1. **Extract facts present only**: Never infer missing facts
2. **Evidence everywhere**: Every extracted field has evidence pointers
3. **Handle conflicts explicitly**: Store all candidates, flag CONFLICT, do not choose
4. **Safe normalization**: Only normalize if parseable, never guess
5. **Non-invasive integration**: Enrichment adds evidence but does not modify existing logic
6. **Maintain blockers**: Ambiguous enrichment cannot unblock filing-prep export

## Files Created

- `backend/app/models/enrichment_bundle.py`: EnrichmentBundle model
- `backend/app/models/document_record.py`: DocumentRecord model
- `backend/app/services/document_ingestion_service.py`: Document ingestion
- `backend/app/services/field_extractor_service.py`: Field extraction
- `backend/app/services/normalization_service.py`: Safe normalization
- `backend/app/services/enrichment_integration_service.py`: Integration hooks
- `backend/app/services/enrichment_audit_service.py`: Auditability
- `backend/app/api/v1/enrichment.py`: API endpoints
- `backend/tests/test_enrichment.py`: Tests

## Exit Criteria Met

✅ User can upload CI and PL  
✅ NECO extracts line items, quantity, value, and other supported fields with evidence  
✅ Ambiguity produces CONFLICT and does not silently fill  
✅ Filing-prep becomes faster on clean docs, but never unsafe on messy docs  
✅ Tests pass and no locked logic is touched  

**Sprint 10 is CLOSED. NECO enrichment is evidence-backed and safe.**

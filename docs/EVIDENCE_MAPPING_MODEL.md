# NECO — Evidence Mapping Model (Cursor Ready)

**Objective:** Build a structured evidence system that answers, for every alternative HTS surfaced by NECO:
- what evidence supports it
- what evidence weakens it
- where the evidence came from
- exactly where in the source document it came from
- what external authority supports it
- how that evidence should affect decision-making

This is the trust layer.

---

## 1. Core Principle

Do not store "evidence" as vague text blobs.

**Wrong:** "Used Entry Summary and Commercial Invoice"

**Right:**
- Entry Summary, page 2, field HTS, extracted value 8471500000
- Commercial Invoice, row 4, product description "Cisco UCS B200 M5 Blade Server"
- CBP ruling HQ123456, matched by HTS similarity and product keywords

Evidence must be: structured, linkable, explainable, renderable in UI.

---

## 2. Evidence Model Architecture

5 layers:
1. Source Document
2. Extracted Evidence
3. Evidence Link
4. Authority Reference
5. Decision Summary

Flow: Document / Ruling / Signal → extracted field or citation → linked to shipment item → linked to declared HTS and alternative HTS → scored as supporting / conflicting / neutral → surfaced in drawer and review flow.

---

## 3. Database Tables

### A. source_documents
- id, shipment_id, document_type, file_name, file_storage_url, mime_type, uploaded_at, parser_status, page_count, checksum
- Links to shipment_documents via shipment_document_id (nullable)

### B. document_pages
- id, source_document_id, page_number, image_url, extracted_text, ocr_confidence, created_at

### C. extracted_fields
- id, source_document_id, page_id (nullable), shipment_item_id (nullable), field_name, field_value_raw, field_value_normalized, field_type, extraction_method, extraction_confidence, bounding_box_json (nullable), row_reference (nullable), created_at

### D. authority_references
- id, authority_type, reference_id, title, url, effective_date, source_agency, summary, raw_text, hts_codes (array), countries (array), keywords (array), created_at

### E. recommendation_evidence_links
- id, shipment_id, shipment_item_id, declared_hts, alternative_hts, evidence_source_type, source_document_id (nullable), page_id (nullable), extracted_field_id (nullable), authority_reference_id (nullable), evidence_role, evidence_strength, summary, detail_text, supports_declared, supports_alternative, is_conflicting, created_at

### F. recommendation_summaries
- id, shipment_id, shipment_item_id, declared_hts, alternative_hts, estimated_savings, estimated_savings_percent, evidence_strength, review_level, support_summary, risk_summary, next_step_summary, reasoning_summary, created_at, updated_at

---

## 4. Evidence Roles
- SUPPORTING — strengthens alternative HTS
- CONFLICTING — weakens alternative HTS
- CONTEXTUAL — helpful background
- WARNING — increases review need

---

## 5. Evidence Strength
- STRONG, MODERATE, WEAK
- Derived from: document_match_score, authority_support_score, data_completeness_score, contradiction_penalty, regulatory_risk_penalty

---

## 6. Review Level
- LOW, MEDIUM, HIGH, BLOCKING
- Rename "risk" to "review level" in UI

---

## 7. UI Rendering (Drawer)
1. Alternative HTS identified — declared, alternative, savings, evidence strength, review level
2. Why this may fit — 3–5 supporting bullets with source label + page
3. What weakens this — conflicting and warning evidence
4. Evidence details — Documents, Authorities, Signals, Audit tabs
5. Suggested next step — clear action

---

## 8. API Endpoints
- GET /api/v1/shipments/{id}/analysis/items/{item_id}/evidence
- GET /api/v1/documents/{id}/pages/{page_number}
- GET /api/v1/authorities/{id}
- POST /api/v1/shipments/{id}/analysis/items/{item_id}/override

---

## 9. Decision-Safe Copy
Use: Alternative HTS identified, Evidence strength, Review level, Supporting evidence, Conflicting evidence, Suggested next step.
Avoid: AI thinks, model confidence, best guess, probably, maybe right.

# NECO classification & customs — repo-backed system map

This document traces **actual** code paths (not shipment-specific guesses). File paths are relative to the repository root.

---

## 1. PRODUCT-FAMILY ASSIGNMENT

* **Entry point(s):** `ClassificationEngine.generate_alternatives` → `ProductAnalyzer.analyze` (`backend/app/engines/classification/engine.py`, `backend/app/engines/classification/product_analysis.py`). After clarification merge, `identify_product_family` is called again (`engine.py` ~96–106).
* **Files involved:** `backend/app/engines/classification/product_analysis.py`, `backend/app/engines/classification/required_attributes.py`, `backend/app/engines/classification/chapter_clusters.py`, `backend/app/engines/classification/attribute_maps.py`
* **Main functions/classes:** `ProductAnalyzer.analyze`, `identify_product_family`, `get_required_attributes`, `get_chapter_numbers`
* **Current control flow:** Description (+ optional COO) → `ProductAnalyzer` extracts attributes → `identify_product_family(description, extracted_attributes)` → `ProductFamily` enum → `get_required_attributes` populates `missing_required_attributes` → engine may short-circuit to `CLARIFICATION_REQUIRED` before retrieval.
* **Current decision rules:** Pure keyword heuristics in `identify_product_family` (order matters: computing tokens first, then audio, apparel, containers, medical, networking, power, consumer electronics, generic electronics, etc.). `UNKNOWN` has **no** required attributes (`REQUIRED_ATTRIBUTES[UNKNOWN] == []`).
* **Database tables / models:** None for family itself; family is embedded in classification result JSON / metadata on each run.
* **API endpoints involved:** Indirect — any path that calls `generate_alternatives` (`POST /api/v1/shipments/{id}/analyze`, Celery task).
* **UI components involved:** Indirect — analysis tab renders classification payload; clarification UI driven by questions in response.
* **Failure modes:** Mis-keyworded descriptions route to wrong family → wrong required attributes → wrong clarification set or premature `UNKNOWN` with **zero** gates. Product names containing “monitor” can pull toward `CONSUMER_ELECTRONICS`; “bottle” before food check routes to `CONTAINERS`.
* **Why this is architecturally wrong:** Family is a **static lexicon** over free text, not calibrated to tariff nomenclature or importer vocabulary; order-dependent rules are opaque to users and hard to audit.
* **Minimum safe fix:** Version the family rules; add explicit overrides per org/product line; log `product_family` + matched keyword in `metadata` for every run.
* **Longer-term redesign:** Train or rules-engine family from labeled data + optional user-declared category; separate “marketing description” from “technical attributes” inputs.
* **Verification steps:** Unit tests on `identify_product_family` matrix; golden fixtures for edge strings; assert `missing_required_attributes` matches family in integration tests.

---

## 2. DOCUMENT INGESTION AND DOCUMENT TYPING

* **Entry point(s):** `POST /api/v1/shipment-documents/presign` → client PUT → `POST /api/v1/shipment-documents/confirm` (`backend/app/api/v1/shipment_documents.py`). Extraction runs during **analysis**, not at confirm: `ShipmentAnalysisService._parse_documents_and_build_evidence_map` calls `DocumentProcessor.process_document` (`backend/app/services/shipment_analysis_service.py` ~1276+, `backend/app/engines/ingestion/document_processor.py`). Optional `POST .../reprocess` triggers `DocumentProcessor` + `apply_ingestion_metadata_to_shipment_document`.
* **Files involved:** `backend/app/api/v1/shipment_documents.py`, `backend/app/services/s3_upload_service.py`, `backend/app/engines/ingestion/document_processor.py`, `backend/app/services/shipment_analysis_service.py` (`apply_ingestion_metadata_to_shipment_document`, enrichment helpers)
* **Main functions/classes:** `S3UploadService.confirm_upload`, `DocumentProcessor.process_document`, `_parse_documents_and_build_evidence_map`
* **Current control flow:** Confirm creates `ShipmentDocument` with `processing_status="UPLOADED"` and **user-selected** `document_type` — no auto-classification at upload. On analysis, each doc is read from local mock path or S3-backed path, `process_document(path, document_type_hint=doc.document_type.value)`, results stored on `doc.extracted_text`, `doc.structured_data`, `processing_status`.
* **Current decision rules:** MIME/extension allowlist in `S3UploadService`; `document_type` is **request payload**, not inferred. Parser behavior branches on hint + file type inside `DocumentProcessor`.
* **Database tables / models:** `ShipmentDocument` (`document_type`, `structured_data`, `extracted_text`, `processing_status`, etc.)
* **API endpoints involved:** `/shipment-documents/presign`, `/confirm`, `GET .../documents`, `PATCH .../data-sheet-confirmation`, `GET .../table-preview`, `GET .../download-url`, `POST .../reprocess`
* **UI components involved:** `frontend/src/components/shipment-tabs/documents-tab.tsx` (upload flow, document list)
* **Failure modes:** Wrong `document_type` at upload → wrong extraction templates / line-item shapes. Confirm does not validate structured extraction. Local dev: file path fallbacks can silently miss files (`files_not_found` / warnings in evidence map).
* **Why this is architecturally wrong:** **Typing is a user label**, not a validated output of ingestion; no second-pass validation that PDF content matches declared type.
* **Minimum safe fix:** Post-upload validation hook (e.g. minimum signals for CI vs ES) or wizard that forces reclassify before analysis.
* **Longer-term redesign:** Automatic document classification model + confidence; store classifier version on row.
* **Verification steps:** Upload same PDF as different types and diff `structured_data`; assert reprocess updates DB; integration test for evidence_map warnings.

---

## 3. COMMERCIAL INVOICE LINE-ITEM IMPORT

* **Entry point(s):** `ShipmentAnalysisService.run_full_shipment_analysis` → `_import_line_items_from_documents` (`backend/app/services/shipment_analysis_service.py` ~611–614, 1537+).
* **Files involved:** `shipment_analysis_service.py` (import + merge), `ShipmentDocument.structured_data` shape from ingestion
* **Main functions/classes:** `_import_line_items_from_documents`, helpers `_clean_hts`, `_clean_coo`, `_desc_hash`
* **Current control flow:** Scan all `shipment.documents` with `structured_data.line_items`; split into `es_items` / `ci_items` by `document_type`; merge lines by line number with **ES winning** per field; match to existing `ShipmentItem` by description hash or `hts:country` key; merge or create rows; then `_auto_link_line_items_to_source_documents`.
* **Current decision rules:** Line numbers coerced to int; description/HTS/COO/value/qty merged with ES precedence; conflicts recorded when HTS differs on matched item.
* **Database tables / models:** `ShipmentItem` (insert/update), `ShipmentDocument` (read-only)
* **API endpoints involved:** No direct REST for import — runs inside analyze pipeline. Related: `POST .../line-items-from-selection` for manual column mapping path (UI).
* **UI components involved:** `analysis-tab.tsx` (`line-items-from-selection`, extract-preview)
* **Failure modes:** Empty `line_items` in structured_data → no import; duplicate descriptions hash-collide; truncated labels (255) can merge wrong lines.
* **Why this is architecturally wrong:** Import is **tightly coupled** to extraction quality and document type chosen at upload; no stable external ID from source document line.
* **Minimum safe fix:** Persist source `(document_id, line_number)` on `ShipmentItem` or link table for traceability (see §4).
* **Longer-term redesign:** First-class import job with reconciliation UI and conflict resolution.
* **Verification steps:** Test fixtures with ES+CI same shipment; assert merge precedence; assert `import_summary` counts in `result_json`.

---

## 4. ITEM-TO-DOCUMENT LINKING / PROVENANCE

* **Entry point(s):** `_auto_link_line_items_to_source_documents` after import (`shipment_analysis_service.py` ~1703–1766). Manual/API: `POST /api/v1/shipments/{id}/item-document-links`, `DELETE .../item-document-links/{link_id}` (`backend/app/api/v1/shipments.py`). Evidence strings: `_get_item_data_sheet_text`, `_build_item_evidence_used` (same service).
* **Files involved:** `backend/app/models/shipment_item_document.py`, `shipment_analysis_service.py`, `backend/app/api/v1/shipments.py`
* **Main functions/classes:** `_auto_link_line_items_to_source_documents`, `ShipmentItemDocument` rows with `ItemDocumentMappingStatus.AUTO`
* **Current control flow:** For CI/ES docs, match each structured line description to an item by `_desc_hash` or exact label; insert `ShipmentItemDocument` if missing. Item description for classification can append data sheet text when linked.
* **Current decision rules:** Hash / string equality only; no fuzzy match, no line-number join to `ShipmentItem`.
* **Database tables / models:** `ShipmentItemDocument` (`shipment_item_id`, `shipment_document_id`, `mapping_status`, org/shipment ids)
* **API endpoints involved:** `POST .../item-document-links`, `DELETE .../item-document-links/{link_id}`, `GET .../analysis/items/{item_id}/evidence` (referenced from analysis-tab)
* **UI components involved:** `analysis-tab.tsx` (evidence drawer, supplemental evidence uploads)
* **Failure modes:** New `ShipmentItem` rows from import have **no link** until hash matches; manual items may never auto-link. Line number not stored on item → provenance easily lost. Multiple docs with same description → ambiguous link.
* **Why this is architecturally wrong:** Provenance is **derived** from brittle string match, not from stable foreign keys established at import.
* **Minimum safe fix:** Store `source_document_id` + `source_line_index` on import; auto-link using those keys.
* **Longer-term redesign:** Graph of evidence nodes with weights and user-confirmed mappings.
* **Verification steps:** DB query for `ShipmentItemDocument` after analysis; tests where description varies slightly (should fail today).

---

## 5. CLASSIFICATION ANALYSIS PIPELINE

* **Entry point(s):** `POST /api/v1/shipments/{id}/analyze` → `AnalysisOrchestrationService.start_analysis` → Celery `app.tasks.analysis.run_shipment_analysis` → `execute_shipment_analysis_pipeline` (`backend/app/tasks/analysis.py`, `backend/app/services/analysis_pipeline.py`). Sync/dev paths also call `execute_shipment_analysis_pipeline` or inline service depending on settings.
* **Files involved:** `analysis_orchestration_service.py`, `analysis_pipeline.py`, `shipment_analysis_service.py`, `rule_based_classifier.py` (bias)
* **Main functions/classes:** `execute_shipment_analysis_pipeline`, `ShipmentAnalysisService.run_full_shipment_analysis`, `RuleBasedClassifier.classify`, `_apply_rule_based_heading_bias`
* **Current control flow:** Eligibility + entitlement → analysis RUNNING → `run_full_shipment_analysis`: load item-doc links → parse documents / evidence map → import line items → **per item** `classification_engine.generate_alternatives` + rule classifier (mode: enforce/shadow/off) → duty/PSC/regulatory → assemble `result_json` → `analysis_pipeline` adds provenance, persists `ReviewRecord`, `Analysis.result_json`, regulatory rows.
* **Current decision rules:** `CLASSIFICATION_RULE_MODE` controls whether rule output overwrites/biases ML ranking; `SPRINT12_FAST_ANALYSIS_DEV` short-circuits to `_build_fast_local_analysis`.
* **Database tables / models:** `Analysis`, `Shipment`, `ReviewRecord`, `RegulatoryEvaluation`, `ShipmentItem`, documents
* **API endpoints involved:** `POST .../analyze`, `GET .../analysis-status`, orchestration internals
* **UI components involved:** `analysis-tab.tsx` (polls `analysis-status`, posts analyze)
* **Failure modes:** Single item exception → error dict for that item only; fast path changes semantics in dev. Blockers list vs review_record status can diverge in edge cases.
* **Why this is architecturally wrong:** One mega-method orchestrates I/O, ML, rules, and persistence; feature flags alter behavior drastically.
* **Minimum safe fix:** Isolate “engine step” from “persist step”; single feature matrix tested in CI.
* **Longer-term redesign:** Stage-based pipeline with idempotent steps and explicit state machine per shipment.
* **Verification steps:** `pytest` on pipeline; compare `result_json` shape for celery vs sync with same fixture.

---

## 6. SIMILARITY / RETRIEVAL / RANKING LOGIC

* **Entry point(s):** `ClassificationEngine._generate_candidates` and related SQL using PostgreSQL `similarity()` (`backend/app/engines/classification/engine.py` ~869–1114+). Scoring: `_score_candidate`, `_calculate_similarity` for reranking/penalties.
* **Files involved:** `engine.py`, HTS description tables via ORM/raw SQL, `status_model.py` (gates metadata)
* **Main functions/classes:** `_generate_candidates`, `_score_candidate`, `_calculate_similarity`, pg_trgm `ORDER BY similarity(...)`
* **Current control flow:** After product analysis passes clarification gate, retrieval builds candidate list from tariff text similarity, then layered scoring (including family-specific penalties e.g. audio).
* **Current decision rules:** Lexical similarity thresholds appear in engine metadata (`best_similarity`, `threshold_used` strings like `0.18` / `FAMILY_AWARE_0.16`), family-aware branches for 8518, ambiguity_reason strings for REVIEW_REQUIRED.
* **Database tables / models:** HTS reference data (trigram-indexed), not application business tables for scoring
* **API endpoints involved:** Indirect via classification output
* **UI components involved:** Displays `classification_memo` / metadata in analysis UI
* **Failure modes:** Short or noisy descriptions → weak pg_trgm scores; penalty heuristics can suppress correct chapters; multilingual text poorly served.
* **Why this is architecturally wrong:** **Lexical** similarity to tariff language is used as a proxy for legal correctness; scores are blended with ad hoc penalties.
* **Minimum safe fix:** Log retrieval query + top-N codes + scores in audit table for replay.
* **Longer-term redesign:** Embeddings + learned reranker with calibrated probabilities; separate “retrieval” from “legal determination.”
* **Verification steps:** Benchmark harness (`backend/run_benchmark.py`, tests); frozen DB snapshot for similarity tests.

---

## 7. REQUIRED-ATTRIBUTES / CLARIFICATION-QUESTION LOGIC

* **Entry point(s):** `ClassificationEngine.generate_alternatives` — after `ProductAnalyzer.analyze`, if `missing_required` non-empty, immediate return with questions (`engine.py` ~137–169+). `required_attributes.py` defines families, attributes, `get_question_for_attribute`. Ordering: `_order_questions_by_chapter_impact`.
* **Files involved:** `backend/app/engines/classification/required_attributes.py`, `engine.py`, `chapter_clusters.py`
* **Main functions/classes:** `get_required_attributes`, `get_question_for_attribute`, `identify_product_family`, `_order_questions_by_chapter_impact`
* **Current control flow:** Missing attrs → `CLARIFICATION_REQUIRED` payload with questions; **no** candidate retrieval. User answers passed as `clarification_responses` on re-run (`analyze` body); merged into `product_analysis` in engine.
* **Current decision rules:** Template strings in `ATTRIBUTE_QUESTIONS`; family-specific lists; `UNKNOWN` skips clarification entirely.
* **Database tables / models:** Clarifications live in request/response JSON, not normalized DB (unless persisted inside `Analysis.result_json`).
* **API endpoints involved:** `POST .../analyze` with body containing per-item clarification map
* **UI components involved:** Analysis tab must collect answers — flows tied to classification payload
* **Failure modes:** Wrong family → wrong questions; `UNKNOWN` → no questions but weak retrieval downstream; user typos in answers not validated.
* **Why this is architecturally wrong:** Question set is **one-size per family**, not driven by candidate-space uncertainty.
* **Minimum safe fix:** Persist clarification schema version in `result_json`.
* **Longer-term redesign:** Dynamic questions from contrastive candidates (active learning).
* **Verification steps:** Tests for short-circuit ordering; E2E re-run with mocked responses.

---

## 8. EXPLANATION-GENERATION LOGIC

* **Entry point(s):** `generate_review_explanation` (`backend/app/engines/classification/review_explanation.py`) called from classification engine when status is `REVIEW_REQUIRED` (see `engine.py` branches that assemble `review_explanation` / structured reasons).
* **Files involved:** `review_explanation.py`, `status_model.py`, `engine.py` (assembly)
* **Main functions/classes:** `generate_review_explanation`
* **Current control flow:** Deterministic string templates from gates: similarity bands (0.18–0.25), `analysis_confidence < 0.7`, audio 8518 multi-subheading, `reason_code` family-aware gate, `STANDARD_GATE` multi-candidate, `top_candidate_score < 0.25`. Fallback generic message if empty.
* **Current decision rules:** Threshold comparisons hard-coded (0.18, 0.25, 0.7); special case `product_family == "audio_devices"`.
* **Database tables / models:** None — embedded in JSON
* **API endpoints involved:** Via classification in `result_json`
* **UI components involved:** Analysis tab displays memo / reasons
* **Failure modes:** Generic catch-all reason masks true driver; audio-specific branch irrelevant for non-audio.
* **Why this is architecturally wrong:** Explanations duplicate threshold logic already in `status_model` / engine → drift risk.
* **Minimum safe fix:** Single source of truth struct produced by `determine_status` passed into explanation builder.
* **Longer-term redesign:** Rule IDs with localization and analytics on which explanations lead to corrections.
* **Verification steps:** Snapshot tests for `generate_review_explanation` inputs/outputs.

---

## 9. STATUS / CONFIDENCE / FAILURE GATING

* **Entry point(s):** `determine_status` (`backend/app/engines/classification/status_model.py`); consumed in `ClassificationEngine` when finalizing classification. Related: `reporting_service` trust memo (`backend/app/services/reporting_service.py` ~75–79) uses 0.18 for reporting bands.
* **Files involved:** `status_model.py`, `engine.py` (passes `best_similarity`, `top_candidate_score`, `analysis_confidence`, `candidates_exist`), `reporting_service.py`
* **Main functions/classes:** `determine_status`, `ClassificationStatus` enum, `STATUS_DEFINITIONS`
* **Current control flow:** Clarification first → SUCCESS if all thresholds met → if `best_similarity >= 0.18` and not SUCCESS → REVIEW_REQUIRED → if candidates exist → REVIEW_REQUIRED for low similarity → else NO_CONFIDENT_MATCH. **Note:** `NO_CONFIDENT_MATCH` is **not** returned solely for low lexical similarity when candidates exist (see comments in `status_model.py` ~111–139).
* **Current decision rules:** SUCCESS requires `best_similarity >= 0.25`, `top_candidate_score >= 0.20`, `analysis_confidence >= 0.7`, `candidates_exist`.
* **Database tables / models:** `ClassificationAudit` model references threshold_used; persisted via audit flows where used
* **API endpoints involved:** Classification status embedded per item in analysis results; trust workflow may summarize
* **UI components involved:** Analysis tab, trust indicators
* **Failure modes:** Divergence between engine narrative (`ambiguity_reason`) and `determine_status`; reporting_service still buckets by 0.18 for display.
* **Why this is architecturally wrong:** Multiple modules re-implement overlapping threshold semantics.
* **Minimum safe fix:** Export one `StatusContext` dataclass from engine; reuse in reporting and explanations.
* **Longer-term redesign:** Calibrated probabilities instead of fixed cutoffs.
* **Verification steps:** Unit tests for `determine_status` matrix (`backend/scripts/test_review_required.py`, pytest cases).

---

## 10. API RESPONSES USED BY THE UI

* **Entry point(s):** Frontend `useApiClient` in shipment views.
* **Files involved:** `backend/app/api/v1/shipments.py`, `backend/app/api/v1/shipment_documents.py`, frontend `shipment-detail-shell.tsx`, `analysis-tab.tsx`, `documents-tab.tsx`
* **Main functions/classes:** FastAPI route handlers returning `result_json` shapes from `ShipmentAnalysisService`
* **Current control flow:** Documents: presign/confirm/list/preview/download. Analysis: `extract-preview`, `POST /analyze`, `GET /analysis-status`, `GET /trust-workflow`, `PSC` alerts, `line-items-from-selection`, per-item supplemental evidence, item evidence endpoint.
* **Current decision rules:** HTTP errors surface seed/auth issues; `analysis-status` drives polling UX.
* **Database tables / models:** Reads `Analysis`, `Shipment`, items, documents
* **API endpoints involved:** See grep hits in `analysis-tab.tsx`: `/api/v1/shipments/{id}/trust-workflow`, `extract-preview`, `analysis-status`, `psc-radar/alerts`, `analyze`, `line-items-from-selection`, `items/{id}/supplemental-evidence`, `analysis/items/{id}/evidence`
* **UI components involved:** `analysis-tab.tsx`, `documents-tab.tsx`, `shipment-detail-shell.tsx`, `overview-tab.tsx`, `reviews-tab.tsx`, `exports-tab.tsx`
* **Failure modes:** Schema drift between backend `result_json` and frontend types; optional fields missing → UI crashes if not guarded.
* **Why this is architecturally wrong:** **Ad hoc JSON** without shared OpenAPI models for nested classification.
* **Minimum safe fix:** Pydantic response models for `result_json` subsets consumed by UI.
* **Longer-term redesign:** Versioned DTO with migration layer.
* **Verification steps:** Typecheck frontend against generated types; contract tests.

---

## 11. UI COMPONENTS — MAPPING, CLARIFICATIONS, ANALYSIS RESULTS

* **Entry point(s):** Shipment route loads shell + tabs.
* **Files involved:** `frontend/src/components/shipment-tabs/analysis-tab.tsx` (primary), `documents-tab.tsx`, `frontend/src/components/shipment-detail-shell.tsx`
* **Main functions/classes:** React components; hooks polling `analysis-status`
* **Current control flow:** User uploads docs → confirms → optional table selection / line-items-from-selection → extract-preview → analyze → poll status → render items with classification memo, duty, PSC, blockers, evidence drawer (`analysis/items/.../evidence`), supplemental evidence upload.
* **Current decision rules:** Client-side guards on missing `apiGet`; pre-compliance vs compliance modes affect copy.
* **Database tables / models:** N/A (via API)
* **API endpoints involved:** Listed in §10
* **UI components involved:** `analysis-tab.tsx` (line items, analyze, trust workflow, evidence, supplemental uploads), `documents-tab.tsx` (upload pipeline), `reviews-tab.tsx`, `overview-tab.tsx`
* **Failure modes:** Stale polling; large `result_json` rendering perf; clarification UX if backend returns questions but UI does not collect answers consistently.
* **Why this is architecturally wrong:** Single large component aggregates orchestration, mapping, and display concerns.
* **Minimum safe fix:** Split “analysis orchestration” from “item row presentation”; formalize clarification subflow state machine.
* **Longer-term redesign:** Dedicated classification review workspace with immutable run history.
* **Verification steps:** Playwright flows against seeded shipment; snapshot of API responses.

---

## DEPENDENCY MAP (RUNTIME ORDER)

1. **Upload:** `presign` → S3 PUT → `confirm` → `ShipmentDocument` row (`processing_status=UPLOADED`), user-selected `document_type`, eligibility recompute (`s3_upload_service.py`, `shipment_documents.py`).
2. **Document extraction (not at confirm):** `run_full_shipment_analysis` → `_parse_documents_and_build_evidence_map` → `DocumentProcessor.process_document` → `doc.structured_data`, `extracted_text`, `processing_status` (`shipment_analysis_service.py`).
3. **Item creation:** `_import_line_items_from_documents` merges ES/CI `line_items` into `ShipmentItem` (`shipment_analysis_service.py`).
4. **Family routing:** For each item, `generate_alternatives` → `ProductAnalyzer.analyze` → `identify_product_family` / `get_required_attributes` (`engine.py`, `required_attributes.py`).
5. **Clarification selection:** If missing required attrs → return `CLARIFICATION_REQUIRED` with questions — **no retrieval** (`engine.py`).
6. **Candidate generation:** `_generate_candidates` + scoring (`engine.py`); rule classifier may bias (`rule_based_classifier.py`).
7. **Status / result:** `determine_status` + explanations (`status_model.py`, `review_explanation.py`); assembled per item in `run_full_shipment_analysis`.
8. **Persistence:** `execute_shipment_analysis_pipeline` writes `Analysis.result_json`, `ReviewRecord`, regulatory rows (`analysis_pipeline.py`).
9. **UI rendering:** `analysis-tab.tsx` polls `analysis-status`, displays `result_json` fields (classification, memo, blockers, PSC, evidence).

---

## INVENTORY: ALL PLACES SIMILARITY IS USED

| Location | Role |
|----------|------|
| `backend/app/engines/classification/engine.py` | pg_trgm `similarity()` in SQL; `ORDER BY similarity`; `_calculate_similarity`; `_score_candidate`; metadata `best_similarity` |
| `backend/app/engines/classification/status_model.py` | `determine_status` uses `best_similarity` vs 0.18/0.25 |
| `backend/app/engines/classification/review_explanation.py` | Narrative thresholds 0.18, 0.25 |
| `backend/app/services/shipment_analysis_service.py` | `_memo_best_similarity` reads metadata |
| `backend/app/services/reporting_service.py` | Trust bands using 0.18 |
| `backend/app/engines/psc_radar.py` | `final_score >= 0.25` heuristic |
| `backend/run_benchmark.py`, scripts | Diagnostic prints |

---

## INVENTORY: HARD THRESHOLDS THAT BLOCK OR STEER REASONING

| Location | Threshold | Effect |
|----------|-----------|--------|
| `status_model.py` | `best_similarity >= 0.25`, `top_candidate_score >= 0.20`, `analysis_confidence >= 0.7` | Gates SUCCESS |
| `status_model.py` | `best_similarity >= 0.18` | Branches to REVIEW_REQUIRED when below SUCCESS |
| `engine.py` | 0.18, 0.25, 0.16 (8518 family-aware), penalties | Ambiguity strings; family-aware gate |
| `review_explanation.py` | 0.18, 0.25, 0.7 | Text explanations |
| `psc_radar.py` | 0.25 on candidate score | Radar confidence |
| `reporting_service.py` | 0.18 / 0.25 | Memo status buckets |

---

## INVENTORY: DOCUMENT PROVENANCE LOSS

| Location | Issue |
|----------|-------|
| `s3_upload_service.confirm_upload` | No extraction or line linkage at upload |
| `_import_line_items_from_documents` | New items created without `document_id` / line index FK |
| `_auto_link_line_items_to_source_documents` | Hash/string match only; fragile |
| `_parse_documents_and_build_evidence_map` | Warnings on missing local files; may skip content |
| Evidence helpers | If no link, data sheet text may not attach to description |

---

## INVENTORY: FAMILY ASSIGNMENT RISK POINTS

| Location | Risk |
|----------|------|
| `required_attributes.py` `identify_product_family` | Order-sensitive keywords; `UNKNOWN` clears requirements |
| `chapter_clusters.py` / `attribute_maps.py` | Chapter hints tied to family |
| `engine.py` clarification merge | Recomputes family after user answers — can shift requirements mid-flow |
| `rule_based_classifier.py` | Heading rules may conflict with family |

---

## INVENTORY: SHIPMENT-SPECIFIC OR BRITTLE LOGIC

| Location | Note |
|----------|------|
| `shipment_analysis_service.py` | `_build_fast_local_analysis`, `SPRINT12_*` dev flags, origin mismatch blockers, PSC threshold `PSC_DUTY_THRESHOLD` |
| `engine.py` | Audio family penalties; 8518-specific gates; product-family-specific branches |
| `review_explanation.py` | `audio_devices` + 8518 subheading logic |
| `required_attributes.py` | Token list includes model-specific strings (e.g. `xd670`) |
| `analysis_pipeline.py` / `build_analysis_provenance` | Dev flags in provenance JSON |

---

*End of document.*

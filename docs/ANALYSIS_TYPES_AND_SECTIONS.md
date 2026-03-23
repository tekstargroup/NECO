# Analysis Types and Split Sections

## What analysis types exist?

The backend runs **four distinct analysis engines** (plus a prerequisite step). Today they run together in one "Run analysis" call.

| # | Name | What it does | Depends on | Where in code |
|---|------|--------------|------------|----------------|
| 0 | **Documents / Evidence** | Parses PDFs and Excel/CSV, builds evidence map, imports line items from Entry Summary and Commercial Invoice. | Nothing (first step) | `_parse_documents_and_build_evidence_map`, `_import_line_items_from_documents` |
| 1 | **Classification** | HTS classification: suggests alternative HTS codes per line item (LLM). | Line items, optional declared HTS | `ClassificationEngine.generate_alternatives` |
| 2 | **Duty** | Duty resolution: resolves duty rates (general/special) per HTS code. | HTS code (from declared or classification) | `resolve_duty` (scripts.duty_resolution) |
| 3 | **PSC (PSC Radar)** | PSC risk signals per item (e.g. Section 301, 232). | HTS code, value, quantity | `PSCRadar.analyze` |
| 4 | **Regulatory** | Regulatory applicability (e.g. CBP, FDA) per item. | Document evidence, HTS | `RegulatoryApplicabilityEngine.evaluate_regulatory_applicability` |

**Enrichment** is wired but currently minimal (TODO in the service).

So you effectively have **4 runnable analysis types** after documents: **Classification**, **Duty**, **PSC**, **Regulatory**. Documents/Evidence is the prerequisite (run first or as part of "full" run).

---

## Can we run them separately?

**Today: no.** The API has a single `POST /api/v1/shipments/{id}/analyze` that runs the full pipeline (documents → classification → duty → PSC → regulatory) in one go. There is no parameter or endpoint to run only classification, or only duty, etc.

**To support running them separately you’d need:**

1. **Backend**
   - Option A: One endpoint with a `steps` (or `only`) query/body, e.g.  
     `POST .../analyze?steps=documents,classification` or `POST .../analyze` with body `{ "steps": ["documents", "classification"] }`.
   - Option B: Separate endpoints, e.g.  
     `POST .../analyze/documents`, `POST .../analyze/classification`, `POST .../analyze/duty`, `POST .../analyze/psc`, `POST .../analyze/regulatory`.
   - The service would need to:
     - Run only the requested steps.
     - Merge partial results into `result_json` (or a per-step store) so the UI can show each section even when others haven’t run.
   - Dependencies: Classification can run with just line items. Duty needs HTS (declared or from classification). PSC needs HTS + value/quantity. Regulatory needs document evidence. So "run classification only" is valid; "run duty only" is valid if you already have HTS (e.g. from a previous classification run or declared).

2. **Frontend**
   - **4 sections** in the Analysis tab, e.g.:
     - **1. Documents & Evidence** — Run "Process documents" only; show evidence map, line items, extraction errors.
     - **2. Classification** — Run classification only; show HTS alternatives per item.
     - **3. Duty & PSC** — Run duty and PSC (or separate 3a Duty / 3b PSC); show money impact and PSC Radar.
     - **4. Regulatory** — Run regulatory only; show regulatory applicability per item.
   - Each section could have:
     - A **Run [X]** button (calls the new API with that step only).
     - The existing result display for that part of `result_json` (or partial result from the new API).
   - Optional: "Run all" still calls the current full analyze and fills all sections.

---

## Proposed 4-section layout in Analysis tab

| Section | Label | Run action | Shows |
|---------|--------|------------|--------|
| 1 | Documents & Evidence | "Process documents" | Evidence map, line items, extraction errors, table preview |
| 2 | Classification | "Run classification" | HTS alternatives per item (Outcome summary + Structural where classification is used) |
| 3 | Duty & PSC | "Run duty & PSC" | Money impact (duty), PSC Radar (risk) |
| 4 | Regulatory | "Run regulatory" | Regulatory applicability per item |

You could keep the current single "Analyze Shipment" / "Run analysis" that runs all steps, and add per-section "Run [X]" that call the new step-scoped API. Results would be merged so that e.g. after "Run classification" only, sections 2–4 show "Run [section] to see results" until those steps are run.

---

## Summary

- **Four analysis types you can conceptually run separately:** Documents/Evidence, Classification, Duty (and PSC), Regulatory. Today they only run together.
- **To run them separately:** Add backend support (e.g. `steps` or separate endpoints) and a 4-section Analysis UI with a "Run [X]" per section and display of partial `result_json` (or equivalent) per section.

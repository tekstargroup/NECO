# Upload-time column mapping (MailChimp-style)

## Goal

When users upload Excel or CSV (e.g. Commercial Invoice), NECO should **confirm which columns and rows are line items** before running analysis—similar to MailChimp’s “match your columns” step when you upload a list.

## Current behavior

- **Analysis tab:** If analysis finds **no line items**, we show a table (from `evidence_map.documents[].table_preview`) and ask the user to **select which rows are line items**, then “Use selected rows” to create shipment items. This recovers when auto-extraction fails.
- **Table preview API:** `GET /api/v1/shipment-documents/{document_id}/table-preview` returns `{ columns, rows, filename }` for Excel/CSV so the UI can show a preview after upload.

## Proposed: confirm columns at upload

1. **After upload** of an Excel/CSV document, before or alongside “Documents” list, show a step:
   - “Confirm which columns are line item fields”
   - Show first N rows (from `table-preview`) and dropdowns per column: **Description**, **Qty**, **Unit price**, **Total / Extended value**, **HTS code**, **Country of origin**, or **Skip**.
2. **Store mapping** on the document (e.g. `column_mapping` JSON: `{ "Description": "description", "Qty": "quantity", "Extended Value": "total", ... }`). This may require a DB migration to add `ShipmentDocument.column_mapping` (JSONB).
3. **Use in extraction:** In `document_processor` (and Excel fallback), when building `line_items`, use `column_mapping` when present so user-chosen column roles override auto-detection.

## Implementation notes

- **Backend:** Add `column_mapping` to `ShipmentDocument` (migration), `PATCH /api/v1/shipment-documents/{id}` to accept `column_mapping`, and pass it into the analysis document processor.
- **Frontend:** After upload (or when opening a doc), call `GET .../table-preview`, show modal “Map columns” with dropdowns, then PATCH `column_mapping` on save.
- **Processor:** In `_ensure_line_items_from_excel` / `_build_line_items_from_unnamed_header`, if the document has `column_mapping`, use it to map column names to semantic keys (description, quantity, total, etc.) instead of keyword matching.

This gives users control when file layouts vary and reduces “no line items” runs.

# NECO Bulk Import Guide

**Purpose:** Import multiple shipments at once by uploading a zip file with a structured folder layout.

---

## Quick Start

1. Download the template: `docs/bulk_import_template/` (or create a zip from it)
2. Create one subfolder per shipment
3. Place Entry Summary (PDF) and Commercial Invoice (Excel/CSV) in each folder
4. Zip the folder and upload via NECO Bulk Import

---

## Folder Structure

```
my_shipments.zip
  shipment_1/
    ES_561056.pdf
    CI_241211-560386.xlsx
  shipment_2/
    ES_561057.pdf
    CI_241212.xlsx
  PO_560388/
    entry_summary.pdf
    commercial_invoice.xlsx
```

Each subfolder = one shipment. NECO creates a shipment per folder and attaches the documents.

---

## Document Types

| Type | Formats | Required |
|------|---------|----------|
| Entry Summary | PDF | Yes (at least one per shipment) |
| Commercial Invoice | .xlsx, .xls, .csv | Yes (at least one per shipment) |

NECO detects document type by content. File names can be anything.

---

## Naming Suggestions

- **Folders:** `shipment_1`, `PO_560386`, `Entry_1234567890` — use what fits your workflow
- **Entry Summary:** `ES_561056.pdf`, `entry_summary.pdf`
- **Commercial Invoice:** `CI_241211.xlsx`, `commercial_invoice.xlsx`

---

## Bulk Import Feature (Sprint 18)

When the Bulk Import feature is implemented:

- **API:** `POST /api/v1/shipments/bulk-import` (multipart zip)
- **UI:** Drag-drop or file picker for zip upload
- **Flow:** NECO unzips, groups by folder, creates shipments, runs analysis
- **Result:** List of created shipments with links; per-shipment prompts for missing info

---

## Template Location

`docs/bulk_import_template/` — Copy this folder, add your files, and zip.

To create a downloadable example zip:
```bash
cd docs
zip -r bulk_import_example.zip bulk_import_template/
```

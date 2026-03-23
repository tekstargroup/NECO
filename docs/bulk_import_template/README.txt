NECO Bulk Import Template
========================

Use this folder structure when preparing a zip file for bulk import into NECO.
Each subfolder represents one shipment. NECO will create one shipment per folder
and analyze all at once.

FOLDER STRUCTURE
----------------

  bulk_import_template/
    shipment_1/
      ES_561056.pdf          <- Entry Summary (CBP Form 7501)
      CI_241211-560386.xlsx  <- Commercial Invoice
    shipment_2/
      ES_561057.pdf
      CI_241212.xlsx
    shipment_3/
      ...

REQUIREMENTS
------------

- Each shipment folder must contain at least:
  - One Entry Summary (PDF)
  - One Commercial Invoice (Excel or CSV)

- File names can be anything; NECO detects document type by content.
  Suggested naming: ES_<entry_number>.pdf, CI_<invoice_number>.xlsx

- Supported formats:
  - Entry Summary: PDF
  - Commercial Invoice: .xlsx, .xls, .csv

HOW TO USE
----------

1. Copy this template folder
2. Create one subfolder per shipment (e.g. shipment_1, shipment_2, or use PO numbers: PO_560386, PO_560387)
3. Place your Entry Summary PDF and Commercial Invoice in each folder
4. Zip the entire folder: zip -r my_shipments.zip bulk_import_template/
5. In NECO, use the Bulk Import feature to upload the zip
6. NECO will create each shipment, attach documents, and run analysis

NAMING CONVENTIONS (optional)
-----------------------------

- shipment_<number>  - Simple sequential
- PO_<po_number>     - Use PO from your system
- Entry_<entry_no>   - Use CBP entry number

NECO infers shipment grouping from folder structure. Each folder = one shipment.

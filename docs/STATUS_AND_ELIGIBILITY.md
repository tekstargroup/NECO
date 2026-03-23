# Shipment Status & Eligibility

## Status Flow (when each happens)

| Status | When it happens |
|--------|-----------------|
| **DRAFT** | Shipment created; no documents yet, or documents don't satisfy eligibility |
| **READY** | Eligible documents present (Entry Summary OR Commercial Invoice + Data Sheet) |
| **ANALYZING** | User clicked Analyze; analysis job queued or running |
| **COMPLETE** | Analysis finished successfully |
| **REFUSED** | Analysis refused (e.g. insufficient documents, entitlement exceeded) |
| **FAILED** | Analysis ran but failed (error) |

## Eligibility Requirements

**Eligible if either:**
1. **Entry Summary** document present, OR
2. **(Commercial Invoice + Data Sheet)** both present

**Displayed fields:**
- **Date added** — When the shipment was created (`created_at`)
- **Entry Date** — From references (key `ENTRY_DATE` or `ENTRY`) if set
- **Eligibility path** — Which rule was satisfied: `ENTRY_SUMMARY` or `COMMERCIAL_INVOICE_DATA_SHEET`

## Document Types

- Entry Summary
- Commercial Invoice
- Packing List
- Data Sheet

# Sprint 12 Implementation Plan

## Status: Foundation Models Created

Created initial database models for Sprint 12:
- `Organization` - Multi-tenant organizations (mapped to Clerk orgs)
- `Membership` - User-Organization membership with roles (ANALYST default)
- `Shipment` - Primary object for importer workflow
- `ShipmentReference` - Key/value reference pairs (PO, Entry, Invoice, BOL)
- `ShipmentItem` - Items within a shipment

## Next Steps

1. **Continue Database Models**:
   - `ShipmentDocument` - Links documents to shipments with S3 metadata
   - `Analysis` - Analysis runs for shipments
   - `Entitlement` - Monthly entitlement tracking (15 shipments/user/month)

2. **Update User Model**:
   - Add `clerk_user_id` field
   - Add `memberships` relationship

3. **Create Migration 009**:
   - All Sprint 12 tables
   - Proper indexes and constraints
   - FK relationships

4. **Backend Services**:
   - Org-scoped repository pattern
   - Entitlements service
   - Shipments service
   - S3 upload service
   - Analysis orchestration (Celery)

5. **Frontend** (after backend stable):
   - Clerk integration
   - Shipments UI
   - Analysis view (Sprint 11 sections)

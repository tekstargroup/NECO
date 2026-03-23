# Legacy Documents Table - Deprecation Notice

## Status: LEGACY - Entry-Only Workflow

The `documents` table is **legacy** and exists for the Entry-based workflow only (Sprint 1).

**New Shipment workflow (Sprint 12) MUST use `shipment_documents` table only.**

## Constraints (Non-Negotiable)

### Namespace Separation
- ✅ Legacy endpoints: `/api/v1/legacy/*` or `legacy_documents` module
- ✅ New shipment endpoints: `/api/v1/shipments/*` and `/api/v1/shipment-documents/*`
- ❌ No shared "document service" that switches based on inputs

### Storage Segregation
- ✅ Legacy: `UPLOAD_DIR` code path (local filesystem)
- ✅ New: S3 only (presigned uploads)
- ❌ Legacy UPLOAD_DIR disabled for new workflow

### Tenancy Segregation
- ✅ Legacy: `client_id` (old multi-tenant model)
- ✅ New: `organization_id` (Clerk-based multi-tenant)
- ❌ Never join or mix `client_id` and `organization_id`

## Future Migration

TODO: Future sprint to sunset `documents` table:
- Migrate Entry-based workflow to Shipment model
- Archive or migrate legacy documents
- Remove `documents` table

## Table Comparison

| Feature | `documents` (Legacy) | `shipment_documents` (Sprint 12) |
|---------|---------------------|----------------------------------|
| Tenant | `client_id` | `organization_id` |
| Storage | `file_path` (local) | `s3_key` + `sha256_hash` (S3) |
| Linking | `entry_id` | `shipment_id` |
| Workflow | Entry-based | Shipment-based |
| Endpoints | `/api/v1/legacy/*` | `/api/v1/shipments/*` |
| Status | Deprecated | Active |

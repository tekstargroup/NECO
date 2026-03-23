# Sprint 12 Implementation Status

## ✅ Document-Driven Analysis (Closed March 2026)

End-to-end flow: upload Entry Summary + Commercial Invoice → extract line items → import into shipment → full analysis (classification, duty, PSC, regulatory). UX: re-run on failure, dev-login redirect, analysis progress tracker (phases + countdown).

**Wrap doc:** [docs/SPRINT12_DOCUMENT_ANALYSIS_WRAP.md](docs/SPRINT12_DOCUMENT_ANALYSIS_WRAP.md) – scope, local testing, manual checklist, known limits.

---

## ✅ Completed: Database Models (Foundation)

**Created models for Sprint 12:**

1. **Organization** (`backend/app/models/organization.py`)
   - Multi-tenant organizations (mapped to Clerk orgs)
   - Fields: `clerk_org_id`, `name`, `slug`
   - Relationships: `memberships`, `shipments`

2. **Membership** (`backend/app/models/membership.py`)
   - User-Organization membership with roles
   - Role stored in NECO DB (not Clerk)
   - Default role: `ANALYST`
   - Fields: `user_id`, `organization_id`, `role` (ANALYST, REVIEWER, ADMIN)

3. **Shipment** (`backend/app/models/shipment.py`)
   - Primary object for importer workflow
   - Fields: `organization_id`, `created_by`, `name`, `status`
   - Status enum: DRAFT, READY_FOR_ANALYSIS, ANALYSIS_QUEUED, RUNNING, COMPLETE, FAILED, REFUSED

4. **ShipmentReference** (`backend/app/models/shipment.py`)
   - Key/value reference pairs (PO, Entry, Invoice, BOL)
   - Fields: `shipment_id`, `reference_type`, `reference_value`

5. **ShipmentItem** (`backend/app/models/shipment.py`)
   - Items within a shipment
   - Fields: `label`, `declared_hts` (optional), `value`, `currency`, `quantity`, `uom`, `coo`

6. **ShipmentDocument** (`backend/app/models/shipment_document.py`)
   - Links documents to shipments with S3 metadata
   - Document types: ENTRY_SUMMARY, COMMERCIAL_INVOICE, PACKING_LIST, DATA_SHEET
   - Fields: `s3_key`, `sha256_hash`, `retention_expires_at` (60 days), `extracted_text`, `structured_data` (JSONB)
   - Immutable blobs (no mutation)

7. **Analysis** (`backend/app/models/analysis.py`)
   - Analysis runs for shipments (Celery orchestration)
   - Status enum: QUEUED, RUNNING, COMPLETE, FAILED, REFUSED
   - Refusal reason codes: MISSING_ENTRY_SUMMARY, MISSING_COMMERCIAL_INVOICE, MISSING_DATA_SHEET, INSUFFICIENT_DOCUMENTS
   - Fields: `celery_task_id`, `result_json` (Sprint 11 view), `review_record_id` (created at end)

8. **Entitlement** (`backend/app/models/entitlement.py`)
   - Monthly entitlement tracking (15 shipments/user/month)
   - Fields: `user_id`, `period_year`, `period_month`, `shipments_used`, `shipments_limit` (15)
   - Period: calendar month in America/New_York timezone

9. **User** (Updated: `backend/app/models/user.py`)
   - Added `clerk_user_id` field
   - Added `memberships` and `entitlements` relationships
   - `hashed_password` nullable (Clerk auth)
   - `client_id` nullable (migration compatibility)

---

## 🚧 Next Steps

### Phase 1: Database Migration (Priority 1)
- [ ] Create Alembic migration `009_add_sprint12_tables.py`
  - Create `organizations` table
  - Create `memberships` table (with unique constraint on user_id + organization_id)
  - Create `shipments` table
  - Create `shipment_references` table (with unique constraint on shipment_id + reference_type)
  - Create `shipment_items` table
  - Create `shipment_documents` table
  - Create `analyses` table
  - Create `entitlements` table (with unique constraint on user_id + period_year + period_month)
  - Alter `users` table: add `clerk_user_id`, make `hashed_password` nullable, make `client_id` nullable
  - Create all indexes and foreign keys

### Phase 2: Backend Services (Priority 2)
- [ ] Org-scoped repository/service layer
  - Enforce `org_id` in all queries (repository pattern)
  - Middleware/dependency to get current org from Clerk
  
- [ ] Entitlements service
  - Check/update entitlements on shipment creation
  - Monthly reset (calendar month in America/New_York)
  - Enforcement at shipment creation (fail fast)

- [ ] Shipments API
  - CRUD endpoints with org isolation
  - GET /api/v1/shipments
  - POST /api/v1/shipments
  - GET /api/v1/shipments/{id}
  - PUT /api/v1/shipments/{id}

- [ ] S3 Upload Service
  - POST /api/v1/documents/presign-upload
  - POST /api/v1/documents/confirm-upload
  - Store SHA256 hash, S3 key, retention (60 days)

- [ ] Analysis Orchestration
  - POST /api/v1/shipments/{shipment_id}/analyze
  - GET /api/v1/shipments/{shipment_id}/analysis-status
  - Eligibility gate (Entry Summary OR Commercial Invoice + Data Sheet)
  - Celery job integration
  - Regulatory evaluation persistence (Side Sprint A)

- [ ] Review API
  - POST /api/v1/reviews/from-shipment/{shipment_id}
  - GET /api/v1/reviews/{review_id}
  - POST /api/v1/reviews/{review_id}/override

- [ ] Export API
  - POST /api/v1/reviews/{review_id}/export/audit-pack
  - POST /api/v1/reviews/{review_id}/export/broker-prep
  - Block if REVIEW_REQUIRED

- [ ] Telemetry service
  - Write-only event storage
  - Events: shipment_created, document_uploaded, analysis_started, etc.

### Phase 3: Frontend (Priority 3)
- [ ] Clerk integration
  - Sign-in
  - Org selection/switcher

- [ ] Shipments UI
  - /app/shipments (list)
  - /app/shipments/new (create)
  - /app/shipments/[id] (tabs: Overview, Documents, Analysis, Reviews, Exports)

- [ ] Document upload UI
  - Upload with type selection
  - PDF viewer
  - Document list with retention expiry

- [ ] Sprint 11 Analysis View
  - 8 sections in order
  - Regulatory evaluations from DB (Side Sprint A)

- [ ] Review and override UI
  - Review creation
  - Override with justification

- [ ] Export UI
  - Audit pack export
  - Broker prep export
  - Blocker display

---

## 📋 Key Decisions Made

1. **Organizations vs Clients**: New `organizations` table for Sprint 12. `clients` table remains for backward compatibility (nullable `client_id` in users).

2. **Document Storage**: `ShipmentDocument` model with S3 metadata. Documents are immutable blobs (60-day retention).

3. **Analysis Result Storage**: `result_json` (JSONB) stores full Sprint 11 view for rendering.

4. **ReviewRecord Creation**: Created at end of analysis (not during). Links to `analysis.review_record_id`.

5. **Entitlement Enforcement**: At shipment creation (fail fast).

6. **Eligibility Gate**: Entry Summary OR (Commercial Invoice + Data Sheet). Refused status with reason codes.

---

## 🔗 Integration Points

- **Side Sprint A**: Regulatory evaluations persisted to `regulatory_evaluations` and `regulatory_conditions` tables (already created in migration 008)
- **ReviewRecord**: Links to analyses via `analysis.review_record_id`
- **Existing Engines**: Classification engine, duty resolver, PSC Radar (all integrate into analysis job)

---

## ⚠️ Critical Constraints

- Org-scoped queries (enforced at service layer)
- Entitlement enforcement (15 shipments/month)
- Eligibility gate (Entry Summary OR Commercial Invoice + Data Sheet)
- No HTS-only regulatory flags (Side Sprint A)
- Immutable ReviewRecords
- Exports blocked if REVIEW_REQUIRED
- No confidence/recommendation language

---

## 📊 Progress: ~15% Complete

**Foundation Complete:**
- ✅ All database models created
- ✅ Relationships defined
- ✅ Enums and constraints specified

**Remaining:**
- Migration creation and testing
- Backend service implementation
- API endpoints
- Frontend implementation
- Integration testing

**Ready for:** Database migration creation

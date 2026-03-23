# Sprint 12 Backend Services - Build Progress

## ✅ Completed

### 1. Database Models & Migration
- ✅ All Sprint 12 models created
- ✅ Migration 009 created with all constraints
- ✅ RefusalReasonCode enum: INSUFFICIENT_DOCUMENTS, ENTITLEMENT_EXCEEDED, OTHER

### 2. Org-Scoped Repository Layer
- ✅ `OrgScopedRepository` base class
- ✅ Enforces `organization_id` on all queries
- ✅ Returns 404 (not 403) on org mismatch
- ✅ No "optional org_id" parameters

### 3. Entitlements Service
- ✅ `get_or_create(user_id, period_start)` - atomic updates without cron
- ✅ `check_entitlement()` - check if user has entitlement
- ✅ `increment_on_shipment_creation()` - enforce at shipment creation
- ✅ `get_current_usage()` - usage information
- ✅ Monthly reset via `period_start` (first day of calendar month in America/New_York)

### 4. Sprint 12 Dependencies
- ✅ `get_current_user_sprint12()` - Clerk-based authentication
- ✅ Enforces: clerk_user_id required (no anonymous users)
- ✅ `get_current_organization()` - Clerk org verification
- ✅ 404 on org mismatch (not 403) to avoid leakage

---

## 🚧 Next Steps (In Build Order)

### 5. Shipments API
- [ ] `POST /api/v1/shipments` - Create shipment (with entitlement check)
- [ ] `GET /api/v1/shipments` - List shipments (org-scoped)
- [ ] `GET /api/v1/shipments/{id}` - Get shipment detail
- [ ] `POST /api/v1/shipments/{id}/items` - Add items
- [ ] `POST /api/v1/shipments/{id}/references` - Add references
- [ ] No delete endpoints

### 6. S3 Upload Endpoints
- [ ] `POST /api/v1/shipment-documents/presign-upload`
- [ ] `POST /api/v1/shipment-documents/confirm-upload`
- [ ] Handle dedupe: if duplicate hash for shipment, return existing document id

### 7. Analysis Orchestration
- [ ] `POST /api/v1/shipments/{id}/analyze` - Enqueue analysis
- [ ] `GET /api/v1/shipments/{id}/analysis-status` - Get status
- [ ] Eligibility gate: Entry Summary OR (CI + Data Sheet)
- [ ] Enforce entitlement at analyze start
- [ ] Create Analysis record (QUEUED/RUNNING/COMPLETE/REFUSED/FAILED)
- [ ] Celery job integration

### 8. Regulatory Evaluation Persistence
- [ ] Persist to `regulatory_evaluations` and `regulatory_conditions` tables
- [ ] Link to ReviewRecord (prefer auto-create review at analysis completion)

### 9. Review Endpoints
- [ ] `POST /api/v1/reviews/from-shipment/{id}` - Create from shipment
- [ ] `GET /api/v1/reviews/{id}` - Get review
- [ ] `POST /api/v1/reviews/{id}/override` - Override with justification

### 10. Export Endpoints
- [ ] `POST /api/v1/reviews/{id}/export/audit-pack`
- [ ] `POST /api/v1/reviews/{id}/export/broker-prep`
- [ ] Blockers enforced (REVIEW_REQUIRED, missing fields)

### 11. Events Emitter
- [ ] Wire events: shipment_created, document_uploaded, analysis_started, etc.
- [ ] Write-only event storage

---

## 📋 Key Patterns Established

### Org Scoping
- Every query requires `organization_id`
- 404 on org mismatch (not 403)
- Repository pattern enforces at base layer

### Entitlements
- Enforced at shipment creation (fail fast)
- Atomic updates via unique constraint (no cron needed)
- Monthly reset: `period_start` (first day of month in NY timezone)

### Authentication
- Clerk-based (clerk_user_id required in service layer)
- No anonymous users
- Org membership verified

---

## 🔒 Constraints Enforced

- ✅ Namespace separation: shipment_documents vs legacy documents
- ✅ Storage segregation: S3 vs UPLOAD_DIR
- ✅ Tenancy segregation: organization_id vs client_id
- ✅ FK delete behavior: RESTRICT on audit-related
- ✅ Consistent naming: organization_id throughout

# Sprint 12 Frontend Test Summary

## API Endpoint Verification ✅

All frontend API calls match backend routes:

| Frontend Call | Backend Route | Status |
|--------------|---------------|--------|
| `POST /api/v1/shipments` | `POST /api/v1/shipments` | ✅ Match |
| `GET /api/v1/shipments` | `GET /api/v1/shipments` | ✅ Match |
| `GET /api/v1/shipments/{id}` | `GET /api/v1/shipments/{id}` | ✅ Match |
| `POST /api/v1/shipment-documents/presign` | `POST /api/v1/shipment-documents/presign` | ✅ Match |
| `POST /api/v1/shipment-documents/confirm` | `POST /api/v1/shipment-documents/confirm` | ✅ Match |
| `GET /api/v1/shipment-documents/shipments/{id}/documents` | `GET /api/v1/shipment-documents/shipments/{id}/documents` | ✅ Match |
| `GET /api/v1/shipment-documents/{id}/download-url` | `GET /api/v1/shipment-documents/{id}/download-url` | ✅ Match |
| `POST /api/v1/shipments/{id}/analyze` | `POST /api/v1/shipments/{id}/analyze` | ✅ Match |
| `GET /api/v1/shipments/{id}/analysis-status` | `GET /api/v1/shipments/{id}/analysis-status` | ✅ Match |

## Headers Verification ✅

Backend expects:
- `X-Clerk-User-Id` ✅ Implemented
- `X-Clerk-Org-Id` ✅ Implemented

Frontend API client includes both headers on every request.

## Request Payload Fixes ✅

1. **Shipment Create**: Fixed references to use `key`/`value` instead of `reference_type`/`reference_value`
2. **Overview Tab**: Fixed to read `key`/`value` from shipment references

## Test Execution Checklist

### Prerequisites
- [ ] Backend running on `http://localhost:9001`
- [ ] Clerk configured (env vars set)
- [ ] Database migrated (`alembic upgrade head`)
- [ ] Celery worker running (for happy path)
- [ ] Frontend dependencies installed (`npm install`)
- [ ] Frontend running (`npm run dev`)

### Test 1: Auth + Org ⏳
**Manual Steps**:
1. Navigate to `http://localhost:3001`
2. Sign in with Clerk
3. If no org, should redirect to `/app/organizations/select`
4. Select org
5. Should redirect to `/app/shipments`

**Expected**:
- ✅ No `/app` routes accessible without org
- ✅ Org selection page works

### Test 2: Shipment Create ⏳
**Manual Steps**:
1. Go to `/app/shipments/new`
2. Enter name: "Test Shipment"
3. Click "Create Shipment"

**Expected**:
- ✅ Redirects to `/app/shipments/{id}`
- ✅ Shows DRAFT status
- ✅ Shows "Not eligible" with missing requirements

### Test 3: Refusal Path ⏳
**Manual Steps**:
1. Create shipment (Test 2)
2. Go to Documents tab
3. Upload PDF, type "PACKING_LIST" (or "3")
4. Wait for confirmation
5. Go to Analysis tab
6. Click "Analyze Shipment"
7. Wait for status

**Expected**:
- ✅ Status = REFUSED
- ✅ Shows `INSUFFICIENT_DOCUMENTS` code
- ✅ Shows missing requirements in text
- ✅ Entitlement usage unchanged

### Test 4: Happy Path ⏳
**Manual Steps**:
1. Create shipment
2. Upload COMMERCIAL_INVOICE PDF (type "2")
3. Upload DATA_SHEET PDF (type "4")
4. Go to Analysis tab
5. Click "Analyze Shipment"
6. Watch status poll: QUEUED → RUNNING → COMPLETE/REVIEW_REQUIRED

**Expected**:
- ✅ Status transitions correctly
- ✅ Shows `review_id` and `analysis_id` in Overview
- ✅ Shows regulatory outcomes (APPLIES/SUPPRESSED/CONDITIONAL)
- ✅ Shows warnings if extraction errors exist
- ✅ No sections claim missing evidence

### Test 5: Org Isolation ⏳
**Manual Steps**:
1. In Org A, create shipment, note ID from URL
2. Switch to Org B via org switcher
3. Try to access Org A shipment URL directly

**Expected**:
- ✅ Shows 404 / "Not found"
- ✅ No data leakage

## Known Issues / Limitations

1. **Document Type Selector**: Uses browser `prompt()` - needs proper UI dropdown
2. **PDF Viewer**: Opens in new tab instead of inline viewer
3. **Reviews Tab**: Placeholder only
4. **Exports Tab**: Placeholder only

## Next Steps After Tests Pass

1. Replace prompt with proper document type selector UI
2. Integrate PDF viewer component
3. Build Reviews tab (timeline + override)
4. Build Exports tab (generate + download)

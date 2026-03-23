# Sprint 12 Frontend Test Plan

## Prerequisites

1. **Backend running**: `./start_neco.sh` (or ensure backend on port 9000)
2. **Clerk configured**: Set `NEXT_PUBLIC_CLERK_PUBLISHABLE_KEY` in `.env.local`
3. **Database migrated**: `alembic upgrade head`
4. **Celery worker running** (for happy path test)

## Test Execution

### 1. Auth + Org

**Test**: Sign in and select org

**Steps**:
1. Navigate to `http://localhost:3001`
2. Sign in with Clerk
3. If no org selected, should redirect to `/app/organizations/select`
4. Select an organization
5. Should redirect to `/app/shipments`

**Pass Criteria**:
- ✅ App does not render any `/app` route without org
- ✅ Org selection page works
- ✅ Redirect to shipments after org selection

---

### 2. Shipment Create

**Test**: Create shipment with name only

**Steps**:
1. Go to `/app/shipments/new`
2. Enter shipment name (e.g., "Test Shipment")
3. Click "Create Shipment"
4. Should redirect to `/app/shipments/{id}`

**Pass Criteria**:
- ✅ Redirects to detail page
- ✅ Shows status DRAFT
- ✅ Shows eligibility as "Not eligible" with missing requirements

---

### 3. Refusal Path (No Celery Required)

**Test**: Upload only PACKING_LIST, then analyze

**Steps**:
1. On shipment detail page, go to Documents tab
2. Upload a PDF file, select type "PACKING_LIST" (or "3")
3. Wait for upload confirmation
4. Go to Analysis tab
5. Click "Analyze Shipment"
6. Check status

**Pass Criteria**:
- ✅ Status becomes REFUSED
- ✅ Shows `refusal_reason_code: INSUFFICIENT_DOCUMENTS`
- ✅ Shows `refusal_reason_text` with missing requirements
- ✅ Entitlement usage banner stays the same (does not increment)

---

### 4. Happy Path (Celery Required)

**Test**: Upload COMMERCIAL_INVOICE + DATA_SHEET, then analyze

**Steps**:
1. On shipment detail page, go to Documents tab
2. Upload a PDF file, select type "COMMERCIAL_INVOICE" (or "2")
3. Wait for upload confirmation
4. Upload another PDF file, select type "DATA_SHEET" (or "4")
5. Wait for upload confirmation
6. Go to Analysis tab
7. Click "Analyze Shipment"
8. Wait for analysis to complete (polling should show status changes)

**Pass Criteria**:
- ✅ Status transitions: QUEUED → RUNNING → COMPLETE or REVIEW_REQUIRED
- ✅ Shows `review_id` and `analysis_id` in Overview tab
- ✅ Shows regulatory outcomes in Analysis tab:
  - APPLIES/SUPPRESSED/CONDITIONAL with explanations
- ✅ Shows warnings if `extraction_errors` exist in `result_json`
- ✅ No section claims evidence that is missing

---

### 5. Org Isolation Test

**Test**: Create shipment in Org A, switch to Org B, try to access shipment

**Steps**:
1. In Org A, create a shipment and note the shipment ID from URL
2. Switch to Org B using organization switcher
3. Try to access the Org A shipment URL directly: `/app/shipments/{org_a_shipment_id}`
4. Check response

**Pass Criteria**:
- ✅ Shows "Not found" or 404 behavior
- ✅ No data leakage (does not show Org A shipment data)

---

## Manual Test Checklist

- [ ] Test 1: Auth + Org
- [ ] Test 2: Shipment Create
- [ ] Test 3: Refusal Path
- [ ] Test 4: Happy Path
- [ ] Test 5: Org Isolation

---

## Known Issues / TODOs

1. Document type selector uses prompt() - needs proper UI
2. PDF viewer not integrated - download URL opens in new tab
3. Reviews and Exports tabs are placeholders

---

## Environment Setup

```bash
cd frontend
npm install
npm run dev
```

Frontend should run on `http://localhost:3001`

Make sure backend is on `http://localhost:9001`

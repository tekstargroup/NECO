# Frontend Test Execution Guide

## Prerequisites Check

**Node.js/npm**: Must be installed and in PATH. Current shell doesn't have npm available.

### Setup Steps

1. **Install Node.js** (if not installed):
   ```bash
   # macOS (Homebrew)
   brew install node
   
   # Or download from https://nodejs.org
   ```

2. **Verify Installation**:
   ```bash
   node --version  # Should be v18+ or v20+
   npm --version   # Should be 9+
   ```

3. **Install Dependencies**:
   ```bash
   cd frontend
   npm install
   ```

4. **Configure Clerk**:
   Create `frontend/.env.local`:
   ```
   NEXT_PUBLIC_CLERK_PUBLISHABLE_KEY=pk_...
   NEXT_PUBLIC_API_URL=http://localhost:9001
   ```
   
   **Note**: `CLERK_SECRET_KEY` should NOT be in frontend `.env.local` (it's a server-side secret).

5. **Start Frontend Dev Server**:
   ```bash
   cd frontend
   npm run dev
   ```
   Frontend will run on `http://localhost:3001`

## Backend Prerequisites

Verify these are running:
- ✅ Backend API on `http://localhost:9001`
- ✅ PostgreSQL running
- ✅ Redis running
- ✅ Celery worker running

## Test Execution

Execute tests in order from `TEST_PLAN.md`:

### Test 1: Auth + Org
**Steps**:
1. Navigate to `http://localhost:3001`
2. Sign in with Clerk
3. If no org selected, should redirect to `/app/organizations/select`
4. Select an organization
5. Should redirect to `/app/shipments`

**Expected**:
- ✅ App does not render any `/app` route without org
- ✅ Org selection page works
- ✅ Redirect to shipments after org selection

**Record**: ✅ PASS / ❌ FAIL
**If FAIL**: Paste failing step, API response, backend log

---

### Test 2: Shipment Create
**Steps**:
1. Go to `/app/shipments/new`
2. Enter shipment name: "Test Shipment"
3. Click "Create Shipment"
4. Should redirect to `/app/shipments/{id}`

**Expected**:
- ✅ Redirects to detail page
- ✅ Shows status DRAFT
- ✅ Shows eligibility as "Not eligible" with missing requirements

**Record**: ✅ PASS / ❌ FAIL
**If FAIL**: Paste failing step, API response body, backend log

---

### Test 3: Refusal Path (No Celery Required)
**Steps**:
1. On shipment detail page, go to Documents tab
2. Upload a PDF file
3. When prompted, select type "PACKING_LIST" (or "3")
4. Wait for upload confirmation
5. Go to Analysis tab
6. Click "Analyze Shipment"
7. Check status

**Expected**:
- ✅ Status becomes REFUSED
- ✅ Shows `refusal_reason_code: INSUFFICIENT_DOCUMENTS`
- ✅ Shows `refusal_reason_text` with missing requirements
- ✅ Entitlement usage banner stays the same (does not increment)

**Record**: ✅ PASS / ❌ FAIL
**If FAIL**: Paste failing step, API response body, backend log

---

### Test 4: Happy Path (Celery Required)
**Steps**:
1. Create a new shipment
2. Go to Documents tab
3. Upload a PDF file, select type "COMMERCIAL_INVOICE" (or "2")
4. Wait for upload confirmation
5. Upload another PDF file, select type "DATA_SHEET" (or "4")
6. Wait for upload confirmation
7. Go to Analysis tab
8. Click "Analyze Shipment"
9. Watch status poll: QUEUED → RUNNING → COMPLETE or REVIEW_REQUIRED

**Expected**:
- ✅ Status transitions correctly: QUEUED → RUNNING → COMPLETE/REVIEW_REQUIRED
- ✅ Shows `review_id` and `analysis_id` in Overview tab
- ✅ Shows regulatory outcomes in Analysis tab (APPLIES/SUPPRESSED/CONDITIONAL) with explanations
- ✅ Shows warnings if `extraction_errors` exist in `result_json`
- ✅ No section claims evidence that is missing

**Record**: ✅ PASS / ❌ FAIL
**If FAIL**: Paste failing step, API response body, backend log

---

### Test 5: Org Isolation Test
**Steps**:
1. In Org A, create a shipment and note the shipment ID from URL
2. Switch to Org B using organization switcher
3. Try to access the Org A shipment URL directly: `/app/shipments/{org_a_shipment_id}`
4. Check response

**Expected**:
- ✅ Shows "Not found" or 404 behavior
- ✅ No data leakage (does not show Org A shipment data)

**Record**: ✅ PASS / ❌ FAIL
**If FAIL**: Paste failing step, API response body, backend log

---

## Test Results Recording

### Test Results Summary

| Test | Status | Notes |
|------|--------|-------|
| 1. Auth + Org | ⏳ PENDING | |
| 2. Shipment Create | ⏳ PENDING | |
| 3. Refusal Path | ⏳ PENDING | |
| 4. Happy Path | ⏳ PENDING | |
| 5. Org Isolation | ⏳ PENDING | |

### Failure Report Format

If any test fails, record:

**Failing Test**: [Test name]
**Failing Step**: [Specific step that failed]
**Expected Behavior**: [What should have happened]
**Actual Behavior**: [What actually happened]
**API Response Body**:
```json
[paste full response]
```
**Backend Log Lines**:
```
[paste relevant log lines]
```

---

## Notes

### Known Limitations
1. Document type selector uses `prompt()` - needs proper UI dropdown
2. PDF viewer opens in new tab instead of inline viewer
3. Reviews and Exports tabs are placeholders

### Auth Note
`X-Clerk-User-Id` and `X-Clerk-Org-Id` headers are acceptable for local dev. Backend must ultimately trust JWT claims, not headers. This is a post-Sprint-12 hardening task - do not refactor auth now.

---

## After Clean Pass

Once all tests pass, proceed with:

### Build Order After Tests Pass

1. **PDF viewer integration**
2. **Reviews tab** (real, not placeholder)
3. **Exports tab** (real, not placeholder)
4. **Document type selector UI polish**

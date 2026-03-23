# Sprint 7 - Review, Override, and Audit Controls

## Overview

Sprint 7 adds enterprise trust layer on top of Sprint 5 (Extraction + Duty Resolution) and Sprint 6 (PSC Radar). This sprint provides human accountability, auditability, and trust controls.

**Key Principle**: Control-plane sprint, not intelligence sprint. No changes to extraction, duty resolution, classification, or PSC Radar logic.

## Core Components

### 1. Review Record Model

Persistent review records with immutable snapshots:

- `review_id` (UUID)
- `object_type` (CLASSIFICATION | PSC_RADAR)
- `object_snapshot` (JSON, immutable)
- `hts_version_id` (must equal AUTHORITATIVE_HTS_VERSION_ID)
- `status` (DRAFT | REVIEW_REQUIRED | REVIEWED_ACCEPTED | REVIEWED_REJECTED)
- `created_at`, `created_by`
- `reviewed_at`, `reviewed_by` (nullable)
- `review_reason_code`, `review_notes`
- `override_of_review_id` (for overrides)

### 2. Review Lifecycle (Finite State Machine)

**States:**
- `DRAFT`: Initial state
- `REVIEW_REQUIRED`: Submitted for review
- `REVIEWED_ACCEPTED`: Terminal - accepted
- `REVIEWED_REJECTED`: Terminal - rejected

**Rules:**
- State transitions must be explicit
- No automatic transitions
- `REVIEWED_*` states are terminal
- Only REVIEWER can finalize (accept/reject)
- Reviewer cannot review own submission

### 3. Override Mechanics

Overrides create NEW records, they do NOT mutate history:

- Override must reference prior `review_id`
- Requires `reason_code` and free-text `justification`
- Creates new record linked to original
- Original record remains unchanged

### 4. Audit Replay Capability

Given a `review_id`, system can:
- Rehydrate exact snapshot
- Re-run resolver/PSC logic in dry-run mode
- Verify results match stored output
- Emit `AUDIT_MISMATCH` flag if mismatch detected

**Principle**: Detection, not repair. Do NOT auto-correct.

### 5. Minimal RBAC

**Roles:**
- `VIEWER`: Read-only access
- `ANALYST`: Can create drafts and submit for review
- `REVIEWER`: Can accept, reject, override

**Rules:**
- Only REVIEWER can finalize (REVIEWED_*)
- Reviewer cannot review own submission

## Example: Review Lifecycle

### Step 1: Create Classification Review Record

```json
{
  "id": "550e8400-e29b-41d4-a716-446655440000",
  "object_type": "CLASSIFICATION",
  "object_snapshot": {
    "inputs": {
      "description": "Women's cotton knit sweater",
      "country_of_origin": "CN",
      "value": 5000.0,
      "quantity": 100
    },
    "output": {
      "success": true,
      "status": "SUCCESS",
      "candidates": [
        {
          "hts_code": "6112.20.20.30",
          "final_score": 0.85
        }
      ]
    },
    "hts_version_id": "792bb867-c549-4769-80ca-d9d1adc883a3",
    "_snapshot_created_at": "2024-01-15T10:30:00Z",
    "_snapshot_version": "1.0"
  },
  "hts_version_id": "792bb867-c549-4769-80ca-d9d1adc883a3",
  "status": "DRAFT",
  "created_at": "2024-01-15T10:30:00Z",
  "created_by": "analyst_1",
  "reviewed_at": null,
  "reviewed_by": null,
  "review_reason_code": "AUTO_CREATED",
  "review_notes": null,
  "override_of_review_id": null
}
```

### Step 2: Submit for Review

Transition: `DRAFT` → `REVIEW_REQUIRED`

```json
{
  "id": "550e8400-e29b-41d4-a716-446655440000",
  "status": "REVIEW_REQUIRED",
  "reviewed_at": "2024-01-15T11:00:00Z",
  "reviewed_by": "analyst_1",
  "review_reason_code": "MANUAL_CREATION",
  "review_notes": "Submitted for review"
}
```

### Step 3: Reviewer Rejects

Transition: `REVIEW_REQUIRED` → `REVIEWED_REJECTED`

```json
{
  "id": "550e8400-e29b-41d4-a716-446655440000",
  "status": "REVIEWED_REJECTED",
  "reviewed_at": "2024-01-15T14:00:00Z",
  "reviewed_by": "reviewer_1",
  "review_reason_code": "REJECTED_INCORRECT",
  "review_notes": "Classification appears incorrect. Alternative HTS code 6112.20.10.10 may be more appropriate."
}
```

## Example: Override Flow

### Original Record (Rejected)

```json
{
  "id": "550e8400-e29b-41d4-a716-446655440000",
  "status": "REVIEWED_REJECTED",
  "object_snapshot": {
    "output": {
      "candidates": [
        {"hts_code": "6112.20.20.30", "final_score": 0.85}
      ]
    }
  }
}
```

### Override Record (New)

```json
{
  "id": "660e8400-e29b-41d4-a716-446655440001",
  "status": "DRAFT",
  "override_of_review_id": "550e8400-e29b-41d4-a716-446655440000",
  "object_snapshot": {
    "output": {
      "candidates": [
        {"hts_code": "6112.20.10.10", "final_score": 0.90}
      ]
    },
    "_override_of": "550e8400-e29b-41d4-a716-446655440000",
    "_override_reason": "OVERRIDE_EXPERT_JUDGMENT",
    "_override_justification": "Expert judgment: alternative classification is more appropriate based on product construction"
  },
  "created_by": "reviewer_1",
  "review_reason_code": "OVERRIDE_EXPERT_JUDGMENT",
  "review_notes": "Expert judgment: alternative classification is more appropriate based on product construction"
}
```

### Override Accepted

Transition: `DRAFT` → `REVIEWED_ACCEPTED`

```json
{
  "id": "660e8400-e29b-41d4-a716-446655440001",
  "status": "REVIEWED_ACCEPTED",
  "reviewed_at": "2024-01-15T15:00:00Z",
  "reviewed_by": "reviewer_2",
  "review_reason_code": "ACCEPTED_AS_IS",
  "review_notes": "Override accepted. Expert judgment validated."
}
```

**Key Point**: Original record (`550e8400...`) remains `REVIEWED_REJECTED`. Override creates new record (`660e8400...`) with `REVIEWED_ACCEPTED` status.

## Example: Audit Replay Output

### Successful Replay

```json
{
  "matches": true,
  "mismatch_fields": {},
  "flags": []
}
```

### Mismatch Detected (HTS Version Changed)

```json
{
  "matches": false,
  "mismatch_fields": {
    "hts_version_mismatch": {
      "snapshot": "old-version-id",
      "authoritative": "792bb867-c549-4769-80ca-d9d1adc883a3"
    }
  },
  "flags": ["AUDIT_MISMATCH"]
}
```

### Mismatch Detected (Missing Fields)

```json
{
  "matches": false,
  "mismatch_fields": {
    "missing_fields": ["inputs", "output", "hts_version_id"]
  },
  "flags": ["AUDIT_MISMATCH"]
}
```

## Compliance Answer

**Question**: "Who accepted this risk, when, and why?"

**Answer** (from review record):

```
Review ID: 660e8400-e29b-41d4-a716-446655440001
Accepted by: reviewer_2
Accepted at: 2024-01-15T15:00:00Z
Reason: ACCEPTED_AS_IS
Notes: "Override accepted. Expert judgment validated."

Override of: 550e8400-e29b-41d4-a716-446655440000
Override reason: OVERRIDE_EXPERT_JUDGMENT
Override justification: "Expert judgment: alternative classification is more appropriate based on product construction"
```

## Hard Rules

1. **Read-only intelligence remains read-only**
   - Sprint 7 does NOT modify Sprint 5 or 6 logic
   - No changes to extraction, duty resolution, classification, or PSC Radar

2. **Immutability**
   - `object_snapshot` is immutable once created
   - Status changes are append-only (event log or versioned rows)
   - Deletions are forbidden

3. **No mutations for overrides**
   - Overrides create NEW records
   - Original records remain unchanged
   - Full audit trail preserved

4. **Golden tests must pass**
   - Any change breaking goldens is rejected
   - Sprint 7 must not affect Sprint 5 or 6 functionality

## Files Created

- `backend/app/models/review_record.py`: Review record model
- `backend/app/services/review_service.py`: Review and override operations
- `backend/app/services/audit_replay_service.py`: Audit replay verification
- `backend/app/core/rbac.py`: RBAC enforcement
- `backend/tests/test_review_service.py`: Review service tests
- `backend/tests/test_audit_replay.py`: Audit replay tests

## Exit Criteria Met

✅ Review record model with immutable snapshots  
✅ Override flow creates new records (no mutations)  
✅ Audit replay capability with mismatch detection  
✅ RBAC enforcement (VIEWER, ANALYST, REVIEWER)  
✅ Tests covering state transitions, overrides, audit replay  
✅ Compliance director can answer "Who accepted this risk, when, and why?"  

**Sprint 7 is CLOSED. NECO is enterprise-defensible.**

# Migration 009 DDL Plan - Sprint 12 Tables

## ENUM Types to Create

1. `userrole` ENUM: 'ANALYST', 'REVIEWER', 'ADMIN'
   - Used by: memberships.role

2. `shipmentstatus` ENUM: 'DRAFT', 'READY_FOR_ANALYSIS', 'ANALYSIS_QUEUED', 'ANALYSIS_RUNNING', 'ANALYSIS_COMPLETE', 'ANALYSIS_FAILED', 'ANALYSIS_REFUSED'
   - Used by: shipments.status

3. `shipmentdocumenttype` ENUM: 'ENTRY_SUMMARY', 'COMMERCIAL_INVOICE', 'PACKING_LIST', 'DATA_SHEET'
   - Used by: shipment_documents.document_type

4. `analysisstatus` ENUM: 'QUEUED', 'RUNNING', 'COMPLETE', 'FAILED', 'REFUSED'
   - Used by: analyses.status

5. `refusalreasoncode` ENUM: 'MISSING_ENTRY_SUMMARY', 'MISSING_COMMERCIAL_INVOICE', 'MISSING_DATA_SHEET', 'INSUFFICIENT_DOCUMENTS'
   - Used by: analyses.refusal_reason_code

## Tables to Create

### 1. organizations
- id: UUID (PK, gen_random_uuid())
- clerk_org_id: VARCHAR(255) UNIQUE NOT NULL INDEX
- name: VARCHAR(255) NOT NULL INDEX
- slug: VARCHAR(100) UNIQUE INDEX
- created_at: TIMESTAMP NOT NULL DEFAULT now() INDEX
- updated_at: TIMESTAMP NOT NULL DEFAULT now()

**Indexes:**
- idx_organizations_clerk_org_id (clerk_org_id) - unique index
- idx_organizations_name (name)

### 2. memberships
- id: UUID (PK, gen_random_uuid())
- user_id: UUID NOT NULL INDEX FK(users.id) ON DELETE CASCADE
- organization_id: UUID NOT NULL INDEX FK(organizations.id) ON DELETE CASCADE
- role: userrole ENUM NOT NULL DEFAULT 'ANALYST' INDEX
- created_at: TIMESTAMP NOT NULL DEFAULT now() INDEX
- updated_at: TIMESTAMP NOT NULL DEFAULT now()

**Unique Constraint:** (user_id, organization_id) - one membership per user-org pair

**Indexes:**
- idx_memberships_org_user (organization_id, user_id) - composite unique
- idx_memberships_user (user_id)
- idx_memberships_org (organization_id)
- idx_memberships_role (role)

### 3. shipments
- id: UUID (PK, gen_random_uuid())
- organization_id: UUID NOT NULL INDEX FK(organizations.id) ON DELETE RESTRICT
- created_by: UUID NOT NULL INDEX FK(users.id) ON DELETE RESTRICT
- name: VARCHAR(255) NOT NULL INDEX
- status: shipmentstatus ENUM NOT NULL DEFAULT 'DRAFT' INDEX
- created_at: TIMESTAMP NOT NULL DEFAULT now() INDEX
- updated_at: TIMESTAMP NOT NULL DEFAULT now()

**Indexes:**
- idx_shipments_org_created (organization_id, created_at) - **REQUIRED for tenant scoping**
- idx_shipments_status (status)
- idx_shipments_created_by (created_by)

**FK Delete Behavior:** RESTRICT for organization_id and created_by (audit history)

### 4. shipment_references
- id: UUID (PK, gen_random_uuid())
- shipment_id: UUID NOT NULL INDEX FK(shipments.id) ON DELETE CASCADE
- reference_type: VARCHAR(50) NOT NULL INDEX
- reference_value: VARCHAR(255) NOT NULL
- created_at: TIMESTAMP NOT NULL DEFAULT now()

**Unique Constraint:** (shipment_id, reference_type) - one reference per type per shipment

**Indexes:**
- idx_shipment_references_ship_type (shipment_id, reference_type) - composite unique
- idx_shipment_references_type (reference_type)

### 5. shipment_items
- id: UUID (PK, gen_random_uuid())
- shipment_id: UUID NOT NULL INDEX FK(shipments.id) ON DELETE CASCADE
- label: VARCHAR(255) NOT NULL
- declared_hts: VARCHAR(10) INDEX (nullable)
- value: VARCHAR(50) (nullable)
- currency: VARCHAR(3) DEFAULT 'USD'
- quantity: VARCHAR(50) (nullable)
- unit_of_measure: VARCHAR(20) (nullable)
- country_of_origin: VARCHAR(2) (nullable)
- created_at: TIMESTAMP NOT NULL DEFAULT now()
- updated_at: TIMESTAMP NOT NULL DEFAULT now()

**Indexes:**
- idx_shipment_items_shipment (shipment_id)
- idx_shipment_items_hts (declared_hts)

### 6. shipment_documents
- id: UUID (PK, gen_random_uuid())
- shipment_id: UUID NOT NULL INDEX FK(shipments.id) ON DELETE RESTRICT
- organization_id: UUID NOT NULL INDEX FK(organizations.id) ON DELETE RESTRICT
- document_type: shipmentdocumenttype ENUM NOT NULL INDEX
- filename: VARCHAR(255) NOT NULL
- file_size: VARCHAR(20) (nullable)
- mime_type: VARCHAR(100) DEFAULT 'application/pdf'
- s3_key: VARCHAR(500) NOT NULL UNIQUE INDEX
- sha256_hash: VARCHAR(64) NOT NULL UNIQUE INDEX
- retention_expires_at: TIMESTAMP NOT NULL INDEX
- uploaded_by: UUID NOT NULL INDEX FK(users.id) ON DELETE RESTRICT
- uploaded_at: TIMESTAMP NOT NULL DEFAULT now() INDEX
- processing_status: VARCHAR(50) DEFAULT 'UPLOADED'
- processing_error: VARCHAR(500) (nullable)
- extracted_text: TEXT (nullable)
- structured_data: JSONB (nullable)
- created_at: TIMESTAMP NOT NULL DEFAULT now() INDEX

**Unique Constraints:**
- s3_key UNIQUE
- sha256_hash UNIQUE

**Indexes:**
- idx_shipment_documents_ship_type (shipment_id, document_type) - **REQUIRED**
- idx_shipment_documents_org (organization_id) - for tenant scoping
- idx_shipment_documents_type (document_type)
- idx_shipment_documents_retention (retention_expires_at)

**FK Delete Behavior:** RESTRICT for shipment_id, organization_id, uploaded_by (audit history)

### 7. analyses
- id: UUID (PK, gen_random_uuid())
- shipment_id: UUID NOT NULL INDEX FK(shipments.id) ON DELETE RESTRICT
- organization_id: UUID NOT NULL INDEX FK(organizations.id) ON DELETE RESTRICT
- status: analysisstatus ENUM NOT NULL DEFAULT 'QUEUED' INDEX
- refusal_reason_code: refusalreasoncode ENUM (nullable)
- refusal_reason_text: TEXT (nullable)
- celery_task_id: VARCHAR(255) UNIQUE (nullable) INDEX
- queued_at: TIMESTAMP NOT NULL DEFAULT now() INDEX
- started_at: TIMESTAMP (nullable)
- completed_at: TIMESTAMP (nullable)
- failed_at: TIMESTAMP (nullable)
- error_message: TEXT (nullable)
- error_details: JSONB (nullable)
- result_json: JSONB (nullable)
- review_record_id: UUID (nullable) INDEX FK(review_records.id) ON DELETE RESTRICT
- created_at: TIMESTAMP NOT NULL DEFAULT now() INDEX
- updated_at: TIMESTAMP NOT NULL DEFAULT now()

**Indexes:**
- idx_analyses_ship_created (shipment_id, created_at)
- idx_analyses_org_created (organization_id, created_at) - **REQUIRED for tenant scoping**
- idx_analyses_status (status)
- idx_analyses_celery_task (celery_task_id) - unique index

**FK Delete Behavior:** RESTRICT for shipment_id, organization_id, review_record_id (audit history)

### 8. entitlements
- id: UUID (PK, gen_random_uuid())
- user_id: UUID NOT NULL INDEX FK(users.id) ON DELETE CASCADE
- period_start: DATE NOT NULL INDEX - **first day of calendar month**
- shipments_used: INTEGER NOT NULL DEFAULT 0
- shipments_limit: INTEGER NOT NULL DEFAULT 15
- created_at: TIMESTAMP NOT NULL DEFAULT now() INDEX
- updated_at: TIMESTAMP NOT NULL DEFAULT now()

**Unique Constraint:** (user_id, period_start) - **REQUIRED for atomic updates, prevents duplicate rows**

**Indexes:**
- idx_entitlements_user_period (user_id, period_start) - composite unique
- idx_entitlements_period (period_start)

**FK Delete Behavior:** CASCADE (entitlements deleted with user)

## Alter users Table

### Add clerk_user_id
- clerk_user_id: VARCHAR(255) UNIQUE (nullable) INDEX

### Make client_id nullable
- client_id: UUID (nullable) - alter column to allow NULL

### Make hashed_password nullable
- hashed_password: VARCHAR(255) (nullable) - alter column to allow NULL

**Indexes:**
- idx_users_clerk_user_id (clerk_user_id) - unique index

## Summary of FK Delete Behaviors

**CASCADE (cleanup when parent deleted):**
- memberships.user_id → users.id
- memberships.organization_id → organizations.id
- shipment_references.shipment_id → shipments.id
- shipment_items.shipment_id → shipments.id
- entitlements.user_id → users.id

**RESTRICT (protect audit history):**
- shipments.organization_id → organizations.id
- shipments.created_by → users.id
- shipment_documents.shipment_id → shipments.id
- shipment_documents.organization_id → organizations.id
- shipment_documents.uploaded_by → users.id
- analyses.shipment_id → shipments.id
- analyses.organization_id → organizations.id
- analyses.review_record_id → review_records.id

## Critical Indexes for Performance

1. **Tenant Scoping:**
   - shipments(organization_id, created_at)
   - shipment_documents(shipment_id, document_type)
   - analyses(organization_id, created_at)

2. **Unique Constraints:**
   - memberships(user_id, organization_id)
   - entitlements(user_id, period_start)

3. **Lookups:**
   - organizations.clerk_org_id (UNIQUE)
   - users.clerk_user_id (UNIQUE)
   - shipment_documents.s3_key (UNIQUE)
   - shipment_documents.sha256_hash (UNIQUE)

## Notes

- All UUIDs use gen_random_uuid() for PK defaults
- All timestamps use now() for defaults
- JSONB columns allow NULL (no server_default)
- period_start is DATE (first day of month), not separate year/month columns
- RESTRICT on audit-related FKs (shipments, documents, analyses, review_records)
- CASCADE only for cleanup (memberships, references, items, entitlements)

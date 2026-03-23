"""Add Sprint 12 tables for web app MVP

Revision ID: 009_add_sprint12_tables
Revises: 008_add_regulatory_evaluations
Create Date: 2025-01-14 00:00:00.000000

Sprint 12: Web App MVP (Importer Path)

Creates tables for:
- organizations, memberships (Clerk-based multi-tenant)
- shipments, shipment_references, shipment_items (primary objects)
- shipment_documents (S3-based immutable blobs)
- analyses (Celery job orchestration)
- entitlements (15 shipments/user/month)

Key constraints:
- Hard-wired namespace separation: new shipment workflow uses shipment_documents ONLY
- Legacy documents table is Entry-only and deprecated (see LEGACY_DOCUMENTS_DEPRECATION.md)
- Tenancy segregation: organization_id (new) vs client_id (legacy) never mixed
- Storage segregation: S3 (new) vs UPLOAD_DIR (legacy) never mixed
- RESTRICT delete on audit-related FKs (shipments, documents, analyses, review_records)
- Consistent naming: organization_id (not org_id) throughout Sprint 12
"""

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql
from sqlalchemy import text

# revision identifiers, used by Alembic.
revision = '009'
down_revision = '008'
branch_labels = None
depends_on = None


def upgrade():
    """
    Create Sprint 12 tables for web app MVP.
    
    Hard constraints:
    - New shipment workflow uses shipment_documents ONLY (not legacy documents table)
    - Legacy documents table is Entry-only and deprecated
    - No FK can cascade-delete review_records or regulatory_evaluations
    - Consistent naming: organization_id throughout Sprint 12
    """
    
    # Create ENUM types for Sprint 12
    op.execute("""
        CREATE TYPE userrole AS ENUM (
            'ANALYST',
            'REVIEWER',
            'ADMIN'
        )
    """)
    
    op.execute("""
        CREATE TYPE shipmentstatus AS ENUM (
            'DRAFT',
            'READY',
            'ANALYZING',
            'COMPLETE',
            'REFUSED',
            'FAILED'
        )
    """)
    
    op.execute("""
        CREATE TYPE shipmentdocumenttype AS ENUM (
            'ENTRY_SUMMARY',
            'COMMERCIAL_INVOICE',
            'PACKING_LIST',
            'DATA_SHEET'
        )
    """)
    
    op.execute("""
        CREATE TYPE analysisstatus AS ENUM (
            'QUEUED',
            'RUNNING',
            'COMPLETE',
            'FAILED',
            'REFUSED'
        )
    """)
    
    op.execute("""
        CREATE TYPE refusalreasoncode AS ENUM (
            'INSUFFICIENT_DOCUMENTS',
            'ENTITLEMENT_EXCEEDED',
            'OTHER'
        )
    """)
    
    # Create organizations table
    op.create_table(
        'organizations',
        sa.Column('id', postgresql.UUID(as_uuid=True), primary_key=True, server_default=text('gen_random_uuid()')),
        sa.Column('clerk_org_id', sa.String(255), nullable=False, unique=True, index=True),
        sa.Column('name', sa.String(255), nullable=False, index=True),
        sa.Column('slug', sa.String(100), unique=True, index=True),
        sa.Column('created_at', sa.DateTime(), nullable=False, server_default=sa.text('now()'), index=True),
        sa.Column('updated_at', sa.DateTime(), nullable=False, server_default=sa.text('now()')),
    )
    
    # Create memberships table
    userrole_enum = postgresql.ENUM('ANALYST', 'REVIEWER', 'ADMIN', name='userrole', create_type=False)
    
    op.create_table(
        'memberships',
        sa.Column('id', postgresql.UUID(as_uuid=True), primary_key=True, server_default=text('gen_random_uuid()')),
        sa.Column('user_id', postgresql.UUID(as_uuid=True), nullable=False, index=True),
        sa.Column('organization_id', postgresql.UUID(as_uuid=True), nullable=False, index=True),
        sa.Column('role', userrole_enum, nullable=False, server_default='ANALYST', index=True),
        sa.Column('created_at', sa.DateTime(), nullable=False, server_default=sa.text('now()'), index=True),
        sa.Column('updated_at', sa.DateTime(), nullable=False, server_default=sa.text('now()')),
        sa.ForeignKeyConstraint(['user_id'], ['users.id'], ondelete='CASCADE'),
        sa.ForeignKeyConstraint(['organization_id'], ['organizations.id'], ondelete='CASCADE'),
    )
    
    # Unique constraint: one membership per user-org pair
    op.create_unique_constraint(
        'uq_memberships_user_org',
        'memberships',
        ['user_id', 'organization_id']
    )
    
    # Index for tenant scoping
    op.create_index('idx_memberships_org_user', 'memberships', ['organization_id', 'user_id'])
    
    # Create shipments table
    shipmentstatus_enum = postgresql.ENUM('DRAFT', 'READY', 'ANALYZING', 'COMPLETE', 'REFUSED', 'FAILED', name='shipmentstatus', create_type=False)
    
    op.create_table(
        'shipments',
        sa.Column('id', postgresql.UUID(as_uuid=True), primary_key=True, server_default=text('gen_random_uuid()')),
        sa.Column('organization_id', postgresql.UUID(as_uuid=True), nullable=False, index=True),
        sa.Column('created_by', postgresql.UUID(as_uuid=True), nullable=False, index=True),
        sa.Column('name', sa.String(255), nullable=False, index=True),
        sa.Column('status', shipmentstatus_enum, nullable=False, server_default='DRAFT', index=True),
        sa.Column('created_at', sa.DateTime(), nullable=False, server_default=sa.text('now()'), index=True),
        sa.Column('updated_at', sa.DateTime(), nullable=False, server_default=sa.text('now()')),
        sa.ForeignKeyConstraint(['organization_id'], ['organizations.id'], ondelete='RESTRICT'),
        sa.ForeignKeyConstraint(['created_by'], ['users.id'], ondelete='RESTRICT'),
    )
    
    # Critical index for tenant scoping
    op.create_index('idx_shipments_org_created', 'shipments', ['organization_id', 'created_at'])
    # Plain org_id index for large table
    op.create_index('idx_shipments_org', 'shipments', ['organization_id'])
    
    # Create shipment_references table
    op.create_table(
        'shipment_references',
        sa.Column('id', postgresql.UUID(as_uuid=True), primary_key=True, server_default=text('gen_random_uuid()')),
        sa.Column('shipment_id', postgresql.UUID(as_uuid=True), nullable=False, index=True),
        sa.Column('reference_type', sa.String(50), nullable=False, index=True),
        sa.Column('reference_value', sa.String(255), nullable=False),
        sa.Column('created_at', sa.DateTime(), nullable=False, server_default=sa.text('now()')),
        sa.ForeignKeyConstraint(['shipment_id'], ['shipments.id'], ondelete='CASCADE'),
    )
    
    # Unique constraint: one reference per type per shipment
    op.create_unique_constraint(
        'uq_shipment_references_ship_type',
        'shipment_references',
        ['shipment_id', 'reference_type']
    )
    
    op.create_index('idx_shipment_references_type', 'shipment_references', ['reference_type'])
    
    # Create shipment_items table
    op.create_table(
        'shipment_items',
        sa.Column('id', postgresql.UUID(as_uuid=True), primary_key=True, server_default=text('gen_random_uuid()')),
        sa.Column('shipment_id', postgresql.UUID(as_uuid=True), nullable=False, index=True),
        sa.Column('label', sa.String(255), nullable=False),
        sa.Column('declared_hts', sa.String(10), nullable=True, index=True),
        sa.Column('value', sa.String(50)),
        sa.Column('currency', sa.String(3), server_default='USD'),
        sa.Column('quantity', sa.String(50)),
        sa.Column('unit_of_measure', sa.String(20)),
        sa.Column('country_of_origin', sa.String(2)),
        sa.Column('created_at', sa.DateTime(), nullable=False, server_default=sa.text('now()')),
        sa.Column('updated_at', sa.DateTime(), nullable=False, server_default=sa.text('now()')),
        sa.ForeignKeyConstraint(['shipment_id'], ['shipments.id'], ondelete='CASCADE'),
    )
    
    op.create_index('idx_shipment_items_hts', 'shipment_items', ['declared_hts'])
    
    # Create shipment_documents table
    # NOTE: New shipment workflow uses this table ONLY. Legacy documents table is Entry-only and deprecated.
    shipmentdocumenttype_enum = postgresql.ENUM('ENTRY_SUMMARY', 'COMMERCIAL_INVOICE', 'PACKING_LIST', 'DATA_SHEET', name='shipmentdocumenttype', create_type=False)
    
    op.create_table(
        'shipment_documents',
        sa.Column('id', postgresql.UUID(as_uuid=True), primary_key=True, server_default=text('gen_random_uuid()')),
        sa.Column('shipment_id', postgresql.UUID(as_uuid=True), nullable=False, index=True),
        sa.Column('organization_id', postgresql.UUID(as_uuid=True), nullable=False, index=True),
        sa.Column('document_type', shipmentdocumenttype_enum, nullable=False, index=True),
        sa.Column('filename', sa.String(255), nullable=False),
        sa.Column('file_size', sa.String(20)),
        sa.Column('mime_type', sa.String(100), server_default='application/pdf'),
        sa.Column('s3_key', sa.String(500), nullable=False, unique=True, index=True),
        sa.Column('sha256_hash', sa.String(64), nullable=False, unique=True, index=True),
        sa.Column('retention_expires_at', sa.DateTime(), nullable=False, index=True),
        sa.Column('uploaded_by', postgresql.UUID(as_uuid=True), nullable=False, index=True),
        sa.Column('uploaded_at', sa.DateTime(), nullable=False, server_default=sa.text('now()'), index=True),
        sa.Column('processing_status', sa.String(50), server_default='UPLOADED'),
        sa.Column('processing_error', sa.String(500)),
        sa.Column('extracted_text', sa.Text()),
        sa.Column('structured_data', postgresql.JSONB()),
        sa.Column('created_at', sa.DateTime(), nullable=False, server_default=sa.text('now()'), index=True),
        sa.ForeignKeyConstraint(['shipment_id'], ['shipments.id'], ondelete='RESTRICT'),
        sa.ForeignKeyConstraint(['organization_id'], ['organizations.id'], ondelete='RESTRICT'),
        sa.ForeignKeyConstraint(['uploaded_by'], ['users.id'], ondelete='RESTRICT'),
    )
    
    # Unique constraint: prevent duplicate doc attachments per shipment (dedupe by hash)
    op.create_unique_constraint(
        'uq_shipment_documents_ship_hash',
        'shipment_documents',
        ['shipment_id', 'sha256_hash']
    )
    
    # Critical indexes
    op.create_index('idx_shipment_documents_ship_type', 'shipment_documents', ['shipment_id', 'document_type'])
    op.create_index('idx_shipment_documents_org', 'shipment_documents', ['organization_id'])  # Plain org_id for tenant scoping
    op.create_index('idx_shipment_documents_retention', 'shipment_documents', ['retention_expires_at'])
    
    # Create analyses table
    analysisstatus_enum = postgresql.ENUM('QUEUED', 'RUNNING', 'COMPLETE', 'FAILED', 'REFUSED', name='analysisstatus', create_type=False)
    refusalreasoncode_enum = postgresql.ENUM('INSUFFICIENT_DOCUMENTS', 'ENTITLEMENT_EXCEEDED', 'OTHER', name='refusalreasoncode', create_type=False)
    
    op.create_table(
        'analyses',
        sa.Column('id', postgresql.UUID(as_uuid=True), primary_key=True, server_default=text('gen_random_uuid()')),
        sa.Column('shipment_id', postgresql.UUID(as_uuid=True), nullable=False, index=True),
        sa.Column('organization_id', postgresql.UUID(as_uuid=True), nullable=False, index=True),
        sa.Column('status', analysisstatus_enum, nullable=False, server_default='QUEUED', index=True),
        sa.Column('refusal_reason_code', refusalreasoncode_enum),
        sa.Column('refusal_reason_text', sa.Text()),  # Required if refusal_reason_code set
        sa.Column('celery_task_id', sa.String(255), unique=True, index=True),
        sa.Column('queued_at', sa.DateTime(), nullable=False, server_default=sa.text('now()'), index=True),
        sa.Column('started_at', sa.DateTime()),
        sa.Column('completed_at', sa.DateTime()),
        sa.Column('failed_at', sa.DateTime()),
        sa.Column('error_message', sa.Text()),
        sa.Column('error_details', postgresql.JSONB()),
        sa.Column('result_json', postgresql.JSONB()),  # Sprint 11 view JSON
        sa.Column('review_record_id', postgresql.UUID(as_uuid=True), index=True),
        sa.Column('created_at', sa.DateTime(), nullable=False, server_default=sa.text('now()'), index=True),
        sa.Column('updated_at', sa.DateTime(), nullable=False, server_default=sa.text('now()')),
        sa.ForeignKeyConstraint(['shipment_id'], ['shipments.id'], ondelete='RESTRICT'),
        sa.ForeignKeyConstraint(['organization_id'], ['organizations.id'], ondelete='RESTRICT'),
        sa.ForeignKeyConstraint(['review_record_id'], ['review_records.id'], ondelete='RESTRICT'),  # Audit history must not cascade delete
    )
    
    # Critical indexes
    op.create_index('idx_analyses_ship_created', 'analyses', ['shipment_id', 'created_at'])
    op.create_index('idx_analyses_org_created', 'analyses', ['organization_id', 'created_at'])  # Tenant scoping
    op.create_index('idx_analyses_org', 'analyses', ['organization_id'])  # Plain org_id for large table
    
    # Create entitlements table
    op.create_table(
        'entitlements',
        sa.Column('id', postgresql.UUID(as_uuid=True), primary_key=True, server_default=text('gen_random_uuid()')),
        sa.Column('user_id', postgresql.UUID(as_uuid=True), nullable=False, index=True),
        sa.Column('period_start', sa.Date(), nullable=False, index=True),  # First day of calendar month (America/New_York)
        sa.Column('shipments_used', sa.Integer(), nullable=False, server_default='0'),
        sa.Column('shipments_limit', sa.Integer(), nullable=False, server_default='15'),
        sa.Column('created_at', sa.DateTime(), nullable=False, server_default=sa.text('now()'), index=True),
        sa.Column('updated_at', sa.DateTime(), nullable=False, server_default=sa.text('now()')),
        sa.ForeignKeyConstraint(['user_id'], ['users.id'], ondelete='CASCADE'),
    )
    
    # Unique constraint: one entitlement per user per period (atomic updates)
    op.create_unique_constraint(
        'uq_entitlements_user_period',
        'entitlements',
        ['user_id', 'period_start']
    )
    
    op.create_index('idx_entitlements_period', 'entitlements', ['period_start'])
    
    # Alter users table: add clerk_user_id, keep existing fields nullable but don't use
    # Minimal: clerk_user_id (unique, not null), email, created_at
    op.add_column('users', sa.Column('clerk_user_id', sa.String(255), unique=True, nullable=True, index=True))
    op.create_index('idx_users_clerk_user_id', 'users', ['clerk_user_id'], unique=True)
    
    # Make client_id and hashed_password nullable (for Clerk migration compatibility)
    # These are legacy fields - do not use in new shipment workflow
    op.alter_column('users', 'client_id', nullable=True)
    op.alter_column('users', 'hashed_password', nullable=True)


def downgrade():
    """Drop Sprint 12 tables and ENUM types."""
    
    # Drop indexes first
    op.drop_index('idx_users_clerk_user_id', 'users')
    op.drop_column('users', 'clerk_user_id')
    
    # Restore nullable constraints (if needed for downgrade compatibility)
    op.alter_column('users', 'client_id', nullable=False)
    op.alter_column('users', 'hashed_password', nullable=False)
    
    op.drop_index('idx_entitlements_period', 'entitlements')
    op.drop_constraint('uq_entitlements_user_period', 'entitlements', type_='unique')
    op.drop_table('entitlements')
    
    op.drop_index('idx_analyses_org', 'analyses')
    op.drop_index('idx_analyses_org_created', 'analyses')
    op.drop_index('idx_analyses_ship_created', 'analyses')
    op.drop_table('analyses')
    
    op.drop_index('idx_shipment_documents_retention', 'shipment_documents')
    op.drop_index('idx_shipment_documents_org', 'shipment_documents')
    op.drop_index('idx_shipment_documents_ship_type', 'shipment_documents')
    op.drop_constraint('uq_shipment_documents_ship_hash', 'shipment_documents', type_='unique')
    op.drop_table('shipment_documents')
    
    op.drop_index('idx_shipment_items_hts', 'shipment_items')
    op.drop_table('shipment_items')
    
    op.drop_index('idx_shipment_references_type', 'shipment_references')
    op.drop_constraint('uq_shipment_references_ship_type', 'shipment_references', type_='unique')
    op.drop_table('shipment_references')
    
    op.drop_index('idx_shipments_org', 'shipments')
    op.drop_index('idx_shipments_org_created', 'shipments')
    op.drop_table('shipments')
    
    op.drop_index('idx_memberships_org_user', 'memberships')
    op.drop_constraint('uq_memberships_user_org', 'memberships', type_='unique')
    op.drop_table('memberships')
    
    op.drop_table('organizations')
    
    # Drop ENUM types
    op.execute("DROP TYPE IF EXISTS refusalreasoncode")
    op.execute("DROP TYPE IF EXISTS analysisstatus")
    op.execute("DROP TYPE IF EXISTS shipmentdocumenttype")
    op.execute("DROP TYPE IF EXISTS shipmentstatus")
    op.execute("DROP TYPE IF EXISTS userrole")

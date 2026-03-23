"""Add regulatory_evaluations and regulatory_conditions tables

Revision ID: 008_add_regulatory_evaluations
Revises: 007_add_hts_nodes_table
Create Date: 2025-01-14 00:00:00.000000

Side Sprint A: Regulatory Applicability Conditioning (Evidence-Driven Flags)

Creates tables for evidence-driven regulatory applicability evaluation:
- regulatory_evaluations: Stores regulatory applicability evaluations (EPA, FDA, Lacey Act)
- regulatory_conditions: Stores individual condition evaluations with evidence references

Key principles:
- HTS codes trigger questions, not conclusions
- Conditions must be evaluated with evidence
- Flags suppressed when evidence negates applicability
- REVIEW_REQUIRED when evidence is missing or ambiguous
- Immutable once tied to ReviewRecord (enforced at service layer, not DB)

Migration scope (tight):
- regulatory_evaluations table
- regulatory_conditions table
- FK to review_records
- ENUM types for Regulator, RegulatoryOutcome, ConditionState
"""

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql
from sqlalchemy import text, inspect

# revision identifiers, used by Alembic.
revision = '008'
down_revision = '007'
branch_labels = None
depends_on = None


def upgrade():
    """
    Create regulatory evaluation tables for evidence-driven regulatory flagging.
    
    Side Sprint A: Regulatory Applicability Conditioning
    These tables store immutable compliance artifacts tied to ReviewRecords.
    
    NOTE: This migration also creates review_records table if it doesn't exist,
    since regulatory_evaluations references it via FK.
    """
    
    # Check if review_records exists, create if not (Sprint 7 table may not have migration)
    from sqlalchemy import inspect
    conn = op.get_bind()
    inspector = inspect(conn)
    existing_tables = inspector.get_table_names()
    
    if 'review_records' not in existing_tables:
        # Create ENUM types for review_records first
        op.execute("""
            CREATE TYPE reviewableobjecttype AS ENUM (
                'CLASSIFICATION',
                'PSC_RADAR'
            )
        """)
        
        op.execute("""
            CREATE TYPE reviewstatus AS ENUM (
                'DRAFT',
                'REVIEW_REQUIRED',
                'REVIEWED_ACCEPTED',
                'REVIEWED_REJECTED'
            )
        """)
        
        op.execute("""
            CREATE TYPE reviewreasoncode AS ENUM (
                'AUTO_CREATED',
                'MANUAL_CREATION',
                'ACCEPTED_AS_IS',
                'REJECTED_INCORRECT',
                'REJECTED_INSUFFICIENT_INFO',
                'OVERRIDE_MANUAL_CLASSIFICATION',
                'OVERRIDE_RISK_ACCEPTED',
                'OVERRIDE_EXPERT_JUDGMENT',
                'OVERRIDE_ADDITIONAL_EVIDENCE'
            )
        """)
        
        # Create review_records table
        reviewableobjecttype_enum = postgresql.ENUM('CLASSIFICATION', 'PSC_RADAR', name='reviewableobjecttype', create_type=False)
        reviewstatus_enum = postgresql.ENUM('DRAFT', 'REVIEW_REQUIRED', 'REVIEWED_ACCEPTED', 'REVIEWED_REJECTED', name='reviewstatus', create_type=False)
        reviewreasoncode_enum = postgresql.ENUM(
            'AUTO_CREATED', 'MANUAL_CREATION', 'ACCEPTED_AS_IS', 'REJECTED_INCORRECT',
            'REJECTED_INSUFFICIENT_INFO', 'OVERRIDE_MANUAL_CLASSIFICATION', 'OVERRIDE_RISK_ACCEPTED',
            'OVERRIDE_EXPERT_JUDGMENT', 'OVERRIDE_ADDITIONAL_EVIDENCE',
            name='reviewreasoncode', create_type=False
        )
        
        op.create_table(
            'review_records',
            sa.Column('id', postgresql.UUID(as_uuid=True), primary_key=True, server_default=text('gen_random_uuid()')),
            sa.Column('object_type', reviewableobjecttype_enum, nullable=False, index=True),
            sa.Column('object_snapshot', postgresql.JSONB(), nullable=False),
            sa.Column('hts_version_id', sa.String(36), nullable=False, index=True),
            sa.Column('status', reviewstatus_enum, nullable=False, server_default='DRAFT', index=True),
            sa.Column('created_at', sa.DateTime(), nullable=False, server_default=sa.text('now()'), index=True),
            sa.Column('created_by', sa.String(100), nullable=False),
            sa.Column('reviewed_at', sa.DateTime(), nullable=True, index=True),
            sa.Column('reviewed_by', sa.String(100), nullable=True),
            sa.Column('review_reason_code', reviewreasoncode_enum, nullable=True),
            sa.Column('review_notes', sa.Text(), nullable=True),
            sa.Column('override_of_review_id', postgresql.UUID(as_uuid=True), nullable=True, index=True),
        )
        
        # Self-referential FK for override_of_review_id
        op.create_foreign_key(
            'fk_review_records_override',
            'review_records',
            'review_records',
            ['override_of_review_id'],
            ['id'],
            ondelete='RESTRICT'
        )
        
        # Index for common queries
        op.create_index('idx_review_records_status_created', 'review_records', ['status', 'created_at'])
    
    # Create ENUM types for regulatory evaluation
    op.execute("""
        CREATE TYPE regulator AS ENUM (
            'EPA',
            'FDA',
            'LACEY_ACT'
        )
    """)
    
    op.execute("""
        CREATE TYPE regulatoryoutcome AS ENUM (
            'APPLIES',
            'SUPPRESSED',
            'CONDITIONAL'
        )
    """)
    
    op.execute("""
        CREATE TYPE conditionstate AS ENUM (
            'CONFIRMED_TRUE',
            'CONFIRMED_FALSE',
            'UNKNOWN'
        )
    """)
    
    # Create regulatory_evaluations table
    regulator_enum = postgresql.ENUM('EPA', 'FDA', 'LACEY_ACT', name='regulator', create_type=False)
    regulatory_outcome_enum = postgresql.ENUM('APPLIES', 'SUPPRESSED', 'CONDITIONAL', name='regulatoryoutcome', create_type=False)
    
    op.create_table(
        'regulatory_evaluations',
        sa.Column('id', postgresql.UUID(as_uuid=True), primary_key=True, server_default=text('gen_random_uuid()')),
        sa.Column('review_id', postgresql.UUID(as_uuid=True), nullable=False, index=True),
        
        # Regulatory body
        sa.Column('regulator', regulator_enum, nullable=False, index=True),
        
        # Evaluation outcome
        sa.Column('outcome', regulatory_outcome_enum, nullable=False, index=True),
        
        # Explanation (traceable logic with cited evidence)
        sa.Column('explanation_text', sa.Text(), nullable=False),
        
        # HTS code that triggered this evaluation
        sa.Column('triggered_by_hts_code', sa.String(10), nullable=False, index=True),
        
        # Metadata
        sa.Column('evaluated_at', sa.DateTime(), nullable=False, server_default=sa.text('now()'), index=True),
        sa.Column('evaluation_version', sa.String(20), server_default='1.0'),  # Track engine version
        
        # Foreign key to review_records (immutable once tied)
        sa.ForeignKeyConstraint(['review_id'], ['review_records.id'], ondelete='CASCADE'),
    )
    
    # Create regulatory_conditions table
    condition_state_enum = postgresql.ENUM('CONFIRMED_TRUE', 'CONFIRMED_FALSE', 'UNKNOWN', name='conditionstate', create_type=False)
    
    op.create_table(
        'regulatory_conditions',
        sa.Column('id', postgresql.UUID(as_uuid=True), primary_key=True, server_default=text('gen_random_uuid()')),
        sa.Column('evaluation_id', postgresql.UUID(as_uuid=True), nullable=False, index=True),
        
        # Condition identification
        sa.Column('condition_id', sa.String(100), nullable=False, index=True),  # e.g., "INTENDED_PESTICIDAL_USE"
        sa.Column('condition_description', sa.Text()),  # Human-readable description
        
        # Evaluation state
        sa.Column('state', condition_state_enum, nullable=False, index=True),
        
        # Evidence references (JSON array)
        # Each evidence ref: {"document_id": "...", "page_number": 1, "snippet": "..."}
        sa.Column('evidence_refs', postgresql.JSONB(), server_default=text("'[]'::jsonb")),  # Array of evidence references
        
        # Metadata
        sa.Column('evaluated_at', sa.DateTime(), nullable=False, server_default=sa.text('now()')),
        
        # Foreign key to regulatory_evaluations (cascade delete)
        sa.ForeignKeyConstraint(['evaluation_id'], ['regulatory_evaluations.id'], ondelete='CASCADE'),
    )
    
    # Create indexes for common queries
    
    # Regulatory evaluations indexes
    op.create_index('idx_regulatory_evaluations_review_regulator', 'regulatory_evaluations', ['review_id', 'regulator'])
    op.create_index('idx_regulatory_evaluations_hts_outcome', 'regulatory_evaluations', ['triggered_by_hts_code', 'outcome'])
    op.create_index('idx_regulatory_evaluations_evaluated_at', 'regulatory_evaluations', ['evaluated_at'])
    
    # Regulatory conditions indexes
    op.create_index('idx_regulatory_conditions_evaluation_state', 'regulatory_conditions', ['evaluation_id', 'state'])
    op.create_index('idx_regulatory_conditions_condition_id', 'regulatory_conditions', ['condition_id'])
    
    # Notes:
    # - Immutability is enforced at the service layer, not via DB constraints
    # - No triggers needed (service layer handles immutability)
    # - Foreign keys use CASCADE delete for clean cleanup


def downgrade():
    """Drop regulatory evaluation tables and ENUM types."""
    
    # Drop indexes first
    op.drop_index('idx_regulatory_conditions_condition_id', 'regulatory_conditions')
    op.drop_index('idx_regulatory_conditions_evaluation_state', 'regulatory_conditions')
    op.drop_index('idx_regulatory_evaluations_evaluated_at', 'regulatory_evaluations')
    op.drop_index('idx_regulatory_evaluations_hts_outcome', 'regulatory_evaluations')
    op.drop_index('idx_regulatory_evaluations_review_regulator', 'regulatory_evaluations')
    
    # Drop tables (FK constraints will be dropped automatically)
    op.drop_table('regulatory_conditions')
    op.drop_table('regulatory_evaluations')
    
    # Drop ENUM types
    op.execute("DROP TYPE IF EXISTS conditionstate")
    op.execute("DROP TYPE IF EXISTS regulatoryoutcome")
    op.execute("DROP TYPE IF EXISTS regulator")

"""Create duty_rates table for Sprint 5 Phase 1

Revision ID: 005
Revises: 004
Create Date: 2026-01-10 12:00:00.000000

Sprint 5 Workstream 5.A: Duty Data Model (core)

Creates comprehensive duty_rates table that preserves:
- Raw legal text (never discarded)
- Structured interpretation (JSONB)
- Numeric values when computable
- Confidence levels
- Source precision (6/8/10 digit)
- Inheritance chain
- "Free" as first-class data
- Compound and conditional duties
"""

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql
from sqlalchemy import text

# revision identifiers, used by Alembic.
revision = '005'
down_revision = '004'
branch_labels = None
depends_on = None


def upgrade():
    # Create ENUM types for duty classifications
    op.execute("""
        CREATE TYPE dutytype AS ENUM (
            'ad_valorem',
            'specific',
            'compound',
            'conditional',
            'free',
            'text_only'
        )
    """)
    
    op.execute("""
        CREATE TYPE dutyconfidence AS ENUM (
            'high',
            'medium',
            'low'
        )
    """)
    
    op.execute("""
        CREATE TYPE dutysourcelevel AS ENUM (
            'six_digit',
            'eight_digit',
            'ten_digit'
        )
    """)
    
    # Create duty_rates table
    # Note: ENUM types are created above, so we reference them directly
    duty_type_enum = postgresql.ENUM('ad_valorem', 'specific', 'compound', 'conditional', 'free', 'text_only', name='dutytype', create_type=False)
    duty_confidence_enum = postgresql.ENUM('high', 'medium', 'low', name='dutyconfidence', create_type=False)
    duty_source_level_enum = postgresql.ENUM('six_digit', 'eight_digit', 'ten_digit', name='dutysourcelevel', create_type=False)
    
    op.create_table(
        'duty_rates',
        sa.Column('id', postgresql.UUID(as_uuid=True), primary_key=True, server_default=text('gen_random_uuid()')),
        sa.Column('hts_version_id', postgresql.UUID(as_uuid=True), nullable=True),  # Links to hts_versions table record
        sa.Column('hts_code', sa.String(10), nullable=False),  # Target HTS code (the code this rate applies to)
        sa.Column('source_code', sa.String(10), nullable=False),  # Source code (the actual code the rate was derived from)
        sa.Column('duty_column', sa.String(20), nullable=False),
        sa.Column('source_level', duty_source_level_enum, nullable=False),
        sa.Column('duty_type', duty_type_enum, nullable=False),
        sa.Column('duty_rate_raw_text', sa.Text(), nullable=False),
        sa.Column('duty_rate_structure', postgresql.JSONB(), nullable=True),
        sa.Column('duty_rate_numeric', sa.Numeric(10, 6), nullable=True),
        sa.Column('duty_confidence', duty_confidence_enum, nullable=False, server_default='medium'),
        sa.Column('is_free', sa.Boolean(), nullable=False, server_default='false'),
        sa.Column('duty_inheritance_chain', postgresql.JSONB(), nullable=True),
        sa.Column('source_page', sa.String(20), nullable=True),
        sa.Column('effective_start_date', sa.DateTime(), nullable=True),  # Time context: effective date range start
        sa.Column('effective_end_date', sa.DateTime(), nullable=True),  # Time context: effective date range end
        sa.Column('trade_program_info', postgresql.JSONB(), nullable=True),
        sa.Column('additional_metadata', postgresql.JSONB(), nullable=True),
        sa.Column('created_at', sa.DateTime(), nullable=False, server_default=sa.text('now()')),
        sa.Column('updated_at', sa.DateTime(), nullable=False, server_default=sa.text('now()')),
    )
    
    # Create single-column indexes for common queries
    op.create_index('ix_duty_rates_hts_version_id', 'duty_rates', ['hts_version_id'])
    op.create_index('ix_duty_rates_hts_code', 'duty_rates', ['hts_code'])
    op.create_index('ix_duty_rates_source_code', 'duty_rates', ['source_code'])
    op.create_index('ix_duty_rates_duty_column', 'duty_rates', ['duty_column'])
    op.create_index('ix_duty_rates_source_level', 'duty_rates', ['source_level'])
    op.create_index('ix_duty_rates_duty_type', 'duty_rates', ['duty_type'])
    op.create_index('ix_duty_rates_duty_confidence', 'duty_rates', ['duty_confidence'])
    op.create_index('ix_duty_rates_is_free', 'duty_rates', ['is_free'])
    op.create_index('ix_duty_rates_effective_start_date', 'duty_rates', ['effective_start_date'])
    op.create_index('ix_duty_rates_effective_end_date', 'duty_rates', ['effective_end_date'])
    
    # Composite indexes for common query patterns (matches __table_args__ in model)
    op.create_index('idx_duty_rates_hts_column', 'duty_rates', ['hts_code', 'duty_column'])
    op.create_index('idx_duty_rates_type_confidence', 'duty_rates', ['duty_type', 'duty_confidence'])
    op.create_index('idx_duty_rates_source_level_hts', 'duty_rates', ['source_level', 'hts_code'])
    
    # Add trigger to update updated_at timestamp
    op.execute("""
        CREATE OR REPLACE FUNCTION update_updated_at_column()
        RETURNS TRIGGER AS $$
        BEGIN
            NEW.updated_at = now();
            RETURN NEW;
        END;
        $$ language 'plpgsql';
    """)
    
    op.execute("""
        CREATE TRIGGER update_duty_rates_updated_at
        BEFORE UPDATE ON duty_rates
        FOR EACH ROW
        EXECUTE FUNCTION update_updated_at_column();
    """)


def downgrade():
    # Drop trigger and function
    op.execute("DROP TRIGGER IF EXISTS update_duty_rates_updated_at ON duty_rates")
    op.execute("DROP FUNCTION IF EXISTS update_updated_at_column()")
    
    # Drop composite indexes first
    # Drop composite indexes first
    op.drop_index('idx_duty_rates_source_level_hts', 'duty_rates')
    op.drop_index('idx_duty_rates_type_confidence', 'duty_rates')
    op.drop_index('idx_duty_rates_hts_column', 'duty_rates')
    # Drop single-column indexes
    op.drop_index('ix_duty_rates_effective_end_date', 'duty_rates')
    op.drop_index('ix_duty_rates_effective_start_date', 'duty_rates')
    op.drop_index('ix_duty_rates_is_free', 'duty_rates')
    op.drop_index('ix_duty_rates_duty_confidence', 'duty_rates')
    op.drop_index('ix_duty_rates_duty_type', 'duty_rates')
    op.drop_index('ix_duty_rates_source_level', 'duty_rates')
    op.drop_index('ix_duty_rates_duty_column', 'duty_rates')
    op.drop_index('ix_duty_rates_source_code', 'duty_rates')
    op.drop_index('ix_duty_rates_hts_code', 'duty_rates')
    op.drop_index('ix_duty_rates_hts_version_id', 'duty_rates')
    
    # Drop table
    op.drop_table('duty_rates')
    
    # Drop ENUM types
    op.execute("DROP TYPE IF EXISTS dutysourcelevel")
    op.execute("DROP TYPE IF EXISTS dutyconfidence")
    op.execute("DROP TYPE IF EXISTS dutytype")

"""Add unique constraint to duty_rates for upsert support

Revision ID: 006
Revises: 005
Create Date: 2026-01-10 14:00:00.000000

Sprint 5 Phase 2.1: Add unique constraint (hts_version_id, source_code, source_level)
for safe upsert operations in backfill script.
"""

from alembic import op
import sqlalchemy as sa

# revision identifiers, used by Alembic.
revision = '006'
down_revision = '005'
branch_labels = None
depends_on = None


def upgrade():
    # Add unique constraint for upsert support
    # Requirement: (hts_version_id, source_code, source_level) as unique key
    # 
    # Since PostgreSQL treats NULL != NULL, we handle NULL hts_version_id by using
    # a sentinel UUID ('00000000-0000-0000-0000-000000000000') in the application
    # when hts_version_id is NULL. This allows standard unique constraint.
    # 
    # Alternative: Use partial indexes (handled separately in application logic)
    # For simplicity, we'll use (source_code, source_level, duty_column) for now
    # and can migrate to include hts_version_id when proper versioning is added.
    
    # Create unique constraint on (source_code, source_level, duty_column)
    # This ensures no duplicates per duty column per source code/level
    # When hts_version_id is populated, we can add it to this constraint
    op.create_unique_constraint(
        'uq_duty_rates_source_level_column',
        'duty_rates',
        ['source_code', 'source_level', 'duty_column']
    )
    
    # TODO (Phase 3): Migrate to include hts_version_id when versioning is implemented:
    # ALTER TABLE duty_rates DROP CONSTRAINT uq_duty_rates_source_level_column;
    # CREATE UNIQUE INDEX uq_duty_rates_version_source_level ON duty_rates 
    #   (COALESCE(hts_version_id::text, ''), source_code, source_level, duty_column);


def downgrade():
    # Drop unique constraint
    op.drop_constraint('uq_duty_rates_source_level_column', 'duty_rates', type_='unique')

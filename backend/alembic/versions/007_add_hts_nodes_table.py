"""Add hts_nodes table for multi-level HTS hierarchy

Revision ID: 007_add_hts_nodes_table
Revises: 006_add_duty_rates_unique_constraint
Create Date: 2025-01-01 00:00:00.000000

"""
from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql
from sqlalchemy import text

# revision identifiers, used by Alembic.
revision = '007'
down_revision = '006'
branch_labels = None
depends_on = None


def upgrade():
    """
    Create hts_nodes table for storing multi-level HTS hierarchy (6, 8, 10-digit codes).
    
    Sprint 5.1.5: Hierarchy persistence using already extracted nodes.
    This table stores the authoritative parent rates from PDF extraction,
    not derived/aggregated rates from children.
    """
    op.create_table(
        'hts_nodes',
        sa.Column('id', postgresql.UUID(as_uuid=True), primary_key=True, server_default=text('gen_random_uuid()')),
        sa.Column('hts_version_id', postgresql.UUID(as_uuid=True), nullable=True, index=True),
        sa.Column('code_normalized', sa.String(10), nullable=False, index=True),  # Digits only, e.g., "8518301000"
        sa.Column('code_display', sa.String(20), nullable=True),  # With dots, e.g., "8518.30.10.00"
        sa.Column('level', sa.Integer(), nullable=False, index=True),  # 6, 8, or 10
        sa.Column('parent_code_normalized', sa.String(10), nullable=True, index=True),  # Parent node code
        sa.Column('description_short', sa.Text(), nullable=True),  # Short description
        sa.Column('description_long', sa.Text(), nullable=True),  # Full tariff text
        sa.Column('duty_general_raw', sa.Text(), nullable=True),  # Raw General duty text
        sa.Column('duty_special_raw', sa.Text(), nullable=True),  # Raw Special duty text
        sa.Column('duty_column2_raw', sa.Text(), nullable=True),  # Raw Column 2 duty text
        sa.Column('source_lineage', postgresql.JSONB(), nullable=True),  # Page, line, offsets
        sa.Column('created_at', sa.DateTime(), nullable=False, server_default=sa.text('now()')),
        sa.Column('updated_at', sa.DateTime(), nullable=False, server_default=sa.text('now()')),
    )
    
    # Unique constraint: one node per (hts_version_id, level, code_normalized)
    op.create_unique_constraint(
        'uq_hts_nodes_version_level_code',
        'hts_nodes',
        ['hts_version_id', 'level', 'code_normalized']
    )
    
    # Indexes for parent-child relationships
    op.create_index('idx_hts_nodes_parent', 'hts_nodes', ['parent_code_normalized', 'level'])
    op.create_index('idx_hts_nodes_code_level', 'hts_nodes', ['code_normalized', 'level'])
    
    # Trigger for updated_at
    op.execute("""
        CREATE TRIGGER update_hts_nodes_updated_at
        BEFORE UPDATE ON hts_nodes
        FOR EACH ROW
        EXECUTE FUNCTION update_updated_at_column();
    """)


def downgrade():
    op.drop_table('hts_nodes')

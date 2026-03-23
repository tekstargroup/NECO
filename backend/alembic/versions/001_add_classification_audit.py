"""add_classification_audit_table

Revision ID: 001
Revises: 
Create Date: 2026-01-08

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

# revision identifiers, used by Alembic.
revision: str = '001'
down_revision: Union[str, None] = None
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    # Create classification_audit table
    op.create_table(
        'classification_audit',
        sa.Column('id', postgresql.UUID(as_uuid=True), primary_key=True, server_default=sa.text('gen_random_uuid()')),
        sa.Column('sku_id', postgresql.UUID(as_uuid=True), nullable=True),
        sa.Column('client_id', postgresql.UUID(as_uuid=True), nullable=True),
        sa.Column('input_description', sa.Text(), nullable=False),
        sa.Column('input_coo', sa.String(2), nullable=True),
        sa.Column('input_value', sa.String(50), nullable=True),
        sa.Column('input_qty', sa.String(50), nullable=True),
        sa.Column('input_current_hts', sa.String(10), nullable=True),
        sa.Column('engine_version', sa.String(20), nullable=True),
        sa.Column('analysis_timestamp', sa.DateTime(), nullable=False),
        sa.Column('context_payload', postgresql.JSONB(), nullable=True),
        sa.Column('prompt', sa.Text(), nullable=True),
        sa.Column('response', sa.Text(), nullable=True),
        sa.Column('provenance', postgresql.JSONB(), nullable=True),
        sa.Column('candidates_generated', sa.String(10), nullable=True),
        sa.Column('top_candidate_hts', sa.String(10), nullable=True),
        sa.Column('top_candidate_score', sa.String(20), nullable=True),
        sa.Column('processing_time_ms', sa.String(20), nullable=True),
        sa.Column('error_message', sa.Text(), nullable=True),
        sa.Column('created_at', sa.DateTime(), nullable=False),
        sa.ForeignKeyConstraint(['sku_id'], ['skus.id'], ),
        sa.ForeignKeyConstraint(['client_id'], ['clients.id'], ),
    )
    op.create_index('ix_classification_audit_sku_id', 'classification_audit', ['sku_id'], unique=False)
    op.create_index('ix_classification_audit_client_id', 'classification_audit', ['client_id'], unique=False)
    op.create_index('ix_classification_audit_created_at', 'classification_audit', ['created_at'], unique=False)


def downgrade() -> None:
    # Drop indexes if they exist
    try:
        op.drop_index('ix_classification_audit_created_at', table_name='classification_audit')
    except:
        pass
    try:
        op.drop_index('ix_classification_audit_client_id', table_name='classification_audit')
    except:
        pass
    try:
        op.drop_index('ix_classification_audit_sku_id', table_name='classification_audit')
    except:
        pass
    op.drop_table('classification_audit')


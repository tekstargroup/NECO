"""add_audit_replayability_fields

Revision ID: 003
Revises: 002
Create Date: 2026-01-08

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

# revision identifiers, used by Alembic.
revision: str = '003'
down_revision: Union[str, None] = '002'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    # Add audit replayability fields to classification_audit table
    op.add_column('classification_audit', sa.Column('applied_filters', postgresql.JSONB(), nullable=True))
    op.add_column('classification_audit', sa.Column('candidate_counts', postgresql.JSONB(), nullable=True))
    op.add_column('classification_audit', sa.Column('similarity_top', sa.String(20), nullable=True))
    op.add_column('classification_audit', sa.Column('threshold_used', sa.String(20), nullable=True))
    op.add_column('classification_audit', sa.Column('reason_code', sa.String(50), nullable=True))
    op.add_column('classification_audit', sa.Column('status', sa.String(50), nullable=True))


def downgrade() -> None:
    op.drop_column('classification_audit', 'status')
    op.drop_column('classification_audit', 'reason_code')
    op.drop_column('classification_audit', 'threshold_used')
    op.drop_column('classification_audit', 'similarity_top')
    op.drop_column('classification_audit', 'candidate_counts')
    op.drop_column('classification_audit', 'applied_filters')

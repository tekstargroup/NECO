"""Add product analysis and clarification fields to classification_audit

Revision ID: 004_add_product_analysis_fields
Revises: 003_add_audit_replayability_fields
Create Date: 2026-01-09 12:00:00.000000

"""
from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

# revision identifiers, used by Alembic.
revision = '004'
down_revision = '003'
branch_labels = None
depends_on = None


def upgrade():
    # Add product analysis and clarification fields
    op.add_column('classification_audit', sa.Column('product_analysis', postgresql.JSONB(), nullable=True))
    op.add_column('classification_audit', sa.Column('clarification_questions', postgresql.JSONB(), nullable=True))
    op.add_column('classification_audit', sa.Column('clarification_responses', postgresql.JSONB(), nullable=True))


def downgrade():
    # Remove product analysis and clarification fields
    op.drop_column('classification_audit', 'clarification_responses')
    op.drop_column('classification_audit', 'clarification_questions')
    op.drop_column('classification_audit', 'product_analysis')

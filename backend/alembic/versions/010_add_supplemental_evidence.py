"""Add supplemental evidence to shipment_items

Revision ID: 010
Revises: 009
Create Date: 2025-02-24

Adds columns for per-line-item supplemental evidence (Amazon URL scrape or PDF)
to improve HTS classification when product description is vague.
"""

from alembic import op
import sqlalchemy as sa

revision = "010"
down_revision = "009"
branch_labels = None
depends_on = None


def upgrade():
    op.add_column(
        "shipment_items",
        sa.Column("supplemental_evidence_text", sa.Text(), nullable=True),
    )
    op.add_column(
        "shipment_items",
        sa.Column("supplemental_evidence_source", sa.String(50), nullable=True),
    )


def downgrade():
    op.drop_column("shipment_items", "supplemental_evidence_source")
    op.drop_column("shipment_items", "supplemental_evidence_text")

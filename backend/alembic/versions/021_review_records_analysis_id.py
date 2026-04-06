"""Review records: analysis_id for idempotent persist on same-analysis retry

Revision ID: 021_review_records_analysis_id
Revises: 020_analysis_pipeline_stages
Create Date: 2026-04-03
"""

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql
from sqlalchemy import text

revision = "021_review_records_analysis_id"
down_revision = "020_analysis_pipeline_stages"
branch_labels = None
depends_on = None


def upgrade():
    op.add_column(
        "review_records",
        sa.Column(
            "analysis_id",
            postgresql.UUID(as_uuid=True),
            sa.ForeignKey("analyses.id", ondelete="SET NULL"),
            nullable=True,
        ),
    )
    op.create_index("ix_review_records_analysis_id", "review_records", ["analysis_id"])
    op.execute(
        text(
            """
            UPDATE review_records rr
            SET analysis_id = a.id
            FROM analyses a
            WHERE a.review_record_id = rr.id AND rr.analysis_id IS NULL;
            """
        )
    )
    op.create_unique_constraint(
        "uq_review_records_analysis_id",
        "review_records",
        ["analysis_id"],
    )


def downgrade():
    op.drop_constraint("uq_review_records_analysis_id", "review_records", type_="unique")
    op.drop_index("ix_review_records_analysis_id", table_name="review_records")
    op.drop_column("review_records", "analysis_id")

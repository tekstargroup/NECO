"""Phase 1 — Active analysis integrity: partial unique index + backfill gaps

Revision ID: 019_phase1_active_integrity
Revises: 018_phase1_analysis_identity
Create Date: 2026-04-03

- Partial UNIQUE on (shipment_id) WHERE is_active (at most one active row per shipment).
- Backfill: exactly one COMPLETE analysis per shipment (highest version, then latest completion) is active;
  all shipment_items.active_analysis_id point to that row.
"""

from alembic import op
from sqlalchemy import text

revision = "019_phase1_active_integrity"
down_revision = "018_phase1_analysis_identity"
branch_labels = None
depends_on = None


def upgrade():
    op.execute(
        text(
            """
            WITH best AS (
                SELECT DISTINCT ON (shipment_id)
                    id AS analysis_id,
                    shipment_id
                FROM analyses
                WHERE status = 'COMPLETE'
                ORDER BY shipment_id, version DESC, COALESCE(completed_at, created_at) DESC
            )
            UPDATE analyses a
            SET is_active = (a.id IN (SELECT analysis_id FROM best));
            """
        )
    )
    op.execute(
        text(
            """
            WITH best AS (
                SELECT DISTINCT ON (shipment_id)
                    id AS analysis_id,
                    shipment_id
                FROM analyses
                WHERE status = 'COMPLETE'
                ORDER BY shipment_id, version DESC, COALESCE(completed_at, created_at) DESC
            )
            UPDATE shipment_items si
            SET active_analysis_id = best.analysis_id
            FROM best
            WHERE si.shipment_id = best.shipment_id;
            """
        )
    )

    op.execute(
        """
        CREATE UNIQUE INDEX IF NOT EXISTS uq_analyses_one_active_per_shipment
        ON analyses (shipment_id)
        WHERE is_active = true;
        """
    )


def downgrade():
    op.execute("DROP INDEX IF EXISTS uq_analyses_one_active_per_shipment")

"""Backfill CLASSIFICATION + FACT_PERSIST rows from legacy CLASSIFICATION_AND_FACTS

Revision ID: 022_backfill_classification_fact_stages_from_legacy
Revises: 021_review_records_analysis_id
Create Date: 2026-04-03

For each analysis_pipeline_stages row where stage = CLASSIFICATION_AND_FACTS and status = SUCCEEDED,
insert CLASSIFICATION and FACT_PERSIST with the same shipment/org/timestamps if missing.
Downgrade removes only those paired rows where a legacy row still exists (best-effort).
"""

from alembic import op
from sqlalchemy import text

revision = "022_backfill_classification_fact_stages_from_legacy"
down_revision = "021_review_records_analysis_id"
branch_labels = None
depends_on = None


def upgrade():
    op.execute(
        text(
            """
            INSERT INTO analysis_pipeline_stages (
                id, analysis_id, shipment_id, organization_id, stage, status,
                error_code, error_message, error_details, started_at, completed_at, ordinal
            )
            SELECT gen_random_uuid(), s.analysis_id, s.shipment_id, s.organization_id,
                   'CLASSIFICATION', s.status, s.error_code, s.error_message, s.error_details,
                   s.started_at, s.completed_at, 30
            FROM analysis_pipeline_stages s
            WHERE s.stage = 'CLASSIFICATION_AND_FACTS' AND s.status = 'SUCCEEDED'
              AND NOT EXISTS (
                  SELECT 1 FROM analysis_pipeline_stages x
                  WHERE x.analysis_id = s.analysis_id AND x.stage = 'CLASSIFICATION'
              );
            """
        )
    )
    op.execute(
        text(
            """
            INSERT INTO analysis_pipeline_stages (
                id, analysis_id, shipment_id, organization_id, stage, status,
                error_code, error_message, error_details, started_at, completed_at, ordinal
            )
            SELECT gen_random_uuid(), s.analysis_id, s.shipment_id, s.organization_id,
                   'FACT_PERSIST', s.status, s.error_code, s.error_message, s.error_details,
                   s.started_at, s.completed_at, 31
            FROM analysis_pipeline_stages s
            WHERE s.stage = 'CLASSIFICATION_AND_FACTS' AND s.status = 'SUCCEEDED'
              AND NOT EXISTS (
                  SELECT 1 FROM analysis_pipeline_stages x
                  WHERE x.analysis_id = s.analysis_id AND x.stage = 'FACT_PERSIST'
              );
            """
        )
    )


def downgrade():
    op.execute(
        text(
            """
            DELETE FROM analysis_pipeline_stages a
            USING analysis_pipeline_stages leg
            WHERE leg.stage = 'CLASSIFICATION_AND_FACTS'
              AND leg.analysis_id = a.analysis_id
              AND a.stage IN ('CLASSIFICATION', 'FACT_PERSIST')
              AND a.status = 'SUCCEEDED';
            """
        )
    )

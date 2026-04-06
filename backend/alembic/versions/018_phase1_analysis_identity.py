"""Phase 1 — Decision integrity: analysis lifecycle + active pointer per item

Revision ID: 018_phase1_analysis_identity
Revises: 017_classification_facts
Create Date: 2026-04-03

Adds:
- analyses.version, decision_status, supersedes_analysis_id, is_active
- shipment_items.active_analysis_id (FK analyses.id)

Backfills active analysis from latest COMPLETE run per shipment (legacy behavior codified).
"""

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql
from sqlalchemy import text

revision = "018_phase1_analysis_identity"
down_revision = "017_classification_facts"
branch_labels = None
depends_on = None


def upgrade():
    op.execute(
        """
        DO $$ BEGIN
            CREATE TYPE decisionstatus AS ENUM (
                'TRUSTED',
                'REVIEW_REQUIRED',
                'INSUFFICIENT_DATA',
                'DEGRADED',
                'BLOCKED'
            );
        EXCEPTION
            WHEN duplicate_object THEN null;
        END $$;
        """
    )

    decision_enum = postgresql.ENUM(
        "TRUSTED",
        "REVIEW_REQUIRED",
        "INSUFFICIENT_DATA",
        "DEGRADED",
        "BLOCKED",
        name="decisionstatus",
        create_type=False,
    )

    op.add_column(
        "analyses",
        sa.Column("version", sa.Integer(), nullable=False, server_default="1"),
    )
    op.add_column("analyses", sa.Column("decision_status", decision_enum, nullable=True))
    op.add_column(
        "analyses",
        sa.Column(
            "supersedes_analysis_id",
            postgresql.UUID(as_uuid=True),
            sa.ForeignKey("analyses.id", ondelete="SET NULL"),
            nullable=True,
        ),
    )
    op.add_column(
        "analyses",
        sa.Column("is_active", sa.Boolean(), nullable=False, server_default=sa.text("false")),
    )
    op.create_index(
        "ix_analyses_shipment_active",
        "analyses",
        ["shipment_id", "is_active"],
    )

    op.add_column(
        "shipment_items",
        sa.Column(
            "active_analysis_id",
            postgresql.UUID(as_uuid=True),
            sa.ForeignKey("analyses.id", ondelete="SET NULL"),
            nullable=True,
        ),
    )
    op.create_index(
        "ix_shipment_items_active_analysis_id",
        "shipment_items",
        ["active_analysis_id"],
    )

    # Backfill: latest COMPLETE analysis per shipment becomes active; items point to it.
    op.execute(
        text(
            """
            WITH ranked AS (
                SELECT DISTINCT ON (shipment_id)
                    id AS analysis_id,
                    shipment_id
                FROM analyses
                WHERE status = 'COMPLETE'
                ORDER BY shipment_id, COALESCE(completed_at, created_at) DESC
            )
            UPDATE analyses a
            SET is_active = (a.id IN (SELECT analysis_id FROM ranked));
            """
        )
    )
    op.execute(
        text(
            """
            WITH ranked AS (
                SELECT DISTINCT ON (shipment_id)
                    id AS analysis_id,
                    shipment_id
                FROM analyses
                WHERE status = 'COMPLETE'
                ORDER BY shipment_id, COALESCE(completed_at, created_at) DESC
            )
            UPDATE shipment_items si
            SET active_analysis_id = ranked.analysis_id
            FROM ranked
            WHERE si.shipment_id = ranked.shipment_id;
            """
        )
    )

    op.alter_column("analyses", "version", server_default=None)


def downgrade():
    op.drop_index("ix_shipment_items_active_analysis_id", table_name="shipment_items")
    op.drop_column("shipment_items", "active_analysis_id")

    op.drop_index("ix_analyses_shipment_active", table_name="analyses")
    op.drop_column("analyses", "is_active")
    op.drop_column("analyses", "supersedes_analysis_id")
    op.drop_column("analyses", "decision_status")
    op.drop_column("analyses", "version")

    op.execute("DROP TYPE IF EXISTS decisionstatus")

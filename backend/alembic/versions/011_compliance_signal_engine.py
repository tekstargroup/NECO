"""Compliance Signal Engine tables

Revision ID: 011
Revises: 010
Create Date: 2025-03-17

Adds tables for Compliance Signal Engine:
- raw_signals: raw ingestion from RSS/API
- normalized_signals: parsed and normalized
- signal_classifications: category, impact_type
- signal_scores: relevance, financial, urgency, final
- psc_alerts: actionable alerts linked to signals
- importer_hts_usage: HTS usage per org for scoring
"""

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql
from sqlalchemy import text

revision = "011"
down_revision = "010"
branch_labels = None
depends_on = None


def upgrade():
    # Create signal category enum (idempotent)
    op.execute("""
        DO $$ BEGIN
            CREATE TYPE signalcategory AS ENUM (
                'TARIFF_CHANGE',
                'HTS_UPDATE',
                'QUOTA_UPDATE',
                'SANCTION',
                'IMPORT_RESTRICTION',
                'RULING',
                'TRADE_ACTION',
                'DOCUMENTATION_RULE'
            );
        EXCEPTION
            WHEN duplicate_object THEN NULL;
        END $$;
    """)

    # Create psc_alert_status enum (idempotent)
    op.execute("""
        DO $$ BEGIN
            CREATE TYPE pscalertstatus AS ENUM (
                'new',
                'reviewed',
                'dismissed'
            );
        EXCEPTION
            WHEN duplicate_object THEN NULL;
        END $$;
    """)

    # raw_signals
    op.create_table(
        "raw_signals",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True, server_default=text("gen_random_uuid()")),
        sa.Column("source", sa.String(100), nullable=False, index=True),
        sa.Column("title", sa.String(500), nullable=False),
        sa.Column("content", sa.Text(), nullable=True),
        sa.Column("url", sa.String(1000), nullable=False, index=True),
        sa.Column("published_at", sa.DateTime(), nullable=True, index=True),
        sa.Column("ingested_at", sa.DateTime(), nullable=False, server_default=sa.text("now()"), index=True),
    )
    op.create_index("idx_raw_signals_url", "raw_signals", ["url"], unique=True)
    op.create_index("idx_raw_signals_source_ingested", "raw_signals", ["source", "ingested_at"])

    # normalized_signals
    op.create_table(
        "normalized_signals",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True, server_default=text("gen_random_uuid()")),
        sa.Column("raw_signal_id", postgresql.UUID(as_uuid=True), nullable=False, index=True),
        sa.Column("summary", sa.Text(), nullable=True),
        sa.Column("full_text", sa.Text(), nullable=True),
        sa.Column("signal_type", sa.String(50), nullable=True, index=True),
        sa.Column("countries", postgresql.JSONB(), nullable=True),
        sa.Column("hts_codes", postgresql.JSONB(), nullable=True),
        sa.Column("keywords", postgresql.JSONB(), nullable=True),
        sa.Column("effective_date", sa.Date(), nullable=True),
        sa.Column("confidence", sa.Float(), nullable=True),
        sa.ForeignKeyConstraint(["raw_signal_id"], ["raw_signals.id"], ondelete="CASCADE"),
    )
    op.create_index("idx_normalized_signals_raw", "normalized_signals", ["raw_signal_id"])

    # signal_classifications
    signalcategory_enum = postgresql.ENUM(
        "TARIFF_CHANGE", "HTS_UPDATE", "QUOTA_UPDATE", "SANCTION",
        "IMPORT_RESTRICTION", "RULING", "TRADE_ACTION", "DOCUMENTATION_RULE",
        name="signalcategory", create_type=False
    )
    op.create_table(
        "signal_classifications",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True, server_default=text("gen_random_uuid()")),
        sa.Column("signal_id", postgresql.UUID(as_uuid=True), nullable=False, index=True),
        sa.Column("category", signalcategory_enum, nullable=False, index=True),
        sa.Column("impact_type", sa.String(100), nullable=True),
        sa.Column("affected_entities", postgresql.JSONB(), nullable=True),
        sa.ForeignKeyConstraint(["signal_id"], ["normalized_signals.id"], ondelete="CASCADE"),
    )
    op.create_index("idx_signal_classifications_signal", "signal_classifications", ["signal_id"])

    # signal_scores
    op.create_table(
        "signal_scores",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True, server_default=text("gen_random_uuid()")),
        sa.Column("signal_id", postgresql.UUID(as_uuid=True), nullable=False, index=True),
        sa.Column("organization_id", postgresql.UUID(as_uuid=True), nullable=True, index=True),
        sa.Column("relevance_score", sa.Integer(), nullable=True),
        sa.Column("financial_impact_score", sa.Integer(), nullable=True),
        sa.Column("urgency_score", sa.Integer(), nullable=True),
        sa.Column("confidence_score", sa.Integer(), nullable=True),
        sa.Column("final_score", sa.Float(), nullable=True, index=True),
        sa.ForeignKeyConstraint(["signal_id"], ["normalized_signals.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["organization_id"], ["organizations.id"], ondelete="CASCADE"),
    )
    op.create_index("idx_signal_scores_org_final", "signal_scores", ["organization_id", "final_score"])

    # psc_alerts (organization-scoped for tenant isolation)
    pscalertstatus_enum = postgresql.ENUM("new", "reviewed", "dismissed", name="pscalertstatus", create_type=False)
    op.create_table(
        "psc_alerts",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True, server_default=text("gen_random_uuid()")),
        sa.Column("organization_id", postgresql.UUID(as_uuid=True), nullable=False, index=True),
        sa.Column("signal_id", postgresql.UUID(as_uuid=True), nullable=False, index=True),
        sa.Column("shipment_id", postgresql.UUID(as_uuid=True), nullable=True, index=True),
        sa.Column("shipment_item_id", postgresql.UUID(as_uuid=True), nullable=True, index=True),
        sa.Column("entry_id", postgresql.UUID(as_uuid=True), nullable=True, index=True),
        sa.Column("line_item_id", postgresql.UUID(as_uuid=True), nullable=True, index=True),
        sa.Column("hts_code", sa.String(10), nullable=True, index=True),
        sa.Column("alert_type", sa.String(100), nullable=True),
        sa.Column("duty_delta_estimate", sa.String(100), nullable=True),
        sa.Column("reason", sa.Text(), nullable=True),
        sa.Column("evidence_links", postgresql.JSONB(), nullable=True),
        sa.Column("status", pscalertstatus_enum, nullable=False, server_default="new", index=True),
        sa.Column("explanation", postgresql.JSONB(), nullable=True),
        sa.Column("created_at", sa.DateTime(), nullable=False, server_default=sa.text("now()"), index=True),
        sa.ForeignKeyConstraint(["organization_id"], ["organizations.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["signal_id"], ["normalized_signals.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["shipment_id"], ["shipments.id"], ondelete="SET NULL"),
        sa.ForeignKeyConstraint(["shipment_item_id"], ["shipment_items.id"], ondelete="SET NULL"),
        # entry_id, line_item_id: no FK (entries/line_items may not exist in all deployments)
    )
    op.create_index("idx_psc_alerts_org_status", "psc_alerts", ["organization_id", "status"])
    op.create_index("idx_psc_alerts_created", "psc_alerts", ["created_at"])

    # importer_hts_usage (materialized/derived view or table for scoring)
    op.create_table(
        "importer_hts_usage",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True, server_default=text("gen_random_uuid()")),
        sa.Column("organization_id", postgresql.UUID(as_uuid=True), nullable=False, index=True),
        sa.Column("hts_code", sa.String(10), nullable=False, index=True),
        sa.Column("frequency", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("total_value", sa.Numeric(15, 2), nullable=True),
        sa.Column("last_used_at", sa.DateTime(), nullable=True),
        sa.ForeignKeyConstraint(["organization_id"], ["organizations.id"], ondelete="CASCADE"),
    )
    op.create_unique_constraint("uq_importer_hts_usage_org_hts", "importer_hts_usage", ["organization_id", "hts_code"])
    op.create_index("idx_importer_hts_usage_org", "importer_hts_usage", ["organization_id"])


def downgrade():
    op.drop_table("importer_hts_usage")
    op.drop_table("psc_alerts")
    op.drop_table("signal_scores")
    op.drop_table("signal_classifications")
    op.drop_table("normalized_signals")
    op.drop_table("raw_signals")
    op.execute("DROP TYPE IF EXISTS pscalertstatus")
    op.execute("DROP TYPE IF EXISTS signalcategory")

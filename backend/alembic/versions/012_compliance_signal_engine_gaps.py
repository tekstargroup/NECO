"""Compliance Signal Engine GAPs - quota, tariff, FDA, CBP rulings, product_hts_map

Revision ID: 012
Revises: 011
Create Date: 2025-03-17

Adds:
- quota_status
- import_restrictions
- cbp_rulings
- product_hts_map
- normalized_signals: duty_rate_change, affected_hts_codes
- psc_alerts: confidence_score, priority
"""

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql
from sqlalchemy import text

revision = "012"
down_revision = "011"
branch_labels = None
depends_on = None


def upgrade():
    # quota_status (GAP 1)
    op.create_table(
        "quota_status",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True, server_default=text("gen_random_uuid()")),
        sa.Column("hts_code", sa.Text(), nullable=False, index=True),
        sa.Column("country", sa.Text(), nullable=True, index=True),
        sa.Column("quota_type", sa.Text(), nullable=True),
        sa.Column("quota_limit", sa.Numeric(15, 3), nullable=True),
        sa.Column("quantity_used", sa.Numeric(15, 3), nullable=True),
        sa.Column("fill_rate", sa.Numeric(5, 4), nullable=True),
        sa.Column("status", sa.String(20), nullable=True, index=True),  # open, near_limit, filled
        sa.Column("effective_date", sa.Date(), nullable=True),
        sa.Column("last_updated", sa.DateTime(), nullable=False, server_default=sa.text("now()")),
        sa.Column("source_signal_id", postgresql.UUID(as_uuid=True), nullable=True, index=True),
    )
    op.create_index("idx_quota_status_hts_country", "quota_status", ["hts_code", "country"])

    # import_restrictions (GAP 3)
    op.create_table(
        "import_restrictions",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True, server_default=text("gen_random_uuid()")),
        sa.Column("agency", sa.String(100), nullable=False, index=True),
        sa.Column("product_keywords", postgresql.JSONB(), nullable=True),
        sa.Column("hts_codes", postgresql.JSONB(), nullable=True),
        sa.Column("country", sa.String(2), nullable=True, index=True),
        sa.Column("severity", sa.String(20), nullable=True),
        sa.Column("description", sa.Text(), nullable=True),
        sa.Column("source_url", sa.String(1000), nullable=True),
        sa.Column("effective_date", sa.Date(), nullable=True),
        sa.Column("created_at", sa.DateTime(), nullable=False, server_default=sa.text("now()")),
    )
    op.create_index("idx_import_restrictions_hts", "import_restrictions", ["hts_codes"], postgresql_using="gin")

    # cbp_rulings (GAP 4) - idempotent
    op.execute("""
        CREATE TABLE IF NOT EXISTS cbp_rulings (
            id UUID DEFAULT gen_random_uuid() PRIMARY KEY,
            ruling_number VARCHAR(50) NOT NULL,
            hts_codes JSONB,
            description TEXT,
            full_text TEXT,
            ruling_date DATE,
            source_url VARCHAR(1000),
            raw_signal_id UUID,
            created_at TIMESTAMP WITHOUT TIME ZONE DEFAULT now() NOT NULL
        )
    """)
    # Add missing columns if table existed with different schema
    op.execute("""
        DO $$ BEGIN
            IF NOT EXISTS (SELECT 1 FROM information_schema.columns WHERE table_name='cbp_rulings' AND column_name='ruling_number') THEN
                ALTER TABLE cbp_rulings ADD COLUMN ruling_number VARCHAR(50);
                UPDATE cbp_rulings SET ruling_number = 'UNKNOWN' WHERE ruling_number IS NULL;
                ALTER TABLE cbp_rulings ALTER COLUMN ruling_number SET NOT NULL;
            END IF;
        END $$;
    """)
    op.execute("CREATE INDEX IF NOT EXISTS idx_cbp_rulings_hts ON cbp_rulings USING gin (hts_codes)")
    op.execute("""
        DO $$ BEGIN
            IF EXISTS (SELECT 1 FROM information_schema.columns WHERE table_name='cbp_rulings' AND column_name='ruling_number')
               AND NOT EXISTS (SELECT 1 FROM pg_indexes WHERE indexname='idx_cbp_rulings_number') THEN
                CREATE INDEX idx_cbp_rulings_number ON cbp_rulings (ruling_number);
            END IF;
        END $$;
    """)

    # product_hts_map (GAP 5 / pinned)
    op.create_table(
        "product_hts_map",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True, server_default=text("gen_random_uuid()")),
        sa.Column("product_id", postgresql.UUID(as_uuid=True), nullable=False, index=True),
        sa.Column("hts_code", sa.String(10), nullable=False, index=True),
        sa.Column("confidence", sa.Float(), nullable=True),
        sa.Column("source", sa.String(50), nullable=True),
        sa.Column("created_at", sa.DateTime(), nullable=False, server_default=sa.text("now()")),
    )
    op.create_index("idx_product_hts_map_product", "product_hts_map", ["product_id"])
    op.create_index("idx_product_hts_map_hts", "product_hts_map", ["hts_code"])

    # Extend normalized_signals (GAP 2)
    op.add_column("normalized_signals", sa.Column("duty_rate_change", sa.Numeric(7, 4), nullable=True))
    op.add_column("normalized_signals", sa.Column("affected_hts_codes", postgresql.JSONB(), nullable=True))
    op.add_column("normalized_signals", sa.Column("quota_limit", sa.Numeric(15, 3), nullable=True))
    op.add_column("normalized_signals", sa.Column("quota_used", sa.Numeric(15, 3), nullable=True))
    op.add_column("normalized_signals", sa.Column("old_duty_rate", sa.Numeric(7, 4), nullable=True))
    op.add_column("normalized_signals", sa.Column("new_duty_rate", sa.Numeric(7, 4), nullable=True))

    # Extend psc_alerts (GAP 8, 9)
    op.add_column("psc_alerts", sa.Column("confidence_score", sa.Float(), nullable=True))
    op.add_column("psc_alerts", sa.Column("priority", sa.String(20), nullable=True))
    op.add_column("psc_alerts", sa.Column("signal_source", sa.String(100), nullable=True))


def downgrade():
    op.drop_column("psc_alerts", "signal_source")
    op.drop_column("psc_alerts", "priority")
    op.drop_column("psc_alerts", "confidence_score")
    op.drop_column("normalized_signals", "new_duty_rate")
    op.drop_column("normalized_signals", "old_duty_rate")
    op.drop_column("normalized_signals", "quota_used")
    op.drop_column("normalized_signals", "quota_limit")
    op.drop_column("normalized_signals", "affected_hts_codes")
    op.drop_column("normalized_signals", "duty_rate_change")
    op.drop_table("product_hts_map")
    op.drop_table("cbp_rulings")
    op.drop_table("import_restrictions")
    op.drop_table("quota_status")

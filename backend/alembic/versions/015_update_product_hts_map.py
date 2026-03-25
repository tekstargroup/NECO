"""Update product_hts_map to match knowledge layer model

Revision ID: 015_product_knowledge
Revises: 014_trust
Create Date: 2026-03-24

Migration 012 created product_hts_map with only (product_id, hts_code,
confidence, source, created_at). The Phase 3 knowledge layer model
requires organization-scoped description-hash lookups, provenance,
supersede tracking, and audit fields.
"""
from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql
from sqlalchemy import text

revision = "015_product_knowledge"
down_revision = "014_trust"
branch_labels = None
depends_on = None


def upgrade():
    # Drop the old product_id column (no longer used)
    op.drop_index("idx_product_hts_map_product", table_name="product_hts_map")
    op.drop_column("product_hts_map", "product_id")

    # Add new columns required by the ProductHTSMap model
    op.add_column("product_hts_map", sa.Column(
        "organization_id", postgresql.UUID(as_uuid=True), nullable=False,
        server_default=text("'00000000-0000-0000-0000-000000000000'::uuid"),
    ))
    op.add_column("product_hts_map", sa.Column("description_hash", sa.String(64), nullable=False, server_default=""))
    op.add_column("product_hts_map", sa.Column("description_text", sa.Text(), nullable=True))
    op.add_column("product_hts_map", sa.Column("hts_heading", sa.String(4), nullable=True))
    op.add_column("product_hts_map", sa.Column("country_of_origin", sa.String(3), nullable=True))
    op.add_column("product_hts_map", sa.Column("source_review_id", postgresql.UUID(as_uuid=True), nullable=True))
    op.add_column("product_hts_map", sa.Column("source_shipment_id", postgresql.UUID(as_uuid=True), nullable=True))
    op.add_column("product_hts_map", sa.Column("source_item_id", postgresql.UUID(as_uuid=True), nullable=True))
    op.add_column("product_hts_map", sa.Column("provenance", postgresql.JSONB(), nullable=True))
    op.add_column("product_hts_map", sa.Column("accepted_by", sa.String(255), nullable=True))
    op.add_column("product_hts_map", sa.Column("accepted_at", sa.DateTime(), nullable=True))
    op.add_column("product_hts_map", sa.Column("superseded", sa.Boolean(), nullable=False, server_default="false"))
    op.add_column("product_hts_map", sa.Column("superseded_by_id", postgresql.UUID(as_uuid=True), nullable=True))
    op.add_column("product_hts_map", sa.Column("updated_at", sa.DateTime(), nullable=True))

    # Update source column default
    op.alter_column("product_hts_map", "source", server_default="review_accepted")

    # Indexes for the knowledge lookup query
    op.create_index("idx_product_hts_map_org_id", "product_hts_map", ["organization_id"])
    op.create_index("idx_product_hts_map_desc_hash", "product_hts_map", ["description_hash"])
    op.create_index(
        "idx_product_hts_map_org_desc_hash",
        "product_hts_map",
        ["organization_id", "description_hash"],
    )

    # Remove server defaults that were only needed for the migration
    op.alter_column("product_hts_map", "organization_id", server_default=None)
    op.alter_column("product_hts_map", "description_hash", server_default=None)
    op.alter_column("product_hts_map", "superseded", server_default=None)


def downgrade():
    op.drop_index("idx_product_hts_map_org_desc_hash", table_name="product_hts_map")
    op.drop_index("idx_product_hts_map_desc_hash", table_name="product_hts_map")
    op.drop_index("idx_product_hts_map_org_id", table_name="product_hts_map")

    op.drop_column("product_hts_map", "updated_at")
    op.drop_column("product_hts_map", "superseded_by_id")
    op.drop_column("product_hts_map", "superseded")
    op.drop_column("product_hts_map", "accepted_at")
    op.drop_column("product_hts_map", "accepted_by")
    op.drop_column("product_hts_map", "provenance")
    op.drop_column("product_hts_map", "source_item_id")
    op.drop_column("product_hts_map", "source_shipment_id")
    op.drop_column("product_hts_map", "source_review_id")
    op.drop_column("product_hts_map", "country_of_origin")
    op.drop_column("product_hts_map", "hts_heading")
    op.drop_column("product_hts_map", "description_text")
    op.drop_column("product_hts_map", "description_hash")
    op.drop_column("product_hts_map", "organization_id")

    # Revert source column default to match 012 (no default)
    op.alter_column("product_hts_map", "source", server_default=None)

    # Re-add product_id with a migration-safe default for existing rows
    op.add_column("product_hts_map", sa.Column(
        "product_id", postgresql.UUID(as_uuid=True), nullable=False,
        server_default=text("gen_random_uuid()"),
    ))
    op.alter_column("product_hts_map", "product_id", server_default=None)
    op.create_index("idx_product_hts_map_product", "product_hts_map", ["product_id"])

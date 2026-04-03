"""
Apply missing 014_trust pieces when the DB is partially migrated (e.g. table exists
but columns/indexes were never applied). Idempotent — safe to run more than once.

Run from backend/:
  source venv/bin/activate
  python scripts/complete_partial_014.py
Then:
  python scripts/verify_alembic_014.py
  alembic stamp 014_trust
  alembic upgrade head
"""
import asyncio
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from sqlalchemy import text
from sqlalchemy.ext.asyncio import create_async_engine
from app.core.config import settings

STATEMENTS = [
    # shipment_documents columns (match 014_trust_workflow_ingestion_item_links.py)
    "ALTER TABLE shipment_documents ADD COLUMN IF NOT EXISTS extraction_method VARCHAR(32)",
    "ALTER TABLE shipment_documents ADD COLUMN IF NOT EXISTS ocr_used BOOLEAN",
    "ALTER TABLE shipment_documents ADD COLUMN IF NOT EXISTS page_count INTEGER",
    "ALTER TABLE shipment_documents ADD COLUMN IF NOT EXISTS char_count INTEGER",
    "ALTER TABLE shipment_documents ADD COLUMN IF NOT EXISTS table_detected BOOLEAN",
    "ALTER TABLE shipment_documents ADD COLUMN IF NOT EXISTS extraction_status VARCHAR(32)",
    "ALTER TABLE shipment_documents ADD COLUMN IF NOT EXISTS usable_for_analysis BOOLEAN",
    "ALTER TABLE shipment_documents ADD COLUMN IF NOT EXISTS data_sheet_user_confirmed BOOLEAN NOT NULL DEFAULT false",
    # review_records
    "ALTER TABLE review_records ADD COLUMN IF NOT EXISTS item_decisions JSONB",
    # Indexes (names must match migration)
    "CREATE INDEX IF NOT EXISTS ix_shipment_item_documents_item ON shipment_item_documents (shipment_item_id)",
    "CREATE INDEX IF NOT EXISTS ix_shipment_item_documents_doc ON shipment_item_documents (shipment_document_id)",
]


async def main() -> None:
    engine = create_async_engine(settings.DATABASE_URL)
    async with engine.begin() as conn:
        for sql in STATEMENTS:
            await conn.execute(text(sql))
            print("OK:", sql[:70] + ("..." if len(sql) > 70 else ""))
    await engine.dispose()
    print("\nDone. Run: python scripts/verify_alembic_014.py")


if __name__ == "__main__":
    asyncio.run(main())

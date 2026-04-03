"""Verify DB matches alembic 014_trust before stamping. Run from backend/: python scripts/verify_alembic_014.py"""
import asyncio
import sys
from pathlib import Path

# So `from app...` works when cwd is backend/ (not only via uvicorn)
sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
from sqlalchemy import text
from sqlalchemy.ext.asyncio import create_async_engine
from app.core.config import settings

DOC_COLS = (
    "extraction_method",
    "ocr_used",
    "page_count",
    "char_count",
    "table_detected",
    "extraction_status",
    "usable_for_analysis",
    "data_sheet_user_confirmed",
)
INDEXES = (
    "ix_shipment_item_documents_shipment_id",
    "ix_shipment_item_documents_item",
    "ix_shipment_item_documents_doc",
)


async def main() -> None:
    engine = create_async_engine(settings.DATABASE_URL)
    async with engine.connect() as conn:
        r = await conn.execute(
            text(
                """
                SELECT column_name FROM information_schema.columns
                WHERE table_schema = 'public' AND table_name = 'shipment_documents'
                  AND column_name = ANY(:names)
                """
            ),
            {"names": list(DOC_COLS)},
        )
        doc_found = {row[0] for row in r.fetchall()}

        r2 = await conn.execute(
            text(
                "SELECT EXISTS (SELECT 1 FROM pg_tables WHERE schemaname = 'public' "
                "AND tablename = 'shipment_item_documents')"
            )
        )
        has_link = r2.scalar()

        r3 = await conn.execute(
            text(
                """
                SELECT indexname FROM pg_indexes
                WHERE schemaname = 'public' AND tablename = 'shipment_item_documents'
                  AND indexname = ANY(:names)
                """
            ),
            {"names": list(INDEXES)},
        )
        idx_found = {row[0] for row in r3.fetchall()}

        r4 = await conn.execute(
            text(
                """
                SELECT EXISTS (
                  SELECT 1 FROM information_schema.columns
                  WHERE table_schema = 'public' AND table_name = 'review_records'
                    AND column_name = 'item_decisions'
                )
                """
            )
        )
        has_item_decisions = r4.scalar()

    await engine.dispose()

    missing_cols = [c for c in DOC_COLS if c not in doc_found]
    missing_idx = [i for i in INDEXES if i not in idx_found]

    print("shipment_documents columns (014):", sorted(doc_found))
    if missing_cols:
        print("MISSING columns:", missing_cols)
    print("shipment_item_documents table:", has_link)
    print("Indexes on shipment_item_documents:", sorted(idx_found))
    if missing_idx:
        print("MISSING indexes:", missing_idx)
    print("review_records.item_decisions:", has_item_decisions)

    if not missing_cols and has_link and not missing_idx and has_item_decisions:
        print("\n=> 014 looks fully applied. Safe: alembic stamp 014_trust && alembic upgrade head")
    else:
        print("\n=> 014 is incomplete — do NOT stamp 014_trust yet.")


if __name__ == "__main__":
    asyncio.run(main())

"""Freeze shipment line provenance into analysis-scoped snapshot rows (idempotent per analysis)."""

from __future__ import annotations

import logging
from uuid import UUID

from sqlalchemy import delete, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.analysis_line_provenance_snapshot import AnalysisLineProvenanceSnapshot
from app.models.shipment_item_line_provenance import ShipmentItemLineProvenance

logger = logging.getLogger(__name__)


async def replace_line_provenance_snapshots_for_analysis(
    db: AsyncSession,
    *,
    analysis_id: UUID,
    shipment_id: UUID,
    organization_id: UUID,
) -> None:
    """
    Delete all snapshot rows for this analysis, then copy current shipment line provenance.

    Same-analysis Celery retries replace in place — no duplicate (analysis_id, item, doc, line) rows.
    """
    await db.execute(
        delete(AnalysisLineProvenanceSnapshot).where(
            AnalysisLineProvenanceSnapshot.analysis_id == analysis_id
        )
    )
    res = await db.execute(
        select(ShipmentItemLineProvenance).where(ShipmentItemLineProvenance.shipment_id == shipment_id)
    )
    rows = list(res.scalars().all())
    for row in rows:
        db.add(
            AnalysisLineProvenanceSnapshot(
                analysis_id=analysis_id,
                shipment_id=shipment_id,
                organization_id=organization_id,
                shipment_item_id=row.shipment_item_id,
                shipment_document_id=row.shipment_document_id,
                line_index=row.line_index,
                logical_line_number=row.logical_line_number,
                mapping_method=row.mapping_method,
                raw_line_text=row.raw_line_text,
                structured_snapshot=row.structured_snapshot,
            )
        )
    await db.flush()
    logger.info(
        "line_provenance_snapshots: analysis_id=%s wrote %s rows",
        analysis_id,
        len(rows),
    )

"""
PATCH B — Shipment item line provenance at creation (user selection / manual API).

Requires a real ``ShipmentDocument`` row (FK); no DB migration.
"""

from __future__ import annotations

from typing import List, Optional
from uuid import UUID

from sqlalchemy import and_, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.shipment import Shipment, ShipmentItem
from app.models.shipment_document import ShipmentDocument
from app.models.shipment_item_line_provenance import (
    LineProvenanceMappingMethod,
    ShipmentItemLineProvenance,
)


async def ensure_provenance_user_selection_from_table(
    db: AsyncSession,
    shipment: Shipment,
    items_in_order: List[ShipmentItem],
    source_shipment_document_id: UUID,
) -> int:
    """
    Insert USER_SELECTION_FROM_TABLE provenance rows for items created from UI table selection.

    Returns count of rows inserted (skips duplicates per unique constraint).
    """
    if not items_in_order:
        return 0
    r = await db.execute(
        select(ShipmentDocument).where(
            and_(
                ShipmentDocument.id == source_shipment_document_id,
                ShipmentDocument.shipment_id == shipment.id,
                ShipmentDocument.organization_id == shipment.organization_id,
            )
        )
    )
    doc = r.scalar_one_or_none()
    if not doc:
        return 0

    inserted = 0
    for i, item in enumerate(items_in_order):
        existing = await db.execute(
            select(ShipmentItemLineProvenance.id).where(
                and_(
                    ShipmentItemLineProvenance.shipment_item_id == item.id,
                    ShipmentItemLineProvenance.shipment_document_id == source_shipment_document_id,
                    ShipmentItemLineProvenance.line_index == i,
                )
            ).limit(1)
        )
        if existing.scalar_one_or_none():
            continue
        label = (item.label or "")[:8000]
        db.add(
            ShipmentItemLineProvenance(
                shipment_id=shipment.id,
                organization_id=shipment.organization_id,
                shipment_item_id=item.id,
                shipment_document_id=source_shipment_document_id,
                line_index=i,
                logical_line_number=i + 1,
                raw_line_text=label or None,
                mapping_method=LineProvenanceMappingMethod.USER_SELECTION_FROM_TABLE,
                structured_snapshot={
                    "source": "user_table_selection",
                    "row_index": i,
                    "document_type": doc.document_type.value if doc.document_type else None,
                },
            )
        )
        inserted += 1
    return inserted


async def ensure_provenance_manual_api(
    db: AsyncSession,
    shipment: Shipment,
    item: ShipmentItem,
    *,
    shipment_document_id: UUID,
    line_index: int,
    logical_line_number: Optional[int] = None,
) -> bool:
    """
    Single provenance row for POST /items when client supplies document + index.
    Returns True if a new row was inserted.
    """
    r = await db.execute(
        select(ShipmentDocument).where(
            and_(
                ShipmentDocument.id == shipment_document_id,
                ShipmentDocument.shipment_id == shipment.id,
                ShipmentDocument.organization_id == shipment.organization_id,
            )
        )
    )
    if r.scalar_one_or_none() is None:
        return False

    existing = await db.execute(
        select(ShipmentItemLineProvenance.id).where(
            and_(
                ShipmentItemLineProvenance.shipment_item_id == item.id,
                ShipmentItemLineProvenance.shipment_document_id == shipment_document_id,
                ShipmentItemLineProvenance.line_index == line_index,
            )
        ).limit(1)
    )
    if existing.scalar_one_or_none():
        return False

    db.add(
        ShipmentItemLineProvenance(
            shipment_id=shipment.id,
            organization_id=shipment.organization_id,
            shipment_item_id=item.id,
            shipment_document_id=shipment_document_id,
            line_index=line_index,
            logical_line_number=logical_line_number if logical_line_number is not None else line_index + 1,
            raw_line_text=(item.label or "")[:8000] or None,
            mapping_method=LineProvenanceMappingMethod.MANUAL_API,
            structured_snapshot={"source": "manual_api"},
        )
    )
    return True

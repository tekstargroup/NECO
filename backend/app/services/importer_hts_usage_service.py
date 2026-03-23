"""
Importer HTS Usage Service - Tier 8 Internal Data

Populates importer_hts_usage from ShipmentItem data for relevance scoring.
Runs as a scheduled job or after analysis.
"""

import logging
from decimal import Decimal
from typing import Dict, Any, Optional
from uuid import UUID

from sqlalchemy import select, text, delete
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.shipment import Shipment, ShipmentItem
from app.models.importer_hts_usage import ImporterHTSUsage

logger = logging.getLogger(__name__)


async def refresh_importer_hts_usage(db: AsyncSession, organization_id: Optional[UUID] = None) -> Dict[str, int]:
    """
    Refresh importer_hts_usage from ShipmentItem data.

    Aggregates declared_hts and value per organization from shipment_items.
    If organization_id is provided, only refreshes that org; otherwise all orgs.

    Returns:
        {"organizations_updated": N, "rows_upserted": N}
    """
    # Raw SQL for efficient aggregation (avoids N+1)
    org_filter = ""
    params = {}
    if organization_id:
        org_filter = " AND s.organization_id = :org_id"
        params["org_id"] = str(organization_id)

    sql = f"""
        SELECT s.organization_id, si.declared_hts,
               COUNT(*)::int AS frequency,
               COALESCE(SUM(
                   CASE WHEN si.value ~ '^[0-9]+(\\.[0-9]+)?$' THEN (si.value)::numeric ELSE 0 END
               ), 0) AS total_value
        FROM shipment_items si
        JOIN shipments s ON si.shipment_id = s.id
        WHERE si.declared_hts IS NOT NULL
          AND TRIM(si.declared_hts) != ''
          {org_filter}
        GROUP BY s.organization_id, si.declared_hts
    """
    try:
        result = await db.execute(text(sql), params)
        rows = result.fetchall()
    except Exception as e:
        logger.warning("Failed to aggregate HTS usage: %s", e)
        return {"organizations_updated": 0, "rows_upserted": 0}

    if not rows:
        return {"organizations_updated": 0, "rows_upserted": 0}

    # Delete existing for affected orgs (full refresh)
    org_ids = list({r[0] for r in rows})
    await db.execute(
        delete(ImporterHTSUsage).where(ImporterHTSUsage.organization_id.in_(org_ids))
    )

    # Insert aggregated rows
    for org_id, hts_code, frequency, total_value in rows:
        usage = ImporterHTSUsage(
            organization_id=org_id,
            hts_code=hts_code.strip()[:10],
            frequency=frequency,
            total_value=Decimal(str(total_value)) if total_value else None,
        )
        db.add(usage)

    return {"organizations_updated": len(org_ids), "rows_upserted": len(rows)}

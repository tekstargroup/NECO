"""Product Knowledge Service — lookup and record accepted HTS per product.

Audit boundary rules:
  - Prior knowledge is returned as a SUGGESTION, never silently applied.
  - Every suggestion carries full provenance (who accepted, when, from which review).
  - Suggestions are tagged with `knowledge_reuse: true` in the result so the UI
    can display a clear "Prior classification found" notice.
  - Knowledge is scoped to organization_id and NOT shared across orgs.
  - Superseded entries are soft-deleted (superseded=True) and never returned.
"""

import hashlib
import logging
from datetime import datetime
from typing import Any, Dict, List, Optional
from uuid import UUID

from sqlalchemy import select, and_
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.product_hts_map import ProductHTSMap

logger = logging.getLogger(__name__)


def product_description_hash(description: str) -> str:
    """Stable hash of a product description for knowledge lookup.

    Normalizes whitespace and case before hashing so minor formatting
    differences don't create duplicate entries.
    """
    normalized = " ".join(description.lower().split())
    return hashlib.sha256(normalized.encode("utf-8")).hexdigest()


class ProductKnowledgeService:
    def __init__(self, db: AsyncSession):
        self.db = db

    async def lookup(
        self,
        organization_id: UUID,
        description: str,
        country_of_origin: Optional[str] = None,
    ) -> Optional[Dict[str, Any]]:
        """Find prior accepted classification for a product description.

        Returns None if no knowledge exists. Otherwise returns a suggestion
        dict that the caller can present to the user.
        """
        desc_hash = product_description_hash(description)
        filters = [
            ProductHTSMap.organization_id == organization_id,
            ProductHTSMap.description_hash == desc_hash,
            ProductHTSMap.superseded == False,  # noqa: E712
        ]
        if country_of_origin:
            coo = country_of_origin.strip().upper()[:3]
            filters.append(ProductHTSMap.country_of_origin == coo)

        result = await self.db.execute(
            select(ProductHTSMap)
            .where(and_(*filters))
            .order_by(ProductHTSMap.created_at.desc())
            .limit(1)
        )
        entry = result.scalar_one_or_none()
        if not entry:
            return None

        return {
            "knowledge_reuse": True,
            "prior_hts_code": entry.hts_code,
            "prior_hts_heading": entry.hts_heading,
            "prior_confidence": entry.confidence,
            "source": entry.source,
            "source_review_id": str(entry.source_review_id) if entry.source_review_id else None,
            "source_shipment_id": str(entry.source_shipment_id) if entry.source_shipment_id else None,
            "accepted_by": entry.accepted_by,
            "accepted_at": entry.accepted_at.isoformat() if entry.accepted_at else None,
            "provenance": entry.provenance,
            "warning": "Prior classification — verify against current shipment before accepting",
        }

    async def record_acceptance(
        self,
        *,
        organization_id: UUID,
        description: str,
        hts_code: str,
        country_of_origin: Optional[str] = None,
        confidence: Optional[float] = None,
        source_review_id: Optional[UUID] = None,
        source_shipment_id: Optional[UUID] = None,
        source_item_id: Optional[UUID] = None,
        accepted_by: Optional[str] = None,
        provenance: Optional[Dict[str, Any]] = None,
    ) -> ProductHTSMap:
        """Record a newly accepted classification in the knowledge base.

        If a prior entry exists for the same description hash (and COO),
        it is superseded — not deleted — so the full history is preserved.
        """
        desc_hash = product_description_hash(description)
        coo = country_of_origin.strip().upper()[:3] if country_of_origin else None
        heading = hts_code[:4] if hts_code and len(hts_code) >= 4 else None

        existing_filters = [
            ProductHTSMap.organization_id == organization_id,
            ProductHTSMap.description_hash == desc_hash,
            ProductHTSMap.superseded == False,  # noqa: E712
        ]
        if coo:
            existing_filters.append(ProductHTSMap.country_of_origin == coo)

        existing_result = await self.db.execute(
            select(ProductHTSMap).where(and_(*existing_filters))
        )
        existing_entries = list(existing_result.scalars().all())

        new_entry = ProductHTSMap(
            organization_id=organization_id,
            description_hash=desc_hash,
            description_text=description[:500],
            hts_code=hts_code,
            hts_heading=heading,
            country_of_origin=coo,
            confidence=confidence,
            source="review_accepted",
            source_review_id=source_review_id,
            source_shipment_id=source_shipment_id,
            source_item_id=source_item_id,
            provenance=provenance,
            accepted_by=accepted_by,
            accepted_at=datetime.utcnow(),
        )
        self.db.add(new_entry)

        for old in existing_entries:
            old.superseded = True
            old.superseded_by_id = new_entry.id
            old.updated_at = datetime.utcnow()

        await self.db.flush()
        return new_entry

    async def list_knowledge(
        self,
        organization_id: UUID,
        *,
        limit: int = 50,
        offset: int = 0,
        include_superseded: bool = False,
    ) -> List[Dict[str, Any]]:
        """List knowledge entries for an organization (for admin/audit UI)."""
        filters = [ProductHTSMap.organization_id == organization_id]
        if not include_superseded:
            filters.append(ProductHTSMap.superseded == False)  # noqa: E712

        result = await self.db.execute(
            select(ProductHTSMap)
            .where(and_(*filters))
            .order_by(ProductHTSMap.created_at.desc())
            .limit(limit)
            .offset(offset)
        )
        entries = result.scalars().all()
        return [
            {
                "id": str(e.id),
                "description_hash": e.description_hash,
                "description_text": e.description_text,
                "hts_code": e.hts_code,
                "hts_heading": e.hts_heading,
                "country_of_origin": e.country_of_origin,
                "confidence": e.confidence,
                "source": e.source,
                "accepted_by": e.accepted_by,
                "accepted_at": e.accepted_at.isoformat() if e.accepted_at else None,
                "superseded": e.superseded,
                "created_at": e.created_at.isoformat() if e.created_at else None,
            }
            for e in entries
        ]

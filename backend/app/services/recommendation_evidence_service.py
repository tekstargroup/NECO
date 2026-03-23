"""
RecommendationEvidenceService - Builds evidence bundles for PSC recommendations.

Per EVIDENCE_MAPPING_MODEL.md:
- Collects extracted fields, authority references, evidence links
- Classifies evidence into supporting / conflicting / warning
- Computes evidence strength and review level
- Returns ShipmentItemEvidenceBundle for drawer UI

When structured evidence (recommendation_evidence_links, recommendation_summaries) exists,
uses it. Otherwise derives from analysis result_json for MVP compatibility.
"""

import logging
from typing import Any, Dict, List, Optional
from uuid import UUID
from decimal import Decimal

from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select
from sqlalchemy.orm import selectinload

from app.models.analysis import Analysis
from app.models.evidence import (
    RecommendationEvidenceLink,
    RecommendationSummary,
    ExtractedField,
    AuthorityReference,
    SourceDocument,
    DocumentPage,
)
from app.models.shipment import ShipmentItem

logger = logging.getLogger(__name__)


def _evidence_item(
    summary: str,
    source_label: str = "",
    page_ref: Optional[str] = None,
    reference_id: Optional[str] = None,
    evidence_role: str = "SUPPORTING",
    evidence_strength: Optional[str] = None,
) -> Dict[str, Any]:
    """Build a single evidence item for UI."""
    out: Dict[str, Any] = {"summary": summary, "source_label": source_label or ""}
    if page_ref:
        out["page_ref"] = page_ref
    if reference_id:
        out["reference_id"] = reference_id
    if evidence_role:
        out["evidence_role"] = evidence_role
    if evidence_strength:
        out["evidence_strength"] = evidence_strength
    return out


def _doc_ref(doc_type: str, filename: str, page: Optional[int] = None) -> Dict[str, Any]:
    """Build document reference for UI."""
    out: Dict[str, Any] = {"document_type": doc_type, "filename": filename}
    if page is not None:
        out["page"] = page
    return out


def _authority_ref(
    authority_type: str,
    reference_id: Optional[str],
    title: Optional[str],
    relation: str = "",
    role: str = "SUPPORTING",
    strength: Optional[str] = None,
) -> Dict[str, Any]:
    """Build authority reference for UI."""
    return {
        "authority_type": authority_type,
        "reference_id": reference_id,
        "title": title or "",
        "relation": relation,
        "role": role,
        "strength": strength,
    }


class RecommendationEvidenceService:
    """Builds evidence bundles for recommendation drawer."""

    def __init__(self, db: AsyncSession):
        self.db = db

    async def build_item_evidence_bundle(
        self,
        shipment_id: UUID,
        item_id: UUID,
        result_json: Optional[Dict[str, Any]] = None,
    ) -> Dict[str, Any]:
        """
        Build ShipmentItemEvidenceBundle for a shipment item.

        When structured evidence exists (recommendation_summaries, recommendation_evidence_links),
        uses it. Otherwise derives from result_json for MVP.
        """
        # Try structured evidence first
        summary = await self._get_recommendation_summary(shipment_id, item_id)
        links = await self._get_evidence_links(shipment_id, item_id)

        if summary or links:
            return await self._build_from_structured(
                shipment_id, item_id, summary, links
            )

        # Fallback: derive from result_json
        return self._build_from_result_json(shipment_id, item_id, result_json or {})

    async def _get_recommendation_summary(
        self, shipment_id: UUID, item_id: UUID
    ) -> Optional[RecommendationSummary]:
        """Get recommendation summary for item if exists."""
        result = await self.db.execute(
            select(RecommendationSummary)
            .where(RecommendationSummary.shipment_id == shipment_id)
            .where(RecommendationSummary.shipment_item_id == item_id)
            .order_by(RecommendationSummary.updated_at.desc())
            .limit(1)
        )
        return result.scalar_one_or_none()

    async def _get_evidence_links(
        self, shipment_id: UUID, item_id: UUID
    ) -> List[RecommendationEvidenceLink]:
        """Get evidence links for item."""
        result = await self.db.execute(
            select(RecommendationEvidenceLink)
            .where(RecommendationEvidenceLink.shipment_id == shipment_id)
            .where(RecommendationEvidenceLink.shipment_item_id == item_id)
            .order_by(RecommendationEvidenceLink.created_at)
        )
        return list(result.scalars().all())

    async def _build_from_structured(
        self,
        shipment_id: UUID,
        item_id: UUID,
        summary: Optional[RecommendationSummary],
        links: List[RecommendationEvidenceLink],
    ) -> Dict[str, Any]:
        """Build bundle from structured DB evidence."""
        supporting: List[Dict[str, Any]] = []
        conflicting: List[Dict[str, Any]] = []
        warning: List[Dict[str, Any]] = []
        document_refs: List[Dict[str, Any]] = []
        authority_refs: List[Dict[str, Any]] = []

        for link in links:
            ev = _evidence_item(
                summary=link.summary or "",
                source_label=self._link_source_label(link),
                page_ref=await self._link_page_ref(link) if link.page_id else None,
                reference_id=await self._link_authority_ref(link) if link.authority_reference_id else None,
                evidence_role=link.evidence_role,
                evidence_strength=link.evidence_strength,
            )
            if link.evidence_role == "SUPPORTING":
                supporting.append(ev)
            elif link.evidence_role == "CONFLICTING":
                conflicting.append(ev)
            elif link.evidence_role == "WARNING":
                warning.append(ev)

            if link.source_document_id:
                doc = await self._get_source_doc(link.source_document_id)
                if doc:
                    document_refs.append(_doc_ref(doc.document_type, doc.file_name))

            if link.authority_reference_id:
                auth = await self._get_authority(link.authority_reference_id)
                if auth:
                    authority_refs.append(
                        _authority_ref(
                            auth.authority_type,
                            auth.reference_id,
                            auth.title,
                            auth.summary or "",
                            link.evidence_role,
                            link.evidence_strength,
                        )
                    )

        decl = summary.declared_hts if summary else None
        alt = summary.alternative_hts if summary else None
        sav = float(summary.estimated_savings) if summary and summary.estimated_savings is not None else None
        strength = summary.evidence_strength if summary else "MODERATE"
        level = summary.review_level if summary else "MEDIUM"

        return {
            "shipment_item_id": str(item_id),
            "declared_hts": decl,
            "alternative_hts": alt,
            "estimated_savings": sav,
            "evidence_strength": strength,
            "review_level": level,
            "supporting_evidence": supporting,
            "conflicting_evidence": conflicting,
            "warning_evidence": warning,
            "document_refs": document_refs,
            "authority_refs": authority_refs,
            "explanation_summary": summary.support_summary if summary else "",
            "next_step": summary.next_step_summary or "Review supporting documents and confirm with broker before export.",
        }

    def _link_source_label(self, link: RecommendationEvidenceLink) -> str:
        """Get source label for evidence link (from source_document if loaded)."""
        return link.evidence_source_type.replace("_", " ").title()

    async def _link_page_ref(self, link: RecommendationEvidenceLink) -> Optional[str]:
        if not link.page_id:
            return None
        result = await self.db.execute(
            select(DocumentPage).where(DocumentPage.id == link.page_id)
        )
        page = result.scalar_one_or_none()
        return f"Page {page.page_number}" if page else None

    async def _link_authority_ref(self, link: RecommendationEvidenceLink) -> Optional[str]:
        if not link.authority_reference_id:
            return None
        auth = await self._get_authority(link.authority_reference_id)
        return auth.reference_id if auth else None

    async def _get_source_doc(self, doc_id: UUID) -> Optional[SourceDocument]:
        result = await self.db.execute(select(SourceDocument).where(SourceDocument.id == doc_id))
        return result.scalar_one_or_none()

    async def _get_authority(self, auth_id: UUID) -> Optional[AuthorityReference]:
        result = await self.db.execute(
            select(AuthorityReference).where(AuthorityReference.id == auth_id)
        )
        return result.scalar_one_or_none()

    def _build_from_result_json(
        self,
        shipment_id: UUID,
        item_id: UUID,
        result_json: Dict[str, Any],
    ) -> Dict[str, Any]:
        """Derive evidence bundle from analysis result_json (MVP fallback)."""
        items = result_json.get("items") or []
        raw_item = next((i for i in items if i.get("id") == str(item_id)), None)
        evidence_map = result_json.get("evidence_map") or {}
        docs = evidence_map.get("documents") or []

        declared_hts = None
        alternative_hts = None
        estimated_savings = None
        evidence_strength = "MODERATE"
        review_level = "MEDIUM"
        support_summary = ""
        risk_summary = ""
        next_step = "Review supporting documents and confirm with broker before export."

        supporting: List[Dict[str, Any]] = []
        conflicting: List[Dict[str, Any]] = []
        warning: List[Dict[str, Any]] = []
        document_refs: List[Dict[str, Any]] = []
        authority_refs: List[Dict[str, Any]] = []

        if raw_item:
            declared_hts = raw_item.get("hts_code") or raw_item.get("declared_hts")
            psc = raw_item.get("psc") or {}
            classification = raw_item.get("classification") or {}
            duty = raw_item.get("duty") or {}
            regulatory = raw_item.get("regulatory") or []

            # Alternative HTS from PSC or classification
            alts = psc.get("alternatives") or []
            primary = classification.get("primary_candidate") or {}
            if alts:
                best = alts[0]
                alternative_hts = best.get("hts_code") or best.get("alternative_hts")
                delta = best.get("duty_delta_amount") or best.get("savings")
                if delta is not None:
                    try:
                        estimated_savings = float(delta)
                    except (TypeError, ValueError):
                        pass
            elif primary.get("hts_code") and primary.get("hts_code") != declared_hts:
                alternative_hts = primary.get("hts_code")

            # Evidence strength from confidence
            conf = classification.get("metadata", {}).get("analysis_confidence")
            if conf is not None:
                if conf >= 0.7:
                    evidence_strength = "STRONG"
                elif conf >= 0.5:
                    evidence_strength = "MODERATE"
                else:
                    evidence_strength = "WEAK"

            # Review level from risk
            if regulatory:
                review_level = "HIGH"
            elif evidence_strength == "WEAK":
                review_level = "MEDIUM"
            else:
                review_level = "LOW"

            # Supporting evidence (derived)
            if raw_item.get("label"):
                supporting.append(
                    _evidence_item(
                        f"Product description: {raw_item['label'][:80]}{'...' if len(raw_item.get('label', '')) > 80 else ''}",
                        "Commercial Invoice" if docs else "Document",
                        evidence_role="SUPPORTING",
                    )
                )
            if alternative_hts:
                supporting.append(
                    _evidence_item(
                        f"Alternative HTS {alternative_hts} identified from classification analysis.",
                        "Classification engine",
                        evidence_role="SUPPORTING",
                    )
                )
            if primary.get("hts_code"):
                supporting.append(
                    _evidence_item(
                        f"Classification engine matched product to HTS structure.",
                        "Classification",
                        evidence_role="SUPPORTING",
                    )
                )

            # Conflicting / warning
            if not psc.get("alternatives") and alternative_hts:
                conflicting.append(
                    _evidence_item(
                        "No direct CBP ruling match for this exact product.",
                        "PSC Radar",
                        evidence_role="CONFLICTING",
                    )
                )
            if regulatory:
                for r in regulatory[:2]:
                    warning.append(
                        _evidence_item(
                            f"{r.get('regulator', 'Regulator')}: {r.get('condition', 'Review required')}",
                            r.get("regulator", "Regulatory"),
                            evidence_role="WARNING",
                        )
                    )
            if evidence_strength != "STRONG":
                conflicting.append(
                    _evidence_item(
                        "Confirm classification with broker before filing.",
                        "NECO",
                        evidence_role="CONTEXTUAL",
                    )
                )

            support_summary = "Alternative HTS aligns with product description and comparable classification patterns."
            risk_summary = "No direct ruling match found." if not psc.get("alternatives") else "Regulatory review flags are present." if regulatory else ""

        # Document refs from evidence_map
        for d in docs:
            document_refs.append(
                _doc_ref(
                    d.get("document_type", "Document"),
                    d.get("filename", "Unknown"),
                    d.get("page"),
                )
            )
        if not document_refs and docs:
            for d in docs:
                document_refs.append(_doc_ref(d.get("document_type", "Document"), d.get("filename", "Unknown")))

        return {
            "shipment_item_id": str(item_id),
            "declared_hts": declared_hts,
            "alternative_hts": alternative_hts,
            "estimated_savings": estimated_savings,
            "evidence_strength": evidence_strength,
            "review_level": review_level,
            "supporting_evidence": supporting,
            "conflicting_evidence": conflicting,
            "warning_evidence": warning,
            "document_refs": document_refs,
            "authority_refs": authority_refs,
            "explanation_summary": support_summary,
            "next_step": next_step,
        }

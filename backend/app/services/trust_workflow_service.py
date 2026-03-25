"""
Trust workflow states — derived from persisted DB only (Sprint A).

UI must not infer readiness from draft input; use this service + analysis_provenance.
"""

from __future__ import annotations

from typing import Any, Dict, List, Optional
from uuid import UUID

from sqlalchemy import select, and_
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import joinedload

from app.models.shipment import Shipment, ShipmentItem
from app.models.shipment_document import ShipmentDocument, ShipmentDocumentType
from app.models.analysis import Analysis, AnalysisStatus
from app.models.review_record import ReviewRecord, ReviewStatus
from app.models.shipment_item_document import ShipmentItemDocument, ItemDocumentMappingStatus
from app.repositories.org_scoped_repository import OrgScopedRepository
from app.services.shipment_eligibility_service import ShipmentEligibilityService


def _document_trust_state(doc: ShipmentDocument) -> Dict[str, Any]:
    """Derive document pipeline state from persisted columns (Sprint B enriches)."""
    text = (doc.extracted_text or "").strip()
    ext_status = getattr(doc, "extraction_status", None)
    if ext_status:
        state = ext_status
    elif doc.extracted_text is None:
        state = "uploaded"  # never processed in analysis parse
    elif len(text) == 0:
        state = "text_empty"
    else:
        state = "text_extracted"
    ocr_used = getattr(doc, "ocr_used", None)
    char_count = getattr(doc, "char_count", None)
    if char_count is None and doc.extracted_text is not None:
        char_count = len(doc.extracted_text or "")
    return {
        "document_id": str(doc.id),
        "filename": doc.filename,
        "document_type": doc.document_type.value if doc.document_type else None,
        "state": state,
        "char_count": char_count,
        "ocr_used": ocr_used,
        "usable_for_analysis": getattr(doc, "usable_for_analysis", None) if getattr(doc, "usable_for_analysis", None) is not None else (len(text) > 0),
        "data_sheet_user_confirmed": getattr(doc, "data_sheet_user_confirmed", False),
    }


def _item_readiness(
    item: ShipmentItem,
    assigned_doc_ids: List[UUID],
    *,
    shipment_has_data_sheet: bool,
) -> Dict[str, Any]:
    coo = (item.country_of_origin or "").strip()
    has_coo = len(coo) == 2
    mapped = len(assigned_doc_ids) > 0
    if not has_coo:
        stage = "partially_ready"
    elif shipment_has_data_sheet and not mapped:
        stage = "documents_unmapped"
    else:
        stage = "ready_for_classification"
    return {
        "item_id": str(item.id),
        "label": item.label,
        "readiness": stage,
        "has_saved_coo": has_coo,
        "assigned_document_ids": [str(x) for x in assigned_doc_ids],
    }


class TrustWorkflowService:
    def __init__(self, db: AsyncSession):
        self.db = db

    async def compute_trust_workflow(self, shipment_id: UUID, organization_id: UUID) -> Dict[str, Any]:
        repo = OrgScopedRepository(self.db, Shipment)
        shipment = await repo.get_by_id(shipment_id, organization_id)
        await self.db.refresh(shipment, ["items", "documents", "references"])

        eligibility = await ShipmentEligibilityService(self.db).compute_eligibility(shipment_id)

        docs_out = [_document_trust_state(d) for d in (shipment.documents or [])]
        shipment_has_data_sheet = any(
            d.document_type == ShipmentDocumentType.DATA_SHEET for d in (shipment.documents or [])
        )

        # Item -> assigned docs from link table (Sprint C)
        item_doc_map: Dict[UUID, List[UUID]] = {}
        r = await self.db.execute(
            select(ShipmentItemDocument).where(ShipmentItemDocument.shipment_id == shipment_id)
        )
        for row in r.scalars().all():
            if row.mapping_status == ItemDocumentMappingStatus.REJECTED:
                continue
            item_doc_map.setdefault(row.shipment_item_id, []).append(row.shipment_document_id)

        items_out = [
            _item_readiness(
                it,
                item_doc_map.get(it.id, []),
                shipment_has_data_sheet=shipment_has_data_sheet,
            )
            for it in (shipment.items or [])
        ]

        analysis_state = "not_started"
        review_ui = "not_reviewed"
        ar = await self.db.execute(
            select(Analysis)
            .where(
                and_(
                    Analysis.shipment_id == shipment_id,
                    Analysis.organization_id == organization_id,
                )
            )
            .order_by(Analysis.created_at.desc())
            .limit(1)
        )
        analysis = ar.scalar_one_or_none()
        if analysis:
            if analysis.status == AnalysisStatus.COMPLETE and analysis.result_json:
                analysis_state = "generated"
            elif analysis.status == AnalysisStatus.REFUSED:
                analysis_state = "needs_input"
            elif analysis.status in (AnalysisStatus.QUEUED, AnalysisStatus.RUNNING):
                analysis_state = "running"
            elif analysis.status == AnalysisStatus.FAILED:
                analysis_state = "failed"
            if analysis.review_record_id:
                rr = await self.db.execute(select(ReviewRecord).where(ReviewRecord.id == analysis.review_record_id))
                rec = rr.scalar_one_or_none()
                if rec:
                    if rec.status == ReviewStatus.REVIEW_REQUIRED:
                        review_ui = "review_required"
                    elif rec.status == ReviewStatus.REVIEWED_ACCEPTED:
                        review_ui = "reviewed_accepted"
                    elif rec.status == ReviewStatus.REVIEWED_REJECTED:
                        review_ui = "reviewed_rejected"
                    else:
                        review_ui = "not_reviewed"

        # Per-domain readiness (backend-derived, never inferred by client)
        usable_docs = sum(1 for d in docs_out if d.get("usable_for_analysis"))
        total_docs = len(docs_out)
        ready_items = sum(1 for it in items_out if it.get("readiness") == "ready_for_classification")
        total_items = len(items_out)

        result_json = analysis.result_json if analysis else None
        has_supported = False
        has_duty = False
        has_regulatory = False
        if isinstance(result_json, dict):
            for it in result_json.get("items") or []:
                memo = it.get("classification_memo") or {}
                level = memo.get("support_level", "")
                if level == "supported":
                    has_supported = True
                ds = it.get("duty_scenarios") or it.get("duty") or {}
                if isinstance(ds, dict) and not ds.get("unavailable") and ds:
                    has_duty = True
            if result_json.get("regulatory_evaluations") or any(
                it.get("regulatory") for it in result_json.get("items") or []
            ):
                has_regulatory = True

        domain_readiness = {
            "documents": {
                "usable": usable_docs,
                "total": total_docs,
                "ready": usable_docs > 0,
                "label": f"{usable_docs}/{total_docs} usable",
            },
            "items": {
                "ready": ready_items,
                "total": total_items,
                "all_ready": total_items > 0 and ready_items == total_items,
                "label": f"{ready_items}/{total_items} ready",
            },
            "classification": {
                "state": analysis_state,
                "has_supported": has_supported,
                "label": "Analysis generated" if analysis_state == "generated" else analysis_state.replace("_", " ").capitalize(),
            },
            "duty": {
                "available": has_duty,
                "label": "Duty estimates available" if has_duty else "No duty estimates yet",
            },
            "regulatory": {
                "signals_available": has_regulatory,
                "label": "Regulatory signals available" if has_regulatory else "No regulatory signals found",
            },
        }

        # Derive review progress from item_decisions (Sprint E: item-level derives shipment)
        item_review_summary = {"total": 0, "accepted": 0, "rejected": 0, "pending": 0}
        if analysis and hasattr(analysis, "review_record_id") and analysis.review_record_id:
            rr_q = await self.db.execute(select(ReviewRecord).where(ReviewRecord.id == analysis.review_record_id))
            rr_rec = rr_q.scalar_one_or_none()
            if rr_rec and rr_rec.item_decisions and isinstance(rr_rec.item_decisions, dict):
                for _iid, dec in rr_rec.item_decisions.items():
                    item_review_summary["total"] += 1
                    st = (dec.get("status") or "pending").lower()
                    if st == "accepted":
                        item_review_summary["accepted"] += 1
                    elif st == "rejected":
                        item_review_summary["rejected"] += 1
                    else:
                        item_review_summary["pending"] += 1

        derived_review_state = review_ui
        if item_review_summary["total"] > 0:
            if item_review_summary["pending"] == 0:
                derived_review_state = "review_completed"
            elif item_review_summary["accepted"] > 0 or item_review_summary["rejected"] > 0:
                derived_review_state = "partially_reviewed"

        return {
            "shipment_id": str(shipment_id),
            "shipment_status": shipment.status.value if shipment.status else None,
            "documents": docs_out,
            "items": items_out,
            "analysis": {"state": analysis_state},
            "review": {"state": derived_review_state, "item_summary": item_review_summary},
            "eligibility": eligibility,
            "ready_for_classification": bool(eligibility.get("eligible")),
            "domain_readiness": domain_readiness,
        }

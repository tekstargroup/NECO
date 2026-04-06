"""
Shipment Analysis Service - Sprint 12

Full analysis orchestration for shipments.
Integrates all engines: document processing, classification, duty, PSC, enrichment, regulatory.

This is the "truth payload" that the Celery task calls.
"""

import asyncio
import hashlib
import json
import logging
import re
from typing import Dict, Any, List, Optional, Tuple, Set
from uuid import UUID
from datetime import datetime
from pathlib import Path
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, and_
from sqlalchemy.dialects.postgresql import insert as pg_insert

from app.models.shipment import Shipment, ShipmentStatus, ShipmentItem
from app.models.shipment_document import ShipmentDocument, ShipmentDocumentType
from app.models.shipment_item_document import ShipmentItemDocument, ItemDocumentMappingStatus
from app.models.shipment_item_line_provenance import (
    ShipmentItemLineProvenance,
    LineProvenanceMappingMethod,
)
from app.models.shipment_item_classification_facts import ShipmentItemClassificationFacts
from app.engines.classification.classification_facts import build_classification_facts_payload
from app.engines.classification.heading_reasoning_trace import build_heading_reasoning_trace
from app.models.review_record import ReviewRecord, ReviewStatus, ReviewableObjectType, ReviewReasonCode
from app.models.regulatory_evaluation import RegulatoryEvaluation, RegulatoryCondition, Regulator, RegulatoryOutcome, ConditionState
from app.engines.ingestion.document_processor import DocumentProcessor
from app.engines.classification.engine import ClassificationEngine
from app.engines.classification.rule_based_classifier import (
    RuleBasedClassifier,
    ProductInput as RuleProductInput,
)
from app.engines.psc_radar import PSCRadar
from app.engines.regulatory_applicability import RegulatoryApplicabilityEngine
from scripts.duty_resolution import resolve_duty
from app.core.hts_constants import AUTHORITATIVE_HTS_VERSION_ID
from app.services.enrichment_integration_service import EnrichmentIntegrationService
from app.services.s3_upload_service import get_s3_client
from app.core.config import settings
from app.services.classification_memo import build_classification_memo, stable_classification_outcome
from app.models.analysis_pipeline_stage import PipelineStageName, PipelineStageStatus
from app.services.pipeline_stage_service import PipelineStageContext
from app.services.reasoning_trace_persistence import persist_reasoning_traces_from_result_items

logger = logging.getLogger(__name__)


async def upsert_shipment_item_classification_facts(
    db: AsyncSession,
    *,
    analysis_id: UUID,
    shipment_id: UUID,
    organization_id: UUID,
    shipment_item_id: UUID,
    facts_json: Dict[str, Any],
    missing_facts_json: List[Any],
) -> None:
    """Idempotent facts row per (analysis_id, shipment_item_id) for Celery retries."""
    tbl = ShipmentItemClassificationFacts
    ins = pg_insert(tbl).values(
        analysis_id=analysis_id,
        shipment_id=shipment_id,
        organization_id=organization_id,
        shipment_item_id=shipment_item_id,
        facts_json=facts_json,
        missing_facts_json=missing_facts_json,
        schema_version="1",
    )
    stmt = ins.on_conflict_do_update(
        constraint="uq_classification_facts_analysis_item",
        set_={
            "facts_json": ins.excluded.facts_json,
            "missing_facts_json": ins.excluded.missing_facts_json,
            "shipment_id": ins.excluded.shipment_id,
            "organization_id": ins.excluded.organization_id,
            "schema_version": ins.excluded.schema_version,
        },
    )
    await db.execute(stmt)


def _product_analysis_from_classification_result(result: Optional[Dict[str, Any]]) -> Dict[str, Any]:
    """Extract serialized product_analysis dict from engine response (Patch D facts layer)."""
    if not result or not isinstance(result, dict):
        return {}


def _product_analysis_for_classification_facts(classification: Optional[Dict[str, Any]]) -> Dict[str, Any]:
    """Product analysis payload for facts upsert (handles CLARIFICATION_REQUIRED → original_classification)."""
    if isinstance(classification, dict) and classification.get("status") == "CLARIFICATION_REQUIRED":
        orig = classification.get("original_classification")
        return _product_analysis_from_classification_result(orig if isinstance(orig, dict) else None)
    return _product_analysis_from_classification_result(classification)
    meta = result.get("metadata") or {}
    pa = meta.get("product_analysis")
    if isinstance(pa, dict) and pa:
        return pa
    inner = result.get("product_analysis")
    if isinstance(inner, dict) and inner:
        return inner
    orig = result.get("original_classification")
    if isinstance(orig, dict):
        return _product_analysis_from_classification_result(orig)
    return {}


def _get_hts_if_supported(
    classification: Optional[Dict[str, Any]],
    memo: Optional[Dict[str, Any]],
) -> Optional[str]:
    """Return HTS only when classification is "supported" — the only level reliable
    enough for downstream duty and PSC.  All other levels are blocked.
    """
    if not memo or memo.get("support_level") != "supported":
        return None
    return _get_hts_from_classification(classification)


def apply_ingestion_metadata_to_shipment_document(doc: ShipmentDocument, process_result: Dict[str, Any]) -> None:
    """Persist Sprint B observability fields from DocumentProcessor output."""
    if not process_result.get("success"):
        doc.extraction_status = "failed"
        doc.usable_for_analysis = False
        doc.char_count = 0
        return
    text = process_result.get("extracted_text") or ""
    stripped = text.strip()
    meta = process_result.get("metadata") or {}
    doc.page_count = meta.get("page_count")
    if doc.page_count is None and isinstance(meta.get("sheet_count"), int):
        doc.page_count = meta.get("sheet_count")
    doc.table_detected = bool(meta.get("has_tables") or (meta.get("table_count") or 0) > 0)
    doc.ocr_used = bool(meta.get("ocr_used"))
    doc.char_count = len(text)
    ocr = bool(meta.get("ocr_used"))
    if stripped:
        doc.extraction_method = "ocr" if ocr else (meta.get("extraction_method") or "pdf_text")
        doc.extraction_status = "success"
        doc.usable_for_analysis = True
    else:
        doc.extraction_method = "ocr" if ocr else (meta.get("extraction_method") or "pdf_text")
        doc.extraction_status = "empty"
        doc.usable_for_analysis = False


_MPN_RE = re.compile(
    r"(?:p/?n|part\s*(?:no\.?|number)|model\s*(?:no\.?|number)|sku|item\s*(?:no\.?|number)|cat\.?\s*(?:no\.?|number)|ref\.?\s*(?:no\.?|number))"
    r"\s*[:=\-]?\s*([A-Z0-9][A-Z0-9\-./]{2,30})",
    re.IGNORECASE,
)

def enrich_structured_data_with_extraction(structured_data: Optional[Dict[str, Any]], extracted_text: str) -> Dict[str, Any]:
    """Extract assistive metadata from text and store under _assistive_extraction.

    These fields are for display and analyst reference only.
    They MUST NOT drive classification, duty, or regulatory logic.
    """
    sd = dict(structured_data) if structured_data else {}
    if not extracted_text or not extracted_text.strip():
        return sd

    lines = [l.strip() for l in extracted_text.split("\n") if l.strip()]

    product_name = None
    mpn = None
    key_phrases: list = []

    for line in lines[:15]:
        cleaned = line.strip("•·-–—►▶ \t")
        if 5 < len(cleaned) < 120 and not cleaned.startswith(("page", "Page", "PAGE", "date", "Date")):
            product_name = cleaned
            break

    for line in lines[:40]:
        m = _MPN_RE.search(line)
        if m:
            mpn = m.group(1).strip()
            break

    text_lower = extracted_text.lower()
    kw_patterns = [
        "stainless steel", "carbon steel", "alloy", "plastic", "rubber",
        "disposable", "reusable", "surgical", "medical", "industrial",
        "for human use", "not for human use", "single use",
        "assembled in", "manufactured in", "made in",
        "class ii", "class iii", "510(k)", "fda",
    ]
    for kw in kw_patterns:
        if kw in text_lower:
            key_phrases.append(kw)
    key_phrases = key_phrases[:10]

    sd["_assistive_extraction"] = {
        "product_name": product_name,
        "mpn": mpn,
        "key_phrases": key_phrases,
        "source": "heuristic_text_scan",
        "warning": "Assistive only — not benchmarked for classification use",
    }

    return sd


def _get_hts_from_classification(classification: Optional[Dict[str, Any]]) -> Optional[str]:
    """Extract HTS code from classification (primary_candidate or candidates[0])."""
    if not classification or not isinstance(classification, dict):
        return None
    pc = classification.get("primary_candidate")
    if not pc:
        candidates = classification.get("candidates") or []
        pc = candidates[0] if candidates else None
    return pc.get("hts_code") if pc else None


def _item_needs_supplemental(classification: Optional[Dict[str, Any]]) -> bool:
    """True if classification suggests supplemental evidence would help (low confidence)."""
    if not classification or not isinstance(classification, dict):
        return False
    meta = classification.get("metadata") or {}
    conf = meta.get("analysis_confidence")
    if conf is not None and isinstance(conf, (int, float)) and conf < 0.7:
        return True
    missing = meta.get("missing_required_attributes") or []
    pa = meta.get("product_analysis") or {}
    if isinstance(pa, dict):
        missing = missing or pa.get("missing_required_attributes") or []
    return len(missing) > 0


_ATTRIBUTE_QUESTIONS = {
    "material": "What is the primary material composition?",
    "material_composition": "What is the primary material composition?",
    "intended_use": "What is the intended use of this product?",
    "used_on_humans": "Is this product used on or in the human body?",
    "disposable": "Is this product single-use / disposable?",
    "system_vs_part": "Is this imported as a complete system or as a component/part?",
    "weight": "What is the approximate weight?",
    "voltage": "What is the operating voltage?",
    "capacity": "What is the capacity or volume?",
    "fiber_content": "What is the fiber/textile content composition?",
}

CRITICAL_ATTRIBUTES_BY_FAMILY = {
    "medical": ["intended_use", "used_on_humans", "disposable"],
    "textile": ["material_composition", "fiber_content"],
    "machinery": ["intended_use"],
    "chemical": ["material_composition"],
    "default": ["intended_use", "material"],
}


def _question_for(attribute: str) -> str:
    """Map an attribute name to a human-readable question for the user."""
    return _ATTRIBUTE_QUESTIONS.get(attribute, f"Please provide: {attribute.replace('_', ' ')}")


def _get_critical_missing(
    missing_attrs: List[str],
    description: str,
) -> List[str]:
    """Determine which missing attributes are critical based on product-family heuristics."""
    if getattr(settings, "CLASSIFICATION_FAMILY_ROUTER_ENABLED", False):
        from app.engines.classification.family_router import critical_missing_for_family

        return critical_missing_for_family(missing_attrs, description)
    d = (description or "").lower()
    family = "default"
    if any(kw in d for kw in ("surgical", "endoscop", "medical", "clinical", "patient")):
        family = "medical"
    elif any(kw in d for kw in ("woven", "knitted", "cotton", "polyester", "fiber", "fabric", "textile")):
        family = "textile"
    elif any(kw in d for kw in ("machine", "motor", "pump", "cnc", "robot")):
        family = "machinery"
    elif any(kw in d for kw in ("chemical", "solution", "hydroxide", "acid", "compound")):
        family = "chemical"
    critical_set = set(CRITICAL_ATTRIBUTES_BY_FAMILY.get(family, CRITICAL_ATTRIBUTES_BY_FAMILY["default"]))
    return [a for a in missing_attrs if a in critical_set]


def _normalize_match_key(raw: Optional[str]) -> str:
    if not raw:
        return ""
    return re.sub(r"[^a-z0-9]+", "", str(raw).lower())


def _get_item_data_sheet_text(
    item_label: Optional[str],
    documents: List[ShipmentDocument],
    item_id: Optional[UUID] = None,
    item_doc_link_map: Optional[Dict[str, List[UUID]]] = None,
) -> Optional[str]:
    """
    Prefer explicit item-document links (Sprint C); else filename/label heuristic.
    """
    docs_by_id = {d.id: d for d in (documents or [])}
    if item_id and item_doc_link_map:
        for did in item_doc_link_map.get(str(item_id), []):
            doc = docs_by_id.get(did)
            if not doc or doc.document_type != ShipmentDocumentType.DATA_SHEET:
                continue
            text = (doc.extracted_text or "").strip()
            if text:
                return text[:5000]

    label_key = _normalize_match_key(item_label)
    if not label_key:
        return None

    for doc in documents or []:
        if doc.document_type != ShipmentDocumentType.DATA_SHEET:
            continue
        file_key = _normalize_match_key(doc.filename)
        if not file_key:
            continue
        if label_key in file_key or file_key in label_key:
            text = (doc.extracted_text or "").strip()
            if text:
                return text[:5000]
    return None


def _build_item_evidence_used(
    item_label: Optional[str],
    documents: List[ShipmentDocument],
    item_id: Optional[UUID] = None,
    item_doc_link_map: Optional[Dict[str, List[UUID]]] = None,
) -> List[Dict[str, Any]]:
    """Build a per-item list of evidence sources with snippets and match reasons (Sprint D.2)."""
    result: List[Dict[str, Any]] = []
    docs_by_id = {d.id: d for d in (documents or [])}
    used_doc_ids: set = set()

    if item_id and item_doc_link_map:
        for did in item_doc_link_map.get(str(item_id), []):
            doc = docs_by_id.get(did)
            if not doc:
                continue
            text = (doc.extracted_text or "").strip()
            result.append({
                "document_id": str(doc.id),
                "filename": doc.filename,
                "document_type": doc.document_type.value if doc.document_type else None,
                "snippet": text[:300] if text else "",
                "match_reason": "item_doc_link",
                "match_confidence": "high",
            })
            used_doc_ids.add(doc.id)

    label_key = _normalize_match_key(item_label)
    if label_key:
        for doc in documents or []:
            if doc.id in used_doc_ids:
                continue
            if doc.document_type != ShipmentDocumentType.DATA_SHEET:
                continue
            file_key = _normalize_match_key(doc.filename)
            if file_key and (label_key in file_key or file_key in label_key):
                text = (doc.extracted_text or "").strip()
                result.append({
                    "document_id": str(doc.id),
                    "filename": doc.filename,
                    "document_type": doc.document_type.value if doc.document_type else None,
                    "snippet": text[:300] if text else "",
                    "match_reason": "filename_heuristic",
                    "match_confidence": "low",
                })
                used_doc_ids.add(doc.id)

    for doc in documents or []:
        if doc.id in used_doc_ids:
            continue
        if doc.document_type in (ShipmentDocumentType.ENTRY_SUMMARY, ShipmentDocumentType.COMMERCIAL_INVOICE):
            text = (doc.extracted_text or "").strip()
            if text:
                result.append({
                    "document_id": str(doc.id),
                    "filename": doc.filename,
                    "document_type": doc.document_type.value if doc.document_type else None,
                    "snippet": text[:300],
                    "match_reason": "all_docs",
                    "match_confidence": "medium",
                })
                used_doc_ids.add(doc.id)

    return result


def _build_rule_product_input(item: ShipmentItem, description: str) -> RuleProductInput:
    """
    Build deterministic rule-engine inputs from item + text cues.
    """
    d = (description or "").lower()
    training_cues = ["simulator", "simulation", "training", "demonstration", "demonstrational"]
    medical_cues = [
        "surgical",
        "endoscopic",
        "endoscopy",
        "medical",
        "procedure",
        "patient",
        "clinical",
    ]
    robotic_cues = ["robot", "robotic", "robot-assisted"]
    action_cues = ["grasp", "traction", "closure", "clip", "cut", "manipulat", "inserted"]
    system_cues = ["system", "controller", "driver unit", "cartridge", "platform"]

    is_training = any(c in d for c in training_cues)
    is_medical = any(c in d for c in medical_cues)
    is_robotic = any(c in d for c in robotic_cues)
    performs_action = any(c in d for c in action_cues)
    integrated_system = any(c in d for c in system_cues)

    # Heuristic interpretation of patient-use:
    # training simulators are not patient use; procedural cues imply patient use.
    used_on_humans = False if is_training else (True if (is_medical and ("training" not in d)) else None)
    purpose = "training" if is_training else ("treatment" if is_medical else "other")

    return RuleProductInput(
        product_name=item.label or "",
        description=description,
        used_on_humans=used_on_humans,
        purpose=purpose,
        is_robotic=is_robotic if is_robotic else None,
        is_medical_field=is_medical if is_medical else None,
        performs_direct_action=performs_action if performs_action else None,
        interacts_with_body=performs_action if performs_action else None,
        multiple_components=integrated_system if integrated_system else None,
        performs_integrated_function=integrated_system if integrated_system else None,
    )


def _apply_rule_based_heading_bias(
    classification_result: Dict[str, Any],
    rule_assessment: Dict[str, Any],
) -> Dict[str, Any]:
    """
    Re-rank candidates toward deterministic legal heading assessment and attach explainability.
    """
    if not isinstance(classification_result, dict):
        return classification_result
    out = dict(classification_result)
    heading = str((rule_assessment or {}).get("heading") or "").strip()
    preferred_htsus = str((rule_assessment or {}).get("htsus") or "").strip()
    if not heading:
        out["rule_based_assessment"] = rule_assessment
        return out

    candidates = out.get("candidates") or []
    if isinstance(candidates, list) and candidates:
        preferred_prefix = heading
        reordered = sorted(
            candidates,
            key=lambda c: (
                0 if str(c.get("hts_code", "")).startswith(preferred_prefix) else 1,
                -(c.get("final_score", 0.0) or 0.0),
            ),
        )
        # If no candidate matches deterministic heading and we have a concrete htsus, inject advisory candidate.
        has_match = any(str(c.get("hts_code", "")).startswith(preferred_prefix) for c in reordered)
        if (not has_match) and preferred_htsus and "xx" not in preferred_htsus.lower():
            top_score = float((reordered[0].get("final_score") or 0.0)) if reordered else 0.0
            injected = {
                "hts_code": preferred_htsus,
                "final_score": max(top_score + 0.01, 0.75),
                "similarity_score": reordered[0].get("similarity_score", 0.0) if reordered else 0.0,
                "display_text": f"{preferred_htsus} (rule-based heading preference)",
                "rule_injected": True,
            }
            reordered.insert(0, injected)
        out["candidates"] = reordered[:5]
        out["primary_candidate"] = out["candidates"][0] if out["candidates"] else out.get("primary_candidate")

    out["rule_based_assessment"] = rule_assessment
    meta = dict(out.get("metadata") or {})
    meta["rule_based_heading"] = heading
    meta["rule_based_confidence"] = (rule_assessment or {}).get("confidence")
    out["metadata"] = meta
    return out


class ShipmentAnalysisService:
    """Service for running full shipment analysis"""
    
    def __init__(self, db: AsyncSession):
        self.db = db
        self.document_processor = DocumentProcessor()
        self.classification_engine = ClassificationEngine(db)
        self.psc_radar = PSCRadar(db)
        self.regulatory_engine = RegulatoryApplicabilityEngine(db)
        self.enrichment_service = EnrichmentIntegrationService(db)
        self.rule_classifier = RuleBasedClassifier()

    async def _persist_reasoning_traces_phase2(
        self,
        *,
        analysis_id: Optional[UUID],
        organization_id: Optional[UUID],
        shipment_id: UUID,
        result_json: Dict[str, Any],
        stage_ctx: Optional[PipelineStageContext],
    ) -> None:
        """Canonical DB rows for heading reasoning trace; idempotent per (analysis_id, item_id)."""
        if not analysis_id or not organization_id:
            return
        items = result_json.get("items") or []
        if stage_ctx:
            await stage_ctx.mark(
                PipelineStageName.REASONING_TRACE_PERSIST,
                PipelineStageStatus.RUNNING,
                ordinal=32,
            )
        try:
            await persist_reasoning_traces_from_result_items(
                self.db,
                analysis_id=analysis_id,
                shipment_id=shipment_id,
                organization_id=organization_id,
                items=items if isinstance(items, list) else [],
            )
            if stage_ctx:
                await stage_ctx.mark(
                    PipelineStageName.REASONING_TRACE_PERSIST,
                    PipelineStageStatus.SUCCEEDED,
                    ordinal=32,
                )
        except Exception as e:
            if stage_ctx:
                await stage_ctx.mark(
                    PipelineStageName.REASONING_TRACE_PERSIST,
                    PipelineStageStatus.FAILED,
                    ordinal=32,
                    error_code="REASONING_TRACE_PERSIST_FAILED",
                    error_message=str(e),
                )
            raise

    async def run_full_shipment_analysis(
        self,
        shipment_id: UUID,
        organization_id: UUID,
        actor_user_id: UUID,
        clarification_responses: Optional[Dict[str, Dict[str, Any]]] = None,
        analysis_id: Optional[UUID] = None,
        stage_ctx: Optional[PipelineStageContext] = None,
    ) -> Tuple[Dict[str, Any], Dict[str, Any], List[str]]:
        """
        Run full shipment analysis.
        
        Steps in order:
        1. Load shipment data (org-scoped)
        2. Parse PDFs and build evidence map
        3. Run existing engines: classification, duty resolver, PSC radar, enrichment
        4. Run Side Sprint A regulatory evaluation
        5. Create ReviewRecord snapshot
        6. Persist regulatory evaluations linked to review_id
        7. Determine blockers (REVIEW_REQUIRED triggers)
        8. Build result_json for Sprint 11 rendering
        
        Args:
            shipment_id: Shipment ID
            organization_id: Organization ID
            actor_user_id: User ID who initiated analysis
        
        Returns:
            Tuple of (analysis_result_json, review_snapshot_json, blockers)
        """
        # Step 1: Load shipment data (org-scoped)
        from app.repositories.org_scoped_repository import OrgScopedRepository
        repo = OrgScopedRepository(self.db, Shipment)
        shipment = await repo.get_by_id(shipment_id, organization_id)
        
        # Load relationships
        await self.db.refresh(shipment, ["references", "items", "documents"])

        link_result = await self.db.execute(
            select(ShipmentItemDocument).where(ShipmentItemDocument.shipment_id == shipment_id)
        )
        item_doc_link_map: Dict[str, List[UUID]] = {}
        for row in link_result.scalars().all():
            if row.mapping_status == ItemDocumentMappingStatus.REJECTED:
                continue
            item_doc_link_map.setdefault(str(row.shipment_item_id), []).append(row.shipment_document_id)
        
        # Step 2: Parse PDFs and build evidence map
        doc_count = len(shipment.documents or [])
        logger.info("run_full_shipment_analysis: parsing %s document(s) for shipment %s", doc_count, shipment_id)
        if stage_ctx:
            await stage_ctx.mark(
                PipelineStageName.DOCUMENT_EVIDENCE,
                PipelineStageStatus.RUNNING,
                ordinal=10,
            )
        try:
            evidence_map = await self._parse_documents_and_build_evidence_map(shipment)
        except Exception as e:
            if stage_ctx:
                await stage_ctx.mark(
                    PipelineStageName.DOCUMENT_EVIDENCE,
                    PipelineStageStatus.FAILED,
                    ordinal=10,
                    error_code="DOCUMENT_EVIDENCE_FAILED",
                    error_message=str(e),
                )
            raise
        if stage_ctx:
            await stage_ctx.mark(
                PipelineStageName.DOCUMENT_EVIDENCE,
                PipelineStageStatus.SUCCEEDED,
                ordinal=10,
            )
        ev_docs = evidence_map.get("documents") or []
        ev_warnings = evidence_map.get("warnings") or []
        logger.info("run_full_shipment_analysis: documents parsed (evidence_map has %s docs), importing line items", len(ev_docs))

        # Step 2b: Import / reconcile line items from Entry Summary / Commercial Invoice
        import_summary: Dict[str, Any] = {
            "imported": 0,
            "merged": 0,
            "skipped": 0,
            "conflicts": [],
            "provenance_skipped": [],
        }
        if stage_ctx:
            await stage_ctx.mark(
                PipelineStageName.LINE_ITEM_IMPORT,
                PipelineStageStatus.RUNNING,
                ordinal=20,
            )
        try:
            import_summary = await self._import_line_items_from_documents(shipment)
        except Exception as e:
            logger.error("Line item import failed (mandatory stage): %s", e, exc_info=True)
            if stage_ctx:
                await stage_ctx.mark(
                    PipelineStageName.LINE_ITEM_IMPORT,
                    PipelineStageStatus.FAILED,
                    ordinal=20,
                    error_code="LINE_ITEM_IMPORT_FAILED",
                    error_message=str(e),
                )
            raise RuntimeError(f"Line item import failed: {e}") from e
        if stage_ctx:
            await stage_ctx.mark(
                PipelineStageName.LINE_ITEM_IMPORT,
                PipelineStageStatus.SUCCEEDED,
                ordinal=20,
            )
        await self.db.refresh(shipment, ["items"])

        if settings.SPRINT12_FAST_ANALYSIS_DEV and settings.ENVIRONMENT.lower() in {"development", "dev", "local"}:
            logger.info("run_full_shipment_analysis: using fast local analysis for shipment %s (%s items)", shipment_id, len(shipment.items or []))
            result_json, review_snapshot, blockers = await self._build_fast_local_analysis(
                shipment=shipment,
                shipment_id=shipment_id,
                actor_user_id=actor_user_id,
                evidence_map=evidence_map,
                item_doc_link_map=item_doc_link_map,
                analysis_id=analysis_id,
                organization_id=organization_id,
                stage_ctx=stage_ctx,
            )
            result_json["import_summary"] = import_summary
            logger.info("run_full_shipment_analysis: fast local analysis done for shipment %s", shipment_id)
            return result_json, review_snapshot, blockers
        
        # Step 3: Run existing engines
        logger.info("run_full_shipment_analysis: running classification/duty/PSC for shipment %s (%s items)", shipment_id, len(shipment.items or []))
        classification_results = {}
        classification_facts_by_item: Dict[str, Any] = {}
        duty_results = {}
        psc_results = {}
        enrichment_conflicts = []

        def _item_description_for_engine(item: ShipmentItem) -> str:
            description = item.label or ""
            if getattr(item, "supplemental_evidence_text", None) and item.supplemental_evidence_text.strip():
                return f"{description}\n\nSupplemental evidence:\n{item.supplemental_evidence_text.strip()}"
            ds_text = _get_item_data_sheet_text(
                item.label, shipment.documents or [], item.id, item_doc_link_map
            )
            if ds_text:
                return f"{description}\n\nData sheet evidence:\n{ds_text}"
            return description

        if stage_ctx:
            await stage_ctx.mark(
                PipelineStageName.CLASSIFICATION,
                PipelineStageStatus.RUNNING,
                ordinal=30,
            )

        async def _phase_classification() -> None:
            for item in shipment.items:
                item_id = str(item.id)
                description = _item_description_for_engine(item)
                try:
                    item_responses = (clarification_responses or {}).get(item_id) if clarification_responses else None
                    classification_result = await self.classification_engine.generate_alternatives(
                        description=description,
                        country_of_origin=item.country_of_origin,
                        value=float(item.value) if item.value else None,
                        quantity=float(item.quantity) if item.quantity else None,
                        current_hts_code=item.declared_hts,
                        clarification_responses=item_responses,
                    )
                    rule_input = _build_rule_product_input(item, description)
                    rule_result = self.rule_classifier.classify(rule_input)
                    rule_assessment = {
                        "heading": rule_result.heading,
                        "subheading": rule_result.subheading,
                        "htsus": rule_result.htsus,
                        "confidence": rule_result.confidence,
                        "justification": rule_result.justification,
                        "alternative_headings_considered": rule_result.alternative_headings_considered,
                        "warnings": rule_result.warnings,
                        "reasoning_path": rule_result.reasoning_path,
                    }
                    rule_mode = str(getattr(settings, "CLASSIFICATION_RULE_MODE", "enforce")).strip().lower()
                    if rule_mode == "enforce":
                        classification_result = _apply_rule_based_heading_bias(classification_result, rule_assessment)
                    elif isinstance(classification_result, dict):
                        if rule_mode == "shadow":
                            classification_result = dict(classification_result)
                            classification_result["rule_based_assessment"] = rule_assessment
                            logger.info(
                                "classification_rule_shadow item_id=%s heading=%s htsus=%s confidence=%s",
                                item_id,
                                rule_result.heading,
                                rule_result.htsus,
                                rule_result.confidence,
                            )
                    classification_results[item_id] = classification_result
                except Exception as e:
                    logger.error(f"Classification engine error for item {item_id}: {e}", exc_info=True)
                    raise RuntimeError(
                        f"Classification engine failed for item {item_id}; CLASSIFICATION stage cannot succeed: {e}"
                    ) from e

                clf_for_check = classification_results.get(item_id)
                if isinstance(clf_for_check, dict):
                    meta_chk = clf_for_check.get("metadata") or {}
                    pa_chk = meta_chk.get("product_analysis") or {}
                    raw_missing = (
                        meta_chk.get("missing_required_attributes")
                        or pa_chk.get("missing_required_attributes")
                        or []
                    )
                    item_responses = (clarification_responses or {}).get(item_id) if clarification_responses else None
                    critical_missing = _get_critical_missing(raw_missing, description)
                    if critical_missing and not item_responses:
                        classification_results[item_id] = {
                            "status": "CLARIFICATION_REQUIRED",
                            "questions": [
                                {"attribute": attr, "question": _question_for(attr)}
                                for attr in critical_missing
                            ],
                            "blocking_reason": f"Cannot classify: missing {', '.join(critical_missing)}",
                            "original_classification": clf_for_check,
                        }
                        duty_results[item_id] = None
                        psc_results[item_id] = None
                        continue

        try:
            await _phase_classification()
        except Exception as e:
            if stage_ctx:
                await stage_ctx.mark(
                    PipelineStageName.CLASSIFICATION,
                    PipelineStageStatus.FAILED,
                    ordinal=30,
                    error_code="CLASSIFICATION_FAILED",
                    error_message=str(e),
                )
            raise
        if stage_ctx:
            await stage_ctx.mark(
                PipelineStageName.CLASSIFICATION,
                PipelineStageStatus.SUCCEEDED,
                ordinal=30,
            )

        if stage_ctx:
            await stage_ctx.mark(
                PipelineStageName.FACT_PERSIST,
                PipelineStageStatus.RUNNING,
                ordinal=31,
            )

        async def _phase_fact_persist() -> None:
            for item in shipment.items:
                item_id = str(item.id)
                description = _item_description_for_engine(item)

                async def _persist_item_classification_facts(pa: Optional[Dict[str, Any]]) -> None:
                    base = dict(pa) if pa else {}
                    if not base.get("product_family"):
                        base.setdefault("product_family", "unknown")
                    base.setdefault("extracted_attributes", {})
                    base.setdefault("missing_required_attributes", [])
                    base.setdefault("analysis_confidence", base.get("analysis_confidence", 0.0))
                    base.setdefault("rationale", base.get("rationale", ""))
                    fp = build_classification_facts_payload(
                        product_analysis=base,
                        shipment_item=item,
                        description_used=description,
                    )
                    classification_facts_by_item[item_id] = fp
                    if analysis_id:
                        await upsert_shipment_item_classification_facts(
                            self.db,
                            analysis_id=analysis_id,
                            shipment_id=shipment.id,
                            organization_id=organization_id,
                            shipment_item_id=item.id,
                            facts_json=fp,
                            missing_facts_json=fp.get("missing_facts") or [],
                        )

                pa = _product_analysis_for_classification_facts(classification_results.get(item_id))
                await _persist_item_classification_facts(pa)

        try:
            await _phase_fact_persist()
        except Exception as e:
            if stage_ctx:
                await stage_ctx.mark(
                    PipelineStageName.FACT_PERSIST,
                    PipelineStageStatus.FAILED,
                    ordinal=31,
                    error_code="FACT_PERSIST_FAILED",
                    error_message=str(e),
                )
            raise
        if stage_ctx:
            await stage_ctx.mark(
                PipelineStageName.FACT_PERSIST,
                PipelineStageStatus.SUCCEEDED,
                ordinal=31,
            )

        async def _phase_duty_psc() -> None:
            for item in shipment.items:
                item_id = str(item.id)
                item_memo = build_classification_memo(classification_results.get(item_id))
                hts_for_duty = item.declared_hts or _get_hts_if_supported(
                    classification_results.get(item_id), item_memo,
                )
                if hts_for_duty:
                    try:
                        resolved_duty = await resolve_duty(
                            hts_for_duty,
                            db=self.db,
                            hts_version_id=AUTHORITATIVE_HTS_VERSION_ID
                        )
                        duty_results[item_id] = resolved_duty.to_dict() if resolved_duty else None
                    except Exception as e:
                        logger.error(f"Duty resolution error for item {item_id}: {e}")
                        duty_results[item_id] = {"error": str(e)}

                if hts_for_duty and item.value:
                    try:
                        psc_result = await self.psc_radar.analyze(
                            product_description=item.label or "",
                            declared_hts_code=hts_for_duty,
                            quantity=float(item.quantity) if item.quantity else 1.0,
                            customs_value=float(item.value)
                        )
                        psc_results[item_id] = {
                            "alternatives": [alt.__dict__ for alt in psc_result.alternatives],
                            "flags": [f.value for f in psc_result.flags],
                            "summary": psc_result.summary
                        }
                    except Exception as e:
                        logger.error(f"PSC Radar error for item {item_id}: {e}")
                        psc_results[item_id] = {"error": str(e)}

            if analysis_id:
                await self.db.flush()

        await _phase_duty_psc()

        if stage_ctx:
            await stage_ctx.mark(
                PipelineStageName.DUTY_PSC_ADVISORY,
                PipelineStageStatus.RUNNING,
                ordinal=35,
            )
        duty_psc_ok = not any(
            isinstance(d, dict) and d.get("error")
            for d in list(duty_results.values()) + list(psc_results.values())
        )
        if stage_ctx:
            await stage_ctx.mark(
                PipelineStageName.DUTY_PSC_ADVISORY,
                PipelineStageStatus.SUCCEEDED if duty_psc_ok else PipelineStageStatus.FAILED,
                ordinal=35,
                error_code=None if duty_psc_ok else "DUTY_OR_PSC_ITEM_ERROR",
                error_message=(
                    None
                    if duty_psc_ok
                    else "One or more items have duty or PSC error payloads in JSON (advisory; does not block TRUSTED)"
                ),
            )
        
        # Enrichment (check for conflicts)
        # TODO: Integrate enrichment service properly
        
        # Step 4: Run Side Sprint A regulatory evaluation
        regulatory_evaluations_data = []
        
        if stage_ctx:
            await stage_ctx.mark(
                PipelineStageName.REGULATORY_ENGINE,
                PipelineStageStatus.RUNNING,
                ordinal=40,
            )
        try:
            for item in shipment.items:
                clf = classification_results.get(str(item.id))
                reg_memo = build_classification_memo(clf)
                hts_code = item.declared_hts or _get_hts_if_supported(clf, reg_memo)
                if not hts_code:
                    continue
                
                # Prepare document evidence for regulatory evaluation
                document_evidence = []
                for doc in shipment.documents:
                    if doc.extracted_text:
                        document_evidence.append({
                            "document_id": str(doc.id),
                            "document_type": doc.document_type.value,
                            "text": doc.extracted_text,
                            "structured_data": doc.structured_data
                        })
                
                try:
                    reg_results = await self.regulatory_engine.evaluate_regulatory_applicability(
                        declared_hts_code=hts_code,
                        product_description=item.label,
                        document_evidence=document_evidence
                    )
                    
                    # Store for later persistence
                    # reg_result is a RegulatoryEvaluationResult dataclass
                    for reg_result in reg_results:
                        regulatory_evaluations_data.append({
                            "item_id": str(item.id),
                            "regulator": reg_result.regulator,  # Regulator enum
                            "outcome": reg_result.outcome,  # RegulatoryOutcome enum
                            "explanation_text": reg_result.explanation_text,
                            "triggered_by_hts_code": reg_result.triggered_by_hts_code,
                            "condition_evaluations": reg_result.condition_evaluations  # List[ConditionEvaluation] dataclasses
                        })
                except Exception as e:
                    logger.error(f"Regulatory evaluation error for item {item.id}: {e}", exc_info=True)
                    raise RuntimeError(
                        f"Regulatory evaluation failed for item {item.id}; REGULATORY_ENGINE stage cannot succeed: {e}"
                    ) from e

        except Exception as e:
            if stage_ctx:
                await stage_ctx.mark(
                    PipelineStageName.REGULATORY_ENGINE,
                    PipelineStageStatus.FAILED,
                    ordinal=40,
                    error_code="REGULATORY_ENGINE_FAILED",
                    error_message=str(e),
                )
            raise
        if stage_ctx:
            await stage_ctx.mark(
                PipelineStageName.REGULATORY_ENGINE,
                PipelineStageStatus.SUCCEEDED,
                ordinal=40,
            )

        # Step 5: review_snapshot is built later as deepcopy(result_json)
        # Capture metadata that will be merged into the snapshot after result_json is built
        _snapshot_meta = {
            "analysis_id": None,
            "eligibility_path": self._determine_eligibility_path(shipment),
            "document_ids": [str(doc.id) for doc in shipment.documents],
            "created_by": str(actor_user_id),
        }
        
        # Step 6: Determine blockers (REVIEW_REQUIRED triggers)
        blockers = []
        
        # Check regulatory outcomes for CONDITIONAL
        for reg_eval in regulatory_evaluations_data:
            if reg_eval["outcome"] == RegulatoryOutcome.CONDITIONAL:
                blockers.append(f"Regulatory evaluation {reg_eval['regulator'].value} requires review")
        
        # Check duty missing through 6-digit
        for item_id, duty_result in duty_results.items():
            if duty_result and isinstance(duty_result, dict):
                if duty_result.get("source_level_general") == "none" or duty_result.get("source_level_general") in ["chapter"]:
                    blockers.append(f"Duty missing through 6-digit level for item {item_id}")
        
        # Check enrichment conflicts
        if enrichment_conflicts:
            blockers.extend([f"Enrichment conflict: {c}" for c in enrichment_conflicts])
        
        # Determine review status
        review_status = ReviewStatus.REVIEW_REQUIRED if blockers else ReviewStatus.DRAFT
        
        # Step 7: Build result_json for Sprint 11 rendering
        # Collect warnings from evidence_map and other sources
        warnings = evidence_map.get("warnings", [])
        
        # Add warnings for any engine errors
        for item_id, result in classification_results.items():
            if isinstance(result, dict) and "error" in result:
                warnings.append({
                    "type": "classification_error",
                    "item_id": item_id,
                    "message": f"Classification engine error for item {item_id}: {result['error']}"
                })
        
        for item_id, result in duty_results.items():
            if isinstance(result, dict) and "error" in result:
                warnings.append({
                    "type": "duty_resolution_error",
                    "item_id": item_id,
                    "message": f"Duty resolution error for item {item_id}: {result['error']}"
                })
        
        # Knowledge layer — lookup prior accepted classifications (suggestions only; non-authoritative)
        from app.services.product_knowledge_service import ProductKnowledgeService
        knowledge_svc = ProductKnowledgeService(self.db)
        prior_knowledge: Dict[str, Optional[Dict[str, Any]]] = {}
        prior_knowledge_lookup_errors: List[Dict[str, Any]] = []
        for item in shipment.items or []:
            try:
                pk = await knowledge_svc.lookup(
                    organization_id, item.label or "", item.country_of_origin
                )
                if pk:
                    prior_knowledge[str(item.id)] = pk
            except Exception as ex:
                logger.warning(
                    "Product knowledge lookup failed item_id=%s: %s",
                    item.id,
                    ex,
                    exc_info=True,
                )
                prior_knowledge_lookup_errors.append(
                    {"item_id": str(item.id), "error": str(ex)}
                )

        line_provenance_map: Dict[str, List[ShipmentItemLineProvenance]] = {}
        if shipment.items:
            item_ids = [it.id for it in shipment.items]
            _prov_res = await self.db.execute(
                select(ShipmentItemLineProvenance).where(
                    ShipmentItemLineProvenance.shipment_item_id.in_(item_ids)
                )
            )
            for _pr in _prov_res.scalars().all():
                line_provenance_map.setdefault(str(_pr.shipment_item_id), []).append(_pr)

        def _get_primary_candidate(clf: Optional[Dict[str, Any]]) -> Optional[Dict[str, Any]]:
            """Derive primary_candidate from candidates[0] for frontend compatibility."""
            if not clf or not isinstance(clf, dict):
                return None
            if clf.get("primary_candidate"):
                return clf["primary_candidate"]
            candidates = clf.get("candidates") or []
            return candidates[0] if candidates else None

        def _enrich_classification(clf: Optional[Dict[str, Any]], get_pc) -> Optional[Dict[str, Any]]:
            """Add primary_candidate to classification for frontend; return copy to avoid mutating."""
            if not clf or not isinstance(clf, dict):
                return clf
            pc = get_pc(clf)
            if pc and not clf.get("primary_candidate"):
                out = dict(clf)
                out["primary_candidate"] = pc
                return out
            return clf

        def _duty_scenario_block(it: ShipmentItem, memo: Optional[Dict[str, Any]] = None) -> Optional[Dict[str, Any]]:
            clf = classification_results.get(str(it.id))
            sug = _get_hts_if_supported(clf, memo)
            if not it.declared_hts and not sug:
                return {"unavailable": True, "reason": "No reliable HTS available for duty comparison"}
            return {
                "declared_hts": it.declared_hts,
                "suggested_hts": sug,
                "basis": {
                    "hts_version_id": AUTHORITATIVE_HTS_VERSION_ID,
                    "country_of_origin": it.country_of_origin,
                    "label": "Base duty estimate (scenario comparison)",
                    "disclaimer": "MFN/base-style resolution only; preferential programs and Chapter 99 may apply and are not modeled here.",
                },
            }

        def _build_item_payload(item: ShipmentItem) -> Dict[str, Any]:
            iid = str(item.id)
            clf = classification_results.get(iid)
            memo = build_classification_memo(clf)
            hts = item.declared_hts or _get_hts_if_supported(clf, memo)
            suppress = bool(memo.get("suppress_alternatives"))
            support_level = memo.get("support_level", "unknown") if memo else "unknown"
            ev_used = _build_item_evidence_used(
                item.label, shipment.documents or [], item.id, item_doc_link_map,
            )
            line_prov = self._line_provenance_api_rows(
                line_provenance_map.get(iid, []),
                shipment.documents or [],
            )
            return {
                "id": iid,
                "label": item.label,
                "value": float(item.value) if item.value is not None else None,
                "hts_code": hts,
                "classification": None if suppress else _enrich_classification(clf, _get_primary_candidate),
                "classification_memo": memo,
                "classification_outcome": stable_classification_outcome(support_level),
                "duty": duty_results.get(iid),
                "duty_scenarios": _duty_scenario_block(item, memo),
                "psc": psc_results.get(iid),
                "regulatory": [r for r in regulatory_evaluations_data if r["item_id"] == iid],
                "supplemental_evidence_source": getattr(item, "supplemental_evidence_source", None),
                "needs_supplemental_evidence": _item_needs_supplemental(clf),
                "suppress_alternatives": suppress,
                "evidence_used": ev_used,
                "prior_knowledge": prior_knowledge.get(iid),
                "line_provenance": line_prov,
                "classification_facts": classification_facts_by_item.get(iid),
                "heading_reasoning_trace": build_heading_reasoning_trace(
                    None if suppress else clf,
                    evidence_used=ev_used,
                    line_provenance=line_prov,
                ),
            }

        result_json = {
            "shipment_id": str(shipment_id),
            "items": [_build_item_payload(item) for item in shipment.items],
            "evidence_map": evidence_map,
            "warnings": warnings,
            "blockers": blockers,
            "review_status": review_status.value,
            "generated_at": datetime.utcnow().isoformat(),
            "import_summary": import_summary,
            "regulatory_evaluations": regulatory_evaluations_data,
            "prior_knowledge_lookup_errors": prior_knowledge_lookup_errors,
        }
        if not shipment.items and shipment.documents:
            files_not_found = evidence_map.get("files_not_found") or any(
                "not found" in str(w.get("message", "")).lower() or "file not found" in str(w.get("message", "")).lower()
                for w in evidence_map.get("warnings", [])
            )
            result_json["no_items_hint"] = "files_not_found" if files_not_found else "extraction_returned_no_lines"

        await self._persist_reasoning_traces_phase2(
            analysis_id=analysis_id,
            organization_id=organization_id,
            shipment_id=shipment_id,
            result_json=result_json,
            stage_ctx=stage_ctx,
        )

        import copy
        review_snapshot = copy.deepcopy(result_json)
        review_snapshot.update(_snapshot_meta)
        return result_json, review_snapshot, blockers

    async def extract_preview(
        self,
        shipment_id: UUID,
        organization_id: UUID,
    ) -> Dict[str, Any]:
        """
        Run document parsing and line item import only. Returns summary for user confirmation.
        Use before full analysis so user can confirm: "Y line items / $XXX duty".
        """
        from app.repositories.org_scoped_repository import OrgScopedRepository
        repo = OrgScopedRepository(self.db, Shipment)
        shipment = await repo.get_by_id(shipment_id, organization_id)
        await self.db.refresh(shipment, ["references", "items", "documents"])
        
        evidence_map = await self._parse_documents_and_build_evidence_map(shipment)
        try:
            await self._import_line_items_from_documents(shipment)
        except Exception as e:
            logger.warning(f"Line item import failed during preview: {e}", exc_info=True)
        await self.db.refresh(shipment, ["items"])
        
        items = shipment.items or []
        line_provenance_preview: Dict[str, List[ShipmentItemLineProvenance]] = {}
        if items:
            _pids = [i.id for i in items]
            _pv = await self.db.execute(
                select(ShipmentItemLineProvenance).where(
                    ShipmentItemLineProvenance.shipment_item_id.in_(_pids)
                )
            )
            for _row in _pv.scalars().all():
                line_provenance_preview.setdefault(str(_row.shipment_item_id), []).append(_row)

        es_duty_by_line = self._get_es_duty_per_line(evidence_map)
        duty_total = sum((d.get("amount") or 0) for d in es_duty_by_line.values())
        
        items_preview = [
            {
                "label": getattr(i, "label", None) or f"Item {idx + 1}",
                "value": getattr(i, "value", None),
                "hts_code": getattr(i, "declared_hts", None),
                "line_provenance": self._line_provenance_api_rows(
                    line_provenance_preview.get(str(i.id), []),
                    shipment.documents or [],
                ),
            }
            for idx, i in enumerate(items[:10])
        ]
        
        return {
            "line_items_count": len(items),
            "duty_total": round(duty_total, 2),
            "items_preview": items_preview,
        }

    def _normalize_coo_for_comparison(self, raw: Any) -> Optional[str]:
        """Normalize country of origin to 2-letter code for comparison."""
        if raw is None or (isinstance(raw, float) and str(raw) == "nan"):
            return None
        s = str(raw).strip().upper()
        if not s:
            return None
        coo_map = {
            "CHINA": "CN", "CHINESE": "CN", "001 ARTICLE OF CHINA": "CN",
            "UNITED STATES": "US", "USA": "US",
            "GERMANY": "DE", "VIETNAM": "VN", "VIET NAM": "VN",
            "INDIA": "IN", "MEXICO": "MX", "TAIWAN": "TW",
            "SOUTH KOREA": "KR", "KOREA": "KR",
            "JAPAN": "JP", "CANADA": "CA",
        }
        for k, v in coo_map.items():
            if k in s or s in k:
                return v
        return s[:2] if len(s) >= 2 else s

    def _detect_origin_mismatches_from_evidence(self, evidence_map: Dict[str, Any]) -> List[Dict[str, Any]]:
        """Compare CI vs ES country of origin per line; return mismatches with duty impact."""
        mismatches: List[Dict[str, Any]] = []
        docs = evidence_map.get("documents") or []
        es_doc = next((d for d in docs if d.get("document_type") == "entry_summary"), None)
        ci_doc = next((d for d in docs if d.get("document_type") == "commercial_invoice"), None)
        if not es_doc or not ci_doc:
            return mismatches
        es_items = (es_doc.get("structured_data") or {}).get("line_items") or []
        ci_items = (ci_doc.get("structured_data") or {}).get("line_items") or []
        for i in range(max(len(es_items), len(ci_items))):
            es_li = es_items[i] if i < len(es_items) else {}
            ci_li = ci_items[i] if i < len(ci_items) else {}
            es_coo = self._normalize_coo_for_comparison(es_li.get("country_of_origin"))
            ci_coo = self._normalize_coo_for_comparison(ci_li.get("country_of_origin"))
            if not es_coo or not ci_coo or es_coo == ci_coo:
                continue
            duty_paid = None
            try:
                d = float(es_li.get("duty_amount") or 0)
                s = float(es_li.get("section_301_amount") or 0)
                duty_paid = d + s
            except (TypeError, ValueError):
                pass
            mismatches.append({
                "line_number": i + 1,
                "ci_country": ci_coo,
                "es_country": es_coo,
                "duty_paid": duty_paid,
                "description": es_li.get("description") or ci_li.get("description") or f"Line {i + 1}",
            })
        return mismatches

    def _get_es_duty_per_line(self, evidence_map: Dict[str, Any]) -> Dict[int, Dict[str, Any]]:
        """Extract duty_amount, section_301_amount per line from Entry Summary."""
        out: Dict[int, Dict[str, Any]] = {}
        docs = evidence_map.get("documents") or []
        es_doc = next((d for d in docs if d.get("document_type") == "entry_summary"), None)
        if not es_doc:
            return out
        items = (es_doc.get("structured_data") or {}).get("line_items") or []
        for i, li in enumerate(items):
            if not isinstance(li, dict):
                continue
            idx = i + 1
            duty = 0.0
            sec301 = None
            try:
                if li.get("duty_amount") is not None:
                    duty = float(li.get("duty_amount"))
            except (TypeError, ValueError):
                pass
            try:
                if li.get("section_301_amount") is not None:
                    sec301 = float(li.get("section_301_amount"))
            except (TypeError, ValueError):
                pass
            total = duty + (sec301 or 0)
            if total > 0 or sec301 is not None:
                out[idx] = {"amount": total, "section_301_amount": sec301}
        return out

    async def _build_fast_local_analysis(
        self,
        shipment: Shipment,
        shipment_id: UUID,
        actor_user_id: UUID,
        evidence_map: Dict[str, Any],
        item_doc_link_map: Optional[Dict[str, List[UUID]]] = None,
        analysis_id: Optional[UUID] = None,
        organization_id: Optional[UUID] = None,
        stage_ctx: Optional[PipelineStageContext] = None,
    ) -> Tuple[Dict[str, Any], Dict[str, Any], List[str]]:
        """
        Build a deterministic lightweight analysis result in local/dev mode.
        Enriches with ES duty, origin mismatch, COO confirmation prompt, and PSC for high-duty items.
        """
        classification_results: Dict[str, Any] = {}
        classification_facts_by_item: Dict[str, Any] = {}
        duty_results: Dict[str, Any] = {}
        psc_results: Dict[str, Any] = {}
        enrichment_conflicts: List[str] = []
        regulatory_evaluations_data: List[Dict[str, Any]] = []
        blockers: List[str] = []

        _fast_snapshot_meta = {
            "analysis_id": None,
            "eligibility_path": self._determine_eligibility_path(shipment),
            "document_ids": [str(doc.id) for doc in shipment.documents],
            "created_by": str(actor_user_id),
        }

        warnings_list = list(evidence_map.get("warnings", []))
        no_items_hint = None
        if not shipment.items and shipment.documents:
            files_not_found = evidence_map.get("files_not_found") or any(
                "not found" in str(w.get("message", "")).lower() or "file not found" in str(w.get("message", "")).lower()
                for w in warnings_list
            )
            if files_not_found:
                no_items_hint = "files_not_found"
            else:
                no_items_hint = "extraction_returned_no_lines"

        es_duty_by_line = self._get_es_duty_per_line(evidence_map)
        origin_mismatches = self._detect_origin_mismatches_from_evidence(evidence_map)

        coo_country_names = {"CN": "China", "DE": "Germany", "US": "United States", "VN": "Vietnam", "MX": "Mexico", "JP": "Japan", "KR": "South Korea", "TW": "Taiwan", "IN": "India", "CA": "Canada"}

        line_provenance_map_fast: Dict[str, List[ShipmentItemLineProvenance]] = {}
        if shipment.items:
            _iids = [it.id for it in shipment.items]
            _prov_fast = await self.db.execute(
                select(ShipmentItemLineProvenance).where(
                    ShipmentItemLineProvenance.shipment_item_id.in_(_iids)
                )
            )
            for _pf in _prov_fast.scalars().all():
                line_provenance_map_fast.setdefault(str(_pf.shipment_item_id), []).append(_pf)

        items_payload: List[Dict[str, Any]] = []
        psc_fast_failed = False

        def _fast_item_description(item: ShipmentItem) -> str:
            description = item.label or ""
            if getattr(item, "supplemental_evidence_text", None) and item.supplemental_evidence_text.strip():
                return f"{description}\n\nSupplemental evidence:\n{item.supplemental_evidence_text.strip()}"
            ds_text = _get_item_data_sheet_text(
                item.label,
                shipment.documents or [],
                item.id,
                item_doc_link_map or {},
            )
            if ds_text:
                return f"{description}\n\nData sheet evidence:\n{ds_text}"
            return description

        if stage_ctx:
            await stage_ctx.mark(
                PipelineStageName.CLASSIFICATION,
                PipelineStageStatus.RUNNING,
                ordinal=30,
            )

        async def _phase_fast_classification() -> None:
            for item in shipment.items or []:
                item_id = str(item.id)
                description = _fast_item_description(item)
                try:
                    classification_result = await self.classification_engine.generate_alternatives(
                        description=description,
                        country_of_origin=item.country_of_origin,
                        value=float(item.value) if item.value else None,
                        quantity=float(item.quantity) if item.quantity else None,
                        current_hts_code=item.declared_hts,
                        clarification_responses=None,
                    )
                    rule_input = _build_rule_product_input(item, description)
                    rule_result = self.rule_classifier.classify(rule_input)
                    rule_assessment = {
                        "heading": rule_result.heading,
                        "subheading": rule_result.subheading,
                        "htsus": rule_result.htsus,
                        "confidence": rule_result.confidence,
                        "justification": rule_result.justification,
                        "alternative_headings_considered": rule_result.alternative_headings_considered,
                        "warnings": rule_result.warnings,
                        "reasoning_path": rule_result.reasoning_path,
                    }
                    rule_mode = str(getattr(settings, "CLASSIFICATION_RULE_MODE", "enforce")).strip().lower()
                    if rule_mode == "enforce":
                        classification_result = _apply_rule_based_heading_bias(classification_result, rule_assessment)
                    elif isinstance(classification_result, dict):
                        if rule_mode == "shadow":
                            classification_result = dict(classification_result)
                            classification_result["rule_based_assessment"] = rule_assessment
                            logger.info(
                                "classification_rule_shadow item_id=%s heading=%s htsus=%s confidence=%s",
                                item_id,
                                rule_result.heading,
                                rule_result.htsus,
                                rule_result.confidence,
                            )
                    classification_results[item_id] = classification_result
                except Exception as e:
                    logger.error(f"Classification engine error in fast path for item {item.id}: {e}", exc_info=True)
                    raise RuntimeError(
                        f"Classification engine failed for item {item_id}; CLASSIFICATION stage cannot succeed: {e}"
                    ) from e

        try:
            await _phase_fast_classification()
        except Exception as e:
            if stage_ctx:
                await stage_ctx.mark(
                    PipelineStageName.CLASSIFICATION,
                    PipelineStageStatus.FAILED,
                    ordinal=30,
                    error_code="CLASSIFICATION_FAILED",
                    error_message=str(e),
                )
            raise
        if stage_ctx:
            await stage_ctx.mark(
                PipelineStageName.CLASSIFICATION,
                PipelineStageStatus.SUCCEEDED,
                ordinal=30,
            )

        if stage_ctx:
            await stage_ctx.mark(
                PipelineStageName.FACT_PERSIST,
                PipelineStageStatus.RUNNING,
                ordinal=31,
            )

        async def _phase_fast_fact_persist() -> None:
            for item in shipment.items or []:
                item_id = str(item.id)
                description = _fast_item_description(item)
                pa = _product_analysis_for_classification_facts(classification_results.get(item_id))
                base = dict(pa) if pa else {}
                if not base.get("product_family"):
                    base.setdefault("product_family", "unknown")
                base.setdefault("extracted_attributes", {})
                base.setdefault("missing_required_attributes", [])
                base.setdefault("analysis_confidence", base.get("analysis_confidence", 0.0))
                base.setdefault("rationale", base.get("rationale", ""))
                fp = build_classification_facts_payload(
                    product_analysis=base,
                    shipment_item=item,
                    description_used=description,
                )
                classification_facts_by_item[item_id] = fp
                if analysis_id:
                    await upsert_shipment_item_classification_facts(
                        self.db,
                        analysis_id=analysis_id,
                        shipment_id=shipment_id,
                        organization_id=organization_id,
                        shipment_item_id=item.id,
                        facts_json=fp,
                        missing_facts_json=fp.get("missing_facts") or [],
                    )

        try:
            await _phase_fast_fact_persist()
        except Exception as e:
            if stage_ctx:
                await stage_ctx.mark(
                    PipelineStageName.FACT_PERSIST,
                    PipelineStageStatus.FAILED,
                    ordinal=31,
                    error_code="FACT_PERSIST_FAILED",
                    error_message=str(e),
                )
            raise
        if stage_ctx:
            await stage_ctx.mark(
                PipelineStageName.FACT_PERSIST,
                PipelineStageStatus.SUCCEEDED,
                ordinal=31,
            )

        async def _phase_fast_build_payload() -> None:
            nonlocal psc_fast_failed
            for idx, item in enumerate(shipment.items or []):
                line_idx = idx + 1
                duty_from_es = es_duty_by_line.get(line_idx) or es_duty_by_line.get(idx + 1)
                duty_amount = (duty_from_es or {}).get("amount") or 0
                sec301 = (duty_from_es or {}).get("section_301_amount")
                item_id = str(item.id)

                fast_clf = classification_results.get(item_id)
                fast_memo = build_classification_memo(fast_clf)
                fast_suppress = bool(fast_memo.get("suppress_alternatives"))
                fast_support_level = fast_memo.get("support_level", "unknown") if fast_memo else "unknown"
                fast_ev = _build_item_evidence_used(
                    item.label, shipment.documents or [], item.id, item_doc_link_map or {},
                )
                fast_lp = self._line_provenance_api_rows(
                    line_provenance_map_fast.get(item_id, []),
                    shipment.documents or [],
                )
                item_dict: Dict[str, Any] = {
                    "id": str(item.id),
                    "label": item.label,
                    "hts_code": item.declared_hts or _get_hts_if_supported(fast_clf, fast_memo),
                    "classification": None if fast_suppress else fast_clf,
                    "classification_memo": fast_memo,
                    "classification_outcome": stable_classification_outcome(fast_support_level),
                    "duty": None,
                    "psc": None,
                    "regulatory": [],
                    "supplemental_evidence_source": getattr(item, "supplemental_evidence_source", None),
                    "needs_supplemental_evidence": _item_needs_supplemental(fast_clf),
                    "suppress_alternatives": fast_suppress,
                    "evidence_used": fast_ev,
                    "line_provenance": fast_lp,
                    "classification_facts": classification_facts_by_item.get(item_id),
                    "heading_reasoning_trace": build_heading_reasoning_trace(
                        None if fast_suppress else fast_clf,
                        evidence_used=fast_ev,
                        line_provenance=fast_lp,
                    ),
                }
                if duty_from_es:
                    item_dict["duty_from_entry_summary"] = {
                        "amount": duty_amount,
                        "section_301_amount": sec301,
                    }
            
                origin_mismatch_for_line = next((m for m in origin_mismatches if m.get("line_number") == line_idx), None)
                if origin_mismatch_for_line:
                    item_dict["origin_mismatch"] = {
                        "ci_country": origin_mismatch_for_line["ci_country"],
                        "es_country": origin_mismatch_for_line["es_country"],
                        "duty_paid": origin_mismatch_for_line.get("duty_paid"),
                    }
            
                psc_threshold = getattr(settings, "PSC_DUTY_THRESHOLD", 1000.0)
                if duty_amount > psc_threshold and item.declared_hts and item.value:
                    try:
                        psc_result = await self.psc_radar.analyze(
                            product_description=item.label or "",
                            declared_hts_code=item.declared_hts,
                            quantity=float(item.quantity) if item.quantity else 1.0,
                            customs_value=float(item.value),
                            country_of_origin=item.country_of_origin,
                        )
                        item_dict["psc"] = {
                            "alternatives": [{"alternative_hts_code": a.alternative_hts_code, "alternative_duty_rate": a.alternative_duty_rate, "delta_amount": a.delta_amount, "delta_percent": a.delta_percent} for a in psc_result.alternatives],
                            "summary": psc_result.summary,
                        }
                        if psc_result.alternatives or origin_mismatch_for_line:
                            item_dict["clarification_questions"] = [
                                {"attribute": "country_of_origin", "question": "Where was this product manufactured or assembled? Country of origin affects duty rates."},
                                {"attribute": "product_details", "question": "Can you confirm motor wattage, battery capacity, or other specs that may affect HTS classification?"},
                            ]
                    except Exception as e:
                        psc_fast_failed = True
                        logger.warning(f"PSC Radar error in fast path for item {item.id}: {e}")
            
                items_payload.append(item_dict)
            
            if analysis_id:
                await self.db.flush()

        await _phase_fast_build_payload()

        if stage_ctx:
            await stage_ctx.mark(
                PipelineStageName.DUTY_PSC_ADVISORY,
                PipelineStageStatus.RUNNING,
                ordinal=35,
            )
        if stage_ctx:
            await stage_ctx.mark(
                PipelineStageName.DUTY_PSC_ADVISORY,
                PipelineStageStatus.SUCCEEDED if not psc_fast_failed else PipelineStageStatus.FAILED,
                ordinal=35,
                error_code=None if not psc_fast_failed else "PSC_FAST_PATH_ERROR",
                error_message=None if not psc_fast_failed else "PSC Radar raised in fast local path (advisory)",
            )

        if stage_ctx:
            await stage_ctx.mark(
                PipelineStageName.REGULATORY_ENGINE,
                PipelineStageStatus.RUNNING,
                ordinal=40,
            )
        if stage_ctx:
            await stage_ctx.mark(
                PipelineStageName.REGULATORY_ENGINE,
                PipelineStageStatus.SUCCEEDED,
                ordinal=40,
            )

        for m in origin_mismatches:
            ci_name = coo_country_names.get(m["ci_country"], m["ci_country"])
            es_name = coo_country_names.get(m["es_country"], m["es_country"])
            duty_str = f" (${m.get('duty_paid', 0):,.0f} duty paid)" if m.get("duty_paid") else ""
            blockers.append(
                f"Origin mismatch: Commercial Invoice shows {ci_name}; Entry Summary shows {es_name}{duty_str}. "
                f"If the product is actually from {ci_name}, you may be able to recover ~${m.get('duty_paid', 0):,.0f}. "
                f"Confirm country of origin with your broker and consider filing a protest if applicable."
            )

        coo_confirmation_prompt = None
        psc_threshold = getattr(settings, "PSC_DUTY_THRESHOLD", 1000.0)
        if origin_mismatches or any((i.get("duty_from_entry_summary") or {}).get("amount", 0) > psc_threshold for i in items_payload):
            es_country = origin_mismatches[0]["es_country"] if origin_mismatches else "the declared country"
            es_name = coo_country_names.get(es_country, es_country)
            coo_confirmation_prompt = f"Is the country of origin actually {es_name}? If not, you may qualify for lower or no duty. Verify with your supplier and broker."

        result_json: Dict[str, Any] = {
            "shipment_id": str(shipment_id),
            "items": items_payload,
            "evidence_map": evidence_map,
            "warnings": warnings_list,
            "blockers": blockers,
            "review_status": ReviewStatus.DRAFT.value,
            "generated_at": datetime.utcnow().isoformat(),
            "mode": "FAST_LOCAL_DEV",
            "regulatory_evaluations": regulatory_evaluations_data,
            "prior_knowledge_lookup_errors": [],
        }
        if coo_confirmation_prompt:
            result_json["coo_confirmation_prompt"] = coo_confirmation_prompt
        if origin_mismatches:
            result_json["origin_mismatches"] = origin_mismatches
        if no_items_hint:
            result_json["no_items_hint"] = no_items_hint

        await self._persist_reasoning_traces_phase2(
            analysis_id=analysis_id,
            organization_id=organization_id,
            shipment_id=shipment_id,
            result_json=result_json,
            stage_ctx=stage_ctx,
        )

        import copy
        review_snapshot = copy.deepcopy(result_json)
        review_snapshot.update(_fast_snapshot_meta)
        return result_json, review_snapshot, blockers
    
    async def _parse_documents_and_build_evidence_map(self, shipment: Shipment) -> Dict[str, Any]:
        """
        Parse PDFs and build evidence map.
        
        Returns consistent "evidence map" object that all downstream steps reference.
        """
        evidence_map = {
            "documents": [],
            "extraction_errors": [],
            "warnings": [],
            "files_not_found": False,
        }
        
        for doc in shipment.documents:
            doc_evidence = {
                "document_id": str(doc.id),
                "document_type": doc.document_type.value,
                "filename": doc.filename
            }

            if not settings.S3_BUCKET_NAME:
                # Local/dev mode: try to load from mock_uploads (path fixed so it works regardless of CWD)
                safe_name = doc.s3_key.replace("/", "_")
                local_path = settings.MOCK_UPLOADS_DIR / safe_name
                if not local_path.exists():
                    legacy_path = Path("backend/data/mock_uploads") / safe_name
                    cwd_path = Path.cwd() / "data" / "mock_uploads" / safe_name
                    for candidate in (legacy_path, cwd_path):
                        if candidate.exists():
                            local_path = candidate
                            break
                    if not local_path.exists():
                        # Fallback: find by filename in mock_uploads (in case storage used filename)
                        if doc.filename and settings.MOCK_UPLOADS_DIR.exists():
                            for f in settings.MOCK_UPLOADS_DIR.iterdir():
                                if f.is_file() and f.name == doc.filename:
                                    local_path = f
                                    logger.info("Found document by filename fallback: %s", f)
                                    break
                    if not local_path.exists():
                        logger.warning(
                            "Local document file not found for analysis; tried %s, %s, %s, filename=%s; doc_id=%s",
                            settings.MOCK_UPLOADS_DIR / safe_name, legacy_path, cwd_path, doc.filename, doc.id
                        )
                        
                if local_path.exists():
                    try:
                        hint = doc.document_type.value if doc.document_type else None
                        # Run in thread so sync LLM calls don't block event loop; 90s timeout per doc so one file can't hang the run
                        try:
                            process_result = await asyncio.wait_for(
                                asyncio.get_event_loop().run_in_executor(
                                    None,
                                    lambda p=local_path, h=hint: self.document_processor.process_document(p, document_type_hint=h),
                                ),
                                timeout=90.0,
                            )
                        except asyncio.TimeoutError:
                            logger.warning("Document processing timed out (90s) for doc_id=%s filename=%s", doc.id, doc.filename)
                            process_result = {"success": False, "error": "Processing timed out after 90 seconds"}
                            evidence_map["warnings"].append({
                                "type": "document_processing_timeout",
                                "document_id": str(doc.id),
                                "message": f"{doc.filename}: timed out after 90s",
                            })
                        if process_result["success"]:
                            doc.extracted_text = process_result.get("extracted_text")
                            doc.structured_data = enrich_structured_data_with_extraction(
                                process_result.get("structured_data"),
                                process_result.get("extracted_text") or "",
                            )
                            apply_ingestion_metadata_to_shipment_document(doc, process_result)
                            doc.processing_status = "COMPLETED"
                            doc_evidence["extracted_text"] = process_result.get("extracted_text")
                            doc_evidence["structured_data"] = process_result.get("structured_data")
                            doc_evidence["extraction_status"] = doc.extraction_status
                            doc_evidence["ocr_used"] = doc.ocr_used
                            doc_evidence["char_count"] = doc.char_count
                            doc_evidence["usable_for_analysis"] = doc.usable_for_analysis
                            doc_evidence["evidence_pointers"] = []
                            if process_result.get("table_preview") is not None:
                                doc_evidence["table_preview"] = process_result["table_preview"]
                                doc_evidence["table_columns"] = process_result.get("table_columns") or []
                            li_count = len((process_result.get("structured_data") or {}).get("line_items") or [])
                            if li_count == 0 and doc.document_type and doc.filename:
                                logger.info(
                                    "Document processed but 0 line_items: doc_id=%s filename=%s type=%s",
                                    doc.id, doc.filename, doc.document_type.value
                                )
                        else:
                            apply_ingestion_metadata_to_shipment_document(doc, process_result)
                            doc.processing_status = "FAILED"
                            doc_evidence["error"] = process_result.get("error", "Processing failed")
                            evidence_map["warnings"].append({
                                "type": "document_processing_error",
                                "document_id": str(doc.id),
                                "document_type": doc.document_type.value,
                                "message": f"Failed to process {doc.filename}: {process_result.get('error', 'Unknown error')}"
                            })
                    except Exception as e:
                        logger.warning(f"Error processing local document {doc.id}: {e}")
                        evidence_map["warnings"].append({
                            "type": "document_processing_skipped",
                            "document_id": str(doc.id),
                            "document_type": doc.document_type.value,
                            "message": f"S3 bucket is not configured; local extraction failed: {e}"
                        })
                else:
                    # File not on disk — use previously committed structured_data if available
                    if doc.extracted_text:
                        doc_evidence["extracted_text"] = doc.extracted_text
                    if doc.structured_data:
                        doc_evidence["structured_data"] = doc.structured_data
                    evidence_map["warnings"].append({
                        "type": "document_processing_skipped",
                        "document_id": str(doc.id),
                        "document_type": doc.document_type.value,
                        "message": "Local file not found; using previously extracted data if available."
                    })
                    evidence_map["files_not_found"] = True
                doc_evidence["evidence_pointers"] = doc_evidence.get("evidence_pointers", [])
                evidence_map["documents"].append(doc_evidence)
                continue
            
            try:
                s3_client = get_s3_client()
                # Download from S3 to temp file (use actual extension for document processor)
                import tempfile
                import os
                ext = Path(doc.filename).suffix.lower() if doc.filename else ".pdf"
                if ext not in (".pdf", ".docx", ".xlsx", ".xls", ".csv"):
                    ext = ".pdf"
                with tempfile.NamedTemporaryFile(delete=False, suffix=ext) as tmp_file:
                    tmp_path = Path(tmp_file.name)
                    
                    try:
                        # Download from S3
                        s3_client.download_file(
                            Bucket=settings.S3_BUCKET_NAME,
                            Key=doc.s3_key,
                            Filename=str(tmp_path)
                        )
                        
                        # Process document (use stored type so user categorization drives extraction); 90s timeout per doc
                        hint = doc.document_type.value if doc.document_type else None
                        try:
                            process_result = await asyncio.wait_for(
                                asyncio.get_event_loop().run_in_executor(
                                    None,
                                    lambda p=tmp_path, h=hint: self.document_processor.process_document(p, document_type_hint=h),
                                ),
                                timeout=90.0,
                            )
                        except asyncio.TimeoutError:
                            logger.warning("Document processing timed out (90s) for doc_id=%s", doc.id)
                            process_result = {"success": False, "error": "Processing timed out after 90 seconds"}
                        
                        if process_result["success"]:
                            doc.extracted_text = process_result.get("extracted_text")
                            doc.structured_data = enrich_structured_data_with_extraction(
                                process_result.get("structured_data"),
                                process_result.get("extracted_text") or "",
                            )
                            apply_ingestion_metadata_to_shipment_document(doc, process_result)
                            doc.processing_status = "COMPLETED"

                            # Build evidence pointers
                            doc_evidence["extracted_text"] = process_result.get("extracted_text")
                            doc_evidence["structured_data"] = process_result.get("structured_data")
                            doc_evidence["page_count"] = process_result.get("metadata", {}).get("page_count", 0)
                            doc_evidence["extraction_status"] = doc.extraction_status
                            doc_evidence["ocr_used"] = doc.ocr_used
                            doc_evidence["char_count"] = doc.char_count
                            doc_evidence["usable_for_analysis"] = doc.usable_for_analysis
                            doc_evidence["evidence_pointers"] = []
                            
                            # Create evidence pointers (page number + snippet references)
                            if process_result.get("extracted_text"):
                                # Simple implementation: reference entire document for now
                                # TODO: Implement page-level and snippet-level references
                                doc_evidence["evidence_pointers"].append({
                                    "page_number": 1,
                                    "snippet": process_result.get("extracted_text", "")[:200]  # First 200 chars
                                })
                        else:
                            apply_ingestion_metadata_to_shipment_document(doc, process_result)
                            doc.processing_status = "FAILED"
                            error_msg = process_result.get("error", "Unknown processing error")
                            doc_evidence["error"] = error_msg
                            evidence_map["extraction_errors"].append({
                                "document_id": str(doc.id),
                                "document_type": doc.document_type.value,
                                "filename": doc.filename,
                                "error": error_msg
                            })
                            # Add warning - document processing failed but analysis continues
                            evidence_map["warnings"].append({
                                "type": "document_processing_error",
                                "document_id": str(doc.id),
                                "document_type": doc.document_type.value,
                                "message": f"Failed to process document {doc.filename}: {error_msg}. Analysis continues but evidence from this document is unavailable."
                            })
                    
                    finally:
                        # Clean up temp file
                        if tmp_path.exists():
                            os.unlink(tmp_path)
                
            except Exception as e:
                logger.error(f"Error processing document {doc.id}: {e}")
                error_msg = str(e)
                doc_evidence["error"] = error_msg
                evidence_map["extraction_errors"].append({
                    "document_id": str(doc.id),
                    "document_type": doc.document_type.value,
                    "filename": doc.filename,
                    "error": error_msg
                })
                # Add warning - document processing failed but analysis continues
                evidence_map["warnings"].append({
                    "type": "document_processing_error",
                    "document_id": str(doc.id),
                    "document_type": doc.document_type.value,
                    "message": f"Failed to process document {doc.filename}: {error_msg}. Analysis continues but evidence from this document is unavailable."
                })
            
            evidence_map["documents"].append(doc_evidence)
        
        return evidence_map

    @staticmethod
    def _desc_hash(label: Optional[str]) -> str:
        """Stable short hash of a normalised item description for merge matching."""
        norm = (label or "").strip().lower()
        return hashlib.md5(norm.encode()).hexdigest()[:12] if norm else ""

    @staticmethod
    def _clean_hts(raw: Any) -> Optional[str]:
        if not raw:
            return None
        digits_only = re.sub(r"[^0-9]", "", str(raw))
        return digits_only[:10] if digits_only else None

    _COO_MAP = {
        "CHINA": "CN", "CHINESE": "CN", "001 ARTICLE OF CHINA": "CN",
        "UNITED STATES": "US", "USA": "US",
        "GERMANY": "DE", "VIETNAM": "VN", "VIET NAM": "VN",
        "INDIA": "IN", "MEXICO": "MX", "TAIWAN": "TW",
        "SOUTH KOREA": "KR", "KOREA": "KR",
        "JAPAN": "JP", "CANADA": "CA",
    }

    @classmethod
    def _clean_coo(cls, raw: Any) -> Optional[str]:
        if raw is None:
            return None
        s = str(raw).strip().upper()
        if not s:
            return None
        return cls._COO_MAP.get(s, s[:2])

    @staticmethod
    def _document_type_label(document_type: str) -> str:
        if document_type == ShipmentDocumentType.ENTRY_SUMMARY.value:
            return "Entry Summary"
        if document_type == ShipmentDocumentType.COMMERCIAL_INVOICE.value:
            return "Commercial Invoice"
        return document_type

    def _line_provenance_api_rows(
        self,
        rows: List[ShipmentItemLineProvenance],
        documents: List[Any],
    ) -> List[Dict[str, Any]]:
        """UI/debug payload: human-readable linkage (stable item identity)."""
        doc_map = {d.id: d for d in (documents or [])}
        out: List[Dict[str, Any]] = []
        for p in rows:
            d = doc_map.get(p.shipment_document_id)
            dt = d.document_type.value if d else "UNKNOWN"
            label = self._document_type_label(dt)
            display_ln = p.logical_line_number if p.logical_line_number is not None else (p.line_index + 1)
            out.append(
                {
                    "shipment_document_id": str(p.shipment_document_id),
                    "document_type": dt,
                    "filename": d.filename if d else None,
                    "line_index": p.line_index,
                    "logical_line_number": p.logical_line_number,
                    "mapping_method": p.mapping_method,
                    "summary": f"Linked to {label} line {display_ln} (array index {p.line_index})",
                    "raw_line_text": (p.raw_line_text or "")[:2000],
                    "structured_snapshot": p.structured_snapshot,
                }
            )
        return out

    async def _ensure_line_provenance_for_item(
        self,
        shipment: Shipment,
        item: ShipmentItem,
        sources: List[Dict[str, Any]],
    ) -> None:
        """Idempotent: insert provenance rows for structured CI/ES lines."""
        if not sources:
            return
        for src in sources:
            doc_id = src["document_id"]
            array_index = int(src["array_index"])
            existing = await self.db.execute(
                select(ShipmentItemLineProvenance.id).where(
                    and_(
                        ShipmentItemLineProvenance.shipment_item_id == item.id,
                        ShipmentItemLineProvenance.shipment_document_id == doc_id,
                        ShipmentItemLineProvenance.line_index == array_index,
                    )
                ).limit(1)
            )
            if existing.scalar_one_or_none():
                continue
            raw_dict = src.get("raw_dict") if isinstance(src.get("raw_dict"), dict) else {}
            desc = raw_dict.get("description")
            raw_text = str(desc).strip() if desc is not None else None
            if not raw_text:
                try:
                    raw_text = json.dumps(raw_dict, default=str)[:8000]
                except Exception:
                    raw_text = str(raw_dict)[:8000]
            dt = src.get("document_type") or ""
            method = (
                LineProvenanceMappingMethod.STRUCTURED_IMPORT_ES
                if dt == ShipmentDocumentType.ENTRY_SUMMARY.value
                else LineProvenanceMappingMethod.STRUCTURED_IMPORT_CI
            )
            self.db.add(
                ShipmentItemLineProvenance(
                    shipment_id=shipment.id,
                    organization_id=shipment.organization_id,
                    shipment_item_id=item.id,
                    shipment_document_id=doc_id,
                    line_index=array_index,
                    logical_line_number=src.get("logical_line_number"),
                    raw_line_text=raw_text,
                    mapping_method=method,
                    structured_snapshot=raw_dict or None,
                )
            )

    async def _import_line_items_from_documents(self, shipment: Shipment) -> Dict[str, Any]:
        """Import line items from Entry Summary / Commercial Invoice with idempotent merge.

        Returns a summary: {"imported": N, "merged": N, "skipped": N, "conflicts": [...], "provenance_skipped": [...]}
        Always additive — never silently skips when items already exist.
        """
        summary: Dict[str, Any] = {
            "imported": 0,
            "merged": 0,
            "skipped": 0,
            "conflicts": [],
            "provenance_skipped": [],
        }

        # --- 1. Extract lines from documents (and authoritative line_sources for provenance) ---
        es_items: Dict[int, Dict[str, Any]] = {}
        ci_items: Dict[int, Dict[str, Any]] = {}
        line_sources: Dict[int, List[Dict[str, Any]]] = {}

        for doc in shipment.documents:
            data = doc.structured_data
            if not data or not isinstance(data, dict) or data.get("error"):
                continue
            line_items = data.get("line_items")
            if not line_items or not isinstance(line_items, list):
                continue

            for i, li in enumerate(line_items):
                if not isinstance(li, dict):
                    continue
                idx = li.get("line_number")
                try:
                    idx = int(idx) if idx is not None else i + 1
                except (TypeError, ValueError):
                    idx = i + 1

                if doc.document_type == ShipmentDocumentType.ENTRY_SUMMARY:
                    line_sources.setdefault(idx, []).append(
                        {
                            "document_id": doc.id,
                            "document_type": doc.document_type.value,
                            "array_index": i,
                            "logical_line_number": idx,
                            "raw_dict": li,
                        }
                    )
                    es_items[idx] = {
                        "description": li.get("description"),
                        "hts_code": li.get("hts_code"),
                        "country_of_origin": li.get("country_of_origin"),
                        "quantity": li.get("quantity"),
                        "unit": li.get("unit"),
                        "value": li.get("entered_value"),
                    }
                elif doc.document_type == ShipmentDocumentType.COMMERCIAL_INVOICE:
                    line_sources.setdefault(idx, []).append(
                        {
                            "document_id": doc.id,
                            "document_type": doc.document_type.value,
                            "array_index": i,
                            "logical_line_number": idx,
                            "raw_dict": li,
                        }
                    )
                    val = li.get("total")
                    if val is None and li.get("unit_price") is not None and li.get("quantity") is not None:
                        try:
                            val = float(li.get("unit_price", 0) or 0) * float(li.get("quantity", 0) or 0)
                        except (TypeError, ValueError):
                            pass
                    ci_items[idx] = {
                        "description": li.get("description"),
                        "hts_code": li.get("hts_code"),
                        "country_of_origin": li.get("country_of_origin"),
                        "quantity": li.get("quantity"),
                        "unit": li.get("unit"),
                        "value": val,
                    }

        # --- 2. Merge ES + CI (ES wins per field) ---
        incoming: Dict[int, Dict[str, Any]] = {}
        all_keys = set(es_items.keys()) | set(ci_items.keys())
        for k in sorted(all_keys):
            es = es_items.get(k, {})
            ci = ci_items.get(k, {})
            incoming[k] = {
                "line_number": k,
                "description": es.get("description") or ci.get("description") or f"Line {k}",
                "hts_code": self._clean_hts(es.get("hts_code") or ci.get("hts_code")),
                "country_of_origin": self._clean_coo(es.get("country_of_origin") or ci.get("country_of_origin")),
                "quantity": es.get("quantity") or ci.get("quantity"),
                "unit": es.get("unit") or ci.get("unit"),
                "value": es.get("value") or ci.get("value"),
            }

        if not incoming:
            logger.warning(
                "No line items found in documents for shipment %s", shipment.id,
            )
            return summary

        # --- 3. Build index of existing items for match ---
        existing_by_hash: Dict[str, ShipmentItem] = {}
        existing_by_hts_coo: Dict[str, ShipmentItem] = {}
        for item in (shipment.items or []):
            h = self._desc_hash(item.label)
            if h:
                existing_by_hash[h] = item
            if item.declared_hts and item.country_of_origin:
                existing_by_hts_coo[f"{item.declared_hts}:{item.country_of_origin}"] = item

        # --- 4. Reconcile each incoming line ---
        new_items_by_line: Dict[int, ShipmentItem] = {}
        merged_items_by_line: Dict[int, ShipmentItem] = {}

        for _line_num, m in sorted(incoming.items()):
            label = str(m.get("description") or f"Line {_line_num}")[:255]
            inc_hts = m["hts_code"]
            inc_coo = m["country_of_origin"]
            inc_hash = self._desc_hash(label)
            val = m.get("value")
            val_str = str(val)[:50] if val is not None else None
            qty = m.get("quantity")
            qty_str = str(qty)[:50] if qty is not None else None
            unit_str = str(m["unit"])[:20] if m.get("unit") else None

            # Try to find matching existing item
            matched: Optional[ShipmentItem] = None
            if inc_hash and inc_hash in existing_by_hash:
                matched = existing_by_hash[inc_hash]
            elif inc_hts and inc_coo and f"{inc_hts}:{inc_coo}" in existing_by_hts_coo:
                matched = existing_by_hts_coo[f"{inc_hts}:{inc_coo}"]

            if matched is not None:
                # Both have HTS with different values → conflict
                if matched.declared_hts and inc_hts and matched.declared_hts != inc_hts:
                    summary["conflicts"].append({
                        "existing_label": matched.label,
                        "existing_hts": matched.declared_hts,
                        "incoming_label": label,
                        "incoming_hts": inc_hts,
                        "reason": "HTS mismatch on matched item",
                    })
                    summary["provenance_skipped"].append(
                        {"line_num": _line_num, "reason": "hts_conflict"}
                    )
                    logger.warning(
                        "provenance_skipped shipment_id=%s line_num=%s reason=%s",
                        shipment.id,
                        _line_num,
                        "hts_conflict",
                    )
                    continue

                merged_items_by_line[_line_num] = matched

                # Check if all fields identical → skip
                fields_same = (
                    (matched.declared_hts or "") == (inc_hts or "")
                    and (matched.country_of_origin or "") == (inc_coo or "")
                    and (matched.value or "") == (val_str or "")
                )
                if fields_same:
                    summary["skipped"] += 1
                    continue

                # Merge: fill empty fields on existing item from incoming
                changed = False
                if not matched.declared_hts and inc_hts:
                    matched.declared_hts = inc_hts
                    changed = True
                if not matched.country_of_origin and inc_coo:
                    matched.country_of_origin = inc_coo
                    changed = True
                if not matched.value and val_str:
                    matched.value = val_str
                    changed = True
                if not matched.quantity and qty_str:
                    matched.quantity = qty_str
                    changed = True
                if not matched.unit_of_measure and unit_str:
                    matched.unit_of_measure = unit_str
                    changed = True
                if changed:
                    summary["merged"] += 1
                else:
                    summary["skipped"] += 1
                continue

            # No match → add new item
            new_item = ShipmentItem(
                shipment_id=shipment.id,
                label=label,
                declared_hts=inc_hts,
                value=val_str,
                quantity=qty_str,
                unit_of_measure=unit_str,
                country_of_origin=inc_coo,
            )
            self.db.add(new_item)
            new_items_by_line[_line_num] = new_item
            summary["imported"] += 1

        if incoming:
            await self.db.flush()
            for line_num in sorted(incoming.keys()):
                srcs = line_sources.get(line_num) or []
                if not srcs:
                    continue
                item = new_items_by_line.get(line_num) or merged_items_by_line.get(line_num)
                if item:
                    await self._ensure_line_provenance_for_item(shipment, item, srcs)
            await self.db.flush()

        await self._auto_link_line_items_to_source_documents(shipment)

        total = summary["imported"] + summary["merged"] + summary["skipped"] + len(summary["conflicts"])
        logger.info(
            "import_line_items shipment=%s: imported=%d merged=%d skipped=%d conflicts=%d total=%d",
            shipment.id, summary["imported"], summary["merged"],
            summary["skipped"], len(summary["conflicts"]), total,
        )
        return summary

    async def _auto_link_line_items_to_source_documents(self, shipment: Shipment) -> None:
        """Create AUTO item-document links: provenance-first, then hash/label fallback."""
        await self.db.refresh(shipment, ["items", "documents"])
        org_id = shipment.organization_id
        if not shipment.items or not shipment.documents:
            return

        prov_rows = (
            await self.db.execute(
                select(ShipmentItemLineProvenance).where(
                    ShipmentItemLineProvenance.shipment_id == shipment.id
                )
            )
        ).scalars().all()
        prov_pairs: Set[Tuple[UUID, UUID]] = set()
        for p in prov_rows:
            prov_pairs.add((p.shipment_item_id, p.shipment_document_id))

        # 1) Authoritative: one AUTO link per (item, document) that has structured provenance
        seen_link: Set[Tuple[UUID, UUID]] = set()
        for p in prov_rows:
            pair = (p.shipment_item_id, p.shipment_document_id)
            if pair in seen_link:
                continue
            seen_link.add(pair)
            existing = await self.db.execute(
                select(ShipmentItemDocument.id).where(
                    and_(
                        ShipmentItemDocument.shipment_item_id == p.shipment_item_id,
                        ShipmentItemDocument.shipment_document_id == p.shipment_document_id,
                    )
                ).limit(1)
            )
            if existing.scalar_one_or_none():
                continue
            self.db.add(
                ShipmentItemDocument(
                    shipment_id=shipment.id,
                    organization_id=org_id,
                    shipment_item_id=p.shipment_item_id,
                    shipment_document_id=p.shipment_document_id,
                    mapping_status=ItemDocumentMappingStatus.AUTO,
                )
            )
        await self.db.flush()

        # 2) Fallback: label/hash reconstruction only when no provenance row for (item, doc)
        for doc in shipment.documents:
            if doc.document_type not in (
                ShipmentDocumentType.COMMERCIAL_INVOICE,
                ShipmentDocumentType.ENTRY_SUMMARY,
            ):
                continue
            data = doc.structured_data or {}
            if not isinstance(data, dict) or data.get("error"):
                continue
            line_items = data.get("line_items")
            if not line_items or not isinstance(line_items, list):
                continue

            for i, li in enumerate(line_items):
                if not isinstance(li, dict):
                    continue
                desc = str(li.get("description") or f"Line {i + 1}")[:255]
                h = self._desc_hash(desc)
                matched_item: Optional[ShipmentItem] = None
                for it in shipment.items:
                    if self._desc_hash(it.label) == h or (it.label or "").strip() == desc.strip():
                        matched_item = it
                        break
                if matched_item is None:
                    continue
                if (matched_item.id, doc.id) in prov_pairs:
                    continue

                existing = await self.db.execute(
                    select(ShipmentItemDocument.id).where(
                        and_(
                            ShipmentItemDocument.shipment_item_id == matched_item.id,
                            ShipmentItemDocument.shipment_document_id == doc.id,
                        )
                    ).limit(1)
                )
                if existing.scalar_one_or_none():
                    continue

                self.db.add(
                    ShipmentItemDocument(
                        shipment_id=shipment.id,
                        organization_id=org_id,
                        shipment_item_id=matched_item.id,
                        shipment_document_id=doc.id,
                        mapping_status=ItemDocumentMappingStatus.AUTO,
                    )
                )
        await self.db.flush()

    def _determine_eligibility_path(self, shipment: Shipment) -> str:
        """Determine which eligibility path was used."""
        has_entry_summary = any(doc.document_type == ShipmentDocumentType.ENTRY_SUMMARY for doc in shipment.documents)
        has_commercial_invoice = any(doc.document_type == ShipmentDocumentType.COMMERCIAL_INVOICE for doc in shipment.documents)
        has_data_sheet = any(doc.document_type == ShipmentDocumentType.DATA_SHEET for doc in shipment.documents)
        
        if has_entry_summary:
            return "ENTRY_SUMMARY_ONLY"
        elif has_commercial_invoice and has_data_sheet:
            return "COMMERCIAL_INVOICE_AND_DATA_SHEET"
        else:
            return "UNKNOWN"

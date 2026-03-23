"""
Shipment Analysis Service - Sprint 12

Full analysis orchestration for shipments.
Integrates all engines: document processing, classification, duty, PSC, enrichment, regulatory.

This is the "truth payload" that the Celery task calls.
"""

import asyncio
import logging
import re
from typing import Dict, Any, List, Optional, Tuple
from uuid import UUID
from datetime import datetime
from pathlib import Path
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, and_

from app.models.shipment import Shipment, ShipmentStatus, ShipmentItem
from app.models.shipment_document import ShipmentDocument, ShipmentDocumentType
from app.models.review_record import ReviewRecord, ReviewStatus, ReviewableObjectType, ReviewReasonCode
from app.models.regulatory_evaluation import RegulatoryEvaluation, RegulatoryCondition, Regulator, RegulatoryOutcome, ConditionState
from app.engines.ingestion.document_processor import DocumentProcessor
from app.engines.classification.engine import ClassificationEngine
from app.engines.psc_radar import PSCRadar
from app.engines.regulatory_applicability import RegulatoryApplicabilityEngine
from scripts.duty_resolution import resolve_duty
from app.core.hts_constants import AUTHORITATIVE_HTS_VERSION_ID
from app.services.enrichment_integration_service import EnrichmentIntegrationService
from app.services.s3_upload_service import get_s3_client
from app.core.config import settings

logger = logging.getLogger(__name__)


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


class ShipmentAnalysisService:
    """Service for running full shipment analysis"""
    
    def __init__(self, db: AsyncSession):
        self.db = db
        self.document_processor = DocumentProcessor()
        self.classification_engine = ClassificationEngine(db)
        self.psc_radar = PSCRadar(db)
        self.regulatory_engine = RegulatoryApplicabilityEngine(db)
        self.enrichment_service = EnrichmentIntegrationService(db)
    
    async def run_full_shipment_analysis(
        self,
        shipment_id: UUID,
        organization_id: UUID,
        actor_user_id: UUID,
        clarification_responses: Optional[Dict[str, Dict[str, Any]]] = None,
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
        
        # Step 2: Parse PDFs and build evidence map
        doc_count = len(shipment.documents or [])
        logger.info("run_full_shipment_analysis: parsing %s document(s) for shipment %s", doc_count, shipment_id)
        evidence_map = await self._parse_documents_and_build_evidence_map(shipment)
        ev_docs = evidence_map.get("documents") or []
        ev_warnings = evidence_map.get("warnings") or []
        # #region agent log
        import json
        _log_path = "/Users/stevenbigio/Cursor Projects/NECO/logs/debug_analysis_aa7c8f.log"
        with open(_log_path, "a") as _f:
            _f.write(json.dumps({"sessionId":"aa7c8f","location":"shipment_analysis_service.py:parse_done","message":"Documents parsed","data":{"shipment_id":str(shipment_id),"doc_count":doc_count,"evidence_docs_count":len(ev_docs),"warnings_count":len(ev_warnings),"warnings_sample":[w.get("message","")[:80] for w in ev_warnings[:3]]},"hypothesisId":"H1","timestamp":int(__import__("time").time()*1000)}) + "\n")
        # #endregion
        logger.info("run_full_shipment_analysis: documents parsed (evidence_map has %s docs), importing line items", len(ev_docs))

        # Step 2b: Import line items from Entry Summary / Commercial Invoice if shipment has none
        try:
            await self._import_line_items_from_documents(shipment)
        except Exception as e:
            logger.warning(f"Line item import failed (non-fatal): {e}", exc_info=True)
        await self.db.refresh(shipment, ["items"])

        # #region agent log
        import json
        _log_path = "/Users/stevenbigio/Cursor Projects/NECO/logs/debug_analysis_aa7c8f.log"
        with open(_log_path, "a") as _f:
            _f.write(json.dumps({"sessionId":"aa7c8f","location":"shipment_analysis_service.py:after_import","message":"After line item import","data":{"shipment_id":str(shipment_id),"items_count":len(shipment.items or [])},"hypothesisId":"H6","timestamp":int(__import__("time").time()*1000)}) + "\n")
        # #endregion

        if settings.SPRINT12_FAST_ANALYSIS_DEV and settings.ENVIRONMENT.lower() in {"development", "dev", "local"}:
            logger.info("run_full_shipment_analysis: using fast local analysis for shipment %s (%s items)", shipment_id, len(shipment.items or []))
            result_json, review_snapshot, blockers = await self._build_fast_local_analysis(
                shipment=shipment,
                shipment_id=shipment_id,
                actor_user_id=actor_user_id,
                evidence_map=evidence_map,
            )
            logger.info("run_full_shipment_analysis: fast local analysis done for shipment %s", shipment_id)
            # #region agent log
            import json
            _log_path = "/Users/stevenbigio/Cursor Projects/NECO/logs/debug_analysis_aa7c8f.log"
            with open(_log_path, "a") as _f:
                _f.write(json.dumps({"sessionId":"aa7c8f","location":"shipment_analysis_service.py:fast_done","message":"Fast local analysis done","data":{"shipment_id":str(shipment_id),"items_count":len(result_json.get("items") or [])},"hypothesisId":"H6","timestamp":int(__import__("time").time()*1000)}) + "\n")
            # #endregion
            return result_json, review_snapshot, blockers
        
        # Step 3: Run existing engines
        logger.info("run_full_shipment_analysis: running classification/duty/PSC for shipment %s (%s items)", shipment_id, len(shipment.items or []))
        classification_results = {}
        duty_results = {}
        psc_results = {}
        enrichment_conflicts = []

        # Process each shipment item
        for item in shipment.items:
            item_id = str(item.id)
            
            # Classification engine
            if item.declared_hts:
                description = item.label or ""
                if getattr(item, "supplemental_evidence_text", None) and item.supplemental_evidence_text.strip():
                    description = f"{description}\n\nSupplemental evidence:\n{item.supplemental_evidence_text.strip()}"
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
                    classification_results[item_id] = classification_result
                except Exception as e:
                    logger.error(f"Classification engine error for item {item_id}: {e}")
                    classification_results[item_id] = {"error": str(e)}
            
            # Duty resolver
            hts_code = item.declared_hts or _get_hts_from_classification(classification_results.get(item_id))
            if hts_code:
                try:
                    resolved_duty = await resolve_duty(
                        hts_code,
                        db=self.db,
                        hts_version_id=AUTHORITATIVE_HTS_VERSION_ID
                    )
                    duty_results[item_id] = resolved_duty.to_dict() if resolved_duty else None
                except Exception as e:
                    logger.error(f"Duty resolution error for item {item_id}: {e}")
                    duty_results[item_id] = {"error": str(e)}
            
            # PSC Radar
            if hts_code and item.value:
                try:
                    psc_result = await self.psc_radar.analyze(
                        product_description=item.label or "",
                        declared_hts_code=hts_code,
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
        
        # Enrichment (check for conflicts)
        # TODO: Integrate enrichment service properly
        
        # Step 4: Run Side Sprint A regulatory evaluation
        regulatory_evaluations_data = []
        
        for item in shipment.items:
            hts_code = item.declared_hts or _get_hts_from_classification(classification_results.get(str(item.id)))
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
                logger.error(f"Regulatory evaluation error for item {item.id}: {e}")
        
        # Step 5: Create ReviewRecord snapshot
        review_snapshot = {
            "shipment_id": str(shipment_id),
            "analysis_id": None,  # Will be set after analysis creation
            "eligibility_path": self._determine_eligibility_path(shipment),
            "classification_outputs": classification_results,
            "duty_outputs": duty_results,
            "psc_outputs": psc_results,
            "enrichment_conflicts": enrichment_conflicts,
            "regulatory_evaluations": regulatory_evaluations_data,
            "document_ids": [str(doc.id) for doc in shipment.documents],
            "evidence_map": evidence_map,
            "created_at": datetime.utcnow().isoformat(),
            "created_by": str(actor_user_id)
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

        result_json = {
            "shipment_id": str(shipment_id),
            "items": [
                {
                    "id": str(item.id),
                    "label": item.label,
                    "value": float(item.value) if item.value is not None else None,
                    "hts_code": item.declared_hts or _get_hts_from_classification(classification_results.get(str(item.id))),
                    "classification": _enrich_classification(classification_results.get(str(item.id)), _get_primary_candidate),
                    "duty": duty_results.get(str(item.id)),
                    "psc": psc_results.get(str(item.id)),
                    "regulatory": [r for r in regulatory_evaluations_data if r["item_id"] == str(item.id)],
                    "supplemental_evidence_source": getattr(item, "supplemental_evidence_source", None),
                    "needs_supplemental_evidence": _item_needs_supplemental(classification_results.get(str(item.id))),
                }
                for item in shipment.items
            ],
            "evidence_map": evidence_map,
            "warnings": warnings,  # Top-level warnings for easy access
            "blockers": blockers,
            "review_status": review_status.value,
            "generated_at": datetime.utcnow().isoformat()
        }
        if not shipment.items and shipment.documents:
            files_not_found = evidence_map.get("files_not_found") or any(
                "not found" in str(w.get("message", "")).lower() or "file not found" in str(w.get("message", "")).lower()
                for w in evidence_map.get("warnings", [])
            )
            result_json["no_items_hint"] = "files_not_found" if files_not_found else "extraction_returned_no_lines"
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
        es_duty_by_line = self._get_es_duty_per_line(evidence_map)
        duty_total = sum((d.get("amount") or 0) for d in es_duty_by_line.values())
        
        items_preview = [
            {
                "label": getattr(i, "label", None) or f"Item {idx + 1}",
                "value": getattr(i, "value", None),
                "hts_code": getattr(i, "declared_hts", None),
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
    ) -> Tuple[Dict[str, Any], Dict[str, Any], List[str]]:
        """
        Build a deterministic lightweight analysis result in local/dev mode.
        Enriches with ES duty, origin mismatch, COO confirmation prompt, and PSC for high-duty items.
        """
        classification_results: Dict[str, Any] = {}
        duty_results: Dict[str, Any] = {}
        psc_results: Dict[str, Any] = {}
        enrichment_conflicts: List[str] = []
        regulatory_evaluations_data: List[Dict[str, Any]] = []
        blockers: List[str] = []

        review_snapshot = {
            "shipment_id": str(shipment_id),
            "analysis_id": None,
            "eligibility_path": self._determine_eligibility_path(shipment),
            "classification_outputs": classification_results,
            "duty_outputs": duty_results,
            "psc_outputs": psc_results,
            "enrichment_conflicts": enrichment_conflicts,
            "regulatory_evaluations": regulatory_evaluations_data,
            "document_ids": [str(doc.id) for doc in shipment.documents],
            "evidence_map": evidence_map,
            "created_at": datetime.utcnow().isoformat(),
            "created_by": str(actor_user_id),
            "mode": "FAST_LOCAL_DEV",
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

        items_payload: List[Dict[str, Any]] = []
        for idx, item in enumerate(shipment.items or []):
            line_idx = idx + 1
            duty_from_es = es_duty_by_line.get(line_idx) or es_duty_by_line.get(idx + 1)
            duty_amount = (duty_from_es or {}).get("amount") or 0
            sec301 = (duty_from_es or {}).get("section_301_amount")

            item_dict: Dict[str, Any] = {
                "id": str(item.id),
                "label": item.label,
                "hts_code": item.declared_hts,
                "classification": None,
                "duty": None,
                "psc": None,
                "regulatory": [],
                "supplemental_evidence_source": getattr(item, "supplemental_evidence_source", None),
                "needs_supplemental_evidence": False,
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
                    logger.warning(f"PSC Radar error in fast path for item {item.id}: {e}")

            items_payload.append(item_dict)

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
        }
        if coo_confirmation_prompt:
            result_json["coo_confirmation_prompt"] = coo_confirmation_prompt
        if origin_mismatches:
            result_json["origin_mismatches"] = origin_mismatches
        if no_items_hint:
            result_json["no_items_hint"] = no_items_hint

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
                        # #region agent log
                        import json
                        _log_path = "/Users/stevenbigio/Cursor Projects/NECO/logs/debug_analysis_aa7c8f.log"
                        with open(_log_path, "a") as _f:
                            _f.write(json.dumps({"sessionId":"aa7c8f","location":"shipment_analysis_service.py:file_not_found","message":"Document file not on disk","data":{"doc_id":str(doc.id),"filename":doc.filename,"s3_key":doc.s3_key,"tried_path":str(settings.MOCK_UPLOADS_DIR / safe_name)},"hypothesisId":"H1","timestamp":int(__import__("time").time()*1000)}) + "\n")
                        # #endregion
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
                            doc.structured_data = process_result.get("structured_data")
                            doc_evidence["extracted_text"] = process_result.get("extracted_text")
                            doc_evidence["structured_data"] = process_result.get("structured_data")
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
                            # Update document record with extracted data
                            doc.extracted_text = process_result.get("extracted_text")
                            doc.structured_data = process_result.get("structured_data")
                            
                            # Build evidence pointers
                            doc_evidence["extracted_text"] = process_result.get("extracted_text")
                            doc_evidence["structured_data"] = process_result.get("structured_data")
                            doc_evidence["page_count"] = process_result.get("metadata", {}).get("page_count", 0)
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

    async def _import_line_items_from_documents(self, shipment: Shipment) -> None:
        """
        Import line items from Entry Summary and Commercial Invoice into shipment.items.
        Only runs if shipment has no items. Prefers Entry Summary for HTS codes.
        """
        if shipment.items:
            return

        es_items: Dict[int, Dict[str, Any]] = {}
        ci_items: Dict[int, Dict[str, Any]] = {}

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
                if idx is None:
                    idx = i + 1
                try:
                    idx = int(idx) if idx is not None else i + 1
                except (TypeError, ValueError):
                    idx = i + 1

                if doc.document_type == ShipmentDocumentType.ENTRY_SUMMARY:
                    es_items[idx] = {
                        "description": li.get("description"),
                        "hts_code": li.get("hts_code"),
                        "country_of_origin": li.get("country_of_origin"),
                        "quantity": li.get("quantity"),
                        "unit": li.get("unit"),
                        "value": li.get("entered_value"),
                    }
                elif doc.document_type == ShipmentDocumentType.COMMERCIAL_INVOICE:
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

        # Merge: prefer ES for hts_code; use CI to supplement
        merged: Dict[int, Dict[str, Any]] = {}
        all_keys = set(es_items.keys()) | set(ci_items.keys())
        for k in sorted(all_keys):
            es = es_items.get(k, {})
            ci = ci_items.get(k, {})
            m = {
                "description": es.get("description") or ci.get("description") or f"Line {k}",
                "hts_code": es.get("hts_code") or ci.get("hts_code"),
                "country_of_origin": es.get("country_of_origin") or ci.get("country_of_origin"),
                "quantity": es.get("quantity") or ci.get("quantity"),
                "unit": es.get("unit") or ci.get("unit"),
                "value": es.get("value") or ci.get("value"),
            }
            merged[k] = m

        for k, m in sorted(merged.items()):
            label = m.get("description") or f"Line {k}"
            if not label or not isinstance(label, str):
                label = f"Line {k}"
            val = m.get("value")
            val_str = str(val) if val is not None else None
            qty = m.get("quantity")
            qty_str = str(qty) if qty is not None else None
            # Clean HTS: strip dots/spaces/dashes, keep first 10 digits
            raw_hts = str(m["hts_code"]) if m.get("hts_code") else None
            clean_hts = None
            if raw_hts:
                digits_only = re.sub(r"[^0-9]", "", raw_hts)
                clean_hts = digits_only[:10] if digits_only else None

            # Clean country: map full names to 2-letter ISO codes
            raw_coo = m.get("country_of_origin")
            coo = None
            if raw_coo:
                raw_coo_str = str(raw_coo).strip().upper()
                _coo_map = {
                    "CHINA": "CN", "CHINESE": "CN",
                    "UNITED STATES": "US", "USA": "US",
                    "VIETNAM": "VN", "VIET NAM": "VN",
                    "INDIA": "IN", "MEXICO": "MX", "TAIWAN": "TW",
                    "SOUTH KOREA": "KR", "KOREA": "KR",
                    "JAPAN": "JP", "GERMANY": "DE", "CANADA": "CA",
                }
                coo = _coo_map.get(raw_coo_str, raw_coo_str[:2])

            item = ShipmentItem(
                shipment_id=shipment.id,
                label=label[:255],
                declared_hts=clean_hts,
                value=val_str[:50] if val_str else None,
                quantity=qty_str[:50] if qty_str else None,
                unit_of_measure=str(m["unit"])[:20] if m.get("unit") else None,
                country_of_origin=coo,
            )
            self.db.add(item)
        if merged:
            await self.db.flush()
            logger.info(f"Imported {len(merged)} line items from documents for shipment {shipment.id}")
        else:
            logger.warning(
                "No line items imported for shipment %s: no document had structured_data.line_items (check document types and that files were processed)",
                shipment.id
            )

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

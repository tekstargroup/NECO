"""
Classification Engine

Generates alternative HTS codes for products using:
- Text similarity search against HTS tariff descriptions
- Scoring based on similarity, confidence, and duty rates
- Duty rate selection based on Country of Origin
"""

import logging
import os
import re
import time
from typing import Dict, Any, List, Optional, Tuple
from datetime import date
from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncSession

from app.engines.classification.context_builder import ClassificationContextBuilder
from app.engines.classification.product_analysis import ProductAnalyzer, serialize_analysis
from app.engines.classification.required_attributes import get_question_for_attribute, ProductFamily
from app.engines.classification.status_model import ClassificationStatus, determine_status
from app.engines.classification.synonym_expansion import expand_query_terms

logger = logging.getLogger(__name__)

# Trace flag for specific HTS code debugging
TRACE_HTS_CODE = os.getenv("TRACE_HTS_CODE", "").strip()

# Non-MFN countries (small list for now)
NON_MFN_COUNTRIES = {"KP", "CU"}  # North Korea, Cuba


class ClassificationEngine:
    """Classification engine for generating HTS code alternatives"""
    
    def __init__(self, db: AsyncSession):
        self.db = db
        self.context_builder = ClassificationContextBuilder(db)
        self.product_analyzer = ProductAnalyzer()
        self.engine_version = "v1.0"
    
    async def generate_alternatives(
        self,
        description: str,
        country_of_origin: Optional[str] = None,
        value: Optional[float] = None,
        quantity: Optional[float] = None,
        current_hts_code: Optional[str] = None,
        sku_id: Optional[str] = None,
        client_id: Optional[str] = None,
        clarification_responses: Optional[Dict[str, Any]] = None
    ) -> Dict[str, Any]:
        """
        Generate alternative HTS codes for a product.
        
        Args:
            description: Product description
            country_of_origin: 2-letter country code (e.g., "CN", "MX")
            value: Product value (optional)
            quantity: Product quantity (optional)
            current_hts_code: Current HTS code if known (optional)
            sku_id: SKU ID if available (optional)
            client_id: Client ID (optional)
            clarification_responses: Dict of attribute -> value from user clarification
        
        Returns:
            Dictionary with candidates, scores, and metadata, or CLARIFICATION_REQUIRED status
        """
        start_time = time.time()
        
        try:
            # STEP 1: Product Analysis (NO HTS SUGGESTION)
            product_analysis = await self.product_analyzer.analyze(
                description=description,
                country_of_origin=country_of_origin
            )
            
            # Merge clarification responses if provided
            if clarification_responses:
                for attr, value in clarification_responses.items():
                    if attr in product_analysis.extracted_attributes:
                        # Update existing attribute
                        product_analysis.extracted_attributes[attr].value = value
                        product_analysis.extracted_attributes[attr].source_tokens = ["user_clarification"]
                        product_analysis.extracted_attributes[attr].confidence = 1.0
                    else:
                        # Add new attribute from clarification
                        from app.engines.classification.product_analysis import ExtractedAttribute
                        product_analysis.extracted_attributes[attr] = ExtractedAttribute(
                            value=value,
                            source_tokens=["user_clarification"],
                            confidence=1.0
                        )
                
                # Recompute missing required attributes after merging clarification responses
                from app.engines.classification.required_attributes import (
                    get_required_attributes,
                    identify_product_family
                )
                # Update product family if needed (shouldn't change, but recompute to be safe)
                product_family = identify_product_family(description, {
                    attr: ext_attr.value
                    for attr, ext_attr in product_analysis.extracted_attributes.items()
                })
                product_analysis.product_family = product_family  # Update in case it changed
                required_attrs = get_required_attributes(product_family)
                product_analysis.missing_required_attributes = [
                    attr for attr in required_attrs
                    if attr not in product_analysis.extracted_attributes or 
                       product_analysis.extracted_attributes[attr].value is None or
                       product_analysis.extracted_attributes[attr].value == ""
                ]
                
                # Recompute analysis_confidence after merging clarification responses
                # Confidence should increase when user provides clarification
                resolved_count = len(required_attrs) - len(product_analysis.missing_required_attributes)
                product_analysis.analysis_confidence = max(
                    product_analysis.analysis_confidence,
                    resolved_count / len(required_attrs) if required_attrs else 0.0
                )
                
                # Recompute suggested chapters after clarification (may have changed)
                from app.engines.classification.chapter_clusters import get_chapter_numbers
                suggested_chapter_nums = get_chapter_numbers(product_family.value)
                product_analysis.suggested_chapters = [
                    {"chapter": ch, "confidence": product_analysis.analysis_confidence, "reason": "From clarification responses"}
                    for ch in suggested_chapter_nums[:3]  # Cap at 3 as per requirements
                ]
                
                logger.info(
                    f"Clarification responses merged: {list(clarification_responses.keys())}. "
                    f"Missing required attributes: {product_analysis.missing_required_attributes}. "
                    f"Analysis confidence: {product_analysis.analysis_confidence:.2f}"
                )
            
            # STEP 2: Check if clarification is required
            # CRITICAL: This must happen BEFORE any candidate retrieval or scoring
            # If missing_required_attributes exists, return immediately and do NOT proceed
            missing_required = product_analysis.missing_required_attributes
            
            # Debug logging for product family and required attributes
            detected_family = product_analysis.product_family.value
            from app.engines.classification.required_attributes import get_required_attributes
            required_attrs_list = get_required_attributes(product_analysis.product_family)
            required_attrs_count = len(required_attrs_list)
            
            logger.info(
                f"Product analysis: family={detected_family}, "
                f"required_attributes_count={required_attrs_count}, "
                f"missing_required={len(missing_required)}, "
                f"missing_attrs={missing_required}"
            )
            
            # CRITICAL SHORT-CIRCUIT: If missing_required_attributes is non-empty,
            # return immediately and DO NOT proceed to candidate retrieval or scoring
            if missing_required:
                logger.info(
                    f"CLARIFICATION_REQUIRED: {len(missing_required)} missing attributes. "
                    f"SHORT-CIRCUITING - will NOT call candidate retrieval or scoring."
                )
                # CLARIFICATION_REQUIRED - Do NOT run classification
                # ABSOLUTELY DO NOT CALL candidate retrieval or scoring in this branch
                
                # Order questions by impact on chapter selection (Workstream C)
                missing_attrs_ordered = self._order_questions_by_chapter_impact(
                    missing_required,
                    product_analysis.product_family
                )
                # Limit to top 3 highest-impact questions (but always include at least all missing if <= 3)
                missing_attrs = missing_attrs_ordered[:3] if len(missing_attrs_ordered) > 3 else missing_attrs_ordered
                
                # Build questions list - MUST be non-empty when missing_required is non-empty
                questions = []
                for attr in missing_attrs:
                    question_text = get_question_for_attribute(attr)
                    question_obj = {
                        "attribute": attr,
                        "question": question_text
                    }
                    # Add value options if attribute expects an enum (from attribute map)
                    from app.engines.classification.attribute_maps import get_attribute_map
                    attr_map = get_attribute_map(product_analysis.product_family)
                    attr_requirements = attr_map.get("required_attributes", [])
                    for req in attr_requirements:
                        if req.attribute_name == attr and req.value_options:
                            question_obj["value_options"] = req.value_options
                            break
                    questions.append(question_obj)
                
                # Workstream 4.2-C: Invariant CHECK - CLARIFICATION_REQUIRED must have questions
                if not questions:
                    logger.error(
                        f"CRITICAL BUG: missing_required={missing_required} but questions list is empty. "
                        f"This violates CLARIFICATION_REQUIRED semantics and Workstream 4.2-C invariant."
                    )
                    # Fallback: create questions from all missing attributes
                    questions = [
                        {
                            "attribute": attr,
                            "question": get_question_for_attribute(attr)
                        }
                        for attr in missing_required[:3]
                    ]
                
                # Workstream 4.2-C: Invariant CHECK - question.attribute keys must match missing_required_attributes keys
                question_attrs = {q["attribute"] for q in questions}
                missing_set = set(missing_attrs)
                if not question_attrs.issubset(missing_set):
                    logger.error(
                        f"CRITICAL BUG: Key mismatch - question attributes {question_attrs} not subset of missing {missing_set}. "
                        f"This violates Workstream 4.2-C invariant."
                    )
                    # Fix by ensuring questions only contain missing attributes
                    questions = [
                        q for q in questions if q["attribute"] in missing_set
                    ]
                    # Add any missing attributes that don't have questions
                    for attr in missing_set:
                        if not any(q["attribute"] == attr for q in questions):
                            questions.append({
                                "attribute": attr,
                                "question": get_question_for_attribute(attr)
                            })
                
                # Workstream 4.2-C: Final invariant validation before return
                if not questions:
                    raise RuntimeError(
                        f"CRITICAL INVARIANT VIOLATION: CLARIFICATION_REQUIRED status but questions list is empty. "
                        f"missing_required={missing_required}. This should never happen."
                    )
                
                processing_time_ms = int((time.time() - start_time) * 1000)
                
                # CRITICAL: Status must never be None - validate it
                status_value = ClassificationStatus.CLARIFICATION_REQUIRED.value
                reason_code = "MISSING_REQUIRED_ATTRIBUTES"  # REQUIRED - must not be None
                
                logger.info(
                    f"CLARIFICATION_REQUIRED: Missing attributes {missing_required}. "
                    f"Returning immediately without candidate retrieval or scoring. "
                    f"Questions: {len(questions)}, reason_code: {reason_code}"
                )
                
                return {
                    "success": False,
                    "status": status_value,  # REQUIRED - must not be None
                    "error": "CLARIFICATION_REQUIRED",
                    "error_reason": f"Required classification attributes missing: {', '.join(missing_required)}",
                    "questions": questions,  # MUST be non-empty when missing_required is non-empty
                    "blocking_reason": f"Required classification attributes missing: {', '.join(missing_required)}",
                    "product_analysis": serialize_analysis(product_analysis),
                    "candidates": [],  # No candidates when clarification required
                    "metadata": {
                        "engine_version": self.engine_version,
                        "processing_time_ms": processing_time_ms,
                        "reason_code": reason_code,  # REQUIRED - must not be None
                        "missing_required_attributes": missing_required,
                        "clarification_responses_provided": list(clarification_responses.keys()) if clarification_responses else [],
                        "suggested_chapters": product_analysis.suggested_chapters,
                        "detected_product_family": detected_family,
                        "required_attribute_map_key_used": detected_family,
                        "required_attributes_count": required_attrs_count,
                        "product_analysis": serialize_analysis(product_analysis)
                    }
                }
            
            # STEP 3: Classification can proceed - use suggested chapters to narrow retrieval
            # CRITICAL: This code should NEVER be reached if missing_required_attributes is non-empty
            # The check above should have returned CLARIFICATION_REQUIRED already
            
            # Safety check: If we somehow reach here with missing attributes, fail fast
            if product_analysis.missing_required_attributes:
                raise RuntimeError(
                    f"CRITICAL BUG: Reached candidate retrieval with missing_required_attributes={product_analysis.missing_required_attributes}. "
                    f"This code path should be unreachable. Clarification short-circuit failed."
                )
            
            # Extract suggested chapter numbers for filtering (Workstream D)
            suggested_chapter_numbers = [
                ch["chapter"] for ch in product_analysis.suggested_chapters
                if ch.get("confidence", 0) >= 0.7  # Only use high-confidence suggestions
            ]
            
            # Workstream D: Enforce retrieval constraints
            # Candidate retrieval must be constrained to suggested chapters first
            # Only expand beyond those chapters if analysis_confidence is low and expansion is explicitly logged
            expand_beyond_suggested = False
            if product_analysis.analysis_confidence < 0.5 and not suggested_chapter_numbers:
                # Low confidence and no suggestions - allow expansion but log it
                expand_beyond_suggested = True
                logger.warning(
                    f"Low analysis confidence ({product_analysis.analysis_confidence:.2f}) and no suggested chapters. "
                    f"Expanding retrieval beyond suggested chapters. This expansion is logged for audit."
                )
            
            # 1. Generate candidates (returns candidates and filter counts)
            # CRITICAL: This should only be called if missing_required_attributes is empty
            logger.info("Proceeding to candidate retrieval (all required attributes resolved)")
            candidate_result = await self._generate_candidates(
                description,
                suggested_chapters=suggested_chapter_numbers if not expand_beyond_suggested else None,
                expansion_logged=expand_beyond_suggested,
                product_family=product_analysis.product_family
            )
            candidates = candidate_result["candidates"]
            pre_filter_count = candidate_result.get("pre_filter_count", len(candidates))
            post_filter_count = candidate_result.get("post_filter_count", len(candidates))
            noisy_excluded = candidate_result.get("noisy_excluded", 0)
            noise_ratio = candidate_result.get("noise_ratio", 0.0)
            noise_filter_suspended = candidate_result.get("noise_filter_suspended", False)
            expanded_terms = candidate_result.get("expanded_terms", [])
            gating_mode = candidate_result.get("gating_mode")
            headings_used = candidate_result.get("headings_used", [])
            primary_count = candidate_result.get("primary_count", 0)  # Stage 1: 8518 only
            expanded_count = candidate_result.get("expanded_count", 0)  # Stage 2: expanded
            
            if not candidates:
                # CRITICAL: Status must never be None
                return {
                    "success": False,
                    "status": ClassificationStatus.NO_CONFIDENT_MATCH.value,
                    "error": "No candidates found",
                    "candidates": [],
                    "metadata": {
                        "engine_version": self.engine_version,
                        "processing_time_ms": int((time.time() - start_time) * 1000),
                        "product_analysis": serialize_analysis(product_analysis)
                    }
                }
            
            # 2. Score candidates
            scored_candidates = await self._score_candidates(
                candidates,
                description,
                country_of_origin,
                current_hts_code,
                product_family=product_analysis.product_family,
                product_analysis=product_analysis  # Workstream 4.1-A: Pass product_analysis for subheading priors
            )
            
            # TRACE: Scoring and truncation
            if TRACE_HTS_CODE:
                for i, candidate in enumerate(scored_candidates):
                    if candidate.get("hts_code") == TRACE_HTS_CODE:
                        logger.info(
                            f"[TRACE {TRACE_HTS_CODE}] D) Scoring: "
                            f"similarity_used_in_scoring={candidate.get('similarity_score', 0.0):.6f}, "
                            f"final_score={candidate.get('final_score', 0.0):.6f}, "
                            f"rank_position_before_cutoff={i+1}"
                        )
                        break
                else:
                    # Check if it was in candidates but dropped during scoring
                    for candidate in candidates:
                        if candidate.get("hts_code") == TRACE_HTS_CODE:
                            logger.warning(
                                f"[TRACE {TRACE_HTS_CODE}] D) Scoring: "
                                f"CANDIDATE DROPPED during scoring (was in candidates list)"
                            )
                            break
            
            # TRACE: Check if candidate was dropped due to top_k truncation
            if TRACE_HTS_CODE:
                trace_found_in_top10 = any(c.get("hts_code") == TRACE_HTS_CODE for c in scored_candidates[:10])
                trace_found_in_all = any(c.get("hts_code") == TRACE_HTS_CODE for c in scored_candidates)
                if trace_found_in_all and not trace_found_in_top10:
                    trace_position = next((i for i, c in enumerate(scored_candidates) if c.get("hts_code") == TRACE_HTS_CODE), -1)
                    logger.warning(
                        f"[TRACE {TRACE_HTS_CODE}] D) Truncation: "
                        f"DROPPED due to top_10 cutoff, was at position {trace_position+1} "
                        f"(final_score={scored_candidates[trace_position].get('final_score', 0.0):.6f})"
                    )
                elif trace_found_in_top10:
                    trace_position = next((i for i, c in enumerate(scored_candidates[:10]) if c.get("hts_code") == TRACE_HTS_CODE), -1)
                    logger.info(
                        f"[TRACE {TRACE_HTS_CODE}] D) Truncation: "
                        f"survived top_10 cutoff, position={trace_position+1}"
                    )
            
            # 3. Re-rank to top 5, then final 3-5
            top_10 = sorted(scored_candidates, key=lambda x: x["final_score"], reverse=True)[:10]
            
            # TRACE: Check top_5 truncation
            if TRACE_HTS_CODE:
                trace_found_in_top5 = any(c.get("hts_code") == TRACE_HTS_CODE for c in top_10[:5])
                trace_found_in_top10_list = any(c.get("hts_code") == TRACE_HTS_CODE for c in top_10)
                if trace_found_in_top10_list and not trace_found_in_top5:
                    trace_position = next((i for i, c in enumerate(top_10) if c.get("hts_code") == TRACE_HTS_CODE), -1)
                    logger.warning(
                        f"[TRACE {TRACE_HTS_CODE}] D) Truncation: "
                        f"DROPPED due to top_5 cutoff, was at position {trace_position+1} in top_10 "
                        f"(final_score={top_10[trace_position].get('final_score', 0.0):.6f})"
                    )
                elif trace_found_in_top5:
                    trace_position = next((i for i, c in enumerate(top_10[:5]) if c.get("hts_code") == TRACE_HTS_CODE), -1)
                    logger.info(
                        f"[TRACE {TRACE_HTS_CODE}] D) Truncation: "
                        f"survived top_5 cutoff, position={trace_position+1}"
                    )
            
            final_candidates = sorted(top_10, key=lambda x: x["final_score"], reverse=True)[:5]
            
            post_score_count = len(final_candidates)
            
            # Serialize product analysis for metadata
            analysis_metadata = serialize_analysis(product_analysis)
            
            # 3a. Chapter sanity check - validate expected chapters based on product type
            # This is a deterministic check to catch obviously wrong matches
            expected_chapters = self._get_expected_chapters(description)
            if expected_chapters:
                filtered_candidates = []
                for candidate in final_candidates:
                    candidate_chapter = candidate.get("hts_chapter", "")
                    if candidate_chapter in expected_chapters:
                        filtered_candidates.append(candidate)
                    else:
                        logger.warning(
                            f"Chapter sanity check: Candidate {candidate['hts_code']} (Ch. {candidate_chapter}) "
                            f"does not match expected chapters {expected_chapters} for description: '{description[:60]}...'"
                        )
                
                if filtered_candidates:
                    final_candidates = filtered_candidates
                    logger.info(
                        f"Chapter sanity check: Filtered to {len(final_candidates)} candidates matching expected chapters {expected_chapters}"
                    )
                else:
                    logger.warning(
                        f"Chapter sanity check: No candidates matched expected chapters {expected_chapters}, "
                        f"but proceeding with original candidates to avoid false negatives"
                    )
            
            # STEP 4: Fix similarity metric consistency - use max from FINAL candidates
            best_similarity = max([c.get("similarity_score", 0.0) for c in final_candidates]) if final_candidates else 0.0
            top_score = final_candidates[0]["final_score"] if final_candidates else 0.0
            
            # STEP 2: Family-aware similarity gating for audio_devices (after clarification)
            best_8518_similarity = 0.0
            product_family_str = product_analysis.product_family.value if isinstance(product_analysis.product_family, ProductFamily) else (product_analysis.product_family if product_analysis.product_family else None)
            if product_family_str == "audio_devices" and clarification_responses:
                # After clarification, check if any 8518 candidates exist
                candidates_8518 = [c for c in final_candidates if c.get("hts_code", "").startswith("8518")]
                if candidates_8518:
                    best_8518_similarity = max([c.get("similarity_score", 0.0) for c in candidates_8518])
                    logger.info(
                        f"Family-aware gating: audio_devices with clarification, "
                        f"best_8518_similarity={best_8518_similarity:.6f}, "
                        f"8518_count={len(candidates_8518)}"
                    )
            
            # STEP 2: Gate A - Family-aware status determination
            status = None
            reason_code = None
            if product_family_str == "audio_devices" and clarification_responses and best_8518_similarity >= 0.16:
                # Gate A: If audio_devices with clarification and best_8518_similarity >= 0.16, use REVIEW_REQUIRED
                status = ClassificationStatus.REVIEW_REQUIRED
                reason_code = "FAMILY_AWARE_GATE_8518"
                logger.info(
                    f"Family-aware gate PASSED: audio_devices with clarification, "
                    f"best_8518_similarity={best_8518_similarity:.6f} >= 0.16, "
                    f"status=REVIEW_REQUIRED (not NO_CONFIDENT_MATCH)"
                )
            else:
                # Determine status using standard criteria
                status = determine_status(
                    missing_required_attributes=product_analysis.missing_required_attributes,
                    best_similarity=best_similarity,
                    top_candidate_score=top_score,
                    analysis_confidence=product_analysis.analysis_confidence,
                    candidates_exist=len(final_candidates) > 0
                )
                reason_code = "STANDARD_GATE" if status != ClassificationStatus.NO_CONFIDENT_MATCH else "LOW_SIMILARITY_GATE"
            
            # Handle NO_CONFIDENT_MATCH
            if status == ClassificationStatus.NO_CONFIDENT_MATCH:
                processing_time_ms = int((time.time() - start_time) * 1000)
                logger.warning(
                    f"Confidence gate FAILED: Best similarity {best_similarity:.4f} < 0.18 threshold. "
                    f"Description: '{description[:60]}...'"
                )
                # Return top 5 candidates with full explainability
                untrusted_candidates = []
                for candidate in final_candidates[:5]:
                    score_components = candidate.get("score_components", {})
                    untrusted_candidates.append({
                        "hts_code": candidate["hts_code"],
                        "hts_chapter": candidate["hts_chapter"],
                        "tariff_text_short": candidate.get("tariff_text_short", "")[:100],
                        "similarity_score": candidate.get("similarity_score", 0.0),
                        "final_score": candidate.get("final_score", 0.0),
                        "score_components": {
                            "similarity_raw": score_components.get("similarity_raw", 0.0),
                            "similarity_contribution": score_components.get("similarity_contribution", 0.0),
                            "confidence_penalty": score_components.get("confidence_penalty", 0.0),
                            "duty_penalty": score_components.get("duty_penalty", 0.0),
                            "special_bonus": score_components.get("special_bonus", 0.0),
                            "hts_match_bonus": score_components.get("hts_match_bonus", 0.0)
                        },
                        "duty_rate_general": candidate.get("duty_rate_general"),
                        "duty_rate_special": candidate.get("duty_rate_special"),
                        "duty_rate_column2": candidate.get("duty_rate_column2"),
                        "selected_rate_type": candidate.get("selected_rate_type"),
                        "selected_rate": candidate.get("selected_rate")
                    })
                
                return {
                    "success": False,
                    "status": status.value,
                    "error": "NO_CONFIDENT_MATCH",
                    "error_reason": f"Best similarity {best_similarity:.4f} below confidence threshold (0.18). No confident match available.",
                    "candidates": untrusted_candidates,  # Top 5 with full explainability
                    "metadata": {
                        "engine_version": self.engine_version,
                        "processing_time_ms": processing_time_ms,
                        "total_candidates_found": len(candidates),
                        "pre_filter_count": pre_filter_count,
                        "post_filter_count": post_filter_count,
                        "post_score_count": post_score_count,
                        "best_similarity": best_similarity,
                        "best_8518_similarity": best_8518_similarity if best_8518_similarity > 0 else None,
                        "threshold_used": "FAMILY_AWARE_0.16" if best_8518_similarity >= 0.16 else "0.18",
                        "reason_code": reason_code if reason_code else "LOW_SIMILARITY_GATE",
                        "applied_filters": ["exclude_9903_text", "exclude_ch98_99", "exclude_noisy_desc"],
                        "applied_priors": self._collect_applied_priors(final_candidates) if final_candidates else [],  # Workstream 4.1-A
                        "noisy_excluded": candidate_result.get("noisy_excluded", 0),
                        "noise_ratio": candidate_result.get("noise_ratio", 0.0),
                        "noise_filter_suspended": candidate_result.get("noise_filter_suspended", False),
                        "expanded_terms": candidate_result.get("expanded_terms", []),
                        "gating_mode": gating_mode,
                        "headings_used": headings_used,
                        "candidate_counts": {
                            "pre_filter": pre_filter_count,
                            "post_filter": post_filter_count,
                            "post_score": post_score_count,
                            "primary_8518": primary_count,
                            "expanded": expanded_count
                        },
                        "product_analysis": analysis_metadata
                    }
                }
            
            # Handle REVIEW_REQUIRED
            if status == ClassificationStatus.REVIEW_REQUIRED:
                processing_time_ms = int((time.time() - start_time) * 1000)
                ambiguity_reason = []
                if best_similarity >= 0.18 and best_similarity < 0.25:
                    ambiguity_reason.append(f"Best similarity {best_similarity:.4f} is below strong confidence threshold (0.25)")
                if product_analysis.analysis_confidence < 0.7:
                    ambiguity_reason.append(f"Analysis confidence {product_analysis.analysis_confidence:.2f} is below threshold (0.7)")
                
                # Workstream 4.2-B: Generate review explanation
                from app.engines.classification.review_explanation import generate_review_explanation
                review_explanation = generate_review_explanation(
                    status=status,
                    best_similarity=best_similarity,
                    top_candidate_score=top_score,
                    analysis_confidence=product_analysis.analysis_confidence,
                    product_family=product_family_str,
                    candidates=final_candidates,
                    reason_code=reason_code,
                    best_8518_similarity=best_8518_similarity if best_8518_similarity > 0 else None,
                    missing_required_attributes=product_analysis.missing_required_attributes,
                    ambiguity_reason=ambiguity_reason
                )
                
                # Workstream 4.2-C: Invariant validation - REVIEW_REQUIRED must have explanation
                if not review_explanation.get("primary_reasons"):
                    logger.error(
                        "CRITICAL BUG: REVIEW_REQUIRED status but review_explanation.primary_reasons is empty. "
                        "This violates Workstream 4.2-C invariant."
                    )
                    review_explanation["primary_reasons"] = [
                        "Classification requires review - specific reason logging unavailable"
                    ]
                if not review_explanation.get("what_would_increase_confidence"):
                    logger.error(
                        "CRITICAL BUG: REVIEW_REQUIRED status but review_explanation.what_would_increase_confidence is empty. "
                        "This violates Workstream 4.2-C invariant."
                    )
                    review_explanation["what_would_increase_confidence"] = [
                        "Provide additional product details to increase classification confidence"
                    ]
                
                return {
                    "success": True,  # Candidates exist but need review
                    "status": status.value,
                    "candidates": final_candidates[:5],  # Workstream 4.1-B: display_text already set for medical
                    "review_explanation": review_explanation,  # Workstream 4.2-B
                    "metadata": {
                        "engine_version": self.engine_version,
                        "processing_time_ms": processing_time_ms,
                        "total_candidates_found": len(candidates),
                        "pre_filter_count": pre_filter_count,
                        "post_filter_count": post_filter_count,
                        "post_score_count": post_score_count,
                        "best_similarity": best_similarity,
                        "best_8518_similarity": best_8518_similarity if best_8518_similarity > 0 else None,
                        "top_candidate_score": top_score,
                        "analysis_confidence": product_analysis.analysis_confidence,
                        "ambiguity_reason": "; ".join(ambiguity_reason) if ambiguity_reason else "Multiple plausible candidates",
                        "applied_filters": ["exclude_9903_text", "exclude_ch98_99", "exclude_noisy_desc"],
                        "applied_priors": self._collect_applied_priors(final_candidates),  # Workstream 4.1-A
                        "noisy_excluded": noisy_excluded,
                        "noise_ratio": noise_ratio,
                        "noise_filter_suspended": noise_filter_suspended,
                        "expanded_terms": expanded_terms,
                        "gating_mode": gating_mode,
                        "headings_used": headings_used,
                        "candidate_counts": {
                            "pre_filter": pre_filter_count,
                            "post_filter": post_filter_count,
                            "post_score": post_score_count,
                            "primary_8518": primary_count,
                            "expanded": expanded_count
                        },
                        "threshold_used": "FAMILY_AWARE_0.16" if best_8518_similarity >= 0.16 else "0.18",
                        "reason_code": reason_code if reason_code else "REVIEW_REQUIRED",
                        "product_analysis": analysis_metadata
                    }
                }
            
            # Quality gate: if top score < 0.20, reject all candidates
            # This prevents persistence of low-quality matches
            # Note: Status determination happens above, this is just for quality gating
            if top_score < 0.20:
                processing_time_ms = int((time.time() - start_time) * 1000)
                logger.warning(
                    f"Quality gate FAILED: Top candidate score {top_score:.4f} < 0.20 threshold. "
                    f"Description: '{description[:60]}...', "
                    f"Top candidate: {final_candidates[0]['hts_code'] if final_candidates else 'N/A'} "
                    f"(Ch. {final_candidates[0]['hts_chapter'] if final_candidates else 'N/A'})"
                )
                return {
                    "success": False,
                    "status": "NO_GOOD_MATCH",
                    "error": "NO_GOOD_MATCH",
                    "error_reason": f"Top candidate score {top_score:.4f} below quality threshold (0.20). No alternatives will be persisted.",
                    "candidates": final_candidates[:5] if final_candidates else [],  # Return top 5 for review
                    "metadata": {
                        "engine_version": self.engine_version,
                        "processing_time_ms": processing_time_ms,
                        "total_candidates_found": len(candidates),
                        "pre_filter_count": pre_filter_count,
                        "post_filter_count": post_filter_count,
                        "post_score_count": post_score_count,
                        "top_candidate_score": f"{top_score:.4f}",
                        "best_similarity": best_similarity_for_gate,
                        "quality_gate_failed": True,
                        "quality_gate_threshold": 0.20,
                        "threshold_used": "0.20",
                        "reason_code": "QUALITY_GATE_FAILED",
                    "applied_filters": ["exclude_9903_text", "exclude_ch98_99", "exclude_noisy_desc"],
                    "noisy_excluded": noisy_excluded,
                    "noise_ratio": noise_ratio,
                    "product_analysis": analysis_metadata
                    }
                }
            
            # 4. Select duty rates for each candidate
            for candidate in final_candidates:
                duty_info = self._select_duty_rate(
                    candidate,
                    country_of_origin
                )
                candidate.update(duty_info)
            
            # Workstream 4.1-B: Clean medical candidate display text
            product_family_str = product_analysis.product_family.value if isinstance(product_analysis.product_family, ProductFamily) else (product_analysis.product_family if product_analysis.product_family else None)
            if product_family_str == "medical_devices":
                from app.engines.classification.text_cleanup import clean_medical_candidate_text
                for candidate in final_candidates:
                    cleaned_text = clean_medical_candidate_text(
                        tariff_text_short=candidate.get("tariff_text_short"),
                        tariff_text=candidate.get("tariff_text"),
                        hts_code=candidate.get("hts_code", "")
                    )
                    # Add cleaned display text (keep original for similarity)
                    candidate["display_text"] = cleaned_text
                    logger.debug(f"Medical candidate {candidate.get('hts_code')}: cleaned display_text={cleaned_text[:80]}...")
            
            # 5. Build context for top candidate
            top_candidate = final_candidates[0] if final_candidates else None
            context_payload = None
            provenance = {
                "source_pages": [],
                "code_ids": []
            }
            
            if top_candidate:
                context_payload = await self.context_builder.build_context(
                    top_candidate["hts_code"]
                )
                provenance["source_pages"] = [top_candidate.get("source_page")]
                provenance["code_ids"] = [top_candidate.get("hts_code")]
            
            processing_time_ms = int((time.time() - start_time) * 1000)
            
            # Final status check for SUCCESS (Workstream E)
            # SUCCESS requires: all attributes resolved, high similarity, high score, high confidence
            final_status = determine_status(
                missing_required_attributes=product_analysis.missing_required_attributes,
                best_similarity=best_similarity,
                top_candidate_score=top_score,
                analysis_confidence=product_analysis.analysis_confidence,
                candidates_exist=len(final_candidates) > 0
            )
            
            # Workstream 4.2-C: Invariant validation - SUCCESS must not have missing required attributes
            if final_status == ClassificationStatus.SUCCESS and product_analysis.missing_required_attributes:
                logger.error(
                    f"CRITICAL BUG: SUCCESS status but missing_required_attributes={product_analysis.missing_required_attributes}. "
                    f"This violates Workstream 4.2-C invariant. Forcing REVIEW_REQUIRED."
                )
                final_status = ClassificationStatus.REVIEW_REQUIRED
            
            # Workstream 4.2-B: If status is REVIEW_REQUIRED, generate explanation
            review_explanation = None
            if final_status == ClassificationStatus.REVIEW_REQUIRED:
                from app.engines.classification.review_explanation import generate_review_explanation
                review_explanation = generate_review_explanation(
                    status=final_status,
                    best_similarity=best_similarity,
                    top_candidate_score=top_score,
                    analysis_confidence=product_analysis.analysis_confidence,
                    product_family=product_family_str,
                    candidates=final_candidates,
                    reason_code=reason_code if reason_code else "SUCCESS_FALLBACK",
                    best_8518_similarity=best_8518_similarity if best_8518_similarity > 0 else None,
                    missing_required_attributes=product_analysis.missing_required_attributes,
                    ambiguity_reason=None
                )
                # Workstream 4.2-C: Validate explanation exists
                if not review_explanation.get("primary_reasons") or not review_explanation.get("what_would_increase_confidence"):
                    logger.error(
                        "CRITICAL BUG: REVIEW_REQUIRED status but review_explanation is incomplete. "
                        "This violates Workstream 4.2-C invariant."
                    )
            
            return {
                "success": final_status == ClassificationStatus.SUCCESS,
                "status": final_status.value,
                "candidates": final_candidates,
                "review_explanation": review_explanation,  # Workstream 4.2-B (None if SUCCESS)
                "metadata": {
                    "engine_version": self.engine_version,
                    "processing_time_ms": processing_time_ms,
                    "total_candidates_found": len(candidates),
                    "pre_filter_count": pre_filter_count,
                    "post_filter_count": post_filter_count,
                    "post_score_count": post_score_count,
                    "top_candidate_hts": top_candidate["hts_code"] if top_candidate else None,
                    "top_candidate_score": top_candidate["final_score"] if top_candidate else 0.0,
                    "best_similarity": best_similarity,
                    "best_8518_similarity": best_8518_similarity if best_8518_similarity > 0 else None,
                    "analysis_confidence": product_analysis.analysis_confidence,
                    "applied_filters": ["exclude_9903_text", "exclude_ch98_99", "exclude_noisy_desc"],
                    "applied_priors": self._collect_applied_priors(final_candidates),  # Workstream 4.1-A
                    "noisy_excluded": noisy_excluded,
                    "noise_ratio": noise_ratio,
                    "candidate_counts": {
                        "pre_filter": pre_filter_count,
                        "post_filter": post_filter_count,
                        "post_score": post_score_count,
                        "primary_8518": primary_count,
                        "expanded": expanded_count
                    },
                    "threshold_used": "FAMILY_AWARE_0.16" if best_8518_similarity >= 0.16 else "0.18",
                    "reason_code": reason_code if reason_code else "SUCCESS",
                    "product_analysis": analysis_metadata
                },
                "context_payload": context_payload,
                "provenance": provenance
            }
        
        except Exception as e:
            logger.error(f"Error generating alternatives: {e}", exc_info=True)
            # CRITICAL: Even in error case, status must not be None
            return {
                "success": False,
                "status": ClassificationStatus.NO_CONFIDENT_MATCH.value,  # Default error status
                "error": str(e),
                "candidates": [],
                "metadata": {
                    "engine_version": self.engine_version,
                    "processing_time_ms": int((time.time() - start_time) * 1000)
                }
            }
    
    def _collect_applied_priors(self, candidates: List[Dict]) -> List[str]:
        """
        Collect all applied priors from candidates for audit.
        
        Workstream 4.1-A: Track subheading priors for explainability.
        """
        applied_priors_set = set()
        for candidate in candidates:
            priors = candidate.get("_applied_priors", [])
            if priors:
                applied_priors_set.update(priors)
        return sorted(list(applied_priors_set))
    
    def _order_questions_by_chapter_impact(
        self,
        missing_attrs: List[str],
        product_family: ProductFamily
    ) -> List[str]:
        """
        Order questions by impact on chapter selection (Workstream C).
        
        Attributes that directly influence chapter selection come first.
        """
        from app.engines.classification.attribute_maps import get_required_attributes_with_rationale
        
        # Get attribute requirements with chapter influence
        attr_requirements = get_required_attributes_with_rationale(product_family)
        
        # Create priority map: attributes with more chapter influences get higher priority
        priority_map = {}
        for req in attr_requirements:
            if req.attribute_name in missing_attrs:
                # Priority = number of chapters influenced
                priority_map[req.attribute_name] = len(req.chapter_influence)
        
        # Sort by priority (descending), then by attribute name for stability
        sorted_attrs = sorted(
            missing_attrs,
            key=lambda attr: (priority_map.get(attr, 0), attr),
            reverse=True
        )
        
        return sorted_attrs
    
    async def _generate_candidates(
        self,
        description: str,
        suggested_chapters: Optional[List[int]] = None,
        expansion_logged: bool = False,
        product_family: Optional[str] = None
    ) -> Dict[str, Any]:
        """
        Generate candidate HTS codes using text similarity with pg_trgm.
        
        Requires pg_trgm extension to be enabled.
        
        Args:
            description: Product description
            suggested_chapters: Optional list of chapter numbers to narrow search
        """
        # Check if pg_trgm is available (required for dev)
        try:
            result = await self.db.execute(text("""
                SELECT EXISTS(
                    SELECT 1 FROM pg_extension WHERE extname = 'pg_trgm'
                )
            """))
            extension_exists = result.scalar()
            
            if not extension_exists:
                raise RuntimeError("pg_trgm extension is not enabled. Run: CREATE EXTENSION IF NOT EXISTS pg_trgm;")
            
            # Verify similarity function works
            test_query = text("SELECT similarity('test', 'test') as test_sim")
            test_result = await self.db.execute(test_query)
            test_sim = test_result.scalar()
            if test_sim != 1.0:
                logger.warning(f"pg_trgm similarity test returned {test_sim}, expected 1.0")
        except Exception as e:
            logger.error(f"pg_trgm check failed: {e}")
            raise RuntimeError(f"pg_trgm extension required but not available: {e}")
        
        # Hard exclusions at database query level (blocker filters)
        # NULL safety: COALESCE to empty string to avoid NULL filtering out rows
        # 98/99 exclusion: Normalize hts_code by removing dots/spaces before checking
        where_clause = """
            hts_chapter NOT IN ('98', '99')
            AND REPLACE(REPLACE(hts_code, '.', ''), ' ', '') NOT LIKE '98%'
            AND REPLACE(REPLACE(hts_code, '.', ''), ' ', '') NOT LIKE '99%'
            AND REPLACE(REPLACE(hts_code, '.', ''), ' ', '') NOT LIKE '9903%'
            AND COALESCE(tariff_text, '') NOT ILIKE '%9903.%'
            AND COALESCE(tariff_text_short, '') NOT ILIKE '%9903.%'
        """
        
        # PRIORITY B: Synonym expansion (deterministic, auditable) - MUST be before heading gating
        expanded_description = description
        expanded_terms = []
        product_family_str = product_family.value if isinstance(product_family, ProductFamily) else (product_family if product_family else None)
        if product_family_str:
            expanded_description, expanded_terms = expand_query_terms(
                description,
                product_family_str,
                max_expansions=10
            )
            if expanded_terms:
                logger.info(f"Synonym expansion for {product_family_str}: added {len(expanded_terms)} terms: {expanded_terms}")
        
        # Extract key search terms from expanded description (words > 3 chars, exclude common words)
        search_terms = [w.lower() for w in expanded_description.split() if len(w) > 3]
        # Build text filter: at least one key term must appear
        text_filter = " OR ".join([
            f"(LOWER(tariff_text_short) LIKE :term{i} OR LOWER(tariff_text) LIKE :term{i})"
            for i in range(len(search_terms))
        ]) if search_terms else "1=1"
        
        # Normalize expanded description for similarity search
        normalized_description = expanded_description.lower().strip()
        
        # PRIORITY B: Heading gating for audio_devices
        # If product_family == audio_devices, retrieve from 8518 heading first
        gating_mode = None
        headings_used = []
        heading_gate_applied = False
        
        # Check if product_family is audio_devices (handle both enum and string)
        product_family_value = product_family.value if isinstance(product_family, ProductFamily) else (product_family if product_family else None)
        is_audio_devices = product_family_value == "audio_devices"
        
        if is_audio_devices:
            # STEP 1: Stage 1 - 8518 heading only, retrieve wider set (at least 50 if they exist)
            # Do NOT apply text filter in Stage 1 - get all 8518 candidates, then score them
            heading_where = where_clause + " AND hts_code LIKE '8518%'"
            heading_query = text(f"""
                SELECT 
                    hts_code,
                    hts_chapter,
                    tariff_text_short,
                    tariff_text,
                    duty_rate_general,
                    duty_rate_special,
                    duty_rate_column2,
                    special_countries,
                    source_page,
                    parse_confidence,
                    similarity(
                        LOWER(REGEXP_REPLACE(
                            COALESCE(tariff_text_short, ''),
                            '[^a-zA-Z0-9\\s]', ' ', 'g'
                        )),
                        LOWER(REGEXP_REPLACE(:description, '[^a-zA-Z0-9\\s]', ' ', 'g'))
                    ) as sim_score
                FROM hts_versions
                WHERE {heading_where}
                ORDER BY similarity(
                    LOWER(REGEXP_REPLACE(
                        COALESCE(tariff_text_short, ''),
                        '[^a-zA-Z0-9\\s]', ' ', 'g'
                    )),
                    LOWER(REGEXP_REPLACE(:description, '[^a-zA-Z0-9\\s]', ' ', 'g'))
                ) DESC
                LIMIT 100
            """)
            
            heading_params = {"description": normalized_description}
            heading_params.update({f"term{i}": f"%{term}%" for i, term in enumerate(search_terms)})
            heading_result = await self.db.execute(heading_query, heading_params)
            heading_rows = heading_result.all()
            
            # STEP 1: STRICT heading gating - only 8518 first
            # Score only 8518 candidates first
            rows = heading_rows
            gating_mode = "HEADING_FIRST"
            headings_used = ["8518"]
            
            if len(heading_rows) >= 50:
                # Got enough candidates from 8518 heading - STOP, do not expand
                heading_gate_applied = True
                logger.info(f"Heading gating (STRICT): Retrieved {len(rows)} candidates from 8518 heading (>=50, NOT expanding)")
            else:
                # STEP 2: Expansion - cluster constrained, not broad electronics
                # For audio_devices: 8518 primarily, 8517 only if networking/communications device (earbuds don't),
                # 8543 as last resort (penalized), keep 8466 out entirely
                headings_used = ["8518"]
                # Audio expansion cluster: 8518 (primary), 8543 (last resort, penalized)
                # Do NOT include 8517 unless product analysis indicates networking/communications (earbuds don't)
                # Do NOT include 8466 at all in audio context
                # Do NOT include broad 84/85/90
                audio_expansion_cluster = ["85"]  # Chapter 85 only (excludes 8517 and 8466)
                chapter_filter = f"hts_chapter IN ('85') AND hts_code NOT LIKE '8517%' AND hts_code NOT LIKE '8466%'"
                gating_mode = "HEADING_FIRST_EXPANDED"
                logger.info(f"Heading gating (STRICT): Only {len(heading_rows)} from 8518, expanding to cluster-constrained Chapter 85 (excluding 8517, 8466) (expanded tagged)")
                
                # Use UNION to tag 8518 as primary, expanded as source="expanded"
                expanded_query = text(f"""
                    (
                        SELECT 
                            hts_code,
                            hts_chapter,
                            tariff_text_short,
                            tariff_text,
                            duty_rate_general,
                            duty_rate_special,
                            duty_rate_column2,
                            special_countries,
                            source_page,
                            parse_confidence,
                            similarity(
                                LOWER(REGEXP_REPLACE(
                                    COALESCE(tariff_text_short, ''),
                                    '[^a-zA-Z0-9\\s]', ' ', 'g'
                                )),
                                LOWER(REGEXP_REPLACE(:description, '[^a-zA-Z0-9\\s]', ' ', 'g'))
                            ) as sim_score,
                            1 as priority,  -- 8518 gets priority 1
                            'primary' as source  -- 8518 is primary
                        FROM hts_versions
                        WHERE {heading_where}
                          -- Do NOT apply text filter to Stage 1 (8518 only) - get ALL 8518 candidates, then score them
                    )
                    UNION ALL
                    (
                        SELECT 
                            hts_code,
                            hts_chapter,
                            tariff_text_short,
                            tariff_text,
                            duty_rate_general,
                            duty_rate_special,
                            duty_rate_column2,
                            special_countries,
                            source_page,
                            parse_confidence,
                            similarity(
                                LOWER(REGEXP_REPLACE(
                                    COALESCE(tariff_text_short, ''),
                                    '[^a-zA-Z0-9\\s]', ' ', 'g'
                                )),
                                LOWER(REGEXP_REPLACE(:description, '[^a-zA-Z0-9\\s]', ' ', 'g'))
                            ) as sim_score,
                            2 as priority,  -- Other chapters get priority 2
                            'expanded' as source  -- Expanded candidates tagged
                        FROM hts_versions
                        WHERE {where_clause}
                          AND ({chapter_filter})
                          AND hts_code NOT LIKE '8518%'  -- Exclude 8518 (already in first part)
                          AND hts_code NOT LIKE '8466%'  -- Exclude 8466 entirely in audio context
                          AND ({text_filter})  -- Text filter only on expanded candidates
                    )
                    ORDER BY priority ASC, sim_score DESC
                    LIMIT 50
                """)
                
                expanded_params = {"description": normalized_description}
                expanded_params.update({f"term{i}": f"%{term}%" for i, term in enumerate(search_terms)})
                expanded_result = await self.db.execute(expanded_query, expanded_params)
                rows = expanded_result.all()
                heading_gate_applied = True
                logger.info(f"Heading gating (STRICT): Retrieved {len(rows)} total candidates ({len(heading_rows)} primary from 8518, {len(rows) - len(heading_rows)} expanded from other chapters)")
        else:
            # Workstream D: Add suggested chapters filter if provided (narrow retrieval)
            # Candidate retrieval must be constrained to suggested chapters first
            if suggested_chapters:
                chapter_filter = " OR ".join([f"hts_chapter = '{ch}'" for ch in suggested_chapters])
                where_clause += f" AND ({chapter_filter})"
                logger.info(f"Narrowing candidate retrieval to chapters: {suggested_chapters}")
            elif expansion_logged:
                # Expansion beyond suggested chapters is explicitly logged
                logger.info("Retrieval expanded beyond suggested chapters due to low analysis confidence")
        
        # PRIORITY B: Synonym expansion (deterministic, auditable)
        expanded_description = description
        expanded_terms = []
        if product_family:
            expanded_description, expanded_terms = expand_query_terms(
                description,
                product_family,
                max_expansions=10
            )
            if expanded_terms:
                logger.info(f"Synonym expansion for {product_family}: added {len(expanded_terms)} terms: {expanded_terms}")
        
        # Extract key search terms from expanded description (words > 3 chars, exclude common words)
        search_terms = [w.lower() for w in expanded_description.split() if len(w) > 3]
        # Build text filter: at least one key term must appear
        text_filter = " OR ".join([
            f"(LOWER(tariff_text_short) LIKE :term{i} OR LOWER(tariff_text) LIKE :term{i})"
            for i in range(len(search_terms))
        ]) if search_terms else "1=1"
        
        # Normalize expanded description for similarity search
        normalized_description = expanded_description.lower().strip()
        
        # PRIORITY C: Use tariff_text_short ONLY for similarity (not tariff_text)
        # Keep tariff_text for display/provenance only
        # Only run this query if heading gating didn't already retrieve candidates
        if not heading_gate_applied:
            query = text(f"""
                SELECT 
                    hts_code,
                    hts_chapter,
                    tariff_text_short,
                    tariff_text,
                    duty_rate_general,
                    duty_rate_special,
                    duty_rate_column2,
                    special_countries,
                    source_page,
                    parse_confidence,
                    similarity(
                        LOWER(REGEXP_REPLACE(
                            COALESCE(tariff_text_short, ''),
                            '[^a-zA-Z0-9\\s]', ' ', 'g'
                        )),
                        LOWER(REGEXP_REPLACE(:description, '[^a-zA-Z0-9\\s]', ' ', 'g'))
                    ) as sim_score
                FROM hts_versions
                WHERE {where_clause}
                  AND ({text_filter})
                ORDER BY similarity(
                    LOWER(REGEXP_REPLACE(
                        COALESCE(tariff_text_short, ''),
                        '[^a-zA-Z0-9\\s]', ' ', 'g'
                    )),
                    LOWER(REGEXP_REPLACE(:description, '[^a-zA-Z0-9\\s]', ' ', 'g'))
                ) DESC
                LIMIT 50
            """)
        
        # Use expanded_description for similarity search, original for logging
        # Only execute if heading gating didn't already provide rows
        if not heading_gate_applied:
            params = {"description": normalized_description}  # Use expanded description for similarity
            params.update({f"term{i}": f"%{term}%" for i, term in enumerate(search_terms)})
            result = await self.db.execute(query, params)
            rows = result.all()
        # else: rows already set from heading query above
        
        pre_filter_count = len(rows)
        
        # PRIORITY A: Noise filter suspension / floor
        # Apply noise filters (still in retrieval, before scoring)
        candidates = []
        noisy_count = 0
        noisy_examples = []  # Store examples for logging
        noise_filter_suspended = False
        
        for row in rows:
            hts_code = row[0]
            # Handle UNION query result which has priority column (index 12) vs regular query (no priority)
            tariff_text_short = row[2] or ""
            tariff_text = row[3] or ""
            combined_text = f"{tariff_text_short} {tariff_text}".strip()
            
            # TRACE: SQL returned candidate
            if TRACE_HTS_CODE and hts_code == TRACE_HTS_CODE:
                sim_score_sql = float(row[10]) if len(row) > 10 and row[10] is not None else 0.0
                logger.info(
                    f"[TRACE {TRACE_HTS_CODE}] A) SQL returned candidate: "
                    f"found_in_sql=true, similarity_sql={sim_score_sql:.6f}, "
                    f"chapter={row[1]}, hts_code={hts_code}, "
                    f"tariff_text_short={tariff_text_short[:80]}..."
                )
            
            # Check if noise filter should be applied
            is_noisy = self._is_noisy_description(combined_text)
            
            # TRACE: Noise filter
            if TRACE_HTS_CODE and hts_code == TRACE_HTS_CODE:
                if is_noisy:
                    # Determine which rule excluded it
                    tokens = [t for t in combined_text.split() if len(t) >= 2]
                    total_chars = len(combined_text)
                    digits = sum(1 for c in combined_text if c.isdigit())
                    letters = sum(1 for c in combined_text if c.isalpha())
                    punctuation = sum(1 for c in combined_text if c in '.,;:!?()[]{}"\'-')
                    numeric_density = digits / total_chars if total_chars > 0 else 0
                    punctuation_density = punctuation / total_chars if total_chars > 0 else 0
                    alpha_ratio = letters / total_chars if total_chars > 0 else 0
                    
                    rule = "unknown"
                    if len(tokens) < 4:
                        rule = "too_short"
                    elif numeric_density > 0.35:
                        rule = f"numeric_density_{numeric_density:.2f}"
                    elif punctuation_density > 0.40:
                        rule = f"punctuation_density_{punctuation_density:.2f}"
                    elif alpha_ratio < 0.40:
                        rule = f"alpha_ratio_{alpha_ratio:.2f}"
                    
                    logger.info(
                        f"[TRACE {TRACE_HTS_CODE}] B) Noise filter: noisy=true, "
                        f"rule={rule}, tokens={len(tokens)}, "
                        f"numeric={numeric_density:.2f}, punct={punctuation_density:.2f}, alpha={alpha_ratio:.2f}"
                    )
                else:
                    logger.info(f"[TRACE {TRACE_HTS_CODE}] B) Noise filter: noisy=false")
            
            # PRIORITY A: Suspend noise filtering if ratio > 60% OR if post_filter would drop below 50
            if is_noisy and not noise_filter_suspended:
                noisy_count += 1
                # Store examples (max 5 for logging)
                if len(noisy_examples) < 5:
                    noisy_examples.append({
                        "hts_code": row[0],
                        "text": combined_text[:100] + "..." if len(combined_text) > 100 else combined_text
                    })
                
                # Check if we should suspend filtering
                remaining_after_noise = pre_filter_count - noisy_count
                noise_ratio = (noisy_count / pre_filter_count) if pre_filter_count > 0 else 0.0
                
                if noise_ratio > 0.60 or remaining_after_noise < 50:
                    noise_filter_suspended = True
                    logger.warning(
                        f"Noise filter SUSPENDED: noise_ratio={noise_ratio:.2%}, "
                        f"remaining={remaining_after_noise}, pre_filter={pre_filter_count}. "
                        f"Proceeding with all remaining candidates."
                    )
                    # Don't skip this candidate - include it
                    is_noisy = False
            
            # Add candidate if not noisy (or if filter is suspended)
            if not is_noisy:
                # Handle UNION query (has priority, source) vs regular query (sim_score only)
                # UNION query columns: hts_code(0), hts_chapter(1), tariff_text_short(2), tariff_text(3),
                # duty_rate_general(4), duty_rate_special(5), duty_rate_column2(6), special_countries(7),
                # source_page(8), parse_confidence(9), sim_score(10), priority(11), source(12)
                if len(row) > 12:
                    # UNION query result - sim_score is at index 10, priority at index 11, source at index 12
                    sim_score = float(row[10]) if row[10] is not None else 0.0
                    priority = int(row[11]) if row[11] is not None else 2  # Default to 2 if missing
                    candidate_source = str(row[12]) if row[12] else "primary"  # 'primary' or 'expanded'
                elif len(row) > 11:
                    # UNION query without source column (backward compat)
                    sim_score = float(row[10]) if row[10] is not None else 0.0
                    priority = int(row[11]) if row[11] is not None else 2
                    candidate_source = "primary" if priority == 1 else "expanded"
                else:
                    # Regular query result (8518 only, no expansion) - sim_score is at index 10
                    sim_score = float(row[10]) if len(row) > 10 and row[10] is not None else 0.0
                    priority = 1  # All are primary (8518 only)
                    candidate_source = "primary"  # All are primary when not expanded
                
                # TRACE: Other filters (9903, 98/99 exclusions already done in SQL)
                if TRACE_HTS_CODE and hts_code == TRACE_HTS_CODE:
                    logger.info(
                        f"[TRACE {TRACE_HTS_CODE}] C) Other filters: "
                        f"exclude_9903_text=pass (SQL), exclude_ch98_99=pass (SQL), "
                        f"noise_filter=pass, priority={priority}"
                    )
                
                candidates.append({
                    "hts_code": hts_code,
                    "hts_chapter": row[1],
                    "tariff_text_short": tariff_text_short,
                    "tariff_text": tariff_text,
                    "duty_rate_general": row[4],
                    "duty_rate_special": row[5],
                    "duty_rate_column2": row[6],
                    "special_countries": row[7] or [],
                    "source_page": row[8],
                    "parse_confidence": str(row[9]) if row[9] else "medium",
                    "similarity_score": sim_score,
                    "_priority": priority,  # Internal field for sorting
                    "_source": candidate_source  # 'primary' or 'expanded'
                })
        
        post_filter_count = len(candidates)
        
        # Calculate stage counts for audit (STEP 1)
        primary_count = len([c for c in candidates if c.get("_source") == "primary" or not c.get("_source")])
        expanded_count = len([c for c in candidates if c.get("_source") == "expanded"])
        
        # Sort by priority first (if available), then by similarity
        # This preserves 8518 candidates at the top when heading gating is used
        candidates.sort(key=lambda x: (x.get("_priority", 2), -x["similarity_score"]))
        
        # Log filter counts with warnings
        noise_ratio = (noisy_count / pre_filter_count) if pre_filter_count > 0 else 0.0
        if noise_filter_suspended:
            noise_ratio = 0.0  # Reset ratio since filter was suspended
            noisy_count = 0
        
        logger.info(
            f"Candidate retrieval: pre_filter={pre_filter_count}, "
            f"post_filter={post_filter_count}, noisy_excluded={noisy_count} ({noise_ratio:.1%}), "
            f"noise_filter_suspended={noise_filter_suspended}"
        )
        
        # Warning if noise filtering removes majority of candidates (but wasn't suspended)
        if noise_ratio > 0.50 and not noise_filter_suspended:
            logger.warning(
                f"High noise filter exclusion: {noise_ratio:.1%} of candidates filtered. "
                f"This may indicate overly aggressive filtering or sparse HTS descriptions."
            )
            if noisy_examples:
                logger.debug(f"Noisy examples excluded: {noisy_examples}")
        
        # Log top candidates for debugging with detailed info
        if candidates:
            logger.info(f"Generated {len(candidates)} candidates for description: '{description[:60]}...'")
            logger.info(f"Top 5 candidates by similarity:")
            for i, c in enumerate(candidates[:5], 1):
                logger.info(
                    f"  {i}. HTS {c['hts_code']} (Ch. {c['hts_chapter']}): "
                    f"sim={c['similarity_score']:.4f}, "
                    f"text='{c['tariff_text_short'][:70] if c['tariff_text_short'] else 'N/A'}...'"
                )
        else:
            logger.warning(f"No candidates found for description: '{description[:60]}...'")
        
        # Calculate stage counts for audit
        primary_count = len([c for c in candidates if c.get("_source") == "primary"])
        expanded_count = len([c for c in candidates if c.get("_source") == "expanded"])
        
        return {
            "candidates": candidates[:50],  # Return top 50 for re-ranking
            "pre_filter_count": pre_filter_count,
            "post_filter_count": post_filter_count,
            "noisy_excluded": noisy_count if not noise_filter_suspended else 0,
            "noise_ratio": noise_ratio if not noise_filter_suspended else 0.0,
            "noise_filter_suspended": noise_filter_suspended,
            "expanded_terms": expanded_terms,
            "gating_mode": gating_mode,
            "headings_used": headings_used,
            "primary_count": primary_count,  # Stage 1: 8518 only
            "expanded_count": expanded_count  # Stage 2: expanded (if any)
        }
    
    def _calculate_similarity(self, text1: str, text2: str) -> float:
        """Simple similarity calculation using word overlap"""
        words1 = set(text1.lower().split())
        words2 = set(text2.lower().split())
        
        if not words1 or not words2:
            return 0.0
        
        intersection = words1 & words2
        union = words1 | words2
        
        return len(intersection) / len(union) if union else 0.0
    
    def _is_noisy_description(self, text: str) -> bool:
        """
        Check if description is too noisy to be useful.
        
        Returns True if description should be excluded due to:
        - Too short: fewer than 4-6 meaningful tokens
        - Numeric density too high: digits / total chars > 0.25
        - Punctuation density too high: punctuation / total chars > 0.20
        - Low alpha ratio: letters / total chars < 0.50
        """
        if not text or len(text.strip()) == 0:
            return True
        
        # Count meaningful tokens (words with at least 2 chars)
        tokens = [t for t in text.split() if len(t) >= 2]
        if len(tokens) < 4:
            return True
        
        # Calculate character statistics
        total_chars = len(text)
        if total_chars == 0:
            return True
        
        digits = sum(1 for c in text if c.isdigit())
        letters = sum(1 for c in text if c.isalpha())
        # Count punctuation, but exclude dots used for spacing (common in HTS formatting)
        # Dots followed by spaces or at end of line are likely formatting, not noise
        punctuation_chars = '.,;:!?()[]{}"\'-'
        punctuation = sum(1 for c in text if c in punctuation_chars)
        
        numeric_density = digits / total_chars if total_chars > 0 else 0
        punctuation_density = punctuation / total_chars if total_chars > 0 else 0
        alpha_ratio = letters / total_chars if total_chars > 0 else 0
        
        # Apply thresholds - relaxed for HTS descriptions which have formatting
        if numeric_density > 0.35:  # Increased from 0.25
            return True
        if punctuation_density > 0.40:  # Increased from 0.20 to 0.40 (HTS has formatting dots)
            return True
        if alpha_ratio < 0.40:  # Relaxed from 0.50 to 0.40
            return True
        
        return False
    
    async def _score_candidates(
        self,
        candidates: List[Dict[str, Any]],
        description: str,
        country_of_origin: Optional[str],
        current_hts_code: Optional[str],
        product_family: Optional[ProductFamily] = None,
        product_analysis: Optional[Any] = None  # Workstream 4.1-A: For subheading priors
    ) -> List[Dict[str, Any]]:
        """Score candidates based on multiple factors with detailed per-candidate logging"""
        scored = []
        
        logger.info(f"Scoring {len(candidates)} candidates for description: '{description[:60]}...'")
        
        for idx, candidate in enumerate(candidates):
            score_components = {}
            score = 0.0
            
            # 1. Similarity score (0-1, weight: 0.8 - increased for better matching)
            similarity = float(candidate.get("similarity_score", 0.0))
            similarity_contribution = similarity * 0.8
            score += similarity_contribution
            score_components["similarity_raw"] = similarity
            score_components["similarity_contribution"] = similarity_contribution
            
            # 2. Parse confidence penalty (reduced)
            parse_conf = candidate.get("parse_confidence", "medium")
            confidence_penalty = 0.0
            if parse_conf and "high" not in str(parse_conf).lower():
                if "medium" in str(parse_conf).lower():
                    confidence_penalty = 0.05  # Reduced from 0.1
                else:
                    confidence_penalty = 0.1   # Reduced from 0.2
            score -= confidence_penalty
            score_components["confidence_penalty"] = confidence_penalty
            score_components["parse_confidence"] = str(parse_conf)
            
            # 3. Duty rate general penalty (reduced, only if COO is MFN and general is missing)
            duty_penalty = 0.0
            if country_of_origin and country_of_origin not in NON_MFN_COUNTRIES:
                if not candidate.get("duty_rate_general"):
                    duty_penalty = 0.05  # Reduced from 0.15
            score -= duty_penalty
            score_components["duty_penalty"] = duty_penalty
            score_components["duty_rate_general"] = candidate.get("duty_rate_general")
            
            # 4. Special countries bonus (if COO in special_countries and special implies Free)
            special_bonus = 0.0
            if country_of_origin:
                special_countries = candidate.get("special_countries", [])
                if country_of_origin in special_countries:
                    duty_special = candidate.get("duty_rate_special", "")
                    if duty_special and ("free" in str(duty_special).lower() or duty_special == "0%"):
                        special_bonus = 0.1
            score += special_bonus
            score_components["special_bonus"] = special_bonus
            score_components["special_countries"] = candidate.get("special_countries", [])
            
            # 5. Current HTS match bonus (if provided)
            hts_match_bonus = 0.0
            if current_hts_code:
                normalized_current = current_hts_code.replace(".", "").replace(" ", "").strip()
                normalized_candidate = candidate["hts_code"].replace(".", "").replace(" ", "").strip()
                if normalized_current == normalized_candidate:
                    hts_match_bonus = 0.2
            score += hts_match_bonus
            score_components["hts_match_bonus"] = hts_match_bonus
            
            # STEP 3: Audio family priors - bonus for 8518, penalty for unrelated codes
            audio_family_bonus = 0.0
            audio_family_penalty = 0.0
            audio_subheading_prior = 0.0  # Workstream 4.1-A: Audio subheading intelligence
            applied_priors = []  # Track applied priors for audit
            product_family_str = product_family.value if isinstance(product_family, ProductFamily) else (product_family if product_family else None)
            if product_family_str == "audio_devices":
                candidate_code = candidate.get("hts_code", "")
                candidate_chapter = candidate.get("hts_chapter", "")
                description_lower = description.lower()
                
                # Workstream 4.1-A: Audio subheading priors inside 8518
                # If product_type ∈ {earbuds, earphones, headphones, headset}:
                # Bonus for 851830, Penalty for 851810 unless microphone-centric
                # Workstream 4.1-A: Get product_type from product_analysis if available
                product_type = ""
                if product_analysis and hasattr(product_analysis, 'product_type') and product_analysis.product_type:
                    product_type = product_analysis.product_type.lower()
                elif product_analysis and isinstance(product_analysis, dict):
                    product_type = product_analysis.get('product_type', '').lower()
                if not product_type:
                    # Fallback: infer from description if product_analysis not available
                    product_type = description.lower()
                audio_ear_types = ["earbud", "earphone", "headphone", "headset"]
                is_ear_type = any(audio_type in product_type for audio_type in audio_ear_types) or any(audio_type in description_lower for audio_type in audio_ear_types)
                
                if candidate_code.startswith("8518"):
                    # BONUS: 8518 heading gets bonus in audio context
                    audio_family_bonus = 0.10  # Structural prior bonus for correct heading
                    logger.debug(f"Audio family bonus applied to {candidate_code}: 8518 heading in audio context")
                    
                    # Workstream 4.2-A: Use generic subheading prior framework
                    if is_ear_type and isinstance(product_family, ProductFamily):
                        from app.engines.classification.subheading_priors import apply_subheading_prior
                        prior_value, prior_reasons = apply_subheading_prior(
                            candidate=candidate,
                            product_family=product_family,
                            description=description,
                            product_analysis=product_analysis
                        )
                        audio_subheading_prior = prior_value
                        if prior_reasons:
                            # Extract prior codes for applied_priors list (e.g., "8518.30_bonus", "8518.10_penalty")
                            for reason in prior_reasons:
                                if "851830" in candidate_code or "8518.30" in reason:
                                    if "bonus" in reason.lower():
                                        applied_priors.append("8518.30_bonus")
                                elif "851810" in candidate_code or "8518.10" in reason:
                                    if "penalty" in reason.lower():
                                        applied_priors.append("8518.10_penalty")
                            candidate["_prior_reasons"] = prior_reasons  # Store full reasons for audit
                            logger.debug(f"Subheading prior (framework): {candidate_code}: {prior_value:.3f}, reasons: {prior_reasons}")
                
                # Handle non-8518 codes in audio context
                if not candidate_code.startswith("8518"):
                    # PENALTY: 8517 (telephone/networking) gets strong penalty in audio context
                    if candidate_code.startswith("8517"):
                        audio_family_penalty = 0.20  # Strong penalty for telephone/networking in audio context
                        logger.debug(f"Audio family penalty applied to {candidate_code}: 8517 in audio context")
                    # PENALTY: 8466 (machinery for manufacturing printed circuits) gets strong penalty - should be excluded
                    elif candidate_code.startswith("8466"):
                        audio_family_penalty += 0.25  # Strong penalty for 8466 - should be excluded in audio context
                        logger.debug(f"Audio family penalty applied to {candidate_code}: 8466 should be excluded in audio context")
                    # PENALTY: Unrelated headings (like 8477, 8448) get penalty
                    elif candidate_chapter in ["84"]:
                        # Chapter 84 but not 8518 - likely machinery unrelated to audio
                        audio_family_penalty = 0.15  # Penalty for unrelated machinery
                        logger.debug(f"Audio family penalty applied to {candidate_code}: unrelated Chapter {candidate_chapter} in audio context")
                    # PENALTY: 8543 (electrical machines and apparatus) as last resort, heavily penalized
                    elif candidate_code.startswith("8543"):
                        audio_family_penalty += 0.18  # Heavy penalty for 8543 - last resort only
                        logger.debug(f"Audio family penalty applied to {candidate_code}: 8543 is last resort, heavily penalized")
                
                # PENALTY: Expansion penalty for expanded candidates (applies to all, inside or outside 8518)
                if candidate.get("_source") == "expanded":
                    expansion_penalty = 0.12  # Expansion penalty so expanded can't outrank primary without clearly better similarity
                    audio_family_penalty += expansion_penalty
                    logger.debug(f"Expansion penalty applied to {candidate_code}: expanded candidate in audio context")
                # Additional penalty for networking keywords
                networking_keywords = [
                    "switching", "routing", "apparatus", "protocol", "wi-fi", "wifi",
                    "ethernet", "gateway", "access point", "network", "router"
                ]
                combined_text = f"{candidate.get('tariff_text_short', '')} {candidate.get('tariff_text', '')}".lower()
                keyword_matches = sum(1 for keyword in networking_keywords if keyword in combined_text)
                if keyword_matches >= 2:  # If 2+ networking keywords present
                    additional_penalty = 0.10  # Additional penalty for networking keywords
                    audio_family_penalty += additional_penalty
                    logger.debug(
                        f"Networking keyword penalty applied to {candidate_code}: "
                        f"{keyword_matches} networking keywords detected in audio device query"
                    )
                    # TRACE: Product family gating penalty
                    if TRACE_HTS_CODE and candidate.get("hts_code") == TRACE_HTS_CODE:
                        logger.info(
                            f"[TRACE {TRACE_HTS_CODE}] C) Product family gating: "
                            f"audio_family_penalty={audio_family_penalty}, keyword_matches={keyword_matches}"
                        )
            
            score += audio_family_bonus
            score -= audio_family_penalty
            score += audio_subheading_prior  # Workstream 4.1-A: Audio subheading prior
            score_components["audio_family_bonus"] = audio_family_bonus
            score_components["audio_family_penalty"] = audio_family_penalty
            score_components["audio_subheading_prior"] = audio_subheading_prior  # Workstream 4.1-A
            score_components["subdomain_penalty"] = audio_family_penalty  # Keep for backward compat
            if applied_priors:
                candidate["_applied_priors"] = applied_priors  # Store for audit
            
            # Calculate final score - ensure it's not incorrectly floored
            # Only clamp if score is actually negative or > 1.0
            if score < 0.0:
                logger.warning(
                    f"Candidate {candidate['hts_code']} has negative score {score:.4f} before clamping. "
                    f"Components: {score_components}"
                )
                final_score = 0.0
            elif score > 1.0:
                logger.warning(
                    f"Candidate {candidate['hts_code']} has score > 1.0 ({score:.4f}) before clamping. "
                    f"Components: {score_components}"
                )
                final_score = 1.0
            else:
                final_score = float(score)
            
            candidate["final_score"] = final_score
            candidate["score_components"] = score_components  # Store for debugging
            
            # Per-candidate debug logging for ALL candidates (not just top 3)
            logger.debug(
                f"[Candidate {idx+1}/{len(candidates)}] HTS {candidate['hts_code']} (Ch. {candidate['hts_chapter']}):\n"
                f"  Similarity: {similarity:.4f} → contribution: {similarity_contribution:.4f}\n"
                f"  Confidence penalty: {confidence_penalty:.4f} (parse_conf: {parse_conf})\n"
                f"  Duty penalty: {duty_penalty:.4f} (duty_rate_general: {candidate.get('duty_rate_general', 'N/A')})\n"
                f"  Special bonus: {special_bonus:.4f} (COO: {country_of_origin}, special_countries: {candidate.get('special_countries', [])})\n"
                f"  HTS match bonus: {hts_match_bonus:.4f} (current_hts: {current_hts_code})\n"
                f"  Raw score: {score:.4f} → Final score: {final_score:.4f}\n"
                f"  Text: '{candidate.get('tariff_text_short', 'N/A')[:80]}...'"
                )
            
            scored.append(candidate)
        
        # Log summary
        if scored:
            top_score = max(s["final_score"] for s in scored)
            logger.info(
                f"Scoring complete. Top score: {top_score:.4f}, "
                f"Score range: [{min(s['final_score'] for s in scored):.4f}, {top_score:.4f}], "
                f"Candidates with score > 0: {sum(1 for s in scored if s['final_score'] > 0)}"
            )
        
        return scored
    
    def _select_duty_rate(
        self,
        candidate: Dict[str, Any],
        country_of_origin: Optional[str]
    ) -> Dict[str, Any]:
        """
        Select the appropriate duty rate based on Country of Origin.
        
        Returns:
            Dictionary with selected_rate_type, selected_rate, and duty_rate_numeric
        """
        selected_rate_type = None
        selected_rate = None
        duty_rate_numeric = None
        
        if not country_of_origin:
            # Default to general if no COO
            selected_rate_type = "general"
            selected_rate = candidate.get("duty_rate_general")
        elif country_of_origin in NON_MFN_COUNTRIES:
            # Non-MFN countries use Column 2
            selected_rate_type = "column2"
            selected_rate = candidate.get("duty_rate_column2")
        else:
            # Check if COO is in special_countries and special rate is Free
            special_countries = candidate.get("special_countries", [])
            if country_of_origin in special_countries:
                duty_special = candidate.get("duty_rate_special", "")
                if duty_special and ("free" in str(duty_special).lower() or duty_special == "0%"):
                    selected_rate_type = "special"
                    selected_rate = duty_special
                else:
                    selected_rate_type = "general"
                    selected_rate = candidate.get("duty_rate_general")
            else:
                # Default to general (MFN)
                selected_rate_type = "general"
                selected_rate = candidate.get("duty_rate_general")
        
        # Parse numeric duty rate
        if selected_rate:
            duty_rate_numeric = self._parse_duty_rate(selected_rate)
        
        return {
            "selected_rate_type": selected_rate_type,
            "selected_rate": selected_rate,
            "duty_rate_numeric": duty_rate_numeric
        }
    
    def _parse_duty_rate(self, rate_str: str) -> Optional[float]:
        """Parse duty rate string to numeric value"""
        if not rate_str:
            return None
        
        rate_str = str(rate_str).strip().lower()
        
        # Handle "Free" or "0%"
        if "free" in rate_str or rate_str == "0%" or rate_str == "0":
            return 0.0
        
        # Extract percentage
        match = re.search(r'(\d+\.?\d*)', rate_str)
        if match:
            try:
                return float(match.group(1))
            except:
                return None
        
        return None
    
    def _get_expected_chapters(self, description: str) -> Optional[List[str]]:
        """
        Return expected HTS chapters based on product description.
        This is a deterministic sanity check to catch obviously wrong matches.
        
        Uses explicit chapter clusters from chapter_clusters.py.
        This ensures clusters are explicit and reviewable, not emergent.
        
        Returns:
            List of expected chapter numbers (as strings), or None if no specific expectation
        """
        from app.engines.classification.required_attributes import identify_product_family
        from app.engines.classification.chapter_clusters import get_chapter_numbers
        
        # Identify product family
        product_family = identify_product_family(description, {})
        
        # Get chapter numbers from explicit clusters
        if product_family != ProductFamily.UNKNOWN:
            chapter_numbers = get_chapter_numbers(product_family.value)
            if chapter_numbers:
                return [str(ch) for ch in chapter_numbers]
        
        # No specific expectation - return None to skip check
        return None


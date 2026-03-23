"""
Regulatory Applicability Engine - Side Sprint A

Evidence-driven regulatory flagging with conditional logic.

Key principles:
- HTS codes trigger questions, not conclusions
- Conditions must be evaluated with evidence
- Flags suppressed when evidence negates applicability
- REVIEW_REQUIRED when evidence is missing or ambiguous
"""

from dataclasses import dataclass, field
from typing import Optional, List, Dict, Any
from uuid import UUID
import logging
from enum import Enum

from app.models.regulatory_evaluation import (
    RegulatoryEvaluation,
    RegulatoryCondition,
    Regulator,
    RegulatoryOutcome,
    ConditionState
)
from sqlalchemy.ext.asyncio import AsyncSession

logger = logging.getLogger(__name__)


@dataclass
class RegulatoryConditionDefinition:
    """Definition of a regulatory condition."""
    id: str  # e.g., "INTENDED_PESTICIDAL_USE"
    type: str  # "boolean" for now
    description: str  # Human-readable description


@dataclass
class RegulatoryFlagDefinition:
    """
    Definition of a regulatory flag with conditions.
    
    Replaces binary "flag if HTS ∈ set" logic.
    """
    regulator: Regulator
    hts_triggers: List[str]  # HTS codes/chapters that trigger evaluation
    conditions: List[RegulatoryConditionDefinition]
    required_conditions: List[str]  # IDs of conditions that must be TRUE for flag to apply


@dataclass
class ConditionEvaluation:
    """Result of evaluating a single condition."""
    condition_id: str
    state: ConditionState
    evidence_refs: List[Dict[str, Any]]  # [{document_id, page_number, snippet}]


@dataclass
class RegulatoryEvaluationResult:
    """Result of regulatory applicability evaluation."""
    regulator: Regulator
    outcome: RegulatoryOutcome
    explanation_text: str
    condition_evaluations: List[ConditionEvaluation]
    triggered_by_hts_code: str


class RegulatoryApplicabilityEngine:
    """
    Engine for evaluating regulatory applicability based on evidence.
    
    Never flags based solely on HTS code.
    Requires evidence for all condition evaluations.
    """
    
    def __init__(self, db: AsyncSession):
        self.db = db
        self.flag_definitions = self._load_flag_definitions()
    
    def _load_flag_definitions(self) -> List[RegulatoryFlagDefinition]:
        """
        Load regulatory flag definitions.
        
        Initial set: EPA, FDA (limited), Lacey Act.
        """
        return [
            # EPA - Pesticide/Biocide
            RegulatoryFlagDefinition(
                regulator=Regulator.EPA,
                hts_triggers=["8543.70"],  # Example - expand as needed
                conditions=[
                    RegulatoryConditionDefinition(
                        id="INTENDED_PESTICIDAL_USE",
                        type="boolean",
                        description="Product is intended to prevent, destroy, repel, or mitigate pests"
                    ),
                    RegulatoryConditionDefinition(
                        id="CONTAINS_PESTICIDAL_SUBSTANCE",
                        type="boolean",
                        description="Product contains chemical agents intended to affect biological organisms"
                    )
                ],
                required_conditions=["INTENDED_PESTICIDAL_USE"]  # At least one must be TRUE
            ),
            
            # FDA - General Import Controls (limited scope)
            RegulatoryFlagDefinition(
                regulator=Regulator.FDA,
                hts_triggers=[],  # FDA doesn't use HTS-based triggers - evaluate based on evidence only
                conditions=[
                    RegulatoryConditionDefinition(
                        id="IS_MEDICAL_DEVICE",
                        type="boolean",
                        description="Product is a medical device as defined by FDA"
                    ),
                    RegulatoryConditionDefinition(
                        id="IS_FOOD_COSMETIC_SUPPLEMENT",
                        type="boolean",
                        description="Product is food, cosmetic, or dietary supplement"
                    ),
                    RegulatoryConditionDefinition(
                        id="IS_RADIATION_EMITTING_ELECTRONIC",
                        type="boolean",
                        description="Product is radiation-emitting electronic product (narrow definition, excludes networking equipment, furniture with electronics, wireless access points)"
                    )
                ],
                required_conditions=["IS_MEDICAL_DEVICE", "IS_FOOD_COSMETIC_SUPPLEMENT", "IS_RADIATION_EMITTING_ELECTRONIC"]
            ),
            
            # Lacey Act - Plant-based materials
            RegulatoryFlagDefinition(
                regulator=Regulator.LACEY_ACT,
                hts_triggers=[],  # Not HTS-based - evaluate on evidence
                conditions=[
                    RegulatoryConditionDefinition(
                        id="CONTAINS_PLANT_BASED_MATERIALS",
                        type="boolean",
                        description="Product contains wood, bamboo, cork, paper, or botanical fibers"
                    )
                ],
                required_conditions=["CONTAINS_PLANT_BASED_MATERIALS"]
            )
        ]
    
    async def evaluate_regulatory_applicability(
        self,
        declared_hts_code: str,
        product_description: Optional[str] = None,
        document_evidence: Optional[List[Dict[str, Any]]] = None
    ) -> List[RegulatoryEvaluationResult]:
        """
        Evaluate regulatory applicability for declared HTS code.
        
        Args:
            declared_hts_code: 10-digit HTS code
            product_description: Product description (optional)
            document_evidence: List of document evidence with extraction results
        
        Returns:
            List of regulatory evaluation results
        """
        results = []
        
        # Find relevant flag definitions (triggered by HTS or always evaluate)
        relevant_definitions = self._get_relevant_definitions(declared_hts_code)
        
        # Evaluate each relevant regulator
        for definition in relevant_definitions:
            result = await self._evaluate_regulator(
                definition=definition,
                declared_hts_code=declared_hts_code,
                product_description=product_description,
                document_evidence=document_evidence or []
            )
            results.append(result)
        
        return results
    
    def _get_relevant_definitions(self, hts_code: str) -> List[RegulatoryFlagDefinition]:
        """Get flag definitions relevant to this HTS code."""
        relevant = []
        
        # Extract chapter/heading for matching
        chapter = hts_code[:2] if len(hts_code) >= 2 else ""
        heading = hts_code[:4] if len(hts_code) >= 4 else ""
        
        for definition in self.flag_definitions:
            # Check if HTS triggers this definition
            triggered = False
            
            if not definition.hts_triggers:
                # No HTS triggers = always evaluate (FDA, Lacey Act)
                triggered = True
            else:
                for trigger in definition.hts_triggers:
                    # Check exact match or chapter/heading match
                    if hts_code == trigger or hts_code.startswith(trigger):
                        triggered = True
                        break
                    # Check chapter match
                    if len(trigger) >= 2 and chapter == trigger[:2]:
                        triggered = True
                        break
            
            if triggered:
                relevant.append(definition)
        
        return relevant
    
    async def _evaluate_regulator(
        self,
        definition: RegulatoryFlagDefinition,
        declared_hts_code: str,
        product_description: Optional[str],
        document_evidence: List[Dict[str, Any]]
    ) -> RegulatoryEvaluationResult:
        """
        Evaluate applicability for a single regulator.
        
        Hard logic:
        - Any REQUIRED condition = CONFIRMED_TRUE → FLAG APPLIES
        - All REQUIRED conditions = CONFIRMED_FALSE → FLAG SUPPRESSED
        - Any REQUIRED condition = UNKNOWN → FLAG CONDITIONAL + REVIEW_REQUIRED
        """
        # Evaluate all conditions
        condition_evaluations = []
        
        for condition_def in definition.conditions:
            evaluation = await self._evaluate_condition(
                condition_def=condition_def,
                product_description=product_description,
                document_evidence=document_evidence
            )
            condition_evaluations.append(evaluation)
        
        # Determine outcome based on required conditions
        required_evaluations = [
            e for e in condition_evaluations
            if e.condition_id in definition.required_conditions
        ]
        
        # Check states
        any_true = any(e.state == ConditionState.CONFIRMED_TRUE for e in required_evaluations)
        all_false = all(e.state == ConditionState.CONFIRMED_FALSE for e in required_evaluations)
        any_unknown = any(e.state == ConditionState.UNKNOWN for e in required_evaluations)
        
        # Apply hard logic
        if any_true:
            outcome = RegulatoryOutcome.APPLIES
            explanation = self._build_explanation_applies(definition, condition_evaluations)
        elif all_false:
            outcome = RegulatoryOutcome.SUPPRESSED
            explanation = self._build_explanation_suppressed(definition, condition_evaluations, document_evidence)
        elif any_unknown:
            outcome = RegulatoryOutcome.CONDITIONAL
            explanation = self._build_explanation_conditional(definition, condition_evaluations)
        else:
            # Edge case: no required conditions (shouldn't happen, but handle gracefully)
            outcome = RegulatoryOutcome.CONDITIONAL
            explanation = f"{definition.regulator.value} applicability evaluation incomplete. Review required."
        
        return RegulatoryEvaluationResult(
            regulator=definition.regulator,
            outcome=outcome,
            explanation_text=explanation,
            condition_evaluations=condition_evaluations,
            triggered_by_hts_code=declared_hts_code
        )
    
    async def _evaluate_condition(
        self,
        condition_def: RegulatoryConditionDefinition,
        product_description: Optional[str],
        document_evidence: List[Dict[str, Any]]
    ) -> ConditionEvaluation:
        """
        Evaluate a single condition based on evidence.
        
        If no evidence exists, state = UNKNOWN.
        NECO must not infer.
        """
        evidence_refs = []
        
        # Search document evidence for condition-relevant information
        if document_evidence:
            for doc in document_evidence:
                extracted_text = doc.get("extracted_text", "")
                structured_data = doc.get("structured_data", {})
                
                # Extract relevant snippets (simple keyword matching for now)
                snippets = self._extract_relevant_snippets(
                    condition_id=condition_def.id,
                    text=extracted_text,
                    structured_data=structured_data
                )
                
                for snippet in snippets:
                    evidence_refs.append({
                        "document_id": str(doc.get("document_id", "")),
                        "page_number": snippet.get("page_number"),
                        "snippet": snippet.get("text", "")
                    })
        
        # Determine state based on evidence
        state = self._determine_condition_state(
            condition_id=condition_def.id,
            evidence_refs=evidence_refs,
            product_description=product_description
        )
        
        return ConditionEvaluation(
            condition_id=condition_def.id,
            state=state,
            evidence_refs=evidence_refs
        )
    
    def _extract_relevant_snippets(
        self,
        condition_id: str,
        text: str,
        structured_data: Dict[str, Any]
    ) -> List[Dict[str, Any]]:
        """
        Extract relevant snippets from document text.
        
        For datasheets, look for material composition, intended use, exclusions.
        """
        snippets = []
        text_lower = text.lower()
        
        # Condition-specific keyword matching
        keywords_map = {
            "INTENDED_PESTICIDAL_USE": ["pesticide", "pest", "biocide", "insecticide", "herbicide", "fungicide", "non-pesticidal", "not a pesticide"],
            "CONTAINS_PESTICIDAL_SUBSTANCE": ["pesticidal", "chemical agent", "biological organism"],
            "CONTAINS_PLANT_BASED_MATERIALS": ["wood", "bamboo", "cork", "paper", "fiber", "plant-based", "100% plastic", "100% metal"],
            "IS_MEDICAL_DEVICE": ["medical device", "fda approved", "medical use"],
            "IS_FOOD_COSMETIC_SUPPLEMENT": ["food", "cosmetic", "dietary supplement", "nutrition"],
            "IS_RADIATION_EMITTING_ELECTRONIC": ["radiation", "x-ray", "ultrasound", "medical imaging"]  # Narrow definition
        }
        
        keywords = keywords_map.get(condition_id, [])
        
        # Search for keywords in text (simple approach)
        for keyword in keywords:
            if keyword in text_lower:
                # Extract context around keyword
                idx = text_lower.find(keyword)
                start = max(0, idx - 100)
                end = min(len(text), idx + len(keyword) + 100)
                snippet_text = text[start:end].strip()
                
                snippets.append({
                    "text": snippet_text,
                    "page_number": None  # TODO: Track page numbers from extraction
                })
        
        return snippets
    
    def _determine_condition_state(
        self,
        condition_id: str,
        evidence_refs: List[Dict[str, Any]],
        product_description: Optional[str]
    ) -> ConditionState:
        """
        Determine condition state based on evidence.
        
        If no evidence → UNKNOWN
        If evidence explicitly negates → CONFIRMED_FALSE
        If evidence supports → CONFIRMED_TRUE
        """
        if not evidence_refs:
            return ConditionState.UNKNOWN
        
        # Analyze evidence snippets
        snippets_text = " ".join([e.get("snippet", "").lower() for e in evidence_refs])
        
        # Negation patterns
        negation_patterns = {
            "INTENDED_PESTICIDAL_USE": ["non-pesticidal", "not a pesticide", "not pesticidal"],
            "CONTAINS_PESTICIDAL_SUBSTANCE": ["no chemical agents", "no pesticidal substances"],
            "CONTAINS_PLANT_BASED_MATERIALS": ["100% plastic", "100% metal", "no plant materials", "synthetic only"],
            "IS_MEDICAL_DEVICE": ["not a medical device", "not for medical use"],
            "IS_RADIATION_EMITTING_ELECTRONIC": ["networking equipment", "furniture", "wireless access point"]
        }
        
        negations = negation_patterns.get(condition_id, [])
        
        # Check for explicit negations
        for negation in negations:
            if negation in snippets_text:
                return ConditionState.CONFIRMED_FALSE
        
        # Check for positive indicators (if keywords found)
        # Simple heuristic: if we found relevant snippets, likely TRUE
        # But this is conservative - requires explicit evidence
        # For now, default to UNKNOWN unless explicit negation
        # TODO: Improve with better NLP or structured data extraction
        
        # Default: UNKNOWN if ambiguous (even if snippets found, need explicit positive indicators)
        return ConditionState.UNKNOWN
    
    def _build_explanation_applies(
        self,
        definition: RegulatoryFlagDefinition,
        condition_evaluations: List[ConditionEvaluation]
    ) -> str:
        """Build explanation when flag applies."""
        true_conditions = [e for e in condition_evaluations if e.state == ConditionState.CONFIRMED_TRUE]
        
        return (
            f"{definition.regulator.value} applicability evaluated. "
            f"Evidence confirms {', '.join([e.condition_id.replace('_', ' ').lower() for e in true_conditions])}. "
            f"{definition.regulator.value} applicability identified based on provided evidence."
        )
    
    def _build_explanation_suppressed(
        self,
        definition: RegulatoryFlagDefinition,
        condition_evaluations: List[ConditionEvaluation],
        document_evidence: List[Dict[str, Any]]
    ) -> str:
        """Build explanation when flag is suppressed."""
        false_conditions = [e for e in condition_evaluations if e.state == ConditionState.CONFIRMED_FALSE]
        
        evidence_source = "datasheet" if any("datasheet" in str(doc.get("document_type", "")).lower() for doc in document_evidence) else "documents"
        
        return (
            f"{definition.regulator.value} applicability evaluated. "
            f"{evidence_source.title()} indicates {', '.join([e.condition_id.replace('_', ' ').lower() for e in false_conditions])}. "
            f"{definition.regulator.value} applicability not identified based on provided evidence."
        )
    
    def _build_explanation_conditional(
        self,
        definition: RegulatoryFlagDefinition,
        condition_evaluations: List[ConditionEvaluation]
    ) -> str:
        """Build explanation when flag is conditional (review required)."""
        unknown_conditions = [e for e in condition_evaluations if e.state == ConditionState.UNKNOWN]
        
        condition_descriptions = [e.condition_id.replace('_', ' ').lower() for e in unknown_conditions]
        
        return (
            f"{definition.regulator.value} applicability depends on {', '.join(condition_descriptions)}. "
            f"Provided documents do not confirm or negate applicability. "
            f"Review required."
        )

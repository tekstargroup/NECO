"""
Rule-based HTS classifier for medical/training robotics use cases.

This module adds deterministic legal-style reasoning that can be used to:
- classify obvious training vs medical patterns
- provide a transparent reasoning path
- bias probabilistic candidate lists toward legally-specific headings
"""

from dataclasses import dataclass, field
from typing import List, Optional, Dict, Any


RULE_REGISTRY: List[Dict[str, Any]] = [
    {
        "rule_id": "R1_TRAINING_9023",
        "owner": "compliance_team",
        "rationale": "Training/demo apparatus not used on humans → heading 9023 per GRI 1",
        "families": ["robotics", "medical_training"],
        "enforce": True,
        "test_case_ids": ["gold_training_robot_easy", "gold_demo_phantom"],
    },
    {
        "rule_id": "R2_MEDICAL_HUMAN_9018",
        "owner": "compliance_team",
        "rationale": "Medical use on humans → heading 9018 per Section XVIII Note 2",
        "families": ["medical_surgical", "robotic_surgery"],
        "enforce": True,
        "test_case_ids": ["gold_surgical_robot", "gold_endo_instrument"],
    },
    {
        "rule_id": "R3_ROBOTIC_MEDICAL_OVERRIDE",
        "owner": "compliance_team",
        "rationale": "Medical robot specifically described in 9018 overrides 8479",
        "families": ["robotic_surgery"],
        "enforce": True,
        "test_case_ids": ["gold_surgical_robot"],
    },
    {
        "rule_id": "R4_INTEGRATED_APPARATUS",
        "owner": "compliance_team",
        "rationale": "Multi-component integrated electro-medical apparatus → 9018.90.75",
        "families": ["medical_surgical"],
        "enforce": True,
        "test_case_ids": ["gold_surgical_system"],
    },
    {
        "rule_id": "R5_PROCEDURAL_INSTRUMENT",
        "owner": "compliance_team",
        "rationale": "Active procedural instrument with body interaction → 9018.90.80",
        "families": ["medical_surgical"],
        "enforce": True,
        "test_case_ids": ["gold_endo_instrument"],
    },
    {
        "rule_id": "R6_ACCESSORY_PART",
        "owner": "compliance_team",
        "rationale": "Medical accessory without independent function → 9018.90.xx",
        "families": ["medical_surgical"],
        "enforce": False,
        "test_case_ids": ["gold_trocar_accessory"],
    },
    {
        "rule_id": "R7_NON_MEDICAL_FALLBACK_8479",
        "owner": "compliance_team",
        "rationale": "Non-medical non-training fallback → 8479",
        "families": ["industrial"],
        "enforce": False,
        "test_case_ids": [],
    },
]


@dataclass
class ProductInput:
    product_name: str
    description: str = ""
    used_on_humans: Optional[bool] = None
    purpose: Optional[str] = None  # treatment | diagnosis | training | other
    is_robotic: Optional[bool] = None
    is_medical_field: Optional[bool] = None
    is_handheld: Optional[bool] = None
    is_accessory: Optional[bool] = None
    performs_direct_action: Optional[bool] = None
    interacts_with_body: Optional[bool] = None
    multiple_components: Optional[bool] = None
    performs_integrated_function: Optional[bool] = None
    imported_as_set: Optional[bool] = None
    sterile_or_disposable: Optional[bool] = None
    notes: Dict[str, Any] = field(default_factory=dict)


@dataclass
class ClassificationResult:
    heading: Optional[str]
    subheading: Optional[str]
    htsus: Optional[str]
    confidence: str
    justification: List[str]
    alternative_headings_considered: List[str]
    warnings: List[str]
    reasoning_path: List[str]


class RuleBasedClassifier:
    """
    HTSUS-oriented deterministic rules for medical/training robotics.
    This is advisory logic and must remain non-binding.
    """

    def classify(self, product: ProductInput) -> ClassificationResult:
        justification: List[str] = []
        alternatives: List[str] = []
        warnings: List[str] = []
        path: List[str] = []

        purpose = (product.purpose or "").strip().lower()
        missing_fields = self._find_missing_critical_fields(product)
        if missing_fields:
            warnings.append(f"Missing potentially material facts: {', '.join(missing_fields)}")

        if product.imported_as_set:
            warnings.append("Imported as a set: review GRI 3(b) before final classification.")
            path.append("Set warning triggered: GRI 3(b) review advised.")

        # Rule 1: training/demo only -> 9023
        if purpose == "training" and product.used_on_humans is False:
            path.append("Rule 1 matched: training purpose + not used on humans.")
            justification.extend(
                [
                    "Article is designed for training/demonstration.",
                    "Not used on humans for diagnosis or treatment.",
                    "Heading 9023 is more specific for demonstrational apparatus.",
                ]
            )
            alternatives.extend(
                [
                    "9018 (rejected: no diagnostic or therapeutic use on patients)",
                    "8479 (rejected: 9023 is more specific)",
                ]
            )
            return ClassificationResult(
                heading="9023",
                subheading="9023.00.00",
                htsus="9023.00.00",
                confidence=self._confidence(product, strong=True),
                justification=justification,
                alternative_headings_considered=alternatives,
                warnings=warnings,
                reasoning_path=path,
            )

        # Rule 2: medical use on humans -> heading 9018
        if product.used_on_humans is True and product.is_medical_field is True:
            path.append("Rule 2 matched: used on humans in medical field.")
            justification.append("Article is used in medical/surgical context on patients.")

            # Rule 3: medical robot override
            if product.is_robotic is True:
                path.append("Rule 3 matched: medical robotic function.")
                justification.append(
                    "Medical robotic devices are classified under medical headings rather than general machinery when specifically described."
                )
                alternatives.append("8479 (rejected: less specific than heading 9018)")

            # Rule 4: system/apparatus
            if product.multiple_components is True and product.performs_integrated_function is True:
                path.append("Rule 4 matched: multi-component integrated apparatus.")
                justification.extend(
                    [
                        "The article is an integrated system/apparatus.",
                        "Electrical/robotic medical system suggests electro-medical apparatus.",
                    ]
                )
                return ClassificationResult(
                    heading="9018",
                    subheading="9018.90.75",
                    htsus="9018.90.75",
                    confidence=self._confidence(product, strong=True),
                    justification=justification,
                    alternative_headings_considered=alternatives,
                    warnings=warnings,
                    reasoning_path=path,
                )

            # Rule 5: active procedural instrument
            if product.performs_direct_action is True and product.interacts_with_body is True:
                path.append("Rule 5 matched: direct procedural action in body.")
                justification.extend(
                    [
                        "The article performs active procedural function.",
                        "It is more than a passive component or accessory.",
                        "This supports classification as a surgical/medical instrument.",
                    ]
                )
                return ClassificationResult(
                    heading="9018",
                    subheading="9018.90.80",
                    htsus="9018.90.80",
                    confidence=self._confidence(product, strong=True),
                    justification=justification,
                    alternative_headings_considered=alternatives,
                    warnings=warnings,
                    reasoning_path=path,
                )

            # Rule 6: part/accessory
            if product.is_accessory is True and product.performs_direct_action is not True:
                path.append("Rule 6 matched: accessory/part without independent function.")
                justification.extend(
                    [
                        "The article supports a medical device but does not itself perform core procedural action.",
                        "This suggests parts/accessories treatment within heading 9018.",
                    ]
                )
                warnings.append(
                    "Exact parts/accessories subheading needs closer review against HTSUS structure and CBP rulings."
                )
                return ClassificationResult(
                    heading="9018",
                    subheading="9018.90.xx",
                    htsus="9018.90.xx",
                    confidence=self._confidence(product, strong=False),
                    justification=justification,
                    alternative_headings_considered=alternatives,
                    warnings=warnings,
                    reasoning_path=path,
                )

            path.append("Medical fallback under heading 9018.")
            justification.append("Insufficient facts for narrower medical subheading; heading 9018 remains likely.")
            warnings.append("Subheading requires more detail: apparatus vs instrument vs part/accessory.")
            return ClassificationResult(
                heading="9018",
                subheading="9018.90.xx",
                htsus="9018.90.xx",
                confidence=self._confidence(product, strong=False),
                justification=justification,
                alternative_headings_considered=alternatives,
                warnings=warnings,
                reasoning_path=path,
            )

        # Rule 7: non-medical fallback
        if (product.is_medical_field is False) and purpose != "training":
            path.append("Rule 7 matched: non-medical, non-training fallback.")
            justification.append("No facts support a more specific medical or demonstrational heading.")
            warnings.append("8479 is fallback only. Confirm no more specific heading applies.")
            return ClassificationResult(
                heading="8479",
                subheading="8479.xx.xx",
                htsus="8479.xx.xx",
                confidence="low",
                justification=justification,
                alternative_headings_considered=["9018", "9023"],
                warnings=warnings,
                reasoning_path=path,
            )

        path.append("No decisive rule matched.")
        warnings.append("Unable to determine classification confidently from supplied facts.")
        warnings.append(
            "Ask clarifying questions about intended use, patient contact, and whether article performs direct procedural function."
        )
        return ClassificationResult(
            heading=None,
            subheading=None,
            htsus=None,
            confidence="low",
            justification=["Insufficient facts for reliable classification."],
            alternative_headings_considered=["9018", "9023", "8479"],
            warnings=warnings,
            reasoning_path=path,
        )

    def _find_missing_critical_fields(self, product: ProductInput) -> List[str]:
        critical = {
            "used_on_humans": product.used_on_humans,
            "purpose": product.purpose,
            "is_medical_field": product.is_medical_field,
            "performs_direct_action": product.performs_direct_action,
            "interacts_with_body": product.interacts_with_body,
        }
        return [k for k, v in critical.items() if v is None or v == ""]

    def _confidence(self, product: ProductInput, strong: bool) -> str:
        if strong:
            return "high"
        known_count = sum(
            [
                product.used_on_humans is not None,
                product.purpose is not None,
                product.is_medical_field is not None,
                product.performs_direct_action is not None,
                product.interacts_with_body is not None,
            ]
        )
        return "medium" if known_count >= 4 else "low"


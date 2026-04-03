"""Patch C — UNKNOWN family must not imply analysis_confidence == 1.0 when required_attrs is empty."""

from app.engines.classification.product_analysis import ProductAnalyzer
from app.engines.classification.required_attributes import ProductFamily


def test_unknown_never_gets_full_confidence_when_required_attrs_empty():
    """
    Code path: ProductAnalyzer.analyze → _compute_confidence when
    get_required_attributes(UNKNOWN) returns [].

    Previously, empty required_attrs could short-circuit to return 1.0; UNKNOWN now blends
    router confidence and caps below 1.0.
    """
    pa = ProductAnalyzer()
    conf = pa._compute_confidence(
        extracted_attributes={},
        required_attrs=[],
        missing_required=[],
        product_family=ProductFamily.UNKNOWN,
        family_selection_confidence=0.45,
    )
    assert conf < 1.0
    assert conf <= 0.65


def test_non_unknown_still_full_confidence_when_required_attrs_empty():
    """Families with no required attrs in mapping are rare; if empty list, non-UNKNOWN keeps legacy 1.0."""
    pa = ProductAnalyzer()
    conf = pa._compute_confidence(
        extracted_attributes={},
        required_attrs=[],
        missing_required=[],
        product_family=ProductFamily.ELECTRONICS_COMPUTING,
        family_selection_confidence=0.92,
    )
    assert conf == 1.0

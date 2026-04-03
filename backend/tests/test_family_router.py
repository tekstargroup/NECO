"""PATCH C — family router."""

from app.engines.classification.family_router import (
    CRITICAL_ATTRIBUTES_BY_FAMILY,
    critical_missing_for_family,
    infer_family_key,
)


def test_infer_family_medical():
    assert infer_family_key("surgical endoscopy tool for patient") == "medical"


def test_infer_family_default():
    assert infer_family_key("widget") == "default"


def test_critical_missing_filters_by_family():
    missing = ["used_on_humans", "material", "intended_use"]
    # medical: intended_use, used_on_humans, disposable — material not in set
    cm = critical_missing_for_family(missing, "medical device for clinical use")
    assert "used_on_humans" in cm
    assert "material" not in cm


def test_default_family_includes_material():
    cm = critical_missing_for_family(["material", "voltage"], "generic part")
    assert "material" in cm
    assert "voltage" not in cm


def test_router_sets_documented():
    assert "default" in CRITICAL_ATTRIBUTES_BY_FAMILY

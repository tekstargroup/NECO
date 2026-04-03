"""Patch C — product family router, confidence, and clarification guardrails."""

import pytest

from app.engines.classification.required_attributes import (
    ProductFamily,
    select_product_family,
)


def test_server_compute_routes_to_electronics_computing():
    fs = select_product_family(
        "Dell PowerEdge R750 rackmount server dual CPU 512GB RAM enterprise server",
        {},
    )
    assert fs.family == ProductFamily.ELECTRONICS_COMPUTING
    assert fs.confidence >= 0.9
    assert "computing" in fs.matched_rule or "server" in fs.matched_rule


def test_reusable_bottle_routes_to_containers_not_medical():
    fs = select_product_family("24 oz reusable stainless steel water bottle with screw cap", {})
    assert fs.family in (ProductFamily.CONTAINERS, ProductFamily.FOOD_CONTAINERS)
    assert fs.family != ProductFamily.MEDICAL_DEVICES


def test_industrial_pressure_sensor_not_medical():
    fs = select_product_family("Industrial pressure sensor 4-20mA stainless steel diaphragm", {})
    assert fs.family == ProductFamily.ELECTRONICS
    assert "sensor" in fs.matched_rule or "industrial" in fs.matched_rule


def test_industrial_pressure_transmitter_rule3_current_electronics_future_taxonomy_note():
    """
    Benchmark: transmitters must match Rule 3 (same interim family as pressure sensors).

    Current expectation: ELECTRONICS + rule_industrial_sensor — generic enum pending a dedicated
    instruments/measuring path (e.g. Ch.90 vs Ch.85 product decision) in a later patch.
    """
    fs = select_product_family("Industrial pressure transmitter 4-20mA HART stainless steel", {})
    assert fs.family == ProductFamily.ELECTRONICS
    assert fs.matched_rule == "rule_industrial_sensor"


def test_screws_bolts_washers_fasteners_family():
    fs = select_product_family("M6 hex bolts with matching washers and machine screws zinc plated", {})
    assert fs.family == ProductFamily.FASTENERS_HARDWARE


def test_display_monitor_not_medical_without_clinical_context():
    fs = select_product_family("27 inch LED LCD computer monitor HDMI DisplayPort 4K UHD", {})
    assert fs.family == ProductFamily.CONSUMER_ELECTRONICS
    assert fs.family != ProductFamily.MEDICAL_DEVICES


def test_weak_monitor_not_medical():
    fs = select_product_family("portable monitor device for desk", {})
    assert fs.family != ProductFamily.MEDICAL_DEVICES


def test_get_question_family_specific_medical():
    from app.engines.classification.required_attributes import get_question_for_family_attribute

    q_med = get_question_for_family_attribute(ProductFamily.MEDICAL_DEVICES, "intended_medical_use")
    assert "Chapter 90" in q_med
    q_cont = get_question_for_family_attribute(ProductFamily.CONTAINERS, "material")
    assert "Chapter" in q_cont or "39" in q_cont

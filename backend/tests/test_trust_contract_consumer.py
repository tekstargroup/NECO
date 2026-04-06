"""trust_contract helpers for programmatic consumers."""

from app.services import pipeline_stage_service as pss
from app.services.pipeline_stage_service import build_trust_contract_metadata
from app.services.trust_contract_consumer import (
    artifact_in_trusted_contract,
    classify_artifact_scope,
    get_trust_contract,
)


def test_get_trust_contract_from_result_json():
    tc = build_trust_contract_metadata()
    assert tc.get("version") == "phase2_v3"
    payload = {"trust_contract": tc}
    assert get_trust_contract(payload) == tc
    assert get_trust_contract({}) is None


def test_artifact_matrix_flags_classification_facts_trusted():
    tc = build_trust_contract_metadata()
    assert artifact_in_trusted_contract("classification_facts_db", tc) is True
    assert artifact_in_trusted_contract("duty_resolution_json", tc) is False


def test_classify_artifact_scope():
    tc = build_trust_contract_metadata()
    assert classify_artifact_scope("heading_reasoning_trace", tc) == "advisory"
    assert classify_artifact_scope("classification_engine_output", tc) == "trusted_scope"


def test_classify_heading_reasoning_trace_trusted_when_phase2_gate_on(monkeypatch):
    monkeypatch.setattr(pss.settings, "PHASE2_REASONING_TRACE_TRUSTED_REQUIRED", True)
    tc = build_trust_contract_metadata()
    assert classify_artifact_scope("heading_reasoning_trace", tc) == "trusted_scope"


def test_line_provenance_snapshot_trusted_in_matrix():
    tc = build_trust_contract_metadata()
    assert classify_artifact_scope("line_provenance_snapshot", tc) == "trusted_scope"

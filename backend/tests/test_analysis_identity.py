"""Phase 1 — analysis identity helpers (decision_status derivation, promotion contract)."""

from app.models.analysis import AnalysisStatus, DecisionStatus
from app.services.analysis_identity_service import derive_decision_status


def test_derive_decision_status_instant_dev_is_degraded():
    assert (
        derive_decision_status(
            execution_status=AnalysisStatus.COMPLETE,
            result_json={"mode": "INSTANT_DEV"},
            blockers=[],
            trust_eligible=True,
        )
        == DecisionStatus.DEGRADED
    )


def test_derive_decision_status_blockers_imply_review():
    assert (
        derive_decision_status(
            execution_status=AnalysisStatus.COMPLETE,
            result_json={},
            blockers=["x"],
            trust_eligible=True,
        )
        == DecisionStatus.REVIEW_REQUIRED
    )


def test_derive_trusted_requires_trust_eligible():
    assert (
        derive_decision_status(
            execution_status=AnalysisStatus.COMPLETE,
            result_json={},
            blockers=[],
            trust_eligible=False,
        )
        == DecisionStatus.REVIEW_REQUIRED
    )


def test_derive_decision_status_trusted_when_gate_passes():
    assert (
        derive_decision_status(
            execution_status=AnalysisStatus.COMPLETE,
            result_json={},
            blockers=[],
            trust_eligible=True,
        )
        == DecisionStatus.TRUSTED
    )


def test_derive_decision_status_fast_local_is_degraded():
    assert (
        derive_decision_status(
            execution_status=AnalysisStatus.COMPLETE,
            result_json={"mode": "FAST_LOCAL_DEV"},
            blockers=[],
            trust_eligible=True,
        )
        == DecisionStatus.DEGRADED
    )


def test_derive_decision_status_not_set_for_failed():
    assert (
        derive_decision_status(
            execution_status=AnalysisStatus.FAILED,
            result_json={},
            blockers=[],
            trust_eligible=True,
        )
        is None
    )

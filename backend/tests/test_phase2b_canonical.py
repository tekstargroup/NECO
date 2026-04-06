"""Phase 2b — regulatory analysis scope, snapshot derivation, trust contract (unit tests)."""

from unittest.mock import AsyncMock, MagicMock
from uuid import uuid4

import pytest

from app.services.pipeline_stage_service import build_trust_contract_metadata
from app.services.regulatory_evaluation_service import regulatory_select_for_review
from app.services.review_snapshot_derivation import materialize_review_object_snapshot


def test_trust_contract_version_phase2_v3():
    tc = build_trust_contract_metadata()
    assert tc["version"] == "phase2_v3"
    assert tc.get("phase2b_regulatory_primary_key") == "regulatory_evaluations.analysis_id"
    assert tc.get("phase2b_review_snapshot_derivation") == "materialized_post_persist_from_canonical_db"
    keys = [r["artifact"] for r in tc["artifact_matrix"] if isinstance(r, dict)]
    assert "line_provenance_snapshot" in keys
    assert "regulatory_conditions_db" in keys


def test_regulatory_select_prefers_analysis_id():
    from app.models.review_record import ReviewRecord

    aid, rid = uuid4(), uuid4()
    review = MagicMock(spec=ReviewRecord)
    review.analysis_id = aid
    review.id = rid
    stmt = regulatory_select_for_review(review)
    compiled = str(stmt.compile(compile_kwargs={"literal_binds": False})).lower()
    assert "regulatory_evaluations" in compiled and "analysis" in compiled


def test_regulatory_select_fallback_review_id_only():
    from app.models.review_record import ReviewRecord

    rid = uuid4()
    review = MagicMock(spec=ReviewRecord)
    review.analysis_id = None
    review.id = rid
    stmt = regulatory_select_for_review(review)
    compiled = str(stmt.compile(compile_kwargs={"literal_binds": False})).lower()
    assert "regulatory_evaluations" in compiled and "review" in compiled


@pytest.mark.asyncio
async def test_materialize_early_exit_merges_reasoning_when_shipment_missing(monkeypatch):
    """If shipment row is missing, still attach derivation meta and call reasoning merge."""

    async def _noop_merge(_db, *, analysis_id, result_json):
        return None

    monkeypatch.setattr(
        "app.services.review_snapshot_derivation.merge_reasoning_traces_into_result_json",
        _noop_merge,
    )

    db = AsyncMock()
    result_mock = MagicMock()
    result_mock.scalar_one_or_none = MagicMock(return_value=None)
    db.execute = AsyncMock(return_value=result_mock)

    aid, sid, oid = uuid4(), uuid4(), uuid4()
    out = await materialize_review_object_snapshot(
        db,
        analysis_id=aid,
        shipment_id=sid,
        organization_id=oid,
        engine_result_json={"items": [], "shipment_id": str(sid)},
    )
    assert out["_snapshot_derivation"]["mode"] == "materialized_post_persist"

"""Pipeline stage ledger + trust mandatory list (Phase 1 increment)."""

import pytest

from app.services import pipeline_stage_service as pss
from app.services.pipeline_stage_service import MANDATORY_STAGES_FOR_TRUSTED, mandatory_stages_for_trusted
from app.models.analysis_pipeline_stage import PipelineStageName


def test_mandatory_stages_fine_grained_and_include_review_persist():
    assert PipelineStageName.DOCUMENT_EVIDENCE in MANDATORY_STAGES_FOR_TRUSTED
    assert PipelineStageName.LINE_ITEM_IMPORT in MANDATORY_STAGES_FOR_TRUSTED
    assert PipelineStageName.CLASSIFICATION in MANDATORY_STAGES_FOR_TRUSTED
    assert PipelineStageName.FACT_PERSIST in MANDATORY_STAGES_FOR_TRUSTED
    assert PipelineStageName.REGULATORY_ENGINE in MANDATORY_STAGES_FOR_TRUSTED
    assert PipelineStageName.REVIEW_REGULATORY_PERSIST in MANDATORY_STAGES_FOR_TRUSTED
    assert PipelineStageName.CLASSIFICATION_AND_FACTS not in MANDATORY_STAGES_FOR_TRUSTED
    assert PipelineStageName.DUTY_PSC_ADVISORY not in MANDATORY_STAGES_FOR_TRUSTED
    assert PipelineStageName.REASONING_TRACE_PERSIST not in MANDATORY_STAGES_FOR_TRUSTED


def test_reasoning_trace_not_mandatory_until_phase2_gate_enabled():
    assert PipelineStageName.REASONING_TRACE_PERSIST not in mandatory_stages_for_trusted()


def test_reasoning_trace_mandatory_when_phase2_gate_enabled(monkeypatch):
    monkeypatch.setattr(pss.settings, "PHASE2_REASONING_TRACE_TRUSTED_REQUIRED", True)
    stages = mandatory_stages_for_trusted()
    assert PipelineStageName.REASONING_TRACE_PERSIST in stages
    assert stages.index(PipelineStageName.REASONING_TRACE_PERSIST) > stages.index(PipelineStageName.FACT_PERSIST)


def test_analysis_id_from_task_id_accepts_plain_uuid_string():
    from app.services.analysis_task_ids import parse_analysis_id_from_celery_task_id
    import uuid

    u = uuid.uuid4()
    assert parse_analysis_id_from_celery_task_id(str(u)) == u


def test_analysis_id_from_task_id_accepts_inline_prefix():
    from app.services.analysis_task_ids import parse_analysis_id_from_celery_task_id
    import uuid

    u = uuid.uuid4()
    assert parse_analysis_id_from_celery_task_id(f"inline-{u}") == u

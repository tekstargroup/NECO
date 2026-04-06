"""Persisted pipeline stage runs — one row per (analysis_id, stage) for retries + TRUSTED gating."""

import enum
import uuid
from datetime import datetime

from sqlalchemy import Column, DateTime, ForeignKey, Integer, String, Text, UniqueConstraint
from sqlalchemy.dialects.postgresql import UUID, JSONB
from sqlalchemy import Enum as SQLEnum

from app.core.database import Base


class PipelineStageStatus(str, enum.Enum):
    PENDING = "PENDING"
    RUNNING = "RUNNING"
    SUCCEEDED = "SUCCEEDED"
    FAILED = "FAILED"
    SKIPPED = "SKIPPED"


class PipelineStageName:
    """String stage ids — also used in unique constraint."""

    # Legacy ledger rows only; new runs use fine-grained stages below.
    CORE_ANALYSIS = "CORE_ANALYSIS"

    DOCUMENT_EVIDENCE = "DOCUMENT_EVIDENCE"
    LINE_ITEM_IMPORT = "LINE_ITEM_IMPORT"
    # Legacy ledger rows only — replaced by CLASSIFICATION + FACT_PERSIST.
    CLASSIFICATION_AND_FACTS = "CLASSIFICATION_AND_FACTS"
    CLASSIFICATION = "CLASSIFICATION"
    FACT_PERSIST = "FACT_PERSIST"
    # Phase 2 — persisted heading reasoning trace rows; optional TRUSTED gate via settings.
    REASONING_TRACE_PERSIST = "REASONING_TRACE_PERSIST"
    # Tracked for diagnostics; not required for TRUSTED (duty/PSC are advisory this phase).
    DUTY_PSC_ADVISORY = "DUTY_PSC_ADVISORY"
    REGULATORY_ENGINE = "REGULATORY_ENGINE"
    REVIEW_REGULATORY_PERSIST = "REVIEW_REGULATORY_PERSIST"


class AnalysisPipelineStage(Base):
    __tablename__ = "analysis_pipeline_stages"
    __table_args__ = (
        UniqueConstraint("analysis_id", "stage", name="uq_pipeline_stages_analysis_stage"),
    )

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    analysis_id = Column(UUID(as_uuid=True), ForeignKey("analyses.id", ondelete="CASCADE"), nullable=False, index=True)
    shipment_id = Column(UUID(as_uuid=True), ForeignKey("shipments.id", ondelete="CASCADE"), nullable=False)
    organization_id = Column(UUID(as_uuid=True), ForeignKey("organizations.id"), nullable=False)
    stage = Column(String(64), nullable=False)
    status = Column(SQLEnum(PipelineStageStatus), nullable=False, default=PipelineStageStatus.PENDING)
    error_code = Column(Text, nullable=True)
    error_message = Column(Text, nullable=True)
    error_details = Column(JSONB, nullable=True)
    started_at = Column(DateTime, nullable=True)
    completed_at = Column(DateTime, nullable=True)
    ordinal = Column(Integer, nullable=False, default=0)

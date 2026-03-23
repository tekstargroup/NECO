"""
Tests for Audit Replay Service - Sprint 7

Tests cover:
- Audit replay matches snapshot
- AUDIT_MISMATCH emitted when underlying logic changes
- HTS version mismatch detection
"""

import pytest
from unittest.mock import AsyncMock
from uuid import uuid4

from app.models.review_record import ReviewRecord, ReviewableObjectType, ReviewStatus
from app.services.audit_replay_service import AuditReplayService, AuditMismatchFlag
from app.services.review_service import ReviewService


@pytest.fixture
def mock_db():
    """Mock database session."""
    from unittest.mock import MagicMock
    db = MagicMock()
    async def execute_mock(*args, **kwargs):
        return db._execute_result
    db.execute = execute_mock
    return db


@pytest.fixture
def audit_service(mock_db):
    """Create AuditReplayService instance."""
    return AuditReplayService(mock_db)


@pytest.fixture
def classification_record():
    """Sample classification review record."""
    return ReviewRecord(
        id=uuid4(),
        object_type=ReviewableObjectType.CLASSIFICATION,
        object_snapshot={
            "inputs": {
                "description": "Women's cotton knit sweater",
                "country_of_origin": "CN"
            },
            "output": {
                "success": True,
                "status": "SUCCESS",
                "candidates": []
            },
            "hts_version_id": "792bb867-c549-4769-80ca-d9d1adc883a3"
        },
        hts_version_id="792bb867-c549-4769-80ca-d9d1adc883a3",
        status=ReviewStatus.REVIEWED_ACCEPTED,
        created_by="analyst_1"
    )


@pytest.fixture
def psc_radar_record():
    """Sample PSC Radar review record."""
    return ReviewRecord(
        id=uuid4(),
        object_type=ReviewableObjectType.PSC_RADAR,
        object_snapshot={
            "inputs": {
                "product_description": "Women's cotton knit sweater",
                "declared_hts_code": "6112.20.20.30"
            },
            "output": {
                "alternatives": [],
                "flags": []
            },
            "hts_version_id": "792bb867-c549-4769-80ca-d9d1adc883a3"
        },
        hts_version_id="792bb867-c549-4769-80ca-d9d1adc883a3",
        status=ReviewStatus.REVIEWED_ACCEPTED,
        created_by="analyst_1"
    )


@pytest.mark.asyncio
async def test_audit_replay_matches_snapshot(audit_service, classification_record):
    """Test: Audit replay matches snapshot structure."""
    result = await audit_service.replay_classification(classification_record)
    
    assert result.matches is True
    assert AuditMismatchFlag.AUDIT_MISMATCH not in result.flags


@pytest.mark.asyncio
async def test_audit_replay_hts_version_mismatch(audit_service):
    """Test: AUDIT_MISMATCH emitted when HTS version doesn't match."""
    record = ReviewRecord(
        id=uuid4(),
        object_type=ReviewableObjectType.CLASSIFICATION,
        object_snapshot={
            "inputs": {},
            "output": {},
            "hts_version_id": "old-version-id"  # Wrong version
        },
        hts_version_id="old-version-id",
        status=ReviewStatus.REVIEWED_ACCEPTED,
        created_by="analyst_1"
    )
    
    result = await audit_service.replay_classification(record)
    
    assert result.matches is False
    assert AuditMismatchFlag.AUDIT_MISMATCH in result.flags
    assert "hts_version_mismatch" in result.mismatch_fields


@pytest.mark.asyncio
async def test_audit_replay_missing_fields(audit_service):
    """Test: AUDIT_MISMATCH emitted when snapshot missing required fields."""
    record = ReviewRecord(
        id=uuid4(),
        object_type=ReviewableObjectType.CLASSIFICATION,
        object_snapshot={
            # Missing inputs, output, hts_version_id
        },
        hts_version_id="792bb867-c549-4769-80ca-d9d1adc883a3",
        status=ReviewStatus.REVIEWED_ACCEPTED,
        created_by="analyst_1"
    )
    
    result = await audit_service.replay_classification(record)
    
    assert result.matches is False
    assert AuditMismatchFlag.AUDIT_MISMATCH in result.flags
    assert "missing_fields" in result.mismatch_fields


@pytest.mark.asyncio
async def test_audit_replay_psc_radar(audit_service, psc_radar_record):
    """Test: Audit replay for PSC Radar."""
    result = await audit_service.replay_psc_radar(psc_radar_record)
    
    assert result.matches is True
    assert AuditMismatchFlag.AUDIT_MISMATCH not in result.flags


@pytest.mark.asyncio
async def test_verify_review_record(audit_service, mock_db, classification_record):
    """Test: Verify review record by ID."""
    from unittest.mock import MagicMock
    mock_result = MagicMock()
    mock_result.scalar_one_or_none = MagicMock(return_value=classification_record)
    mock_db._execute_result = mock_result
    audit_service.db = mock_db
    
    result = await audit_service.verify_review_record(classification_record.id)
    
    assert result.matches is True


@pytest.mark.asyncio
async def test_verify_review_record_not_found(audit_service, mock_db):
    """Test: Verify non-existent review record."""
    from unittest.mock import MagicMock
    mock_result = MagicMock()
    mock_result.scalar_one_or_none = MagicMock(return_value=None)
    mock_db._execute_result = mock_result
    audit_service.db = mock_db
    
    result = await audit_service.verify_review_record(uuid4())
    
    assert result.matches is False
    assert "not found" in result.mismatch_fields.get("error", "")

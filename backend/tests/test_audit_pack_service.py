"""
Tests for Audit Pack Service - Sprint 8

Tests cover:
- Audit pack completeness
- Export reproducibility
- JSON/PDF/ZIP export
"""

import pytest
from unittest.mock import AsyncMock, MagicMock
from datetime import datetime, timedelta
from uuid import uuid4
from app.services.audit_pack_service import AuditPackService
from app.models.review_record import ReviewRecord, ReviewStatus, ReviewableObjectType


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
def audit_pack_service(mock_db):
    """Create AuditPackService instance."""
    return AuditPackService(mock_db)


@pytest.mark.asyncio
async def test_generate_audit_pack_by_review_ids(audit_pack_service, mock_db):
    """Test: Generate audit pack for specific review IDs."""
    from unittest.mock import MagicMock
    
    review_id = uuid4()
    record = ReviewRecord(
        id=review_id,
        object_type=ReviewableObjectType.CLASSIFICATION,
        object_snapshot={"inputs": {}, "output": {}},
        hts_version_id="792bb867-c549-4769-80ca-d9d1adc883a3",
        status=ReviewStatus.REVIEWED_ACCEPTED,
        created_by="analyst_1"
    )
    
    mock_result = MagicMock()
    mock_result.scalar_one_or_none = MagicMock(return_value=record)
    mock_db._execute_result = mock_result
    
    pack = await audit_pack_service.generate_audit_pack(review_ids=[review_id])
    
    assert pack["audit_pack_version"] == "2.0"
    assert "hts_version_id" in pack
    assert "disclaimer" in pack
    assert "review_records" in pack
    assert len(pack["review_records"]) == 1
    assert pack["review_records"][0]["review_id"] == str(review_id)


@pytest.mark.asyncio
async def test_generate_audit_pack_by_time_range(audit_pack_service, mock_db):
    """Test: Generate audit pack for time range."""
    from unittest.mock import MagicMock
    
    # Mock empty result
    mock_result = MagicMock()
    mock_scalars = MagicMock()
    mock_scalars.all = MagicMock(return_value=[])
    mock_result.scalars = MagicMock(return_value=mock_scalars)
    
    async def execute_mock(*args, **kwargs):
        return mock_result
    
    mock_db.execute = execute_mock
    audit_pack_service.db = mock_db
    
    start = datetime.utcnow() - timedelta(days=7)
    end = datetime.utcnow()
    
    pack = await audit_pack_service.generate_audit_pack(
        time_range_start=start,
        time_range_end=end,
        include_audit_replay=False
    )
    
    assert pack["summary"]["time_range"]["start"] == start.isoformat()
    assert pack["summary"]["time_range"]["end"] == end.isoformat()


@pytest.mark.asyncio
async def test_export_json(audit_pack_service):
    """Test: JSON export is valid."""
    import json
    
    pack = {
        "audit_pack_version": "1.0",
        "generated_at": datetime.utcnow().isoformat(),
        "review_records": []
    }
    
    json_str = audit_pack_service.export_json(pack)
    
    # Should be valid JSON
    parsed = json.loads(json_str)
    assert parsed["audit_pack_version"] == "1.0"


@pytest.mark.asyncio
async def test_export_pdf(audit_pack_service):
    """Test: PDF export generates text content."""
    pack = {
        "audit_pack_version": "1.0",
        "generated_at": datetime.utcnow().isoformat(),
        "hts_version_id": "792bb867-c549-4769-80ca-d9d1adc883a3",
        "disclaimer": "Test disclaimer",
        "summary": {"total_records": 0},
        "review_records": []
    }
    
    pdf_content = audit_pack_service.export_pdf(pack)
    
    assert "NECO AUDIT PACK" in pdf_content
    assert "disclaimer" in pdf_content.lower() or "Test disclaimer" in pdf_content


@pytest.mark.asyncio
async def test_export_zip(audit_pack_service):
    """Test: ZIP export creates valid ZIP file."""
    import zipfile
    import io
    
    pack = {
        "audit_pack_version": "1.0",
        "generated_at": datetime.utcnow().isoformat(),
        "hts_version_id": "792bb867-c549-4769-80ca-d9d1adc883a3",
        "disclaimer": "Test disclaimer",
        "summary": {"total_records": 0},
        "review_records": []
    }
    
    zip_content = audit_pack_service.export_zip(pack)
    
    # Should be valid ZIP
    zip_file = zipfile.ZipFile(io.BytesIO(zip_content))
    assert "audit_pack.json" in zip_file.namelist()
    assert "audit_pack.txt" in zip_file.namelist()
    assert "README.txt" in zip_file.namelist()


@pytest.mark.asyncio
async def test_audit_pack_includes_replay_results(audit_pack_service, mock_db):
    """Test: Audit pack includes replay results when requested."""
    from unittest.mock import MagicMock
    
    review_id = uuid4()
    record = ReviewRecord(
        id=review_id,
        object_type=ReviewableObjectType.CLASSIFICATION,
        object_snapshot={"inputs": {}, "output": {}, "hts_version_id": "792bb867-c549-4769-80ca-d9d1adc883a3"},
        hts_version_id="792bb867-c549-4769-80ca-d9d1adc883a3",
        status=ReviewStatus.REVIEWED_ACCEPTED,
        created_by="analyst_1",
        created_at=datetime.utcnow()
    )
    
    # Mock record fetch and audit replay
    call_count = [0]
    async def execute_side_effect(*args, **kwargs):
        call_count[0] += 1
        mock_result = MagicMock()
        mock_result.scalar_one_or_none = MagicMock(return_value=record)
        return mock_result
    
    mock_db.execute = execute_side_effect
    audit_pack_service.db = mock_db
    
    pack = await audit_pack_service.generate_audit_pack(
        review_ids=[review_id],
        include_audit_replay=True
    )
    
    assert "audit_replay_results" in pack
    # Note: Actual replay verification would require proper service mocking

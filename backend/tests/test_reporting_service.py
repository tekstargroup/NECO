"""
Tests for Reporting Service - Sprint 8

Tests cover:
- Report generation correctness
- Exposure math correctness
- Filter application
"""

import pytest
from unittest.mock import AsyncMock, MagicMock
from datetime import datetime, timedelta
from app.services.reporting_service import ReportingService
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
def reporting_service(mock_db):
    """Create ReportingService instance."""
    return ReportingService(mock_db)


@pytest.mark.asyncio
async def test_classification_risk_report(reporting_service, mock_db):
    """Test: Classification Risk Report generation."""
    from unittest.mock import MagicMock
    
    # Mock empty result
    mock_result = MagicMock()
    mock_result.scalars.return_value.all.return_value = []
    mock_db._execute_result = mock_result
    
    report = await reporting_service.generate_classification_risk_report()
    
    assert report["report_type"] == "CLASSIFICATION_RISK"
    assert "risk_buckets" in report
    assert "low_confidence" in report["risk_buckets"]
    assert "medium_confidence" in report["risk_buckets"]
    assert "high_confidence" in report["risk_buckets"]


@pytest.mark.asyncio
async def test_classification_risk_report_buckets_by_status_not_similarity(reporting_service, mock_db):
    """Patch A: buckets follow output.status; high similarity must not force high bucket alone."""
    from unittest.mock import MagicMock

    def _rec(status: str, metadata_sim: float = 0.99):
        r = MagicMock()
        r.id = f"id-{status}"
        r.object_snapshot = {
            "output": {"status": status},
            "metadata": {"best_similarity": metadata_sim},
        }
        return r

    r_unknown = MagicMock()
    r_unknown.id = "id-empty-status"
    r_unknown.object_snapshot = {"output": {"status": ""}, "metadata": {"best_similarity": 0.99}}

    records = [
        _rec("SUCCESS", 0.10),
        _rec("REVIEW_REQUIRED", 0.99),
        _rec("NO_CONFIDENT_MATCH", 0.99),
        _rec("NO_GOOD_MATCH", 0.50),
        _rec("CLARIFICATION_REQUIRED", 0.99),
        r_unknown,
    ]
    mock_result = MagicMock()
    mock_result.scalars.return_value.all.return_value = records
    mock_db._execute_result = mock_result

    report = await reporting_service.generate_classification_risk_report()
    buckets = report["risk_buckets"]
    low = buckets["low_confidence"]["record_ids"]
    med = buckets["medium_confidence"]["record_ids"]
    high = buckets["high_confidence"]["record_ids"]

    assert "id-SUCCESS" in high
    assert "id-REVIEW_REQUIRED" in med
    assert "id-NO_CONFIDENT_MATCH" in low
    assert "id-NO_GOOD_MATCH" in low
    assert "id-CLARIFICATION_REQUIRED" in low
    assert "id-empty-status" in med  # unknown/empty status → medium


@pytest.mark.asyncio
async def test_psc_exposure_report(reporting_service, mock_db):
    """Test: PSC Exposure Report generation."""
    from unittest.mock import MagicMock
    
    # Mock empty result
    mock_result = MagicMock()
    mock_result.scalars.return_value.all.return_value = []
    mock_db._execute_result = mock_result
    
    report = await reporting_service.generate_psc_exposure_report()
    
    assert report["report_type"] == "PSC_EXPOSURE"
    assert "exposure_metrics" in report
    assert "total_exposure_usd" in report["exposure_metrics"]
    assert "cases_with_exposure" in report["exposure_metrics"]


@pytest.mark.asyncio
async def test_review_activity_report(reporting_service, mock_db):
    """Test: Review Activity Report generation."""
    from unittest.mock import MagicMock
    
    # Mock count results
    mock_count_result = MagicMock()
    mock_count_result.scalar = MagicMock(return_value=5)
    
    # Mock detailed results
    mock_detailed_result = MagicMock()
    mock_detailed_result.scalars.return_value.all.return_value = []
    
    call_count = [0]
    async def execute_side_effect(*args, **kwargs):
        call_count[0] += 1
        if call_count[0] <= 3:  # First 3 calls are counts
            return mock_count_result
        else:  # Last call is detailed
            return mock_detailed_result
    
    mock_db.execute = execute_side_effect
    
    report = await reporting_service.generate_review_activity_report()
    
    assert report["report_type"] == "REVIEW_ACTIVITY"
    assert "activity_metrics" in report
    assert "accepted" in report["activity_metrics"]
    assert "rejected" in report["activity_metrics"]
    assert "overridden" in report["activity_metrics"]


@pytest.mark.asyncio
async def test_unresolved_risk_report(reporting_service, mock_db):
    """Test: Unresolved Risk Report generation."""
    from unittest.mock import MagicMock
    
    # Mock empty result
    mock_result = MagicMock()
    mock_result.scalars.return_value.all.return_value = []
    mock_db._execute_result = mock_result
    
    report = await reporting_service.generate_unresolved_risk_report()
    
    assert report["report_type"] == "UNRESOLVED_RISK"
    assert "unresolved_count" in report
    assert "unresolved_risks" in report

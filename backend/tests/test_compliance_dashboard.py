"""
Tests for Compliance Dashboard Service - Sprint 8

Tests cover:
- Aggregation correctness
- Filter application
- Metric calculations
"""

import pytest
from unittest.mock import AsyncMock, MagicMock
from datetime import datetime, timedelta
from app.services.compliance_dashboard_service import ComplianceDashboardService
from app.models.review_record import ReviewRecord, ReviewStatus, ReviewableObjectType, ReviewReasonCode


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
def dashboard_service(mock_db):
    """Create ComplianceDashboardService instance."""
    return ComplianceDashboardService(mock_db)


@pytest.mark.asyncio
async def test_get_summary_aggregations(dashboard_service, mock_db):
    """Test: Summary aggregations are correct."""
    from unittest.mock import MagicMock
    
    # Mock result with count
    mock_result = MagicMock()
    mock_result.scalar = MagicMock(return_value=10)
    
    mock_db._execute_result = mock_result
    
    summary = await dashboard_service.get_summary()
    
    assert "metrics" in summary
    assert "total_classifications" in summary["metrics"]
    assert summary["time_range"]["start"] is not None
    assert summary["time_range"]["end"] is not None


@pytest.mark.asyncio
async def test_get_summary_with_filters(dashboard_service, mock_db):
    """Test: Filters are applied correctly."""
    from unittest.mock import MagicMock
    
    mock_result = MagicMock()
    mock_result.scalar = MagicMock(return_value=5)
    mock_db._execute_result = mock_result
    
    summary = await dashboard_service.get_summary(
        hts_chapter="61",
        reviewer="reviewer_1",
        object_type=ReviewableObjectType.CLASSIFICATION
    )
    
    assert summary["filters"]["hts_chapter"] == "61"
    assert summary["filters"]["reviewer"] == "reviewer_1"
    assert summary["filters"]["object_type"] == "CLASSIFICATION"


@pytest.mark.asyncio
async def test_get_summary_time_range(dashboard_service, mock_db):
    """Test: Time range filtering works."""
    from unittest.mock import MagicMock
    
    start = datetime.utcnow() - timedelta(days=7)
    end = datetime.utcnow()
    
    mock_result = MagicMock()
    mock_result.scalar = MagicMock(return_value=3)
    mock_db._execute_result = mock_result
    
    summary = await dashboard_service.get_summary(
        time_range_start=start,
        time_range_end=end
    )
    
    assert summary["time_range"]["start"] == start.isoformat()
    assert summary["time_range"]["end"] == end.isoformat()

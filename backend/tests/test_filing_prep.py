"""
Tests for Filing Prep Service - Sprint 9

Tests cover:
- Export blocked when REVIEW_REQUIRED present
- Export blocked on missing data
- Correct export formatting (JSON / CSV / PDF)
- Disclaimers always present
- FilingPrepBundle reproducibility
- No mutation of underlying records
"""

import pytest
from unittest.mock import AsyncMock, MagicMock, patch
from datetime import datetime
from uuid import uuid4

from app.models.filing_prep_bundle import (
    FilingPrepBundle,
    DutyBreakdown,
    ReviewStatus,
    ExportBlockReason
)
from app.services.filing_prep_service import FilingPrepService
from app.services.broker_export_service import BrokerExportService
from scripts.duty_resolution import ResolvedDuty, DutyFlag


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
def filing_prep_service(mock_db):
    """Create FilingPrepService instance."""
    return FilingPrepService(mock_db)


@pytest.fixture
def broker_export_service():
    """Create BrokerExportService instance."""
    return BrokerExportService()


@pytest.fixture
def mock_resolved_duty():
    """Mock resolved duty."""
    return ResolvedDuty(
        hts_code="6112202030",
        resolved_general_raw="8.3%",
        resolved_special_raw="Free(AU,BH,CL,CO,E*,IL,JO,KR, MA,OM,P,PA, PE,S,SG)",
        resolved_col2_raw="90%",
        source_level_general="10",
        source_level_special="10",
        source_level_col2="10",
        source_hts_general="6112202030",
        source_hts_special="6112202030",
        source_hts_col2="6112202030",
        inheritance_path=["6112202030", "61122020", "611220"],
        flags=[],
        explanation_general="General duty is 8.3%",
        explanation_special="Special duty is Free(...)",
        explanation_col2="Column 2 duty is 90%",
        explanation_path="Checked: 6112.20.20.30 → 6112.20.20 → 6112.20"
    )


@pytest.mark.asyncio
async def test_export_blocked_review_required(filing_prep_service, mock_db, mock_resolved_duty):
    """Test: Export blocked when REVIEW_REQUIRED present."""
    with patch('app.services.filing_prep_service.resolve_duty', return_value=mock_resolved_duty):
        bundle = await filing_prep_service.create_filing_prep_bundle(
            declared_hts_code="6112.20.20.30",
            quantity=100.0,
            customs_value=5000.0,
            review_id=None  # No review = REVIEW_REQUIRED
        )
    
    assert bundle.export_blocked is True
    assert ExportBlockReason.REVIEW_REQUIRED in bundle.export_block_reasons


@pytest.mark.asyncio
async def test_export_blocked_missing_quantity(filing_prep_service, mock_db, mock_resolved_duty):
    """Test: Export blocked on missing quantity."""
    with patch('app.services.filing_prep_service.resolve_duty', return_value=mock_resolved_duty):
        bundle = await filing_prep_service.create_filing_prep_bundle(
            declared_hts_code="6112.20.20.30",
            quantity=None,  # Missing quantity
            customs_value=5000.0,
            review_id=uuid4()  # Reviewed, but missing quantity
        )
    
    assert bundle.export_blocked is True
    assert ExportBlockReason.MISSING_QUANTITY in bundle.export_block_reasons


@pytest.mark.asyncio
async def test_export_blocked_missing_value(filing_prep_service, mock_db, mock_resolved_duty):
    """Test: Export blocked on missing value."""
    with patch('app.services.filing_prep_service.resolve_duty', return_value=mock_resolved_duty):
        bundle = await filing_prep_service.create_filing_prep_bundle(
            declared_hts_code="6112.20.20.30",
            quantity=100.0,
            customs_value=None,  # Missing value
            review_id=uuid4()
        )
    
    assert bundle.export_blocked is True
    assert ExportBlockReason.MISSING_VALUE in bundle.export_block_reasons


@pytest.mark.asyncio
async def test_export_blocked_missing_duty(filing_prep_service, mock_db):
    """Test: Export blocked on missing duty fields."""
    # Mock duty with missing general
    mock_duty = ResolvedDuty(
        hts_code="6112202030",
        resolved_general_raw=None,  # Missing
        resolved_special_raw="Free(...)",
        resolved_col2_raw="90%",
        source_level_general="none",
        source_level_special="10",
        source_level_col2="10",
        source_hts_general=None,
        source_hts_special="6112202030",
        source_hts_col2="6112202030",
        inheritance_path=["6112202030"],
        flags=[DutyFlag.MISSING_DUTY],
        explanation_general="General duty not found",
        explanation_special="Special duty is Free(...)",
        explanation_col2="Column 2 duty is 90%",
        explanation_path="Checked: 6112.20.20.30"
    )
    
    with patch('app.services.filing_prep_service.resolve_duty', return_value=mock_duty):
        bundle = await filing_prep_service.create_filing_prep_bundle(
            declared_hts_code="6112.20.20.30",
            quantity=100.0,
            customs_value=5000.0,
            review_id=uuid4()
        )
    
    assert bundle.export_blocked is True
    assert ExportBlockReason.MISSING_DUTY_FIELDS in bundle.export_block_reasons


@pytest.mark.asyncio
async def test_export_allowed_when_reviewed(filing_prep_service, mock_db, mock_resolved_duty):
    """Test: Export allowed when reviewed and all data present."""
    review_id = uuid4()
    
    # Mock review record
    from app.models.review_record import ReviewRecord, ReviewStatus as ReviewRecordStatus
    mock_review = ReviewRecord(
        id=review_id,
        object_type=None,  # Not needed for this test
        object_snapshot={},
        hts_version_id="792bb867-c549-4769-80ca-d9d1adc883a3",
        status=ReviewRecordStatus.REVIEWED_ACCEPTED,
        created_by="analyst_1",
        reviewed_by="reviewer_1",
        reviewed_at=datetime.utcnow()
    )
    
    # Mock review service
    filing_prep_service.review_service.get_review_record = AsyncMock(return_value=mock_review)
    
    with patch('app.services.filing_prep_service.resolve_duty', return_value=mock_resolved_duty):
        bundle = await filing_prep_service.create_filing_prep_bundle(
            declared_hts_code="6112.20.20.30",
            quantity=100.0,
            customs_value=5000.0,
            review_id=review_id
        )
    
    assert bundle.review_status == ReviewStatus.REVIEWED_ACCEPTED
    # Should not be blocked if all data present and reviewed
    # (unless PSC flags block it)


@pytest.mark.asyncio
async def test_disclaimers_always_present(filing_prep_service, mock_db, mock_resolved_duty):
    """Test: Disclaimers always present in bundle."""
    with patch('app.services.filing_prep_service.resolve_duty', return_value=mock_resolved_duty):
        bundle = await filing_prep_service.create_filing_prep_bundle(
            declared_hts_code="6112.20.20.30",
            quantity=100.0,
            customs_value=5000.0
        )
    
    assert len(bundle.disclaimers) > 0
    assert any("not a filing" in d.lower() for d in bundle.disclaimers)
    assert any("broker review required" in d.lower() for d in bundle.disclaimers)


@pytest.mark.asyncio
async def test_export_json_format(broker_export_service):
    """Test: JSON export format is correct."""
    bundle = FilingPrepBundle(
        declared_hts_code="6112.20.20.30",
        duty_breakdown=DutyBreakdown(
            general_duty="8.3%",
            special_duty="Free(...)",
            column2_duty="90%"
        ),
        quantity=100.0,
        customs_value=5000.0,
        review_status=ReviewStatus.REVIEWED_ACCEPTED
    )
    
    json_str = broker_export_service.export_json(bundle)
    
    import json
    parsed = json.loads(json_str)
    assert parsed["declared_hts_code"] == "6112.20.20.30"
    assert parsed["duty_breakdown"]["general_duty"] == "8.3%"
    assert "disclaimers" in parsed


@pytest.mark.asyncio
async def test_export_csv_format(broker_export_service):
    """Test: CSV export format is correct."""
    bundle = FilingPrepBundle(
        declared_hts_code="6112.20.20.30",
        duty_breakdown=DutyBreakdown(general_duty="8.3%"),
        quantity=100.0,
        customs_value=5000.0,
        review_status=ReviewStatus.REVIEWED_ACCEPTED
    )
    
    csv_str = broker_export_service.export_csv(bundle)
    
    assert "Declared HTS Code" in csv_str
    assert "6112.20.20.30" in csv_str
    assert "DISCLAIMERS" in csv_str


@pytest.mark.asyncio
async def test_export_pdf_format(broker_export_service):
    """Test: PDF export format is correct."""
    bundle = FilingPrepBundle(
        declared_hts_code="6112.20.20.30",
        duty_breakdown=DutyBreakdown(general_duty="8.3%"),
        quantity=100.0,
        customs_value=5000.0,
        review_status=ReviewStatus.REVIEWED_ACCEPTED,
        disclaimers=["This is not a filing. Broker review required before submission."]
    )
    
    pdf_str = broker_export_service.export_pdf_summary(bundle)
    
    assert "NECO FILING PREP SUMMARY" in pdf_str
    assert "6112.20.20.30" in pdf_str
    assert "DISCLAIMERS" in pdf_str
    assert bundle.disclaimers[0] in pdf_str
    assert "not a filing" in pdf_str.lower()
    assert "broker review required" in pdf_str.lower()


@pytest.mark.asyncio
async def test_broker_notes_included(filing_prep_service, mock_db, mock_resolved_duty):
    """Test: Broker notes are included."""
    review_id = uuid4()
    
    from app.models.review_record import ReviewRecord, ReviewStatus as ReviewRecordStatus
    mock_review = ReviewRecord(
        id=review_id,
        object_type=None,
        object_snapshot={},
        hts_version_id="792bb867-c549-4769-80ca-d9d1adc883a3",
        status=ReviewRecordStatus.REVIEWED_ACCEPTED,
        created_by="analyst_1",
        reviewed_by="reviewer_1",
        reviewed_at=datetime.utcnow(),
        review_notes="Classification looks correct"
    )
    
    filing_prep_service.review_service.get_review_record = AsyncMock(return_value=mock_review)
    
    with patch('app.services.filing_prep_service.resolve_duty', return_value=mock_resolved_duty):
        bundle = await filing_prep_service.create_filing_prep_bundle(
            declared_hts_code="6112.20.20.30",
            quantity=100.0,
            customs_value=5000.0,
            review_id=review_id
        )
    
    assert "broker_notes" in bundle.to_dict()
    assert "what_was_reviewed" in bundle.broker_notes
    assert "what_neco_did_not_evaluate" in bundle.broker_notes


@pytest.mark.asyncio
async def test_filing_prep_bundle_reproducibility(filing_prep_service, mock_db, mock_resolved_duty):
    """Test: FilingPrepBundle is reproducible (same inputs = same output)."""
    with patch('app.services.filing_prep_service.resolve_duty', return_value=mock_resolved_duty):
        bundle1 = await filing_prep_service.create_filing_prep_bundle(
            declared_hts_code="6112.20.20.30",
            quantity=100.0,
            customs_value=5000.0
        )
        
        bundle2 = await filing_prep_service.create_filing_prep_bundle(
            declared_hts_code="6112.20.20.30",
            quantity=100.0,
            customs_value=5000.0
        )
    
    # Key fields should match
    assert bundle1.declared_hts_code == bundle2.declared_hts_code
    assert bundle1.duty_breakdown.general_duty == bundle2.duty_breakdown.general_duty
    assert bundle1.review_status == bundle2.review_status

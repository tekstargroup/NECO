"""
Tests for Review Service - Sprint 7

Tests cover:
- Valid state transitions
- Invalid state transitions rejected
- Override creates new record, does not mutate old
- Reviewer cannot review own draft
- RBAC enforcement
"""

import pytest
from unittest.mock import AsyncMock
from uuid import uuid4
from datetime import datetime

from app.models.review_record import (
    ReviewRecord,
    ReviewableObjectType,
    ReviewStatus,
    ReviewReasonCode
)
from app.services.review_service import ReviewService
from app.core.rbac import UserRole


@pytest.fixture
def mock_db():
    """Mock database session."""
    from unittest.mock import MagicMock
    db = MagicMock()
    db.flush = AsyncMock()
    db.add = MagicMock()
    # execute needs to be async
    async def execute_mock(*args, **kwargs):
        return db._execute_result
    db.execute = execute_mock
    return db


@pytest.fixture
def review_service(mock_db):
    """Create ReviewService instance."""
    return ReviewService(mock_db)


@pytest.fixture
def classification_snapshot():
    """Sample classification snapshot."""
    return {
        "inputs": {
            "description": "Women's cotton knit sweater",
            "country_of_origin": "CN",
            "value": 5000.0,
            "quantity": 100
        },
        "output": {
            "success": True,
            "status": "SUCCESS",
            "candidates": [
                {
                    "hts_code": "6112.20.20.30",
                    "final_score": 0.85
                }
            ]
        },
        "hts_version_id": "792bb867-c549-4769-80ca-d9d1adc883a3"
    }


@pytest.mark.asyncio
async def test_create_review_record(review_service, classification_snapshot):
    """Test creating a review record."""
    # Mock the add and flush
    review_service.db.add = AsyncMock()
    
    record = await review_service.create_review_record(
        object_type=ReviewableObjectType.CLASSIFICATION,
        object_snapshot=classification_snapshot,
        created_by="analyst_1",
        initial_status=ReviewStatus.DRAFT
    )
    
    assert record.object_type == ReviewableObjectType.CLASSIFICATION
    assert record.status == ReviewStatus.DRAFT
    assert record.created_by == "analyst_1"
    assert record.hts_version_id == "792bb867-c549-4769-80ca-d9d1adc883a3"
    assert "_snapshot_created_at" in record.object_snapshot
    review_service.db.add.assert_called_once()


@pytest.mark.asyncio
async def test_valid_state_transition_draft_to_review_required(review_service, mock_db):
    """Test valid transition: DRAFT -> REVIEW_REQUIRED."""
    # Create mock record
    record = ReviewRecord(
        id=uuid4(),
        object_type=ReviewableObjectType.CLASSIFICATION,
        object_snapshot={},
        hts_version_id="792bb867-c549-4769-80ca-d9d1adc883a3",
        status=ReviewStatus.DRAFT,
        created_by="analyst_1"
    )
    
    # Mock fetch - setup execute to return result with scalar_one_or_none
    from unittest.mock import MagicMock
    mock_result = MagicMock()
    mock_result.scalar_one_or_none = MagicMock(return_value=record)
    mock_db._execute_result = mock_result
    review_service.db = mock_db
    
    updated = await review_service.transition_status(
        review_id=record.id,
        new_status=ReviewStatus.REVIEW_REQUIRED,
        reviewed_by="analyst_1",
        user_role=UserRole.ANALYST.value,
        reason_code=ReviewReasonCode.MANUAL_CREATION
    )
    
    assert updated.status == ReviewStatus.REVIEW_REQUIRED
    assert updated.reviewed_by == "analyst_1"


@pytest.mark.asyncio
async def test_valid_state_transition_to_reviewed_accepted(review_service, mock_db):
    """Test valid transition: REVIEW_REQUIRED -> REVIEWED_ACCEPTED."""
    record = ReviewRecord(
        id=uuid4(),
        object_type=ReviewableObjectType.CLASSIFICATION,
        object_snapshot={},
        hts_version_id="792bb867-c549-4769-80ca-d9d1adc883a3",
        status=ReviewStatus.REVIEW_REQUIRED,
        created_by="analyst_1"
    )
    
    from unittest.mock import MagicMock
    mock_result = MagicMock()
    mock_result.scalar_one_or_none = MagicMock(return_value=record)
    mock_db._execute_result = mock_result
    review_service.db = mock_db
    
    updated = await review_service.transition_status(
        review_id=record.id,
        new_status=ReviewStatus.REVIEWED_ACCEPTED,
        reviewed_by="reviewer_1",
        user_role=UserRole.REVIEWER.value,
        reason_code=ReviewReasonCode.ACCEPTED_AS_IS,
        notes="Looks correct"
    )
    
    assert updated.status == ReviewStatus.REVIEWED_ACCEPTED
    assert updated.reviewed_by == "reviewer_1"
    assert updated.review_notes == "Looks correct"


@pytest.mark.asyncio
async def test_invalid_state_transition_from_terminal(review_service, mock_db):
    """Test invalid transition: Cannot transition from terminal state."""
    record = ReviewRecord(
        id=uuid4(),
        object_type=ReviewableObjectType.CLASSIFICATION,
        object_snapshot={},
        hts_version_id="792bb867-c549-4769-80ca-d9d1adc883a3",
        status=ReviewStatus.REVIEWED_ACCEPTED,  # Terminal state
        created_by="analyst_1"
    )
    
    from unittest.mock import MagicMock
    mock_result = MagicMock()
    mock_result.scalar_one_or_none = MagicMock(return_value=record)
    mock_db._execute_result = mock_result
    review_service.db = mock_db
    
    with pytest.raises(ValueError, match="Cannot transition from terminal state"):
        await review_service.transition_status(
            review_id=record.id,
            new_status=ReviewStatus.REVIEW_REQUIRED,
            reviewed_by="reviewer_1",
            user_role=UserRole.REVIEWER.value,
            reason_code=ReviewReasonCode.MANUAL_CREATION
        )


@pytest.mark.asyncio
async def test_reviewer_cannot_review_own_submission(review_service, mock_db):
    """Test: Reviewer cannot review their own submission."""
    record = ReviewRecord(
        id=uuid4(),
        object_type=ReviewableObjectType.CLASSIFICATION,
        object_snapshot={},
        hts_version_id="792bb867-c549-4769-80ca-d9d1adc883a3",
        status=ReviewStatus.REVIEW_REQUIRED,
        created_by="reviewer_1"  # Same as reviewer
    )
    
    from unittest.mock import MagicMock
    mock_result = MagicMock()
    mock_result.scalar_one_or_none = MagicMock(return_value=record)
    mock_db._execute_result = mock_result
    review_service.db = mock_db
    
    with pytest.raises(ValueError, match="Reviewer cannot review their own submission"):
        await review_service.transition_status(
            review_id=record.id,
            new_status=ReviewStatus.REVIEWED_ACCEPTED,
            reviewed_by="reviewer_1",  # Same as creator
            user_role=UserRole.REVIEWER.value,
            reason_code=ReviewReasonCode.ACCEPTED_AS_IS
        )


@pytest.mark.asyncio
async def test_only_reviewer_can_finalize(review_service, mock_db):
    """Test: Only REVIEWER can finalize (accept/reject)."""
    record = ReviewRecord(
        id=uuid4(),
        object_type=ReviewableObjectType.CLASSIFICATION,
        object_snapshot={},
        hts_version_id="792bb867-c549-4769-80ca-d9d1adc883a3",
        status=ReviewStatus.REVIEW_REQUIRED,
        created_by="analyst_1"
    )
    
    from unittest.mock import MagicMock
    mock_result = MagicMock()
    mock_result.scalar_one_or_none = MagicMock(return_value=record)
    mock_db._execute_result = mock_result
    review_service.db = mock_db
    
    with pytest.raises(ValueError, match="Only REVIEWER can transition"):
        await review_service.transition_status(
            review_id=record.id,
            new_status=ReviewStatus.REVIEWED_ACCEPTED,
            reviewed_by="analyst_1",
            user_role=UserRole.ANALYST.value,  # Not REVIEWER
            reason_code=ReviewReasonCode.ACCEPTED_AS_IS
        )


@pytest.mark.asyncio
async def test_override_creates_new_record(review_service, mock_db, classification_snapshot):
    """Test: Override creates new record, does not mutate old."""
    # Original record
    original = ReviewRecord(
        id=uuid4(),
        object_type=ReviewableObjectType.CLASSIFICATION,
        object_snapshot=classification_snapshot,
        hts_version_id="792bb867-c549-4769-80ca-d9d1adc883a3",
        status=ReviewStatus.REVIEWED_REJECTED,
        created_by="analyst_1"
    )
    
    # Mock fetch original
    from unittest.mock import MagicMock
    mock_result = MagicMock()
    mock_result.scalar_one_or_none = MagicMock(return_value=original)
    mock_db._execute_result = mock_result
    mock_db.add = MagicMock()
    review_service.db = mock_db
    
    # Create override
    new_snapshot = {
        **classification_snapshot,
        "output": {
            "success": True,
            "status": "SUCCESS",
            "candidates": [
                {
                    "hts_code": "6112.20.10.10",  # Different code
                    "final_score": 0.90
                }
            ]
        }
    }
    
    override = await review_service.create_override(
        original_review_id=original.id,
        new_object_snapshot=new_snapshot,
        created_by="reviewer_1",
        reason_code=ReviewReasonCode.OVERRIDE_EXPERT_JUDGMENT,
        justification="Expert judgment: alternative classification is more appropriate"
    )
    
    # Verify override is new record
    assert override.id != original.id
    assert override.override_of_review_id == original.id
    assert override.status == ReviewStatus.DRAFT
    assert override.created_by == "reviewer_1"
    assert "_override_of" in override.object_snapshot
    assert "_override_justification" in override.object_snapshot
    
    # Verify original unchanged
    assert original.status == ReviewStatus.REVIEWED_REJECTED  # Still rejected


@pytest.mark.asyncio
async def test_override_requires_justification(review_service, mock_db):
    """Test: Override requires justification."""
    original = ReviewRecord(
        id=uuid4(),
        object_type=ReviewableObjectType.CLASSIFICATION,
        object_snapshot={},
        hts_version_id="792bb867-c549-4769-80ca-d9d1adc883a3",
        status=ReviewStatus.REVIEWED_REJECTED,
        created_by="analyst_1"
    )
    
    mock_result = AsyncMock()
    mock_result.scalar_one_or_none = AsyncMock(return_value=original)
    mock_db.execute = AsyncMock(return_value=mock_result)
    review_service.db = mock_db
    
    with pytest.raises(ValueError, match="Override requires justification"):
        await review_service.create_override(
            original_review_id=original.id,
            new_object_snapshot={},
            created_by="reviewer_1",
            reason_code=ReviewReasonCode.OVERRIDE_EXPERT_JUDGMENT,
            justification=""  # Empty justification
        )


@pytest.mark.asyncio
async def test_get_review_history(review_service, mock_db):
    """Test: Get review history including overrides."""
    original_id = uuid4()
    original = ReviewRecord(
        id=original_id,
        object_type=ReviewableObjectType.CLASSIFICATION,
        object_snapshot={},
        hts_version_id="792bb867-c549-4769-80ca-d9d1adc883a3",
        status=ReviewStatus.REVIEWED_REJECTED,
        created_by="analyst_1"
    )
    
    override = ReviewRecord(
        id=uuid4(),
        object_type=ReviewableObjectType.CLASSIFICATION,
        object_snapshot={},
        hts_version_id="792bb867-c549-4769-80ca-d9d1adc883a3",
        status=ReviewStatus.DRAFT,
        created_by="reviewer_1",
        override_of_review_id=original_id
    )
    
    # Mock original fetch
    from unittest.mock import MagicMock
    mock_result1 = MagicMock()
    mock_result1.scalar_one_or_none = MagicMock(return_value=original)
    
    # Mock override fetch
    mock_result2 = MagicMock()
    mock_scalars = MagicMock()
    mock_scalars.all = MagicMock(return_value=[override])
    mock_result2.scalars = MagicMock(return_value=mock_scalars)
    
    # Setup execute to return different results for different calls
    call_count = [0]
    async def execute_side_effect(*args, **kwargs):
        call_count[0] += 1
        if call_count[0] == 1:
            return mock_result1
        else:
            return mock_result2
    
    mock_db.execute = execute_side_effect
    review_service.db = mock_db
    
    history = await review_service.get_review_history(original_id)
    
    assert len(history) == 2
    assert history[0].id == original_id
    assert history[1].id == override.id
    assert history[1].override_of_review_id == original_id

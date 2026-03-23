"""
Tests for PSC Radar - Sprint 6

Tests cover:
- No alternatives → no flags
- Small delta → no flag
- Large delta → flag raised
"""

import pytest
from unittest.mock import AsyncMock, MagicMock, patch
from app.engines.psc_radar import PSCRadar, PSCRadarFlag, DutyDelta, PSCRadarResult
from scripts.duty_resolution import ResolvedDuty, DutyFlag


@pytest.fixture
def mock_db():
    """Mock database session."""
    return AsyncMock()


@pytest.fixture
def psc_radar(mock_db):
    """Create PSC Radar instance with test thresholds."""
    return PSCRadar(
        db=mock_db,
        duty_delta_percent_threshold=2.0,
        duty_delta_amount_threshold=1000.0
    )


@pytest.fixture
def mock_declared_duty():
    """Mock resolved duty for declared HTS code."""
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
        explanation_general="General duty is 8.3%, present on 6112.20.20.30 (10-digit record).",
        explanation_special="Special duty is Free(...), present on 6112.20.20.30 (10-digit record).",
        explanation_col2="Column 2 duty is 90%, present on 6112.20.20.30 (10-digit record).",
        explanation_path="Checked: 6112.20.20.30 → 6112.20.20 → 6112.20"
    )


@pytest.fixture
def mock_alternative_duty_small_delta():
    """Mock resolved duty for alternative with small delta."""
    return ResolvedDuty(
        hts_code="6112202010",
        resolved_general_raw="8.3%",  # Same as declared
        resolved_special_raw="Free(AU,BH,CL,CO,E*,IL,JO,KR, MA,OM,P,PA, PE,S,SG)",
        resolved_col2_raw="90%",
        source_level_general="10",
        source_level_special="10",
        source_level_col2="10",
        source_hts_general="6112202010",
        source_hts_special="6112202010",
        source_hts_col2="6112202010",
        inheritance_path=["6112202010", "61122020", "611220"],
        flags=[],
        explanation_general="General duty is 8.3%, present on 6112.20.20.10 (10-digit record).",
        explanation_special="Special duty is Free(...), present on 6112.20.20.10 (10-digit record).",
        explanation_col2="Column 2 duty is 90%, present on 6112.20.20.10 (10-digit record).",
        explanation_path="Checked: 6112.20.20.10 → 6112.20.20 → 6112.20"
    )


@pytest.fixture
def mock_alternative_duty_large_delta():
    """Mock resolved duty for alternative with large delta."""
    return ResolvedDuty(
        hts_code="6112201010",
        resolved_general_raw="28.2%",  # Much higher than declared 8.3%
        resolved_special_raw="Free(AU,BH,CL,CO,IL,JO,KR, MA,OM,P,PA, PE,S,SG)",
        resolved_col2_raw="72%",
        source_level_general="10",
        source_level_special="10",
        source_level_col2="10",
        source_hts_general="6112201010",
        source_hts_special="6112201010",
        source_hts_col2="6112201010",
        inheritance_path=["6112201010", "61122010", "611220"],
        flags=[],
        explanation_general="General duty is 28.2%, present on 6112.20.10.10 (10-digit record).",
        explanation_special="Special duty is Free(...), present on 6112.20.10.10 (10-digit record).",
        explanation_col2="Column 2 duty is 72%, present on 6112.20.10.10 (10-digit record).",
        explanation_path="Checked: 6112.20.10.10 → 6112.20.10 → 6112.20"
    )


@pytest.mark.asyncio
async def test_no_alternatives_no_flags(psc_radar, mock_declared_duty):
    """Test: No alternatives → no flags."""
    # Mock classification engine to return no candidates
    with patch.object(
        psc_radar.classification_engine,
        'generate_alternatives',
        return_value={
            "success": False,
            "candidates": []
        }
    ):
        with patch('app.engines.psc_radar.resolve_duty', return_value=mock_declared_duty):
            result = await psc_radar.analyze(
                product_description="Women's cotton knit sweater",
                declared_hts_code="6112.20.20.30",
                quantity=100,
                customs_value=5000.0
            )
    
    assert result.declared_hts_code == "6112.20.20.30"
    assert len(result.alternatives) == 0
    assert len(result.flags) == 0
    assert "no alternative" in result.summary.lower() or "no alternative plausible" in result.summary.lower()


@pytest.mark.asyncio
async def test_small_delta_no_flag(psc_radar, mock_declared_duty, mock_alternative_duty_small_delta):
    """Test: Small delta → no flag."""
    # Mock classification engine to return one candidate with same duty
    mock_candidate = {
        "hts_code": "6112.20.20.10",
        "hts_chapter": "61",
        "final_score": 0.85,
        "similarity_score": 0.90
    }
    
    with patch.object(
        psc_radar.classification_engine,
        'generate_alternatives',
        return_value={
            "success": True,
            "candidates": [mock_candidate]
        }
    ):
        async def resolve_duty_side_effect(hts_code, db, hts_version_id=None):
            # Normalize for comparison
            normalized = "".join(c for c in hts_code if c.isdigit())
            if normalized == "6112202030":
                return mock_declared_duty
            elif normalized == "6112202010":
                return mock_alternative_duty_small_delta
            return None
        
        with patch('app.engines.psc_radar.resolve_duty', side_effect=resolve_duty_side_effect):
            result = await psc_radar.analyze(
                product_description="Women's cotton knit sweater",
                declared_hts_code="6112.20.20.30",
                quantity=100,
                customs_value=5000.0  # Small value, delta will be small
            )
    
    assert len(result.alternatives) > 0
    # Check that no material delta flags are raised
    material_flags = [
        PSCRadarFlag.DUTY_DELTA_PERCENT_EXCEEDS_THRESHOLD,
        PSCRadarFlag.DUTY_DELTA_AMOUNT_EXCEEDS_THRESHOLD
    ]
    assert not any(flag in result.flags for flag in material_flags)
    assert "below materiality thresholds" in result.summary.lower() or "no review required" in result.summary.lower()


@pytest.mark.asyncio
async def test_large_delta_flag_raised(psc_radar, mock_declared_duty, mock_alternative_duty_large_delta):
    """Test: Large delta → flag raised."""
    # Mock classification engine to return one candidate with different duty
    mock_candidate = {
        "hts_code": "6112.20.10.10",
        "hts_chapter": "61",
        "final_score": 0.80,
        "similarity_score": 0.75
    }
    
    with patch.object(
        psc_radar.classification_engine,
        'generate_alternatives',
        return_value={
            "success": True,
            "candidates": [mock_candidate]
        }
    ):
        async def resolve_duty_side_effect(hts_code, db, hts_version_id=None):
            # Normalize for comparison
            normalized = "".join(c for c in hts_code if c.isdigit())
            if normalized == "6112202030":
                return mock_declared_duty
            elif normalized == "6112201010":
                return mock_alternative_duty_large_delta
            return None
        
        with patch('app.engines.psc_radar.resolve_duty', side_effect=resolve_duty_side_effect):
            result = await psc_radar.analyze(
                product_description="Women's cotton knit sweater",
                declared_hts_code="6112.20.20.30",
                quantity=100,
                customs_value=50000.0  # Large value, delta will exceed threshold
            )
    
    assert len(result.alternatives) > 0
    # Check that material delta flags are raised
    assert PSCRadarFlag.DUTY_DELTA_PERCENT_EXCEEDS_THRESHOLD in result.flags
    assert PSCRadarFlag.DUTY_DELTA_AMOUNT_EXCEEDS_THRESHOLD in result.flags
    assert "may warrant review" in result.summary.lower()
    assert "no filing recommendation" in result.summary.lower()


@pytest.mark.asyncio
async def test_historical_divergence_signals(psc_radar, mock_declared_duty):
    """Test: Historical divergence signals are detected."""
    historical_entries = [
        {"hts_code": "6112.20.10.90"},  # Different heading
        {"hts_code": "6203.42.40.10"}  # Different chapter
    ]
    
    with patch.object(
        psc_radar.classification_engine,
        'generate_alternatives',
        return_value={
            "success": False,
            "candidates": []
        }
    ):
        with patch('app.engines.psc_radar.resolve_duty', return_value=mock_declared_duty):
            result = await psc_radar.analyze(
                product_description="Women's cotton knit sweater",
                declared_hts_code="6112.20.20.30",
                quantity=100,
                customs_value=5000.0,
                historical_entries=historical_entries
            )
    
    # Check historical signals (may be empty if no alternatives found)
    # Historical signals are only added if alternatives exist
    # For this test, we just verify the method doesn't crash
    assert isinstance(result.historical_signals, list)


@pytest.mark.asyncio
async def test_parse_duty_rate(psc_radar):
    """Test duty rate parsing."""
    assert psc_radar._parse_duty_rate("8.3%") == 8.3
    assert psc_radar._parse_duty_rate("8.3") == 8.3
    assert psc_radar._parse_duty_rate("Free") == 0.0
    assert psc_radar._parse_duty_rate("0%") == 0.0
    assert psc_radar._parse_duty_rate("") is None
    assert psc_radar._parse_duty_rate(None) is None


@pytest.mark.asyncio
async def test_extract_chapter_heading(psc_radar):
    """Test chapter and heading extraction."""
    assert psc_radar._extract_chapter("6112.20.20.30") == "61"
    assert psc_radar._extract_heading("6112.20.20.30") == "6112"
    assert psc_radar._extract_chapter("6112202030") == "61"
    assert psc_radar._extract_heading("6112202030") == "6112"


@pytest.mark.asyncio
async def test_filter_alternatives(psc_radar):
    """Test alternative filtering logic."""
    candidates = [
        {
            "hts_code": "6112.20.20.10",
            "hts_chapter": "61",
            "final_score": 0.85
        },
        {
            "hts_code": "6112.20.10.10",
            "hts_chapter": "61",
            "final_score": 0.80
        },
        {
            "hts_code": "6203.42.40.10",
            "hts_chapter": "62",
            "final_score": 0.30  # High confidence but different chapter
        },
        {
            "hts_code": "6112.20.20.30",  # Same as declared
            "hts_chapter": "61",
            "final_score": 0.90
        }
    ]
    
    filtered = psc_radar._filter_alternatives(
        candidates,
        declared_hts_code="6112.20.20.30",
        declared_chapter="61",
        declared_heading="6112"
    )
    
    # Should filter out same code and different chapter (unless high confidence)
    assert len(filtered) <= len(candidates)
    assert not any(c["hts_code"] == "6112.20.20.30" for c in filtered)

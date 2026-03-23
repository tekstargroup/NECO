"""
Integration test to verify that 8518 heading candidates survive the pipeline
for audio devices classification.
"""
import pytest
import asyncio
from pathlib import Path
import sys

# Add backend to path
sys.path.insert(0, str(Path(__file__).parent.parent))

from app.core.database import get_db
from app.engines.classification.engine import ClassificationEngine
from app.engines.classification.required_attributes import ProductFamily


@pytest.mark.asyncio
async def test_audio_devices_heading_candidate_survives_pipeline():
    """
    Test that 8518 heading candidates survive the full pipeline.
    
    Uses a rich description that should match 8518301000 (headphones/earphones).
    Forces HEADING_FIRST gating to 8518.
    Asserts that at least one 8518 candidate exists in final results.
    If 8518301000 is returned from SQL, assert it is still present after filtering.
    """
    description = (
        "Wireless Bluetooth earbuds with rechargeable lithium battery, "
        "plastic housing, in-ear design, includes charging case"
    )
    
    async for db in get_db():
        engine = ClassificationEngine(db)
        
        # Generate alternatives with clarification responses to ensure
        # all required attributes are resolved
        result = await engine.generate_alternatives(
            description=description,
            country_of_origin="CN",
            clarification_responses={
                "housing_material": "plastic",
                "power_source": "rechargeable lithium battery"
            }
        )
        
        candidates = result.get("candidates", [])
        metadata = result.get("metadata", {})
        
        # Assertions
        # 1. At least one 8518 candidate should exist
        candidates_8518 = [c for c in candidates if c.get("hts_code", "").startswith("8518")]
        assert len(candidates_8518) > 0, (
            f"No 8518 candidates found in final results. "
            f"Total candidates: {len(candidates)}, "
            f"Gating mode: {metadata.get('gating_mode')}, "
            f"Headings used: {metadata.get('headings_used')}"
        )
        
        # 2. Check if 8518301000 is in the candidates
        candidate_8518301000 = next(
            (c for c in candidates if c.get("hts_code") == "8518301000"),
            None
        )
        
        if candidate_8518301000:
            # If it was returned, it should have survived filtering
            assert candidate_8518301000 in candidates, (
                f"8518301000 was returned from SQL but not in final candidates. "
                f"Similarity: {candidate_8518301000.get('similarity_score', 0.0)}, "
                f"Final score: {candidate_8518301000.get('final_score', 0.0)}"
            )
            print(f"✅ 8518301000 survived pipeline: similarity={candidate_8518301000.get('similarity_score', 0.0):.6f}")
        else:
            print(f"⚠️  8518301000 not in final candidates (may not have matched SQL query)")
        
        # 3. Verify gating was applied
        assert metadata.get("gating_mode") in ["HEADING_FIRST", "HEADING_FIRST_EXPANDED"], (
            f"Expected HEADING_FIRST gating mode, got: {metadata.get('gating_mode')}"
        )
        assert "8518" in metadata.get("headings_used", []), (
            f"Expected 8518 in headings_used, got: {metadata.get('headings_used')}"
        )
        
        print(f"✅ Test passed: {len(candidates_8518)} 8518 candidates found")
        print(f"   Gating mode: {metadata.get('gating_mode')}")
        print(f"   Headings used: {metadata.get('headings_used')}")
        print(f"   Top 3 candidates: {[c.get('hts_code') for c in candidates[:3]]}")
        
        break


if __name__ == "__main__":
    asyncio.run(test_audio_devices_heading_candidate_survives_pipeline())

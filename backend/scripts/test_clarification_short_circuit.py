#!/usr/bin/env python3
"""
Integration test: Verify candidate retrieval is NOT called during clarification.

This test mocks the candidate retrieval function and asserts it is not invoked
when missing_required_attributes is non-empty.
"""
import asyncio
import sys
from unittest.mock import AsyncMock, patch
from pathlib import Path
from dotenv import load_dotenv

load_dotenv()
sys.path.insert(0, str(Path(__file__).parent.parent))

from app.core.database import get_db
from app.engines.classification.engine import ClassificationEngine


async def test_clarification_short_circuit():
    """Test that candidate retrieval is NOT called when clarification is required."""
    print("=" * 100)
    print("INTEGRATION TEST: Clarification Short-Circuit")
    print("=" * 100)
    print()
    print("Test: Verify candidate retrieval is NOT called when missing_required_attributes is non-empty")
    print()
    
    async for db in get_db():
        engine = ClassificationEngine(db)
        
        # Mock the candidate retrieval function
        original_generate_candidates = engine._generate_candidates
        mock_generate_candidates = AsyncMock()
        engine._generate_candidates = mock_generate_candidates
        
        try:
            # Test case that should trigger clarification
            description = "Wireless Bluetooth earbuds with charging case"
            
            print(f"Input: {description}")
            print()
            
            # Run classification
            result = await engine.generate_alternatives(
                description=description,
                country_of_origin="CN",
                value=25.99,
                quantity=100
            )
            
            status = result.get("status")
            missing_attrs = result.get("metadata", {}).get("missing_required_attributes", [])
            
            print(f"Status: {status}")
            print(f"Missing required attributes: {missing_attrs}")
            print()
            
            # Check if candidate retrieval was called
            retrieval_called = mock_generate_candidates.called
            retrieval_call_count = mock_generate_candidates.call_count
            
            print("=" * 100)
            print("VERIFICATION:")
            print("=" * 100)
            print()
            
            if status == "CLARIFICATION_REQUIRED":
                print("✅ Status is CLARIFICATION_REQUIRED")
            else:
                print(f"❌ Status is {status}, expected CLARIFICATION_REQUIRED")
            
            if len(missing_attrs) > 0:
                print(f"✅ Missing attributes detected: {missing_attrs}")
            else:
                print("❌ No missing attributes (this would prevent clarification)")
            
            if not retrieval_called:
                print("✅ Candidate retrieval was NOT called (correct - short-circuit worked)")
            else:
                print(f"❌ Candidate retrieval WAS called {retrieval_call_count} time(s) (BUG - should not be called)")
                print("   This proves the short-circuit is broken")
            
            if status == "CLARIFICATION_REQUIRED" and not retrieval_called:
                print()
                print("=" * 100)
                print("✅ TEST PASSED: Clarification short-circuit works correctly")
                print("=" * 100)
                return True
            else:
                print()
                print("=" * 100)
                print("❌ TEST FAILED: Short-circuit is broken")
                print("=" * 100)
                return False
                
        except Exception as e:
            print(f"❌ ERROR: {e}")
            import traceback
            traceback.print_exc()
            return False
        finally:
            # Restore original function
            engine._generate_candidates = original_generate_candidates
            break


if __name__ == "__main__":
    try:
        result = asyncio.run(test_clarification_short_circuit())
        sys.exit(0 if result else 1)
    except KeyboardInterrupt:
        print("\n\n⚠️  Test interrupted by user")
        sys.exit(1)
    except Exception as e:
        print(f"\n\n❌ Error: {e}")
        import traceback
        traceback.print_exc()
        sys.exit(1)

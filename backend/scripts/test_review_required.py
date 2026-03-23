#!/usr/bin/env python3
"""
Test script to verify REVIEW_REQUIRED status is actually reachable.

This script creates test cases that should result in REVIEW_REQUIRED status:
- Attributes are resolved
- Candidates are plausible (similarity >= 0.18)
- Confidence is mid-range (similarity < 0.25 OR analysis_confidence < 0.7)
"""
import asyncio
import sys
from pathlib import Path
from dotenv import load_dotenv

load_dotenv()
sys.path.insert(0, str(Path(__file__).parent.parent))

from app.core.database import get_db
from app.engines.classification.engine import ClassificationEngine
from app.engines.classification.status_model import ClassificationStatus

# Test cases designed to trigger REVIEW_REQUIRED
TEST_CASES = [
    {
        "name": "Mid-range similarity (0.18-0.25)",
        "description": "Wireless Bluetooth earbuds with rechargeable battery",
        "country_of_origin": "CN",
        "expected_status": ClassificationStatus.REVIEW_REQUIRED,
        "expected_conditions": {
            "best_similarity": ">= 0.18 and < 0.25",
            "attributes_resolved": True
        }
    },
    {
        "name": "Low analysis confidence (< 0.7) with good similarity",
        "description": "Laptop computer with 16GB RAM and SSD storage",
        "country_of_origin": "CN",
        "expected_status": ClassificationStatus.REVIEW_REQUIRED,
        "expected_conditions": {
            "best_similarity": ">= 0.25",
            "analysis_confidence": "< 0.7",
            "attributes_resolved": True
        }
    },
    {
        "name": "Consumer electronics with partial attributes",
        "description": "Smartphone with wireless charging",
        "country_of_origin": "CN",
        "expected_status": ClassificationStatus.REVIEW_REQUIRED,
        "expected_conditions": {
            "best_similarity": ">= 0.18",
            "attributes_resolved": True
        }
    },
]


async def test_review_required():
    """Test that REVIEW_REQUIRED status is actually reachable."""
    print("=" * 100)
    print("🧪 TESTING REVIEW_REQUIRED STATUS REACHABILITY")
    print("=" * 100)
    print()
    
    async for db in get_db():
        engine = ClassificationEngine(db)
        
        results = []
        
        for test_case in TEST_CASES:
            print(f"Test: {test_case['name']}")
            print(f"Description: {test_case['description']}")
            print("-" * 100)
            
            try:
                result = await engine.generate_alternatives(
                    description=test_case["description"],
                    country_of_origin=test_case["country_of_origin"],
                    value=100.0,
                    quantity=1
                )
                
                status = result.get("status")
                metadata = result.get("metadata", {})
                product_analysis = metadata.get("product_analysis", {})
                
                best_similarity = float(metadata.get("best_similarity", 0.0)) if metadata.get("best_similarity") else 0.0
                top_score = float(metadata.get("top_candidate_score", 0.0)) if isinstance(metadata.get("top_candidate_score"), str) else metadata.get("top_candidate_score", 0.0)
                analysis_confidence = float(product_analysis.get("analysis_confidence", 0.0)) if product_analysis.get("analysis_confidence") else 0.0
                missing_attrs = product_analysis.get("missing_required_attributes", [])
                attributes_resolved = len(missing_attrs) == 0
                
                print(f"Status: {status}")
                print(f"Best similarity: {best_similarity:.4f}")
                print(f"Top candidate score: {top_score:.4f}")
                print(f"Analysis confidence: {analysis_confidence:.4f}")
                print(f"Attributes resolved: {attributes_resolved}")
                print(f"Missing attributes: {missing_attrs}")
                print(f"Candidates found: {len(result.get('candidates', []))}")
                print()
                
                # Check if status matches expected
                expected_status = test_case["expected_status"]
                status_match = status == expected_status.value
                
                # Check conditions
                conditions_met = True
                if "best_similarity" in test_case["expected_conditions"]:
                    condition = test_case["expected_conditions"]["best_similarity"]
                    if ">= 0.18 and < 0.25" in condition:
                        conditions_met = conditions_met and (0.18 <= best_similarity < 0.25)
                    elif ">= 0.25" in condition:
                        conditions_met = conditions_met and (best_similarity >= 0.25)
                    elif ">= 0.18" in condition:
                        conditions_met = conditions_met and (best_similarity >= 0.18)
                
                if "analysis_confidence" in test_case["expected_conditions"]:
                    condition = test_case["expected_conditions"]["analysis_confidence"]
                    if "< 0.7" in condition:
                        conditions_met = conditions_met and (analysis_confidence < 0.7)
                
                if "attributes_resolved" in test_case["expected_conditions"]:
                    conditions_met = conditions_met and attributes_resolved
                
                results.append({
                    "test_name": test_case["name"],
                    "status": status,
                    "expected_status": expected_status.value,
                    "status_match": status_match,
                    "conditions_met": conditions_met,
                    "best_similarity": best_similarity,
                    "analysis_confidence": analysis_confidence,
                    "attributes_resolved": attributes_resolved
                })
                
                if status_match and conditions_met:
                    print(f"✅ PASS: Status is {status} and conditions are met")
                elif status == ClassificationStatus.REVIEW_REQUIRED.value:
                    print(f"⚠️  PARTIAL: Status is REVIEW_REQUIRED but conditions may not match exactly")
                else:
                    print(f"❌ FAIL: Expected {expected_status.value}, got {status}")
                
                print()
                print("=" * 100)
                print()
                
            except Exception as e:
                print(f"❌ ERROR: {e}")
                import traceback
                traceback.print_exc()
                print()
        
        # Summary
        print("=" * 100)
        print("📊 SUMMARY")
        print("=" * 100)
        print()
        
        review_required_count = sum(1 for r in results if r["status"] == ClassificationStatus.REVIEW_REQUIRED.value)
        total_tests = len(results)
        
        print(f"Total tests: {total_tests}")
        print(f"REVIEW_REQUIRED reached: {review_required_count}")
        print()
        
        if review_required_count > 0:
            print("✅ REVIEW_REQUIRED is reachable!")
            print()
            print("Cases that reached REVIEW_REQUIRED:")
            for r in results:
                if r["status"] == ClassificationStatus.REVIEW_REQUIRED.value:
                    print(f"  - {r['test_name']}: similarity={r['best_similarity']:.4f}, confidence={r['analysis_confidence']:.4f}")
        else:
            print("❌ REVIEW_REQUIRED was never reached!")
            print("This indicates the gates may be wrong.")
            print()
            print("Status distribution:")
            status_counts = {}
            for r in results:
                status_counts[r["status"]] = status_counts.get(r["status"], 0) + 1
            for status, count in status_counts.items():
                print(f"  {status}: {count}")
        
        print()
        break


if __name__ == "__main__":
    try:
        asyncio.run(test_review_required())
    except KeyboardInterrupt:
        print("\n\n⚠️  Test interrupted by user")
        sys.exit(1)
    except Exception as e:
        print(f"\n\n❌ Error: {e}")
        import traceback
        traceback.print_exc()
        sys.exit(1)

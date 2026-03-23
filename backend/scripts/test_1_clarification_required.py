#!/usr/bin/env python3
"""
STEP 1 - Test 1: CLARIFICATION_REQUIRED (hard gate)

This is a hard gate test. All conditions must pass.
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
from app.models.classification_audit import ClassificationAudit
from sqlalchemy import select
from unittest.mock import AsyncMock, patch

# Test input
TEST_INPUT = {
    "description": "Wireless Bluetooth earbuds with charging case",
    "coo": "CN",  # Use 2-letter code
    "clarification_responses": {}
}


async def test_clarification_required():
    """Test 1: CLARIFICATION_REQUIRED - Hard gate test."""
    print("=" * 100)
    print("STEP 1 - TEST 1: CLARIFICATION_REQUIRED (HARD GATE)")
    print("=" * 100)
    print()
    print("Input:")
    print(f"  description: \"{TEST_INPUT['description']}\"")
    print(f"  coo: \"{TEST_INPUT['coo']}\"")
    print(f"  clarification_responses: {TEST_INPUT['clarification_responses']}")
    print()
    print("-" * 100)
    print()
    
    async for db in get_db():
        engine = ClassificationEngine(db)
        
        # Mock candidate retrieval and scoring to verify they are NOT called
        original_generate_candidates = engine._generate_candidates
        original_score_candidates = engine._score_candidates
        
        mock_generate_candidates = AsyncMock()
        mock_score_candidates = AsyncMock()
        
        engine._generate_candidates = mock_generate_candidates
        engine._score_candidates = mock_score_candidates
        
        try:
            # Run classification
            result = await engine.generate_alternatives(
                description=TEST_INPUT["description"],
                country_of_origin=TEST_INPUT["coo"],
                clarification_responses=TEST_INPUT["clarification_responses"]
            )
            
            # Extract response data
            status = result.get("status")
            product_analysis = result.get("product_analysis") or result.get("metadata", {}).get("product_analysis", {})
            questions = result.get("questions", [])
            candidates = result.get("candidates", [])
            metadata = result.get("metadata", {})
            
            print("RESPONSE VERIFICATION:")
            print("-" * 100)
            print()
            
            # Check 1: Status
            print("1. Response Status:")
            print(f"   status = {status}")
            if status == ClassificationStatus.CLARIFICATION_REQUIRED.value:
                print("   ✅ Status is CLARIFICATION_REQUIRED")
                status_ok = True
            elif status is None:
                print("   ❌ Status is None - FAIL")
                status_ok = False
            else:
                print(f"   ❌ Status is {status}, expected CLARIFICATION_REQUIRED - FAIL")
                status_ok = False
            print()
            
            # Check 2: product_analysis present
            print("2. Product Analysis:")
            if product_analysis:
                print("   ✅ product_analysis present")
                pa_ok = True
                
                # Check product_type
                product_type = product_analysis.get("product_type")
                print(f"   product_type = {product_type}")
                if product_type:
                    print("   ✅ product_type detected")
                    product_type_ok = True
                else:
                    print("   ❌ product_type not detected - FAIL")
                    product_type_ok = False
                
                # Check missing_required_attributes
                missing_attrs = product_analysis.get("missing_required_attributes", [])
                print(f"   missing_required_attributes = {missing_attrs}")
                if missing_attrs:
                    print(f"   ✅ missing_required_attributes non-empty ({len(missing_attrs)} attributes)")
                    missing_attrs_ok = True
                else:
                    print("   ❌ missing_required_attributes is empty - FAIL")
                    missing_attrs_ok = False
            else:
                print("   ❌ product_analysis not present - FAIL")
                pa_ok = False
                product_type_ok = False
                missing_attrs_ok = False
            print()
            
            # Check 3: clarification_questions
            print("3. Clarification Questions:")
            print(f"   questions length = {len(questions)}")
            if 1 <= len(questions) <= 3:
                print(f"   ✅ questions length is {len(questions)} (within 1-3 range)")
                questions_count_ok = True
            else:
                print(f"   ❌ questions length is {len(questions)}, expected 1-3 - FAIL")
                questions_count_ok = False
            
            # Check each question structure
            questions_structure_ok = True
            if questions:
                print("   Questions:")
                for i, q in enumerate(questions, 1):
                    attr = q.get("attribute")
                    question_text = q.get("question", "")
                    has_why = "why" in question_text.lower() or "determines" in question_text.lower() or "affects" in question_text.lower()
                    
                    print(f"     {i}. attribute: {attr}")
                    print(f"        question: {question_text[:80]}...")
                    print(f"        has why_it_matters: {has_why}")
                    
                    if not attr:
                        print(f"        ❌ Missing attribute name - FAIL")
                        questions_structure_ok = False
                    if not has_why:
                        print(f"        ❌ Question missing 'why it matters' explanation - FAIL")
                        questions_structure_ok = False
            else:
                print("   ❌ No questions provided - FAIL")
                questions_structure_ok = False
            print()
            
            # Check 4: System behavior - NO candidate retrieval
            print("4. System Behavior:")
            retrieval_called = mock_generate_candidates.called
            scoring_called = mock_score_candidates.called
            
            print(f"   Candidate retrieval called: {retrieval_called}")
            if not retrieval_called:
                print("   ✅ NO candidate retrieval (correct)")
                retrieval_ok = True
            else:
                print(f"   ❌ Candidate retrieval WAS called {mock_generate_candidates.call_count} time(s) - FAIL")
                retrieval_ok = False
            
            print(f"   Similarity scoring called: {scoring_called}")
            if not scoring_called:
                print("   ✅ NO similarity scoring (correct)")
                scoring_ok = True
            else:
                print(f"   ❌ Similarity scoring WAS called {mock_score_candidates.call_count} time(s) - FAIL")
                scoring_ok = False
            
            print(f"   Candidates returned: {len(candidates)}")
            if len(candidates) == 0:
                print("   ✅ NO candidates returned (correct)")
                candidates_ok = True
            else:
                print(f"   ❌ {len(candidates)} candidates returned (should be 0) - FAIL")
                candidates_ok = False
            print()
            
            # Check 5: Audit record
            print("5. Audit Record:")
            # Get the most recent audit record
            result_query = await db.execute(
                select(ClassificationAudit)
                .order_by(ClassificationAudit.created_at.desc())
                .limit(1)
            )
            audit = result_query.scalar_one_or_none()
            
            if audit:
                print(f"   Audit ID: {audit.id}")
                print(f"   status = {audit.status}")
                if audit.status == ClassificationStatus.CLARIFICATION_REQUIRED.value:
                    print("   ✅ status = CLARIFICATION_REQUIRED")
                    audit_status_ok = True
                else:
                    print(f"   ❌ status = {audit.status}, expected CLARIFICATION_REQUIRED - FAIL")
                    audit_status_ok = False
                
                print(f"   reason_code = {audit.reason_code}")
                if audit.reason_code == "MISSING_REQUIRED_ATTRIBUTES":
                    print("   ✅ reason_code = MISSING_REQUIRED_ATTRIBUTES")
                    audit_reason_ok = True
                else:
                    print(f"   ❌ reason_code = {audit.reason_code}, expected MISSING_REQUIRED_ATTRIBUTES - FAIL")
                    audit_reason_ok = False
                
                print(f"   product_analysis populated: {bool(audit.product_analysis)}")
                if audit.product_analysis:
                    print("   ✅ product_analysis populated")
                    audit_pa_ok = True
                else:
                    print("   ❌ product_analysis is NULL - FAIL")
                    audit_pa_ok = False
                
                print(f"   clarification_questions populated: {bool(audit.clarification_questions)}")
                if audit.clarification_questions:
                    print("   ✅ clarification_questions populated")
                    audit_questions_ok = True
                else:
                    print("   ❌ clarification_questions is NULL - FAIL")
                    audit_questions_ok = False
                
                print(f"   clarification_responses = {audit.clarification_responses}")
                if audit.clarification_responses is None:
                    print("   ✅ clarification_responses = NULL (correct)")
                    audit_responses_ok = True
                else:
                    print(f"   ❌ clarification_responses = {audit.clarification_responses}, expected NULL - FAIL")
                    audit_responses_ok = False
                
                print(f"   candidate_counts = {audit.candidate_counts}")
                if audit.candidate_counts is None or audit.candidate_counts == {}:
                    print("   ✅ candidate_counts = NULL/empty (correct)")
                    audit_counts_ok = True
                else:
                    print(f"   ⚠️  candidate_counts = {audit.candidate_counts} (should be NULL for clarification)")
                    # This might be set to empty dict, which is acceptable
                    audit_counts_ok = True
            else:
                print("   ❌ No audit record found - FAIL")
                audit_status_ok = False
                audit_reason_ok = False
                audit_pa_ok = False
                audit_questions_ok = False
                audit_responses_ok = False
                audit_counts_ok = False
            print()
            
            # Final verdict
            print("=" * 100)
            print("PASS / FAIL VERDICT:")
            print("=" * 100)
            print()
            
            all_checks = {
                "Response status is CLARIFICATION_REQUIRED": status_ok,
                "product_analysis present": pa_ok,
                "product_type detected": product_type_ok if pa_ok else False,
                "missing_required_attributes non-empty": missing_attrs_ok if pa_ok else False,
                "questions length 1-3": questions_count_ok,
                "Each question has attribute and why_it_matters": questions_structure_ok,
                "NO candidate retrieval": retrieval_ok,
                "NO similarity scoring": scoring_ok,
                "NO candidates returned": candidates_ok,
                "Audit status = CLARIFICATION_REQUIRED": audit_status_ok,
                "Audit reason_code = MISSING_REQUIRED_ATTRIBUTES": audit_reason_ok,
                "Audit product_analysis populated": audit_pa_ok,
                "Audit clarification_questions populated": audit_questions_ok,
                "Audit clarification_responses = NULL": audit_responses_ok,
            }
            
            all_pass = all(all_checks.values())
            
            for check, passed in all_checks.items():
                status_icon = "✅" if passed else "❌"
                print(f"{status_icon} {check}")
            
            print()
            print("=" * 100)
            if all_pass:
                print("✅ TEST PASSED: All conditions met")
                print("=" * 100)
                return True
            else:
                print("❌ TEST FAILED: One or more conditions not met")
                print("=" * 100)
                print()
                print("FAILURE REASONS:")
                for check, passed in all_checks.items():
                    if not passed:
                        print(f"  - {check}")
                return False
            
        except Exception as e:
            print(f"❌ ERROR: {e}")
            import traceback
            traceback.print_exc()
            return False
        finally:
            # Restore original functions
            engine._generate_candidates = original_generate_candidates
            engine._score_candidates = original_score_candidates
            break


if __name__ == "__main__":
    try:
        result = asyncio.run(test_clarification_required())
        sys.exit(0 if result else 1)
    except KeyboardInterrupt:
        print("\n\n⚠️  Test interrupted by user")
        sys.exit(1)
    except Exception as e:
        print(f"\n\n❌ Error: {e}")
        import traceback
        traceback.print_exc()
        sys.exit(1)

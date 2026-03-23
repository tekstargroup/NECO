#!/usr/bin/env python3
"""
Smoke Test for Classification Engine

Tests the classification engine with 3 sample product descriptions.

Prerequisites:
- PostgreSQL database must be running
- HTS data must be ingested (2025HTS.pdf)
- Run: docker-compose up -d (or start database manually)
"""

import asyncio
import sys
from pathlib import Path
from dotenv import load_dotenv

# Load .env from project root (two levels up from scripts/)
project_root = Path(__file__).parent.parent.parent
load_dotenv(project_root / ".env")

# Add parent directory to path
sys.path.insert(0, str(Path(__file__).parent.parent))

from app.core.database import get_db
from app.engines.classification.engine import ClassificationEngine
from app.models.classification import ClassificationAlternative
from app.models.classification_audit import ClassificationAudit


async def smoke_test():
    """Run smoke tests with sample products"""
    print("⚠️  Checking database connection...")
    
    try:
        async for db in get_db():
            print("=" * 100)
            print("🧪 CLASSIFICATION ENGINE SMOKE TEST")
            print("=" * 100)
            print()
        
        engine = ClassificationEngine(db)
        
        # Test cases - using richer product descriptions with material, function, and HTS hints
        test_cases = [
            {
                "description": "Wireless Bluetooth earbuds with rechargeable battery, noise cancellation, and microphone for hands-free communication",
                "country_of_origin": "CN",
                "value": 25.99,
                "quantity": 100,
                "current_hts_code": None,
                "expected_chapters": ["85", "90"],  # Should be Chapter 85 (electrical) or 90 (instruments), NEVER 44
                "expected_min_score": 0.20  # Quality gate threshold
            },
            {
                "description": "Stainless steel insulated water bottle with double-wall vacuum insulation, 32 ounce capacity, for personal use",
                "country_of_origin": "CN",
                "value": 35.00,
                "quantity": 200,
                "current_hts_code": None,
                "expected_chapters": ["73", "76"],  # Steel articles
                "expected_min_score": 0.20
            },
            {
                "description": "Men's cotton t-shirt, knit fabric, short sleeves, 100% cotton, weight 180 gsm, for retail sale",
                "country_of_origin": "MX",
                "value": 12.50,
                "quantity": 500,
                "current_hts_code": None,
                "expected_chapters": ["61", "62"],  # Apparel
                "expected_min_score": 0.20
            },
            # Adversarial tests - should return NO_CONFIDENT_MATCH
            {
                "description": "Bluetooth earbuds",
                "country_of_origin": "CN",
                "value": 25.99,
                "quantity": 100,
                "current_hts_code": None,
                "expected_chapters": ["85", "90"],
                "expected_min_score": 0.20,
                "adversarial": True,
                "expected_status": "NO_CONFIDENT_MATCH"  # Short, vague - should trigger confidence gate
            },
            {
                "description": "Premium luxury wireless Bluetooth earbuds with advanced noise cancellation technology, premium sound quality, long battery life, sleek design, perfect for music lovers and professionals, award-winning product, best seller, 5-star rated, includes charging case and multiple ear tip sizes for comfort",
                "country_of_origin": "CN",
                "value": 25.99,
                "quantity": 100,
                "current_hts_code": None,
                "expected_chapters": ["85", "90"],
                "expected_min_score": 0.20,
                "adversarial": True,
                "expected_status": "NO_CONFIDENT_MATCH"  # Marketing fluff - should be penalized
            }
        ]
        
        for i, test_case in enumerate(test_cases, 1):
            print(f"Test Case {i}: {test_case['description']}")
            print("-" * 100)
            print(f"COO: {test_case['country_of_origin']}")
            print(f"Value: ${test_case['value']}")
            print(f"Quantity: {test_case['quantity']}")
            expected_chapters = test_case.get('expected_chapters', [])
            if expected_chapters:
                print(f"Expected Chapters: {', '.join(expected_chapters)}")
            print()
            
            try:
                result = await engine.generate_alternatives(
                    description=test_case["description"],
                    country_of_origin=test_case["country_of_origin"],
                    value=test_case["value"],
                    quantity=test_case["quantity"],
                    current_hts_code=test_case["current_hts_code"]
                )
                
                # Check for NO_CONFIDENT_MATCH status
                status = result.get("status")
                if status == "NO_CONFIDENT_MATCH":
                    candidates = result.get("candidates", [])
                    metadata = result.get("metadata", {})
                    best_sim = float(metadata.get('best_similarity', 0.0))
                    reason_code = metadata.get('reason_code', 'UNKNOWN')
                    
                    print("=" * 100)
                    print("📊 STRUCTURED OUTPUT - NO_CONFIDENT_MATCH")
                    print("=" * 100)
                    print(f"status: {status}")
                    print(f"best_similarity: {best_sim:.4f}")
                    print(f"reason_code: {reason_code}")
                    print()
                    print("candidate_counts:")
                    print(f"  pre_filter_count: {metadata.get('pre_filter_count', 0)}")
                    print(f"  post_filter_count: {metadata.get('post_filter_count', 0)}")
                    print(f"  post_score_count: {metadata.get('post_score_count', 0)}")
                    print()
                    print(f"noise_ratio: {metadata.get('noise_ratio', 0.0):.2f}%")
                    print(f"noisy_excluded: {metadata.get('noisy_excluded', 0)}")
                    print()
                    print(f"applied_filters: {metadata.get('applied_filters', [])}")
                    print()
                    print("top_5_candidates:")
                    for j, candidate in enumerate(candidates[:5], 1):
                        print(f"  {j}. hts_code: {candidate.get('hts_code', 'N/A')}")
                        print(f"     hts_chapter: {candidate.get('hts_chapter', 'N/A')}")
                        print(f"     description: {candidate.get('tariff_text_short', 'N/A')[:80]}")
                        print(f"     similarity_score: {candidate.get('similarity_score', 0):.4f}")
                        print(f"     final_score: {candidate.get('final_score', 0):.4f}")
                        score_comp = candidate.get('score_components', {})
                        print(f"     score_components: sim_raw={score_comp.get('similarity_raw', 0):.4f}, "
                              f"sim_contrib={score_comp.get('similarity_contribution', 0):.4f}, "
                              f"conf_penalty={score_comp.get('confidence_penalty', 0):.4f}, "
                              f"duty_penalty={score_comp.get('duty_penalty', 0):.4f}")
                        print()
                    print("=" * 100)
                    print()
                    continue
                
                if result.get("success"):
                    candidates = result.get("candidates", [])
                    metadata = result.get("metadata", {})
                    
                    print("=" * 100)
                    print("📊 STRUCTURED OUTPUT - SUCCESS")
                    print("=" * 100)
                    print(f"status: SUCCESS")
                    top_score = metadata.get('top_candidate_score', 0.0)
                    if isinstance(top_score, str):
                        top_score = float(top_score)
                    best_sim = float(metadata.get('best_similarity', 0.0))
                    print(f"best_similarity: {best_sim:.4f}")
                    print(f"reason_code: None (success)")
                    print()
                    print("candidate_counts:")
                    print(f"  pre_filter_count: {metadata.get('pre_filter_count', 0)}")
                    print(f"  post_filter_count: {metadata.get('post_filter_count', 0)}")
                    print(f"  post_score_count: {metadata.get('post_score_count', 0)}")
                    print()
                    print(f"noise_ratio: {metadata.get('noise_ratio', 0.0):.2f}%")
                    print(f"noisy_excluded: {metadata.get('noisy_excluded', 0)}")
                    print()
                    print(f"applied_filters: {metadata.get('applied_filters', [])}")
                    print()
                    print("top_5_candidates:")
                    for j, candidate in enumerate(candidates[:5], 1):
                        print(f"  {j}. hts_code: {candidate.get('hts_code', 'N/A')}")
                        print(f"     hts_chapter: {candidate.get('hts_chapter', 'N/A')}")
                        print(f"     description: {candidate.get('tariff_text_short', 'N/A')[:80]}")
                        print(f"     similarity_score: {candidate.get('similarity_score', 0):.4f}")
                        print(f"     final_score: {candidate.get('final_score', 0):.4f}")
                        score_comp = candidate.get('score_components', {})
                        print(f"     score_components: sim_raw={score_comp.get('similarity_raw', 0):.4f}, "
                              f"sim_contrib={score_comp.get('similarity_contribution', 0):.4f}, "
                              f"conf_penalty={score_comp.get('confidence_penalty', 0):.4f}, "
                              f"duty_penalty={score_comp.get('duty_penalty', 0):.4f}")
                        print()
                    print("=" * 100)
                    print()
                    
                    # Chapter sanity check
                    if candidates and expected_chapters:
                        top_chapter = candidates[0].get('hts_chapter', '')
                        if top_chapter in expected_chapters:
                            print(f"   ✅ Chapter sanity check PASSED: Ch. {top_chapter} is in expected {expected_chapters}")
                        else:
                            print(f"   ❌ Chapter sanity check FAILED: Ch. {top_chapter} NOT in expected {expected_chapters}")
                    
                    # Score quality check
                    expected_min_score = test_case.get('expected_min_score', 0.20)
                    if top_score >= expected_min_score:
                        print(f"   ✅ Score quality check PASSED: {top_score:.4f} >= {expected_min_score}")
                    else:
                        print(f"   ❌ Score quality check FAILED: {top_score:.4f} < {expected_min_score}")
                    
                    print()
                    
                    print("Top 3 Candidates (with detailed scoring):")
                    for j, candidate in enumerate(candidates[:3], 1):
                        score_components = candidate.get("score_components", {})
                        print(f"   {j}. HTS: {candidate.get('hts_code', 'N/A')} (Ch. {candidate.get('hts_chapter', 'N/A')})")
                        print(f"      Description: {candidate.get('tariff_text_short', 'N/A')[:60]}...")
                        print(f"      Similarity: {candidate.get('similarity_score', 0):.4f}")
                        print(f"      Final Score: {candidate.get('final_score', 0):.4f}")
                        if score_components:
                            print(f"      Score breakdown:")
                            print(f"        - Similarity raw: {score_components.get('similarity_raw', 0):.4f}")
                            print(f"        - Similarity contribution: {score_components.get('similarity_contribution', 0):.4f}")
                            print(f"        - Confidence penalty: {score_components.get('confidence_penalty', 0):.4f}")
                            print(f"        - Duty penalty: {score_components.get('duty_penalty', 0):.4f}")
                            print(f"        - Special bonus: {score_components.get('special_bonus', 0):.4f}")
                            print(f"        - HTS match bonus: {score_components.get('hts_match_bonus', 0):.4f}")
                        print(f"      Selected Rate: {candidate.get('selected_rate', 'N/A')} ({candidate.get('selected_rate_type', 'N/A')})")
                        print(f"      Duty Rate Numeric: {candidate.get('duty_rate_numeric', 'N/A')}")
                        print()
                    
                    # Persist to database for verification (only if quality gate passed)
                    # Quality gate is enforced in the engine, so if we get here, top_score >= 0.20
                    try:
                        from app.models.classification_audit import ClassificationAudit
                        from app.models.classification import ClassificationAlternative
                        
                        # Verify quality gate passed before persisting
                        expected_min_score = test_case.get('expected_min_score', 0.20)
                        if top_score < expected_min_score:
                            print(f"   ⚠️  WARNING: Top score {top_score:.4f} < {expected_min_score}, but engine returned success.")
                            print(f"   ⚠️  This should not happen - quality gate should have rejected this.")
                        
                        # Create audit record
                        audit = ClassificationAudit(
                            input_description=test_case["description"],
                            input_coo=test_case["country_of_origin"],
                            input_value=str(test_case["value"]),
                            input_qty=str(test_case["quantity"]),
                            engine_version=engine.engine_version,
                            context_payload=result.get("context_payload"),
                            provenance=result.get("provenance", {}),
                            candidates_generated=str(len(candidates)),
                            top_candidate_hts=metadata.get("top_candidate_hts"),
                            top_candidate_score=str(top_score),
                            processing_time_ms=str(metadata.get("processing_time_ms", 0))
                        )
                        db.add(audit)
                        await db.flush()
                        
                        # Create alternatives (only persist if quality gate passed)
                        persisted_count = 0
                        for j, candidate in enumerate(candidates):
                            candidate_score = float(candidate.get("final_score", 0.0))
                            # Double-check: don't persist if score is too low
                            if candidate_score >= expected_min_score or j == 0:  # Always persist top candidate for audit
                                alt = ClassificationAlternative(
                                    sku_id=None,
                                    alternative_hts=candidate["hts_code"],
                                    alternative_duty=candidate.get("duty_rate_numeric"),
                                    confidence_score=candidate_score,
                                    is_recommended=2 if j == 0 else (1 if j < 3 else 0),
                                    recommendation_reason="Top candidate" if j == 0 else "Alternative",
                                    created_by="smoke_test",
                                    analysis_version=engine.engine_version
                                )
                                db.add(alt)
                                persisted_count += 1
                        
                        await db.commit()
                        print(f"   💾 Persisted {persisted_count} alternatives and 1 audit record")
                        print()
                    except Exception as persist_error:
                        await db.rollback()
                        print(f"   ⚠️  Warning: Could not persist: {persist_error}")
                        print()
                else:
                    error = result.get('error', 'Unknown error')
                    error_reason = result.get('error_reason', '')
                    metadata = result.get("metadata", {})
                    status = result.get("status", "FAILED")
                    
                    print("=" * 100)
                    print("📊 STRUCTURED OUTPUT - FAILED")
                    print("=" * 100)
                    print(f"status: {status}")
                    best_sim = float(metadata.get('best_similarity', 0.0)) if metadata.get('best_similarity') else 0.0
                    print(f"best_similarity: {best_sim:.4f}")
                    print(f"reason_code: {metadata.get('reason_code', error)}")
                    print(f"threshold_used: {metadata.get('threshold_used', 'N/A')}")
                    print()
                    print("candidate_counts:")
                    print(f"  pre_filter_count: {metadata.get('pre_filter_count', 0)}")
                    print(f"  post_filter_count: {metadata.get('post_filter_count', 0)}")
                    print(f"  post_score_count: {metadata.get('post_score_count', 0)}")
                    print()
                    noise_ratio = float(metadata.get('noise_ratio', 0.0)) if metadata.get('noise_ratio') else 0.0
                    noisy_excluded = metadata.get('noisy_excluded', 0)
                    print(f"noisy_excluded: {noisy_excluded}")
                    print(f"noise_ratio: {noise_ratio:.2f}%")
                    noise_warning = "YES" if noise_ratio > 50 else "NO"
                    print(f"noise_warning_flag: {noise_warning}")
                    print()
                    print(f"applied_filters: {metadata.get('applied_filters', [])}")
                    print()
                    candidates = result.get("candidates", [])
                    if candidates:
                        print("top_5_candidates:")
                        for j, candidate in enumerate(candidates[:5], 1):
                            print(f"  {j}. hts_code: {candidate.get('hts_code', 'N/A')}")
                            print(f"     hts_chapter: {candidate.get('hts_chapter', 'N/A')}")
                            desc = candidate.get('tariff_text_short', '') or candidate.get('tariff_text', '') or 'N/A'
                            print(f"     description: {desc[:80]}")
                            print(f"     similarity_score: {candidate.get('similarity_score', 0):.4f}")
                            print(f"     final_score: {candidate.get('final_score', 0):.4f}")
                            score_comp = candidate.get('score_components', {})
                            if score_comp:
                                print(f"     score_breakdown:")
                                print(f"       similarity_raw: {score_comp.get('similarity_raw', 0):.4f}")
                                print(f"       similarity_contribution: {score_comp.get('similarity_contribution', 0):.4f}")
                                print(f"       confidence_penalty: {score_comp.get('confidence_penalty', 0):.4f}")
                                print(f"       duty_penalty: {score_comp.get('duty_penalty', 0):.4f}")
                                print(f"       special_bonus: {score_comp.get('special_bonus', 0):.4f}")
                                print(f"       hts_match_bonus: {score_comp.get('hts_match_bonus', 0):.4f}")
                            print(f"     selected_duty_rate_type: {candidate.get('selected_rate_type', 'N/A')}")
                            print(f"     selected_duty_rate_value: {candidate.get('selected_rate', 'N/A')}")
                            print()
                    print("=" * 100)
                    print()
                    print(f"❌ Failed: {error}")
                    if error_reason:
                        print(f"   Reason: {error_reason}")
                    
                    # Persist audit record even for failures (quality gate)
                    if error == "NO_GOOD_MATCH":
                        try:
                            from app.models.classification_audit import ClassificationAudit
                            metadata = result.get("metadata", {})
                            audit = ClassificationAudit(
                                input_description=test_case["description"],
                                input_coo=test_case["country_of_origin"],
                                input_value=str(test_case["value"]),
                                input_qty=str(test_case["quantity"]),
                                engine_version=engine.engine_version,
                                error_message=error_reason,
                                candidates_generated="0",
                                processing_time_ms=str(metadata.get("processing_time_ms", 0))
                            )
                            db.add(audit)
                            await db.commit()
                            print(f"   💾 Persisted audit record (quality gate failure)")
                            print()
                        except Exception as persist_error:
                            await db.rollback()
                            print(f"   ⚠️  Warning: Could not persist audit: {persist_error}")
                            print()
                    else:
                        print()
            
            except Exception as e:
                print(f"❌ Error: {str(e)}")
                print()
            
            print("=" * 100)
            print()
        
            print("✅ Smoke test complete!")
            print()
            print("=" * 100)
            print("📊 SQL QUERIES TO VERIFY DATA INSERTION")
            print("=" * 100)
            print()
            print("After calling the API endpoint (POST /api/v1/classification/generate),")
            print("run these queries to verify rows were inserted:")
            print()
            print("1. Count classification_alternatives:")
            print("   SELECT COUNT(*) FROM classification_alternatives;")
            print()
            print("2. Count classification_audit records:")
            print("   SELECT COUNT(*) FROM classification_audit;")
            print()
            print("3. View recent audit records with candidates:")
            print("   SELECT")
            print("       ca.id,")
            print("       ca.input_description,")
            print("       ca.input_coo,")
            print("       ca.top_candidate_hts,")
            print("       ca.top_candidate_score,")
            print("       ca.candidates_generated,")
            print("       ca.created_at")
            print("   FROM classification_audit ca")
            print("   ORDER BY ca.created_at DESC")
            print("   LIMIT 10;")
            print()
            # Don't break - continue to next test case
    
    except OSError as e:
        if "Connect call failed" in str(e) or "5432" in str(e):
            print()
            print("=" * 100)
            print("❌ DATABASE CONNECTION ERROR")
            print("=" * 100)
            print()
            print("The PostgreSQL database is not running or not accessible.")
            print()
            print("To fix this:")
            print("1. Start the database using Docker Compose:")
            print("   cd /Users/stevenbigio/Cursor\\ Projects/NECO")
            print("   docker-compose up -d")
            print()
            print("2. Or start PostgreSQL manually and ensure it's running on port 5432")
            print()
            print("3. Verify your .env file has the correct DATABASE_URL")
            print()
            print("4. Check database is running:")
            print("   docker ps | grep postgres")
            print("   # or")
            print("   psql -h localhost -p 5432 -U postgres -c 'SELECT 1'")
            print()
            sys.exit(1)
        else:
            raise
    except Exception as e:
        print()
        print("=" * 100)
        print("❌ ERROR")
        print("=" * 100)
        print(f"Unexpected error: {e}")
        print()
        import traceback
        traceback.print_exc()
        sys.exit(1)


if __name__ == "__main__":
    asyncio.run(smoke_test())


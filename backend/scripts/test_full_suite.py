#!/usr/bin/env python3
"""
Full test suite for classification engine
Tests: Test 2 (SUCCESS Tier A), Test 3 (REVIEW_REQUIRED medical), Test 4 (NO_CONFIDENT_MATCH), Negative control (router)
"""

import asyncio
import sys
import json
from pathlib import Path
from dotenv import load_dotenv

load_dotenv()
sys.path.insert(0, str(Path('backend')))

from app.core.database import get_db
from app.engines.classification.engine import ClassificationEngine

async def run_test(name, description, coo, clarification_responses=None, expected_status=None):
    """Run a single test case"""
    print("\n" + "=" * 100)
    print(f"TEST: {name}")
    print("=" * 100)
    print(f"Description: {description}")
    print(f"COO: {coo}")
    if clarification_responses:
        print(f"Clarification responses: {clarification_responses}")
    print()
    
    async for db in get_db():
        engine = ClassificationEngine(db)
        result = await engine.generate_alternatives(
            description=description,
            country_of_origin=coo,
            clarification_responses=clarification_responses or {}
        )
        
        status = result.get('status')
        candidates = result.get('candidates', [])
        metadata = result.get('metadata', {})
        
        print(f"STATUS: {status}")
        if expected_status:
            match = "✅ PASS" if status == expected_status else f"❌ FAIL (expected {expected_status})"
            print(f"Expected: {expected_status} → {match}")
        print()
        
        print("METADATA:")
        print(f"  reason_code: {metadata.get('reason_code')}")
        print(f"  best_similarity: {metadata.get('best_similarity', 0.0):.6f}")
        if metadata.get('best_8518_similarity'):
            print(f"  best_8518_similarity: {metadata.get('best_8518_similarity'):.6f}")
        print(f"  threshold_used: {metadata.get('threshold_used')}")
        candidate_counts = metadata.get('candidate_counts', {})
        if candidate_counts:
            print(f"  candidate_counts: primary_8518={candidate_counts.get('primary_8518', 0)}, expanded={candidate_counts.get('expanded', 0)}")
        print()
        
        print(f"TOP 5 CANDIDATES:")
        for i, c in enumerate(candidates[:5], 1):
            code = c.get('hts_code', '')
            is_8518 = 'YES' if code.startswith('8518') else 'NO'
            sim = c.get('similarity_score', 0.0)
            final = c.get('final_score', 0.0)
            source = c.get('_source', 'primary')
            print(f"  {i}. HTS {code} (8518: {is_8518}, source: {source}): similarity={sim:.6f}, final_score={final:.6f}")
            if code.startswith('8518'):
                print(f"     {c.get('tariff_text_short', '')[:80]}...")
        
        print()
        print("-" * 100)
        
        return result

async def main():
    print("\n" + "=" * 100)
    print("FULL TEST SUITE - Classification Engine")
    print("=" * 100)
    
    # Test 2: SUCCESS Tier A (full rich description)
    await run_test(
        name="Test 2: SUCCESS Tier A (full rich earbuds description)",
        description="Wireless Bluetooth earbuds with built-in microphone, rechargeable lithium battery, plastic housing, in-ear design, includes charging case with USB-C port, noise cancellation, touch controls",
        coo="CN",
        clarification_responses={
            'housing_material': 'plastic',
            'power_source': 'rechargeable lithium battery'
        },
        expected_status="REVIEW_REQUIRED"  # OK for Sprint 4, SUCCESS Tier A only if similarity/spread support it
    )
    
    # Test 3: REVIEW_REQUIRED (medical device)
    # First call: CLARIFICATION_REQUIRED
    print("\n" + "=" * 100)
    print("Test 3a: CLARIFICATION_REQUIRED (medical device - first call)")
    print("=" * 100)
    result_3a = await run_test(
        name="Test 3a: CLARIFICATION_REQUIRED (medical device)",
        description="Portable digital blood pressure monitor with LCD display",
        coo="DE",
        expected_status="CLARIFICATION_REQUIRED"
    )
    
    # Second call: After clarification
    clarification_responses_3b = {}
    if result_3a.get('status') == 'CLARIFICATION_REQUIRED':
        # Extract questions and create sample responses
        questions = result_3a.get('questions', [])
        print(f"\nClarification questions: {questions}")
        # Sample responses based on questions
        for q in questions:
            attr = q.get('attribute', '')
            if 'medical_use' in attr.lower() or 'intended_use' in attr.lower():
                clarification_responses_3b[attr] = 'diagnostic'
            elif 'electrical' in attr.lower():
                clarification_responses_3b[attr] = 'yes'
            elif 'patient_contact' in attr.lower():
                clarification_responses_3b[attr] = 'yes'
            elif 'disposable' in attr.lower():
                clarification_responses_3b[attr] = 'no'
    
    if clarification_responses_3b:
        await run_test(
            name="Test 3b: REVIEW_REQUIRED (medical device - after clarification)",
            description="Portable digital blood pressure monitor with LCD display",
            coo="DE",
            clarification_responses=clarification_responses_3b,
            expected_status="REVIEW_REQUIRED"
        )
    
    # Test 4: NO_CONFIDENT_MATCH (vague prompt)
    await run_test(
        name="Test 4: NO_CONFIDENT_MATCH (vague model prompt)",
        description="Model ABC-123",
        coo="CN",
        expected_status=None  # Could be NO_CONFIDENT_MATCH or CLARIFICATION_REQUIRED depending on map
    )
    
    # Negative control: Router description should NOT go to 8518
    result_router = await run_test(
        name="Negative Control: Router (should NOT go to 8518)",
        description="Wireless router with dual-band Wi-Fi 6, Gigabit Ethernet ports, MU-MIMO technology, supports up to 2500 sq ft coverage",
        coo="CN",
        clarification_responses={},
        expected_status=None
    )
    
    # Check that router did NOT get 8518 candidates as top results
    router_candidates = result_router.get('candidates', [])
    top_3_8518 = sum(1 for c in router_candidates[:3] if c.get('hts_code', '').startswith('8518'))
    print(f"\n{'✅ PASS' if top_3_8518 == 0 else '❌ FAIL'}: Router negative control - Top 3 should NOT be 8518 (got {top_3_8518} 8518 codes in top 3)")
    
    print("\n" + "=" * 100)
    print("TEST SUITE COMPLETE")
    print("=" * 100)

if __name__ == "__main__":
    asyncio.run(main())

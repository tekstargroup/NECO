#!/usr/bin/env python3
"""
Performance test: Run 200 classifications and measure query times.
"""
import asyncio
import sys
import time
from pathlib import Path
from statistics import mean, median
from typing import List

from dotenv import load_dotenv

load_dotenv()
sys.path.insert(0, str(Path(__file__).parent.parent))

from app.engines.classification.engine import ClassificationEngine
from app.core.database import get_db

# Test descriptions - mix of realistic queries
TEST_DESCRIPTIONS = [
    "Wireless Bluetooth earbuds with rechargeable battery",
    "Stainless steel water bottle 32 ounce",
    "Men's cotton t-shirt knit fabric",
    "Laptop computer with 16GB RAM",
    "LED light bulb 60 watt",
    "Plastic storage container",
    "Cotton bed sheets queen size",
    "Aluminum cookware set",
    "Wooden dining table",
    "Ceramic coffee mug",
] * 20  # Repeat to get 200 total


async def run_performance_test():
    """Run 200 classifications and measure performance."""
    print("=" * 100)
    print("🚀 CLASSIFICATION ENGINE PERFORMANCE TEST")
    print("=" * 100)
    print()
    print(f"Running {len(TEST_DESCRIPTIONS)} classifications...")
    print()
    
    async for db in get_db():
        engine = ClassificationEngine(db)
        
        query_times: List[float] = []
        total_times: List[float] = []
        
        for i, description in enumerate(TEST_DESCRIPTIONS, 1):
            start_time = time.time()
            
            try:
                result = await engine.generate_alternatives(
                    description=description,
                    country_of_origin="CN",
                    value=25.99,
                    quantity=100
                )
                
                total_time = time.time() - start_time
                total_times.append(total_time)
                
                # Extract query time from metadata if available
                metadata = result.get("metadata", {})
                processing_ms = metadata.get("processing_time_ms", 0)
                if processing_ms:
                    query_time = processing_ms / 1000.0  # Convert to seconds
                    query_times.append(query_time)
                else:
                    query_times.append(total_time)
                
                if i % 50 == 0:
                    print(f"  Completed {i}/{len(TEST_DESCRIPTIONS)} classifications...")
                    
            except Exception as e:
                print(f"  ⚠️  Error on classification {i}: {e}")
                continue
        
        print()
        print("=" * 100)
        print("📊 PERFORMANCE RESULTS")
        print("=" * 100)
        print()
        
        if query_times:
            query_times_sorted = sorted(query_times)
            p95_index = int(len(query_times_sorted) * 0.95)
            p95_time = query_times_sorted[p95_index] if p95_index < len(query_times_sorted) else query_times_sorted[-1]
            
            print("Candidate Retrieval Query Times:")
            print(f"  Average: {mean(query_times):.3f}s")
            print(f"  Median:  {median(query_times):.3f}s")
            print(f"  P95:     {p95_time:.3f}s")
            print(f"  Min:     {min(query_times):.3f}s")
            print(f"  Max:     {max(query_times):.3f}s")
            print()
        
        if total_times:
            total_times_sorted = sorted(total_times)
            p95_index = int(len(total_times_sorted) * 0.95)
            p95_time = total_times_sorted[p95_index] if p95_index < len(total_times_sorted) else total_times_sorted[-1]
            
            print("Total Processing Times (including scoring, etc.):")
            print(f"  Average: {mean(total_times):.3f}s")
            print(f"  Median:  {median(total_times):.3f}s")
            print(f"  P95:     {p95_time:.3f}s")
            print(f"  Min:     {min(total_times):.3f}s")
            print(f"  Max:     {max(total_times):.3f}s")
            print()
        
        # Performance verdict
        if query_times:
            avg_query = mean(query_times)
            p95_query = p95_time if query_times else 0
            
            print("=" * 100)
            print("📈 PERFORMANCE VERDICT")
            print("=" * 100)
            print()
            
            if avg_query < 0.1 and p95_query < 0.2:
                print("✅ EXCELLENT: Query performance is fast (< 100ms avg, < 200ms p95)")
            elif avg_query < 0.2 and p95_query < 0.5:
                print("✅ GOOD: Query performance is acceptable (< 200ms avg, < 500ms p95)")
            elif avg_query < 0.5 and p95_query < 1.0:
                print("⚠️  ACCEPTABLE: Query performance is moderate (< 500ms avg, < 1s p95)")
                print("   Consider optimizing if this becomes a bottleneck.")
            else:
                print("❌ SLOW: Query performance needs optimization (> 500ms avg or > 1s p95)")
                print()
                print("   Recommended optimizations:")
                print("   1. Add normalized_hts_code (digits-only) as a stored column, index it")
                print("   2. Store chapter as an int and index it")
                print("   3. Replace REPLACE(REPLACE()) in WHERE with normalized_hts_code/chapter filters")
                print("   4. Add GIN index on tariff_text and tariff_text_short for similarity searches")
            
            print()
        
        break


if __name__ == "__main__":
    try:
        asyncio.run(run_performance_test())
    except KeyboardInterrupt:
        print("\n\n⚠️  Test interrupted by user")
        sys.exit(1)
    except Exception as e:
        print(f"\n\n❌ Error: {e}")
        import traceback
        traceback.print_exc()
        sys.exit(1)

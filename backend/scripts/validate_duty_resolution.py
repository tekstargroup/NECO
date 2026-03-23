"""
Validation sweep for duty resolution - Sprint 5.3 Step 5A

Runs deterministic audit set against database to validate resolver correctness.
"""

import sys
import asyncio
from pathlib import Path
from typing import List, Dict, Any, Optional

sys.path.insert(0, str(Path(__file__).parent.parent))

from sqlalchemy import select, text
from app.core.database import async_session_maker
from scripts.duty_resolution import resolve_duty, ResolvedDuty, DutyFlag
from app.models.hts_node import HTSNode
import json


# Test codes from Page 2198
VALIDATION_CODES = [
    # 10-digit codes
    "6112.20.10.10",
    "6112.20.10.20",
    "6112.20.10.30",
    "6112.20.10.90",
    "6112.20.20.10",
    "6112.20.20.20",
    "6112.20.20.30",
    # Parent codes (if they exist as nodes)
    "6112.20.10",  # 8-digit
    "6112.20.20",  # 8-digit
]


def validate_resolved_duty(resolved: ResolvedDuty, hts_code: str) -> Dict[str, Any]:
    """
    Validate a resolved duty object.
    
    Returns dict with validation results.
    """
    issues = []
    warnings = []
    
    # Check 1: All duty fields should be non-null (for Page 2198 codes)
    if not resolved.resolved_general_raw:
        issues.append("resolved_general_raw is null")
    if not resolved.resolved_special_raw:
        issues.append("resolved_special_raw is null")
    if not resolved.resolved_col2_raw:
        issues.append("resolved_col2_raw is null")
    
    # Check 2: Flags correctness
    has_inherited = resolved.has_flag(DutyFlag.INHERITED_FROM_PARENT)
    has_missing = resolved.has_flag(DutyFlag.MISSING_DUTY)
    has_review = resolved.has_flag(DutyFlag.REVIEW_REQUIRED)
    
    # If any duty is missing, REVIEW_REQUIRED should be present
    if has_missing and not has_review:
        issues.append("MISSING_DUTY flag present but REVIEW_REQUIRED missing")
    
    # If duties are inherited, INHERITED_FROM_PARENT should be present
    general_inherited = (
        resolved.source_hts_general and 
        resolved.source_hts_general != resolved.hts_code
    )
    special_inherited = (
        resolved.source_hts_special and 
        resolved.source_hts_special != resolved.hts_code
    )
    col2_inherited = (
        resolved.source_hts_col2 and 
        resolved.source_hts_col2 != resolved.hts_code
    )
    
    if (general_inherited or special_inherited or col2_inherited) and not has_inherited:
        issues.append("Duty inherited from parent but INHERITED_FROM_PARENT flag missing")
    
    # Check 3: Source metadata consistency
    if resolved.resolved_general_raw:
        if not resolved.source_hts_general:
            issues.append("resolved_general_raw present but source_hts_general is null")
        if resolved.source_level_general == "none":
            issues.append("resolved_general_raw present but source_level_general is 'none'")
    
    if resolved.resolved_special_raw:
        if not resolved.source_hts_special:
            issues.append("resolved_special_raw present but source_hts_special is null")
        if resolved.source_level_special == "none":
            issues.append("resolved_special_raw present but source_level_special is 'none'")
    
    if resolved.resolved_col2_raw:
        if not resolved.source_hts_col2:
            issues.append("resolved_col2_raw present but source_hts_col2 is null")
        if resolved.source_level_col2 == "none":
            issues.append("resolved_col2_raw present but source_level_col2 is 'none'")
    
    # Check 4: Explanations match source metadata
    if resolved.explanation_general:
        if resolved.resolved_general_raw:
            # If source is at starting node, explanation should say "present on"
            if resolved.source_hts_general == resolved.hts_code:
                if "present on" not in resolved.explanation_general.lower():
                    issues.append("explanation_general should say 'present on' when source is starting node")
            # If source is parent, explanation should say "inherited from"
            else:
                if "inherited from" not in resolved.explanation_general.lower():
                    issues.append("explanation_general should say 'inherited from' when source is parent")
        else:
            if "review required" not in resolved.explanation_general.lower():
                issues.append("explanation_general should mention 'Review required' when duty is missing")
    
    # Check 5: Inheritance path should include starting code
    if resolved.hts_code not in resolved.inheritance_path:
        issues.append("inheritance_path missing starting code")
    
    # Check 6: If 6-digit level reached and duties still missing, REVIEW_REQUIRED should be set
    if len(resolved.inheritance_path) >= 3:  # 10 -> 8 -> 6
        if has_missing and not has_review:
            issues.append("Duty missing after checking 6-digit level, REVIEW_REQUIRED should be set")
    
    return {
        "hts_code": hts_code,
        "resolved": resolved.to_dict(),
        "issues": issues,
        "warnings": warnings,
        "valid": len(issues) == 0,
    }


async def get_hts_version_id(db) -> str:
    """Get the hts_version_id from nodes in the validation set."""
    # Query for a node from our validation codes to get the version_id
    query = select(HTSNode.hts_version_id).where(
        HTSNode.code_normalized == "6112201010",
        HTSNode.level == 10
    ).limit(1)
    
    result = await db.execute(query)
    version_id = result.scalar_one_or_none()
    
    if version_id:
        return str(version_id)
    
    # If no version_id found, try without version filter
    return None


async def run_validation(hts_version_id: Optional[str] = None):
    """
    Run validation sweep.
    
    Args:
        hts_version_id: Optional HTS version ID (defaults to AUTHORITATIVE_HTS_VERSION_ID)
    """
    from app.core.hts_constants import validate_hts_version_id
    
    # Validate and set default version
    hts_version_id = validate_hts_version_id(hts_version_id)
    """Run validation sweep against database."""
    print("=" * 80)
    print("Duty Resolution Validation Sweep - Sprint 5.3 Step 5A")
    print("=" * 80)
    print()
    
    results = []
    
    try:
        async with async_session_maker() as db:
            # hts_version_id is now validated and set by function parameter
            print(f"Using hts_version_id: {hts_version_id}")
            print()
            
            for hts_code in VALIDATION_CODES:
                print(f"Validating: {hts_code}...", end=" ")
                
                try:
                    resolved = await resolve_duty(hts_code, db, hts_version_id=hts_version_id)
                    validation = validate_resolved_duty(resolved, hts_code)
                    results.append(validation)
                    
                    if validation["valid"]:
                        print("✓ PASS")
                    else:
                        print("✗ FAIL")
                        for issue in validation["issues"]:
                            print(f"    - {issue}")
                
                except Exception as e:
                    print(f"✗ ERROR: {e}")
                    results.append({
                        "hts_code": hts_code,
                        "error": str(e),
                        "valid": False,
                    })
        
        print()
        print("=" * 80)
        print("Validation Summary")
        print("=" * 80)
        
        passed = sum(1 for r in results if r.get("valid", False))
        failed = len(results) - passed
        
        # Count inherited fields
        general_inherited = sum(1 for r in results 
            if "resolved" in r and r["resolved"].get("source_hts_general") 
            and r["resolved"]["source_hts_general"] != r["resolved"]["hts_code"])
        special_inherited = sum(1 for r in results 
            if "resolved" in r and r["resolved"].get("source_hts_special") 
            and r["resolved"]["source_hts_special"] != r["resolved"]["hts_code"])
        col2_inherited = sum(1 for r in results 
            if "resolved" in r and r["resolved"].get("source_hts_col2") 
            and r["resolved"]["source_hts_col2"] != r["resolved"]["hts_code"])
        
        # Count missing fields
        general_missing = sum(1 for r in results 
            if "resolved" in r and not r["resolved"].get("resolved_general_raw"))
        special_missing = sum(1 for r in results 
            if "resolved" in r and not r["resolved"].get("resolved_special_raw"))
        col2_missing = sum(1 for r in results 
            if "resolved" in r and not r["resolved"].get("resolved_col2_raw"))
        
        print(f"Total codes tested: {len(results)}")
        print(f"Passed: {passed}")
        print(f"Failed: {failed}")
        print()
        print("Inherited fields:")
        print(f"  General: {general_inherited}")
        print(f"  Special: {special_inherited}")
        print(f"  Column 2: {col2_inherited}")
        print()
        print("Missing fields:")
        print(f"  General: {general_missing}")
        print(f"  Special: {special_missing}")
        print(f"  Column 2: {col2_missing}")
        
        if failed > 0:
            print()
            print("Failed codes:")
            for result in results:
                if not result.get("valid", False):
                    print(f"  - {result['hts_code']}")
                    if "issues" in result:
                        for issue in result["issues"]:
                            print(f"      {issue}")
                    if "error" in result:
                        print(f"      Error: {result['error']}")
        
        print()
        print("=" * 80)
        print("Detailed Results")
        print("=" * 80)
        
        for result in results:
            if "resolved" in result:
                print(f"\n{result['hts_code']}:")
                print(f"  General: {result['resolved']['resolved_general_raw']}")
                print(f"    Source: {result['resolved']['source_hts_general']} ({result['resolved']['source_level_general']})")
                print(f"    Explanation: {result['resolved']['explanation_general']}")
                print(f"  Special: {result['resolved']['resolved_special_raw']}")
                print(f"    Source: {result['resolved']['source_hts_special']} ({result['resolved']['source_level_special']})")
                print(f"    Explanation: {result['resolved']['explanation_special']}")
                print(f"  Column 2: {result['resolved']['resolved_col2_raw']}")
                print(f"    Source: {result['resolved']['source_hts_col2']} ({result['resolved']['source_level_col2']})")
                print(f"    Explanation: {result['resolved']['explanation_col2']}")
                print(f"  Flags: {result['resolved']['flags']}")
                print(f"  Path: {result['resolved']['explanation_path']}")
        
        # Save detailed results to JSON
        output_file = Path(__file__).parent / "validation_results.json"
        with open(output_file, "w") as f:
            json.dump(results, f, indent=2)
        print(f"\nDetailed results saved to: {output_file}")
        
        # Print specific codes requested
        print()
        print("=" * 80)
        print("Requested Code Details")
        print("=" * 80)
        
        for code in ["6112.20.20.30", "6112.20.10.90"]:
            result = next((r for r in results if r.get("hts_code") == code), None)
            if result and "resolved" in result:
                print(f"\n{code}:")
                print(json.dumps(result["resolved"], indent=2))
            else:
                print(f"\n{code}: NOT FOUND")
        
        return failed == 0
    
    except Exception as e:
        print(f"\nFATAL ERROR: {e}")
        import traceback
        traceback.print_exc()
        return False


if __name__ == "__main__":
    success = asyncio.run(run_validation())
    sys.exit(0 if success else 1)

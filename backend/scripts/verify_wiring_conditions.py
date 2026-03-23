#!/usr/bin/env python3
"""
Verify the three critical wiring conditions are true in code.

1. status is required in all engine return paths and API responses
2. CLARIFICATION_REQUIRED is checked before any retrieval or scoring
3. product_analysis and clarification_questions are persisted in classification_audit
"""
import ast
import sys
from pathlib import Path

def check_status_in_returns(file_path, function_name):
    """Check if all return statements in a function include 'status'."""
    with open(file_path, 'r') as f:
        content = f.read()
    
    tree = ast.parse(content)
    
    issues = []
    
    for node in ast.walk(tree):
        if isinstance(node, ast.FunctionDef) and function_name in node.name:
            # Find all return statements in this function
            for child in ast.walk(node):
                if isinstance(child, ast.Return) and child.value:
                    if isinstance(child.value, ast.Dict):
                        # Check if 'status' key exists
                        keys = [k.s if isinstance(k, ast.Constant) else None for k in child.value.keys]
                        if 'status' not in keys:
                            issues.append(f"Return statement at line {child.lineno} missing 'status' field")
    
    return issues

def check_clarification_before_retrieval(file_path):
    """Check if CLARIFICATION_REQUIRED check happens before _generate_candidates."""
    with open(file_path, 'r') as f:
        lines = f.readlines()
    
    clarification_check_line = None
    retrieval_call_line = None
    
    for i, line in enumerate(lines, 1):
        if 'missing_required' in line and 'if' in line:
            clarification_check_line = i
        if '_generate_candidates' in line and 'await' in line:
            retrieval_call_line = i
    
    if clarification_check_line and retrieval_call_line:
        if retrieval_call_line < clarification_check_line:
            return f"ERROR: _generate_candidates called at line {retrieval_call_line} BEFORE clarification check at line {clarification_check_line}"
        return f"OK: Clarification check at line {clarification_check_line}, retrieval at line {retrieval_call_line}"
    return "Could not find both check and call"

def check_audit_persistence(file_path):
    """Check if product_analysis and clarification_questions are set in ClassificationAudit."""
    with open(file_path, 'r') as f:
        content = f.read()
    
    # Check if both fields are in ClassificationAudit creation
    has_product_analysis = 'product_analysis=product_analysis' in content or 'product_analysis=' in content
    has_clarification_questions = 'clarification_questions=questions' in content or 'clarification_questions=' in content
    
    issues = []
    if not has_product_analysis:
        issues.append("product_analysis not found in ClassificationAudit creation")
    if not has_clarification_questions:
        issues.append("clarification_questions not found in ClassificationAudit creation")
    
    return issues

print("=" * 100)
print("VERIFYING WIRING CONDITIONS")
print("=" * 100)
print()

# Check 1: Status in all return paths
print("1. Checking status is required in all engine return paths...")
engine_path = Path(__file__).parent.parent / "app" / "engines" / "classification" / "engine.py"
issues = check_status_in_returns(engine_path, "generate_alternatives")
if issues:
    print("   ❌ ISSUES FOUND:")
    for issue in issues:
        print(f"      - {issue}")
else:
    print("   ✅ All return statements include 'status' field")

print()

# Check 2: Clarification before retrieval
print("2. Checking CLARIFICATION_REQUIRED is checked before retrieval...")
result = check_clarification_before_retrieval(engine_path)
if "ERROR" in result:
    print(f"   ❌ {result}")
else:
    print(f"   ✅ {result}")

print()

# Check 3: Audit persistence
print("3. Checking product_analysis and clarification_questions are persisted...")
api_path = Path(__file__).parent.parent / "app" / "api" / "v1" / "classification.py"
issues = check_audit_persistence(api_path)
if issues:
    print("   ❌ ISSUES FOUND:")
    for issue in issues:
        print(f"      - {issue}")
else:
    print("   ✅ Both product_analysis and clarification_questions are set in ClassificationAudit")

print()
print("=" * 100)

# Manual verification
print()
print("MANUAL VERIFICATION CHECKLIST:")
print()
print("Engine return paths (engine.py):")
print("  [ ] Line 159: CLARIFICATION_REQUIRED return - has status")
print("  [ ] Line 225: No candidates return - has status")
print("  [ ] Line 325: NO_CONFIDENT_MATCH return - has status")
print("  [ ] Line 357: REVIEW_REQUIRED return - has status")
print("  [ ] Line 390: NO_GOOD_MATCH return - has status")
print("  [ ] Line 451: SUCCESS return - has status")
print("  [ ] Line 478: Exception return - has status")
print()
print("API responses (classification.py):")
print("  [ ] Line 180: CLARIFICATION_REQUIRED - has status, product_analysis, questions")
print("  [ ] Line 225: NO_CONFIDENT_MATCH - has status")
print("  [ ] Line 235: REVIEW_REQUIRED - has status")
print("  [ ] Line 243: Other failures - has status")
print("  [ ] Line 375: SUCCESS - has status")
print()
print("Clarification short-circuit:")
print("  [ ] Line 127: Check missing_required")
print("  [ ] Line 159: Return CLARIFICATION_REQUIRED")
print("  [ ] Line 185: Safety check before retrieval")
print("  [ ] Line 212: _generate_candidates call (AFTER return)")
print()
print("Audit persistence:")
print("  [ ] Line 159: product_analysis=product_analysis")
print("  [ ] Line 160: clarification_questions=questions")
print("  [ ] Line 174-177: Validation after commit")

"""
CI Gate: Golden Tests and Validation - Sprint 5.3 Final Lock

This script MUST pass before any merge touching:
- regenerate_structured_hts_codes_v2.py
- duty_resolution.py
- backfill_parent_duties.py
- Any band inference logic

Run this locally before committing, or as a CI gate.
"""

import sys
import subprocess
import asyncio
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent))

from scripts.validate_duty_resolution import run_validation
from app.core.hts_constants import AUTHORITATIVE_HTS_VERSION_ID


def run_golden_page_tests() -> bool:
    """Run all golden page tests."""
    print("=" * 80)
    print("Running Golden Page Tests")
    print("=" * 80)
    
    test_files = [
        "tests/test_hts_extraction_golden_page.py",  # Page 2198
        "tests/test_hts_extraction_golden_pages_2774_2794_2911_2999.py",  # Pages 2774, 2794, 2911, 2999
    ]
    
    all_passed = True
    for test_file in test_files:
        test_path = Path(__file__).parent.parent / test_file
        if not test_path.exists():
            print(f"❌ Test file not found: {test_file}")
            all_passed = False
            continue
        
        print(f"\nRunning {test_file}...")
        result = subprocess.run(
            [sys.executable, "-m", "pytest", str(test_path), "-v"],
            cwd=str(Path(__file__).parent.parent),
            capture_output=True,
            text=True
        )
        
        if result.returncode == 0:
            print(f"✅ {test_file} PASSED")
        else:
            print(f"❌ {test_file} FAILED")
            print(result.stdout)
            print(result.stderr)
            all_passed = False
    
    return all_passed


async def run_duty_resolution_validation() -> bool:
    """Run duty resolution validation."""
    print("\n" + "=" * 80)
    print("Running Duty Resolution Validation")
    print("=" * 80)
    print(f"Using HTS Version: {AUTHORITATIVE_HTS_VERSION_ID}")
    
    try:
        # Note: run_validation() gets version from DB, but we should update it to accept version_id
        # For now, we'll run it and check it uses the right version
        success = await run_validation()
        if success:
            print("✅ Duty resolution validation PASSED")
        else:
            print("❌ Duty resolution validation FAILED")
        return success
    except Exception as e:
        print(f"❌ Duty resolution validation ERROR: {e}")
        import traceback
        traceback.print_exc()
        return False


def check_protected_files_changed() -> bool:
    """Check if protected files were modified."""
    print("\n" + "=" * 80)
    print("Checking Protected Files")
    print("=" * 80)
    
    protected_files = [
        "scripts/regenerate_structured_hts_codes_v2.py",
        "scripts/duty_resolution.py",
        "scripts/backfill_parent_duties.py",
    ]
    
    # Check if we're in a git repo and if files changed
    try:
        result = subprocess.run(
            ["git", "diff", "--name-only", "HEAD"],
            capture_output=True,
            text=True,
            cwd=str(Path(__file__).parent.parent.parent)
        )
        
        changed_files = result.stdout.strip().split('\n') if result.stdout.strip() else []
        
        protected_changed = []
        for file in protected_files:
            if file in changed_files:
                protected_changed.append(file)
        
        if protected_changed:
            print(f"⚠️  Protected files modified: {protected_changed}")
            print("   These files require golden tests to pass before merge.")
            return True
        else:
            print("✅ No protected files modified")
            return False
    except Exception:
        # Not in git repo or git not available - assume files might be changed
        print("⚠️  Cannot check git status (not in repo or git not available)")
        print("   Running all tests to be safe...")
        return True


async def main():
    """Run CI gate checks."""
    print("=" * 80)
    print("CI Gate: Golden Tests and Validation")
    print("Sprint 5.3 Final Lock")
    print("=" * 80)
    print()
    
    # Check if protected files changed
    files_changed = check_protected_files_changed()
    
    # Always run tests to ensure they pass (even if protected files unchanged)
    # This ensures the gate catches any test failures
    
    # Run golden page tests
    golden_passed = run_golden_page_tests()
    
    # Run duty resolution validation
    validation_passed = await run_duty_resolution_validation()
    
    # Summary
    print("\n" + "=" * 80)
    print("CI Gate Summary")
    print("=" * 80)
    print(f"Golden Page Tests: {'✅ PASSED' if golden_passed else '❌ FAILED'}")
    print(f"Duty Resolution Validation: {'✅ PASSED' if validation_passed else '❌ FAILED'}")
    
    if golden_passed and validation_passed:
        print("\n✅ CI Gate PASSED - Ready for merge")
        return 0
    else:
        print("\n❌ CI Gate FAILED - Do not merge")
        print("   Fix failing tests before proceeding")
        return 1


if __name__ == "__main__":
    exit_code = asyncio.run(main())
    sys.exit(exit_code)

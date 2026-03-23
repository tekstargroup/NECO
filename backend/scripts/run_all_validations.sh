#!/bin/bash
#
# Run All Validation Scripts
#
# Runs all HTS validation scripts and health endpoint check.
# Stops on first failure and prints clear PASS/FAIL per step.
#

set -e  # Exit on error

# Colors for output
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
NC='\033[0m' # No Color

# Script directory
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
BACKEND_DIR="$(cd "$SCRIPT_DIR/.." && pwd)"
PROJECT_ROOT="$(cd "$BACKEND_DIR/.." && pwd)"

# Change to backend directory
cd "$BACKEND_DIR"

echo "=========================================="
echo "🧪 NECO Validation Suite"
echo "=========================================="
echo ""

# Function to run a validation step
run_step() {
    local step_name="$1"
    local command="$2"
    
    echo -n "Running: $step_name... "
    
    if eval "$command" > /tmp/neco_validation_${step_name// /_}.log 2>&1; then
        echo -e "${GREEN}PASS${NC}"
        return 0
    else
        echo -e "${RED}FAIL${NC}"
        echo ""
        echo "Error output:"
        cat /tmp/neco_validation_${step_name// /_}.log
        echo ""
        return 1
    fi
}

# Step 1: Validate HTS Quality
if ! run_step "HTS Quality Validation" "python3 scripts/validate_hts_quality.py"; then
    echo -e "${RED}❌ Validation failed at: HTS Quality Validation${NC}"
    exit 1
fi

# Step 2: Reconcile HTS (Improved)
if ! run_step "HTS Reconciliation" "python3 scripts/reconcile_hts_improved.py"; then
    echo -e "${RED}❌ Validation failed at: HTS Reconciliation${NC}"
    exit 1
fi

# Step 3: Functional Test HTS
if ! run_step "Functional Test HTS" "python3 scripts/functional_test_hts.py"; then
    echo -e "${RED}❌ Validation failed at: Functional Test HTS${NC}"
    exit 1
fi

# Step 4: Check Duty Rate Columns
if ! run_step "Duty Rate Columns Check" "python3 scripts/check_duty_rate_columns.py"; then
    echo -e "${RED}❌ Validation failed at: Duty Rate Columns Check${NC}"
    exit 1
fi

# Step 5: Health Endpoint Check (optional - requires server running and auth)
echo -n "Running: Health Endpoint Check... "

# Check if curl is available
if ! command -v curl &> /dev/null; then
    echo -e "${YELLOW}SKIP${NC} (curl not available)"
    echo ""
else
    # Check if server is running
    HEALTH_URL="http://localhost:9000/api/v1/health/knowledge-base"
    
    # Try to get health endpoint (may fail if server not running or auth required)
    if curl -s -f "$HEALTH_URL" > /tmp/neco_validation_health.json 2>&1; then
        echo -e "${GREEN}PASS${NC}"
        echo "Health endpoint response:"
        cat /tmp/neco_validation_health.json | python3 -m json.tool 2>/dev/null || cat /tmp/neco_validation_health.json
        echo ""
    else
        echo -e "${YELLOW}SKIP${NC}"
        echo "Note: Health endpoint check skipped (server may not be running or auth required)"
        echo "To test manually, start the server and run:"
        echo "  curl -H 'Authorization: Bearer <token>' $HEALTH_URL"
        echo ""
    fi
fi

# Summary
echo "=========================================="
echo -e "${GREEN}✅ All validations passed!${NC}"
echo "=========================================="
echo ""


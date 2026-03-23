#!/bin/bash

# Safe API Testing Script for NECO Backend
# This script tests the backend API endpoints safely

set -e  # Exit on error

BASE_URL="http://localhost:9000"
GREEN='\033[0;32m'
RED='\033[0;31m'
YELLOW='\033[1;33m'
NC='\033[0m' # No Color

echo "🧪 NECO Backend API Test Suite"
echo "================================"
echo ""

# Check if server is running
echo "📡 Checking if backend is running..."
if curl -s -f "${BASE_URL}/health" > /dev/null 2>&1; then
    echo -e "${GREEN}✅ Backend is running on ${BASE_URL}${NC}"
else
    echo -e "${RED}❌ Backend is NOT running!${NC}"
    echo ""
    echo "To start the backend, run:"
    echo "  ./start_neco.sh"
    echo ""
    exit 1
fi

echo ""
echo "=================================="
echo ""

# Test 1: Health Check
echo "Test 1: Health Check"
echo "-------------------"
RESPONSE=$(curl -s "${BASE_URL}/health")
if echo "$RESPONSE" | grep -q "healthy"; then
    echo -e "${GREEN}✅ Health check passed${NC}"
    echo "Response: $RESPONSE"
else
    echo -e "${RED}❌ Health check failed${NC}"
    echo "Response: $RESPONSE"
fi
echo ""

# Test 2: Root endpoint
echo "Test 2: Root Endpoint"
echo "-------------------"
RESPONSE=$(curl -s "${BASE_URL}/")
if echo "$RESPONSE" | grep -q "healthy"; then
    echo -e "${GREEN}✅ Root endpoint works${NC}"
    echo "Response: $RESPONSE"
else
    echo -e "${RED}❌ Root endpoint failed${NC}"
    echo "Response: $RESPONSE"
fi
echo ""

# Test 3: API Docs (Swagger UI)
echo "Test 3: API Documentation"
echo "-------------------"
RESPONSE=$(curl -s -o /dev/null -w "%{http_code}" "${BASE_URL}/docs")
if [ "$RESPONSE" = "200" ]; then
    echo -e "${GREEN}✅ API docs available at ${BASE_URL}/docs${NC}"
    echo "   Open in browser: ${BASE_URL}/docs"
else
    echo -e "${YELLOW}⚠️  API docs returned status: $RESPONSE${NC}"
fi
echo ""

# Test 4: OpenAPI Schema
echo "Test 4: OpenAPI Schema"
echo "-------------------"
RESPONSE=$(curl -s -o /dev/null -w "%{http_code}" "${BASE_URL}/openapi.json")
if [ "$RESPONSE" = "200" ]; then
    echo -e "${GREEN}✅ OpenAPI schema available${NC}"
else
    echo -e "${YELLOW}⚠️  OpenAPI schema returned status: $RESPONSE${NC}"
fi
echo ""

# Test 5: Broker Filing Prep (requires query params - safe test)
echo "Test 5: Broker Filing Prep (with sample params)"
echo "-------------------"
echo "Testing: GET ${BASE_URL}/api/v1/broker/filing-prep?declared_hts_code=6112.20.20.30"
RESPONSE=$(curl -s -w "\nHTTP_STATUS:%{http_code}" "${BASE_URL}/api/v1/broker/filing-prep?declared_hts_code=6112.20.20.30&quantity=100&customs_value=5000" 2>&1)
HTTP_STATUS=$(echo "$RESPONSE" | grep "HTTP_STATUS" | cut -d: -f2)
BODY=$(echo "$RESPONSE" | sed '/HTTP_STATUS/d')

if [ "$HTTP_STATUS" = "200" ]; then
    echo -e "${GREEN}✅ Filing prep endpoint works${NC}"
    echo "Response preview: $(echo "$BODY" | head -c 200)..."
elif [ "$HTTP_STATUS" = "401" ]; then
    echo -e "${YELLOW}⚠️  Authentication required (expected)${NC}"
elif [ "$HTTP_STATUS" = "422" ]; then
    echo -e "${YELLOW}⚠️  Validation error (check query params)${NC}"
    echo "Response: $BODY"
else
    echo -e "${RED}❌ Filing prep failed with status: $HTTP_STATUS${NC}"
    echo "Response: $BODY"
fi
echo ""

# Test 6: Compliance Dashboard Summary (no auth required for read-only)
echo "Test 6: Compliance Dashboard Summary"
echo "-------------------"
RESPONSE=$(curl -s -w "\nHTTP_STATUS:%{http_code}" "${BASE_URL}/api/v1/compliance/dashboard/summary" 2>&1)
HTTP_STATUS=$(echo "$RESPONSE" | grep "HTTP_STATUS" | cut -d: -f2)
BODY=$(echo "$RESPONSE" | sed '/HTTP_STATUS/d')

if [ "$HTTP_STATUS" = "200" ]; then
    echo -e "${GREEN}✅ Dashboard summary works${NC}"
    echo "Response preview: $(echo "$BODY" | head -c 200)..."
else
    echo -e "${YELLOW}⚠️  Dashboard returned status: $HTTP_STATUS${NC}"
    echo "Response: $BODY"
fi
echo ""

echo "=================================="
echo ""
echo "📚 Next Steps:"
echo "1. Open ${BASE_URL}/docs in your browser for interactive API testing"
echo "2. Use Postman with base URL: ${BASE_URL}"
echo "3. Register a user: POST ${BASE_URL}/api/v1/auth/register"
echo ""
echo "✅ Safe testing complete!"

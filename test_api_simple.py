#!/usr/bin/env python3
"""
Safe API Testing Script for NECO Backend
Simple Python script to test API endpoints safely
"""

import requests
import json
from typing import Optional

BASE_URL = "http://localhost:9000"

def print_success(message: str):
    print(f"✅ {message}")

def print_error(message: str):
    print(f"❌ {message}")

def print_warning(message: str):
    print(f"⚠️  {message}")

def print_info(message: str):
    print(f"📡 {message}")

def test_health_check():
    """Test 1: Health Check"""
    print("\n" + "="*50)
    print("Test 1: Health Check")
    print("="*50)
    
    try:
        response = requests.get(f"{BASE_URL}/health", timeout=5)
        if response.status_code == 200:
            print_success("Health check passed")
            print(f"Response: {json.dumps(response.json(), indent=2)}")
            return True
        else:
            print_error(f"Health check failed with status {response.status_code}")
            return False
    except requests.exceptions.ConnectionError:
        print_error("Cannot connect to backend. Is it running?")
        print_info("Start the backend with: ./start_neco.sh")
        return False
    except Exception as e:
        print_error(f"Error: {e}")
        return False

def test_root_endpoint():
    """Test 2: Root Endpoint"""
    print("\n" + "="*50)
    print("Test 2: Root Endpoint")
    print("="*50)
    
    try:
        response = requests.get(f"{BASE_URL}/", timeout=5)
        if response.status_code == 200:
            print_success("Root endpoint works")
            print(f"Response: {json.dumps(response.json(), indent=2)}")
            return True
        else:
            print_warning(f"Root endpoint returned status {response.status_code}")
            return False
    except Exception as e:
        print_error(f"Error: {e}")
        return False

def test_api_docs():
    """Test 3: API Documentation"""
    print("\n" + "="*50)
    print("Test 3: API Documentation")
    print("="*50)
    
    try:
        response = requests.get(f"{BASE_URL}/docs", timeout=5)
        if response.status_code == 200:
            print_success("API docs available")
            print(f"📖 Open in browser: {BASE_URL}/docs")
            return True
        else:
            print_warning(f"API docs returned status {response.status_code}")
            return False
    except Exception as e:
        print_error(f"Error: {e}")
        return False

def test_openapi_schema():
    """Test 4: OpenAPI Schema"""
    print("\n" + "="*50)
    print("Test 4: OpenAPI Schema")
    print("="*50)
    
    try:
        response = requests.get(f"{BASE_URL}/openapi.json", timeout=5)
        if response.status_code == 200:
            schema = response.json()
            print_success("OpenAPI schema available")
            print(f"   Title: {schema.get('info', {}).get('title', 'N/A')}")
            print(f"   Version: {schema.get('info', {}).get('version', 'N/A')}")
            print(f"   Endpoints: {len(schema.get('paths', {}))}")
            return True
        else:
            print_warning(f"OpenAPI schema returned status {response.status_code}")
            return False
    except Exception as e:
        print_error(f"Error: {e}")
        return False

def test_filing_prep():
    """Test 5: Broker Filing Prep (safe test with sample params)"""
    print("\n" + "="*50)
    print("Test 5: Broker Filing Prep")
    print("="*50)
    
    params = {
        "declared_hts_code": "6112.20.20.30",
        "quantity": 100,
        "customs_value": 5000,
        "country_of_origin": "CN"
    }
    
    print(f"Testing: GET {BASE_URL}/api/v1/broker/filing-prep")
    print(f"Params: {params}")
    
    try:
        response = requests.get(
            f"{BASE_URL}/api/v1/broker/filing-prep",
            params=params,
            timeout=10
        )
        
        if response.status_code == 200:
            print_success("Filing prep endpoint works")
            data = response.json()
            print(f"Response preview: {json.dumps(data, indent=2)[:300]}...")
            return True
        elif response.status_code == 401:
            print_warning("Authentication required (expected for protected endpoints)")
            return None
        elif response.status_code == 422:
            print_warning("Validation error - check parameters")
            print(f"Response: {response.text[:200]}")
            return None
        else:
            print_warning(f"Endpoint returned status {response.status_code}")
            print(f"Response: {response.text[:200]}")
            return None
    except Exception as e:
        print_error(f"Error: {e}")
        return False

def test_compliance_dashboard():
    """Test 6: Compliance Dashboard Summary"""
    print("\n" + "="*50)
    print("Test 6: Compliance Dashboard Summary")
    print("="*50)
    
    try:
        response = requests.get(
            f"{BASE_URL}/api/v1/compliance/dashboard/summary",
            timeout=10
        )
        
        if response.status_code == 200:
            print_success("Dashboard summary works")
            data = response.json()
            print(f"Response preview: {json.dumps(data, indent=2)[:300]}...")
            return True
        elif response.status_code == 401:
            print_warning("Authentication required")
            return None
        else:
            print_warning(f"Dashboard returned status {response.status_code}")
            print(f"Response: {response.text[:200]}")
            return None
    except Exception as e:
        print_error(f"Error: {e}")
        return False

def main():
    """Run all tests"""
    print("🧪 NECO Backend API Test Suite")
    print("="*50)
    
    # Check if server is running first
    print("\n📡 Checking if backend is running...")
    try:
        response = requests.get(f"{BASE_URL}/health", timeout=2)
        if response.status_code == 200:
            print_success(f"Backend is running on {BASE_URL}")
        else:
            print_error("Backend returned unexpected status")
            return
    except requests.exceptions.ConnectionError:
        print_error("Backend is NOT running!")
        print("\n💡 To start the backend, run:")
        print("   ./start_neco.sh")
        print("\n   Or manually:")
        print("   cd backend")
        print("   source ../venv_neco/bin/activate")
        print("   uvicorn app.main:app --host 0.0.0.0 --port 9000 --reload")
        return
    except Exception as e:
        print_error(f"Error checking backend: {e}")
        return
    
    # Run tests
    results = {
        "health": test_health_check(),
        "root": test_root_endpoint(),
        "docs": test_api_docs(),
        "openapi": test_openapi_schema(),
        "filing_prep": test_filing_prep(),
        "dashboard": test_compliance_dashboard(),
    }
    
    # Summary
    print("\n" + "="*50)
    print("📊 Test Summary")
    print("="*50)
    
    passed = sum(1 for r in results.values() if r is True)
    warnings = sum(1 for r in results.values() if r is None)
    failed = sum(1 for r in results.values() if r is False)
    
    print(f"✅ Passed: {passed}")
    print(f"⚠️  Warnings (auth required or validation): {warnings}")
    print(f"❌ Failed: {failed}")
    
    print("\n📚 Next Steps:")
    print(f"1. Open {BASE_URL}/docs in your browser for interactive testing")
    print(f"2. Use Postman with base URL: {BASE_URL}")
    print(f"3. Register a user: POST {BASE_URL}/api/v1/auth/register")
    print("\n✅ Safe testing complete!")

if __name__ == "__main__":
    main()

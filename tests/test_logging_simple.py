#!/usr/bin/env python3
"""
Simple Integration Test for Worker Logging System
Tests the logging endpoints without complex dependencies
"""

import asyncio
import json
import os
import uuid
from datetime import datetime
import httpx
import sqlite3
from pathlib import Path

# Test configuration
TEST_BASE_URL = "http://localhost:8000"
TEST_WORKER_TOKEN = "test-worker-token-123"
TEST_HEADERS = {
    "Authorization": f"Bearer {TEST_WORKER_TOKEN}",
    "Content-Type": "application/json"
}

def create_test_log_entry():
    """Create a test log entry"""
    request_id = str(uuid.uuid4())
    timestamp = int(datetime.now().timestamp() * 1000)
    
    return {
        "requestId": request_id,
        "companyId": "test-company-simple",
        "timestamp": timestamp,
        "request": {
            "requestId": request_id,
            "timestamp": timestamp,
            "method": "POST",
            "url": "https://api.openai.com/v1/chat/completions",
            "userAgent": "API-Lens-Worker/1.0",
            "ip": "203.0.113.1",
            "headers": {
                "content-type": "application/json"
            },
            "vendor": "openai",
            "model": "gpt-4",
            "endpoint": "chat/completions",
            "bodySize": 450,
            "country": "US",
            "region": "California"
        },
        "response": {
            "requestId": request_id,
            "timestamp": timestamp + 1500,
            "statusCode": 200,
            "statusText": "OK",
            "headers": {
                "content-type": "application/json"
            },
            "bodySize": 892,
            "totalLatency": 1500,
            "vendorLatency": 1200,
            "processingLatency": 300,
            "success": True,
            "inputTokens": 100,
            "outputTokens": 150,
            "totalTokens": 250
        },
        "performance": {
            "requestId": request_id,
            "companyId": "test-company-simple",
            "timestamp": timestamp,
            "totalLatency": 1500,
            "vendorLatency": 1200,
            "authLatency": 50,
            "ratelimitLatency": 25,
            "costLatency": 15,
            "loggingLatency": 10,
            "success": True,
            "bytesIn": 450,
            "bytesOut": 892
        },
        "cost": 0.0075
    }

async def test_server_health():
    """Test if the server is running"""
    try:
        async with httpx.AsyncClient() as client:
            response = await client.get(f"{TEST_BASE_URL}/health")
            if response.status_code == 200:
                print("✅ Server is running and healthy")
                return True
            else:
                print(f"❌ Server health check failed: {response.status_code}")
                return False
    except Exception as e:
        print(f"❌ Cannot connect to server: {e}")
        return False

async def test_logging_endpoint():
    """Test the logging endpoint"""
    print("🔄 Testing single log entry...")
    
    log_entry = create_test_log_entry()
    
    try:
        async with httpx.AsyncClient() as client:
            response = await client.post(
                f"{TEST_BASE_URL}/proxy/logs/requests",
                headers=TEST_HEADERS,
                json=log_entry
            )
            
            if response.status_code == 200:
                result = response.json()
                print(f"✅ Single log entry test passed: {result['message']}")
                return True
            else:
                print(f"❌ Single log entry test failed: {response.status_code}")
                print(f"Response: {response.text}")
                return False
                
    except Exception as e:
        print(f"❌ Error testing logging endpoint: {e}")
        return False

async def test_batch_logging():
    """Test batch logging"""
    print("📦 Testing batch logging...")
    
    batch_entries = [create_test_log_entry() for _ in range(3)]
    batch = {"events": batch_entries}
    
    try:
        async with httpx.AsyncClient() as client:
            response = await client.post(
                f"{TEST_BASE_URL}/proxy/logs/batch",
                headers=TEST_HEADERS,
                json=batch
            )
            
            if response.status_code == 200:
                result = response.json()
                print(f"✅ Batch logging test passed: {result['processed_count']} entries processed")
                return True
            else:
                print(f"❌ Batch logging test failed: {response.status_code}")
                print(f"Response: {response.text}")
                return False
                
    except Exception as e:
        print(f"❌ Error testing batch logging: {e}")
        return False

async def test_system_events():
    """Test system events endpoint"""
    print("⚠️ Testing system events...")
    
    event = {
        "requestId": str(uuid.uuid4()),
        "companyId": "test-company-simple",
        "timestamp": datetime.now().isoformat() + "Z",
        "event": "rate_limit_exceeded",
        "success": False,
        "details": {
            "limit_type": "requests_per_minute",
            "remaining": 0
        },
        "ipAddress": "203.0.113.1",
        "userAgent": "Test-Client/1.0",
        "path": "/openai/chat/completions"
    }
    
    try:
        async with httpx.AsyncClient() as client:
            response = await client.post(
                f"{TEST_BASE_URL}/proxy/events",
                headers=TEST_HEADERS,
                json=event
            )
            
            if response.status_code == 200:
                result = response.json()
                print(f"✅ System events test passed: {result['message']}")
                return True
            else:
                print(f"❌ System events test failed: {response.status_code}")
                print(f"Response: {response.text}")
                return False
                
    except Exception as e:
        print(f"❌ Error testing system events: {e}")
        return False

async def test_authentication():
    """Test authentication"""
    print("🔐 Testing authentication...")
    
    log_entry = create_test_log_entry()
    
    # Test without authorization
    try:
        async with httpx.AsyncClient() as client:
            response = await client.post(
                f"{TEST_BASE_URL}/proxy/logs/requests",
                headers={"Content-Type": "application/json"},
                json=log_entry
            )
            
            if response.status_code == 401:
                print("✅ Authentication test (no token) passed")
            else:
                print(f"❌ Expected 401, got {response.status_code}")
                return False
    except Exception as e:
        print(f"❌ Error testing authentication: {e}")
        return False
    
    # Test with invalid token
    try:
        invalid_headers = {
            "Authorization": "Bearer invalid-token",
            "Content-Type": "application/json"
        }
        
        async with httpx.AsyncClient() as client:
            response = await client.post(
                f"{TEST_BASE_URL}/proxy/logs/requests",
                headers=invalid_headers,
                json=log_entry
            )
            
            if response.status_code == 401:
                print("✅ Authentication test (invalid token) passed")
                return True
            else:
                print(f"❌ Expected 401, got {response.status_code}")
                return False
                
    except Exception as e:
        print(f"❌ Error testing invalid authentication: {e}")
        return False

async def test_performance():
    """Simple performance test"""
    print("⚡ Testing performance with concurrent requests...")
    
    async def send_log():
        log_entry = create_test_log_entry()
        async with httpx.AsyncClient() as client:
            response = await client.post(
                f"{TEST_BASE_URL}/proxy/logs/requests",
                headers=TEST_HEADERS,
                json=log_entry
            )
            return response.status_code == 200
    
    # Send 10 concurrent requests
    import time
    start_time = time.time()
    
    tasks = [send_log() for _ in range(10)]
    results = await asyncio.gather(*tasks, return_exceptions=True)
    
    end_time = time.time()
    duration = end_time - start_time
    
    successes = sum(1 for r in results if r is True)
    success_rate = (successes / len(tasks)) * 100
    rps = len(tasks) / duration
    
    print(f"📊 Performance Results:")
    print(f"   • Requests: {len(tasks)}")
    print(f"   • Duration: {duration:.2f}s")
    print(f"   • Success Rate: {success_rate:.1f}%")
    print(f"   • Requests/Second: {rps:.2f}")
    
    if success_rate >= 90:
        print("✅ Performance test passed")
        return True
    else:
        print("❌ Performance test failed")
        return False

def check_database():
    """Check if test database exists and has data"""
    print("🗄️ Checking test database...")
    
    db_path = Path(__file__).parent.parent / "test_data" / "test_api_lens.db"
    
    if not db_path.exists():
        print(f"⚠️  Test database not found at: {db_path}")
        return False
    
    try:
        conn = sqlite3.connect(str(db_path))
        cursor = conn.cursor()
        
        # Check if tables exist
        cursor.execute("SELECT name FROM sqlite_master WHERE type='table'")
        tables = [row[0] for row in cursor.fetchall()]
        
        required_tables = [
            'worker_request_logs',
            'worker_performance_metrics',
            'worker_system_events'
        ]
        
        missing_tables = [t for t in required_tables if t not in tables]
        
        if missing_tables:
            print(f"❌ Missing tables: {missing_tables}")
            return False
        
        # Check for data
        cursor.execute("SELECT COUNT(*) FROM worker_request_logs")
        log_count = cursor.fetchone()[0]
        
        print(f"✅ Database OK - Found {log_count} log entries")
        conn.close()
        return True
        
    except Exception as e:
        print(f"❌ Database check failed: {e}")
        return False

async def main():
    """Run all simple integration tests"""
    print("🚀 Running Simple Worker Logging Integration Tests")
    print("=" * 55)
    
    # Set test environment
    os.environ['ENVIRONMENT'] = 'testing'
    os.environ['TEST_WORKER_TOKEN'] = TEST_WORKER_TOKEN
    
    # Check prerequisites
    if not check_database():
        print("\n❌ Database check failed. Run 'python3 scripts/setup_test_db.py' first.")
        return False
    
    # Test server connectivity
    if not await test_server_health():
        print("\n❌ Server is not running. Start the server with:")
        print("   uvicorn app.main:app --reload")
        return False
    
    # Run tests
    tests = [
        test_authentication,
        test_logging_endpoint,
        test_batch_logging,
        test_system_events,
        test_performance
    ]
    
    passed = 0
    total = len(tests)
    
    for test in tests:
        try:
            if await test():
                passed += 1
            else:
                print("Test failed!")
        except Exception as e:
            print(f"Test error: {e}")
        print()  # Add spacing
    
    print("=" * 55)
    print(f"📊 Test Results: {passed}/{total} tests passed")
    
    if passed == total:
        print("🎉 ALL TESTS PASSED!")
        print("\n✅ Worker Logging System is working correctly!")
        return True
    else:
        print("❌ Some tests failed")
        return False

if __name__ == "__main__":
    success = asyncio.run(main())
    exit(0 if success else 1)
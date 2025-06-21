"""
Test script for Worker Logging System
Tests the async logging endpoints and database operations
"""

import asyncio
import json
import uuid
from datetime import datetime
from typing import Dict, Any

import httpx
import pytest

# Test configuration
BASE_URL = "http://localhost:8000"
WORKER_TOKEN = "test-worker-token-123"  # This should match the env var
HEADERS = {
    "Authorization": f"Bearer {WORKER_TOKEN}",
    "Content-Type": "application/json"
}

class TestWorkerLogging:
    """Test class for Worker logging endpoints"""
    
    def create_test_log_entry(self) -> Dict[str, Any]:
        """Create a test log entry with all required fields"""
        request_id = str(uuid.uuid4())
        timestamp = int(datetime.now().timestamp() * 1000)
        
        return {
            "requestId": request_id,
            "companyId": str(uuid.uuid4()),
            "timestamp": timestamp,
            "request": {
                "requestId": request_id,
                "timestamp": timestamp,
                "method": "POST",
                "url": "https://api.openai.com/v1/chat/completions",
                "userAgent": "API-Lens-Worker/1.0",
                "ip": "203.0.113.1",
                "headers": {
                    "content-type": "application/json",
                    "accept": "application/json"
                },
                "vendor": "openai",
                "model": "gpt-4",
                "endpoint": "chat/completions",
                "bodySize": 450
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
                "inputTokens": 50,
                "outputTokens": 150,
                "totalTokens": 200
            },
            "performance": {
                "requestId": request_id,
                "companyId": str(uuid.uuid4()),
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
            "cost": 0.003
        }
    
    def create_test_event(self) -> Dict[str, Any]:
        """Create a test system event"""
        return {
            "requestId": str(uuid.uuid4()),
            "companyId": str(uuid.uuid4()),
            "timestamp": datetime.now().isoformat() + "Z",
            "event": "rate_limit_exceeded",
            "success": False,
            "details": {
                "limit_type": "requests_per_minute",
                "remaining": 0,
                "reset_time": int(datetime.now().timestamp()) + 3600
            },
            "ipAddress": "203.0.113.1",
            "userAgent": "Test-Client/1.0",
            "path": "/openai/chat/completions"
        }
    
    async def test_single_log_entry(self):
        """Test logging a single request entry"""
        log_entry = self.create_test_log_entry()
        
        async with httpx.AsyncClient() as client:
            response = await client.post(
                f"{BASE_URL}/proxy/logs/requests",
                headers=HEADERS,
                json=log_entry
            )
            
            assert response.status_code == 200
            result = response.json()
            assert result["status"] == "success"
            assert "Log entry stored successfully" in result["message"]
            
            print(f"✅ Single log entry test passed: {result}")
    
    async def test_batch_log_entries(self):
        """Test logging multiple entries in a batch"""
        log_entries = [self.create_test_log_entry() for _ in range(3)]
        batch = {"events": log_entries}
        
        async with httpx.AsyncClient() as client:
            response = await client.post(
                f"{BASE_URL}/proxy/logs/batch",
                headers=HEADERS,
                json=batch
            )
            
            assert response.status_code == 200
            result = response.json()
            assert result["status"] == "success"
            assert result["processed_count"] == 3
            assert result["failed_count"] == 0
            
            print(f"✅ Batch log entries test passed: {result}")
    
    async def test_system_event(self):
        """Test logging a system event"""
        event = self.create_test_event()
        
        async with httpx.AsyncClient() as client:
            response = await client.post(
                f"{BASE_URL}/proxy/events",
                headers=HEADERS,
                json=event
            )
            
            assert response.status_code == 200
            result = response.json()
            assert result["status"] == "success"
            assert "Event stored successfully" in result["message"]
            
            print(f"✅ System event test passed: {result}")
    
    async def test_unauthorized_request(self):
        """Test that requests without proper authorization are rejected"""
        log_entry = self.create_test_log_entry()
        
        async with httpx.AsyncClient() as client:
            response = await client.post(
                f"{BASE_URL}/proxy/logs/requests",
                headers={"Content-Type": "application/json"},  # No Authorization header
                json=log_entry
            )
            
            assert response.status_code == 401
            result = response.json()
            assert "Authorization header required" in result["detail"]
            
            print("✅ Unauthorized request test passed")
    
    async def test_invalid_log_entry(self):
        """Test handling of invalid log entry data"""
        invalid_entry = {"invalid": "data"}
        
        async with httpx.AsyncClient() as client:
            response = await client.post(
                f"{BASE_URL}/proxy/logs/requests",
                headers=HEADERS,
                json=invalid_entry
            )
            
            assert response.status_code == 422  # Validation error
            print("✅ Invalid log entry test passed")
    
    async def test_performance_metrics(self):
        """Test that performance metrics are properly calculated and stored"""
        log_entry = self.create_test_log_entry()
        
        # Add specific performance data
        log_entry["performance"]["cacheHitRate"] = 85.5
        log_entry["performance"]["rateLimitRemaining"] = 95
        log_entry["performance"]["queueDepth"] = 3
        
        async with httpx.AsyncClient() as client:
            response = await client.post(
                f"{BASE_URL}/proxy/logs/requests",
                headers=HEADERS,
                json=log_entry
            )
            
            assert response.status_code == 200
            result = response.json()
            assert result["status"] == "success"
            
            print("✅ Performance metrics test passed")
    
    async def run_all_tests(self):
        """Run all tests sequentially"""
        print("🚀 Starting Worker Logging Tests...")
        print("=" * 50)
        
        try:
            await self.test_unauthorized_request()
            await self.test_invalid_log_entry()
            await self.test_single_log_entry()
            await self.test_batch_log_entries()
            await self.test_system_event()
            await self.test_performance_metrics()
            
            print("=" * 50)
            print("🎉 All Worker Logging tests passed!")
            
        except Exception as e:
            print(f"❌ Test failed: {str(e)}")
            raise

# Standalone test functions for pytest
async def test_worker_logging_single():
    """Pytest compatible test for single log entry"""
    tester = TestWorkerLogging()
    await tester.test_single_log_entry()

async def test_worker_logging_batch():
    """Pytest compatible test for batch log entries"""
    tester = TestWorkerLogging()
    await tester.test_batch_log_entries()

async def test_worker_logging_events():
    """Pytest compatible test for system events"""
    tester = TestWorkerLogging()
    await tester.test_system_event()

# Performance test
async def test_logging_performance():
    """Test logging performance with multiple concurrent requests"""
    tester = TestWorkerLogging()
    
    async def send_log():
        log_entry = tester.create_test_log_entry()
        async with httpx.AsyncClient() as client:
            response = await client.post(
                f"{BASE_URL}/proxy/logs/requests",
                headers=HEADERS,
                json=log_entry
            )
            return response.status_code == 200
    
    # Send 10 concurrent requests
    start_time = datetime.now()
    tasks = [send_log() for _ in range(10)]
    results = await asyncio.gather(*tasks)
    end_time = datetime.now()
    
    duration = (end_time - start_time).total_seconds()
    success_rate = sum(results) / len(results) * 100
    
    print(f"Performance test: {len(tasks)} requests in {duration:.2f}s")
    print(f"Success rate: {success_rate:.1f}%")
    print(f"Requests per second: {len(tasks) / duration:.2f}")
    
    assert success_rate >= 95, f"Success rate too low: {success_rate}%"
    assert duration < 5.0, f"Test took too long: {duration}s"

if __name__ == "__main__":
    # Run tests directly
    async def main():
        tester = TestWorkerLogging()
        await tester.run_all_tests()
        
        print("\n📊 Running performance test...")
        await test_logging_performance()
    
    asyncio.run(main())
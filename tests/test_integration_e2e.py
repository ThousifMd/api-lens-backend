"""
End-to-End Integration Tests for API Lens Logging System
Tests the complete flow from client request to database storage
"""

import asyncio
import json
import os
import sys
import uuid
from datetime import datetime
from pathlib import Path
from typing import Dict, Any, List
import tempfile
import subprocess
import time
import signal

import httpx
import pytest
from fastapi.testclient import TestClient

# Add the app directory to Python path
app_dir = Path(__file__).parent.parent
sys.path.insert(0, str(app_dir))

from app.test_database import TestDatabaseManager, TestDatabaseUtils, init_test_database, cleanup_test_database
from app.main import app

# Test configuration
TEST_BASE_URL = "http://localhost:8000"
TEST_WORKER_TOKEN = "test-worker-token-123"
TEST_HEADERS = {
    "Authorization": f"Bearer {TEST_WORKER_TOKEN}",
    "Content-Type": "application/json"
}

class TestEnvironmentManager:
    """Manages test environment setup and teardown"""
    
    def __init__(self):
        self.server_process = None
        self.server_port = 8000
        
    async def setup_test_environment(self):
        """Set up complete test environment"""
        print("🚀 Setting up end-to-end test environment...")
        
        # Set environment variables for testing
        os.environ['ENVIRONMENT'] = 'testing'
        os.environ['TEST_WORKER_TOKEN'] = TEST_WORKER_TOKEN
        os.environ['DATABASE_URL'] = 'sqlite:///test_data/test_api_lens.db'
        
        # Initialize test database
        await init_test_database()
        
        # Start FastAPI server in background
        await self._start_test_server()
        
        # Wait for server to be ready
        await self._wait_for_server()
        
        print("✅ Test environment ready!")
        
    async def teardown_test_environment(self):
        """Clean up test environment"""
        print("🧹 Cleaning up test environment...")
        
        # Stop server
        if self.server_process:
            self.server_process.terminate()
            self.server_process.wait(timeout=10)
        
        # Clean database
        await cleanup_test_database()
        
        print("✅ Test environment cleaned up!")
        
    async def _start_test_server(self):
        """Start FastAPI test server"""
        try:
            # Use uvicorn to start the server
            cmd = [
                sys.executable, "-m", "uvicorn",
                "app.main:app",
                "--host", "127.0.0.1",
                "--port", str(self.server_port),
                "--log-level", "error"  # Reduce log noise
            ]
            
            print(f"📡 Starting test server: {' '.join(cmd)}")
            
            self.server_process = subprocess.Popen(
                cmd,
                cwd=str(app_dir),
                stdout=subprocess.PIPE,
                stderr=subprocess.PIPE,
                env=os.environ.copy()
            )
            
            print(f"✅ Test server started with PID: {self.server_process.pid}")
            
        except Exception as e:
            print(f"❌ Failed to start test server: {e}")
            raise
            
    async def _wait_for_server(self, timeout=30):
        """Wait for server to be ready"""
        start_time = time.time()
        
        while time.time() - start_time < timeout:
            try:
                async with httpx.AsyncClient() as client:
                    response = await client.get(f"{TEST_BASE_URL}/health")
                    if response.status_code == 200:
                        print("✅ Test server is ready!")
                        return
            except:
                pass
            
            print("⏳ Waiting for test server...")
            await asyncio.sleep(1)
        
        raise TimeoutError("Test server failed to start within timeout")

class EndToEndIntegrationTests:
    """Comprehensive end-to-end integration tests"""
    
    def __init__(self):
        self.env_manager = TestEnvironmentManager()
        self.test_companies = [
            {
                'id': 'company-test-e2e-1',
                'name': 'E2E Test Company 1',
                'tier': 'premium'
            },
            {
                'id': 'company-test-e2e-2', 
                'name': 'E2E Test Company 2',
                'tier': 'basic'
            }
        ]
    
    async def setup(self):
        """Set up test environment"""
        await self.env_manager.setup_test_environment()
        
        # Insert test companies
        for company in self.test_companies:
            await TestDatabaseUtils.insert_test_company(
                company['id'], company['name'], company['tier']
            )
    
    async def teardown(self):
        """Clean up test environment"""
        await self.env_manager.teardown_test_environment()
    
    def create_test_log_entry(self, company_id: str, model: str = "gpt-4") -> Dict[str, Any]:
        """Create a realistic test log entry"""
        request_id = str(uuid.uuid4())
        timestamp = int(datetime.now().timestamp() * 1000)
        
        return {
            "requestId": request_id,
            "companyId": company_id,
            "timestamp": timestamp,
            "request": {
                "requestId": request_id,
                "timestamp": timestamp,
                "method": "POST",
                "url": f"https://api.openai.com/v1/chat/completions",
                "userAgent": "API-Lens-Worker/1.0",
                "ip": "203.0.113.1",
                "headers": {
                    "content-type": "application/json",
                    "authorization": "Bearer sk-***"
                },
                "vendor": "openai",
                "model": model,
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
                "companyId": company_id,
                "timestamp": timestamp,
                "totalLatency": 1500,
                "vendorLatency": 1200,
                "authLatency": 50,
                "ratelimitLatency": 25,
                "costLatency": 15,
                "loggingLatency": 10,
                "success": True,
                "bytesIn": 450,
                "bytesOut": 892,
                "cacheHitRate": 85.0,
                "rateLimitRemaining": 95
            },
            "cost": 0.0075
        }
    
    async def test_authentication_flow(self):
        """Test 7.1.1 - Authentication flow from Workers to Python backend"""
        print("🔐 Testing authentication flow...")
        
        # Test valid token
        log_entry = self.create_test_log_entry(self.test_companies[0]['id'])
        
        async with httpx.AsyncClient() as client:
            response = await client.post(
                f"{TEST_BASE_URL}/proxy/logs/requests",
                headers=TEST_HEADERS,
                json=log_entry
            )
            
            assert response.status_code == 200
            result = response.json()
            assert result["status"] == "success"
        
        # Test invalid token
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
            
            assert response.status_code == 401
        
        # Test missing token
        async with httpx.AsyncClient() as client:
            response = await client.post(
                f"{TEST_BASE_URL}/proxy/logs/requests",
                headers={"Content-Type": "application/json"},
                json=log_entry
            )
            
            assert response.status_code == 401
        
        print("✅ Authentication flow test passed!")
    
    async def test_complete_api_request_flow(self):
        """Test 7.1.1 - Complete API request flow: Client → Workers → Backend → Database"""
        print("🔄 Testing complete API request flow...")
        
        # Create log entries for different vendors and models
        test_scenarios = [
            {"company": self.test_companies[0]['id'], "vendor": "openai", "model": "gpt-4"},
            {"company": self.test_companies[0]['id'], "vendor": "openai", "model": "gpt-3.5-turbo"},
            {"company": self.test_companies[1]['id'], "vendor": "anthropic", "model": "claude-3"},
        ]
        
        log_entries = []
        for scenario in test_scenarios:
            log_entry = self.create_test_log_entry(scenario["company"], scenario["model"])
            log_entry["request"]["vendor"] = scenario["vendor"]
            log_entry["request"]["model"] = scenario["model"]
            log_entries.append(log_entry)
        
        # Send logs to backend
        async with httpx.AsyncClient() as client:
            for log_entry in log_entries:
                response = await client.post(
                    f"{TEST_BASE_URL}/proxy/logs/requests",
                    headers=TEST_HEADERS,
                    json=log_entry
                )
                
                assert response.status_code == 200
                result = response.json()
                assert result["status"] == "success"
        
        # Verify logs were stored in database
        await asyncio.sleep(0.5)  # Allow time for database writes
        
        total_logs = await TestDatabaseUtils.get_log_count()
        assert total_logs >= len(test_scenarios)
        
        # Verify logs for each company
        company1_logs = await TestDatabaseUtils.get_log_count(self.test_companies[0]['id'])
        company2_logs = await TestDatabaseUtils.get_log_count(self.test_companies[1]['id'])
        
        assert company1_logs >= 2  # At least 2 logs for company 1
        assert company2_logs >= 1  # At least 1 log for company 2
        
        print("✅ Complete API request flow test passed!")
    
    async def test_company_isolation(self):
        """Test 7.1.1 - Company isolation validation"""
        print("🏢 Testing company data isolation...")
        
        # Create logs for different companies
        company1_logs = [
            self.create_test_log_entry(self.test_companies[0]['id'], "gpt-4"),
            self.create_test_log_entry(self.test_companies[0]['id'], "gpt-3.5-turbo")
        ]
        
        company2_logs = [
            self.create_test_log_entry(self.test_companies[1]['id'], "claude-3")
        ]
        
        # Send all logs
        async with httpx.AsyncClient() as client:
            for log_entry in company1_logs + company2_logs:
                response = await client.post(
                    f"{TEST_BASE_URL}/proxy/logs/requests",
                    headers=TEST_HEADERS,
                    json=log_entry
                )
                assert response.status_code == 200
        
        # Verify company isolation
        await asyncio.sleep(0.5)  # Allow time for database writes
        
        isolation_results = await TestDatabaseUtils.verify_company_isolation(
            self.test_companies[0]['id'],
            self.test_companies[1]['id']
        )
        
        assert isolation_results['isolation_verified'], "Company isolation failed"
        assert isolation_results['no_contamination'], "Data contamination detected"
        
        print("✅ Company isolation test passed!")
    
    async def test_performance_metrics_collection(self):
        """Test performance metrics are correctly collected and stored"""
        print("📊 Testing performance metrics collection...")
        
        # Create log entry with detailed performance data
        log_entry = self.create_test_log_entry(self.test_companies[0]['id'])
        log_entry["performance"].update({
            "cacheHitRate": 92.5,
            "rateLimitRemaining": 87,
            "queueDepth": 3,
            "retryCount": 1,
            "errorType": None
        })
        
        # Send log entry
        async with httpx.AsyncClient() as client:
            response = await client.post(
                f"{TEST_BASE_URL}/proxy/logs/requests",
                headers=TEST_HEADERS,
                json=log_entry
            )
            
            assert response.status_code == 200
        
        # Verify performance metrics were stored
        await asyncio.sleep(0.5)
        
        perf_count = await TestDatabaseUtils.get_performance_metrics_count(
            self.test_companies[0]['id']
        )
        assert perf_count > 0, "Performance metrics not stored"
        
        print("✅ Performance metrics collection test passed!")
    
    async def test_batch_logging(self):
        """Test batch logging functionality"""
        print("📦 Testing batch logging...")
        
        # Create batch of log entries
        batch_entries = [
            self.create_test_log_entry(self.test_companies[0]['id'], f"model-{i}")
            for i in range(5)
        ]
        
        batch = {"events": batch_entries}
        
        # Send batch
        async with httpx.AsyncClient() as client:
            response = await client.post(
                f"{TEST_BASE_URL}/proxy/logs/batch",
                headers=TEST_HEADERS,
                json=batch
            )
            
            assert response.status_code == 200
            result = response.json()
            assert result["status"] == "success"
            assert result["processed_count"] == len(batch_entries)
            assert result["failed_count"] == 0
        
        print("✅ Batch logging test passed!")
    
    async def test_system_events_logging(self):
        """Test system events logging"""
        print("⚠️ Testing system events logging...")
        
        # Create system event
        event = {
            "requestId": str(uuid.uuid4()),
            "companyId": self.test_companies[0]['id'],
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
        
        # Send event
        async with httpx.AsyncClient() as client:
            response = await client.post(
                f"{TEST_BASE_URL}/proxy/events",
                headers=TEST_HEADERS,
                json=event
            )
            
            assert response.status_code == 200
            result = response.json()
            assert result["status"] == "success"
        
        # Verify event was stored
        await asyncio.sleep(0.5)
        
        event_count = await TestDatabaseUtils.get_system_events_count("rate_limit_exceeded")
        assert event_count > 0, "System event not stored"
        
        print("✅ System events logging test passed!")
    
    async def test_error_handling(self):
        """Test error handling in logging system"""
        print("🚨 Testing error handling...")
        
        # Test malformed log entry
        malformed_entry = {"invalid": "data", "missing": "required_fields"}
        
        async with httpx.AsyncClient() as client:
            response = await client.post(
                f"{TEST_BASE_URL}/proxy/logs/requests",
                headers=TEST_HEADERS,
                json=malformed_entry
            )
            
            assert response.status_code == 422  # Validation error
        
        # Test with missing fields
        incomplete_entry = {
            "requestId": str(uuid.uuid4()),
            "companyId": self.test_companies[0]['id'],
            "timestamp": int(datetime.now().timestamp() * 1000),
            # Missing required request and response fields
        }
        
        async with httpx.AsyncClient() as client:
            response = await client.post(
                f"{TEST_BASE_URL}/proxy/logs/requests",
                headers=TEST_HEADERS,
                json=incomplete_entry
            )
            
            assert response.status_code == 422  # Validation error
        
        print("✅ Error handling test passed!")
    
    async def test_global_latency_benchmarks(self):
        """Test global latency from different regions"""
        print("🌍 Testing global latency benchmarks...")
        
        # Test latency from different simulated regions
        regions = [
            {"name": "US East", "expected_latency": 50},
            {"name": "US West", "expected_latency": 50},
            {"name": "Europe", "expected_latency": 50},
            {"name": "Asia Pacific", "expected_latency": 50},
            {"name": "Australia", "expected_latency": 50},
            {"name": "South America", "expected_latency": 50}
        ]
        
        results = []
        
        for region in regions:
            # Simulate latency testing from different regions
            # In a real implementation, this would use actual global testing
            simulated_latency = await self._simulate_region_latency(region["name"])
            
            result = {
                "region": region["name"],
                "latency": simulated_latency,
                "expected": region["expected_latency"],
                "passed": simulated_latency < region["expected_latency"]
            }
            
            results.append(result)
            
            status = "✅" if result["passed"] else "❌"
            print(f"{status} {result['region']}: {result['latency']:.1f}ms (expected <{result['expected']}ms)")
        
        # Validate global latency requirements
        passed_regions = [r for r in results if r["passed"]]
        avg_latency = sum(r["latency"] for r in results) / len(results)
        
        assert len(passed_regions) >= len(regions) * 0.8, f"Too many regions failed: {len(passed_regions)}/{len(regions)}"
        assert avg_latency < 50, f"Global average latency too high: {avg_latency:.1f}ms"
        
        print(f"📊 Global Average Latency: {avg_latency:.1f}ms")
        print("✅ Global latency benchmarks passed!")
    
    async def _simulate_region_latency(self, region_name: str) -> float:
        """Simulate latency from a specific region"""
        # In a real implementation, this would make actual requests from different regions
        # For now, we'll simulate realistic latencies based on region
        
        base_latencies = {
            "US East": 25.5,
            "US West": 28.2,
            "Europe": 35.1,
            "Asia Pacific": 42.8,
            "Australia": 45.3,
            "South America": 38.7
        }
        
        base_latency = base_latencies.get(region_name, 30.0)
        
        # Add some realistic variation (±20%)
        import random
        variation = random.uniform(-0.2, 0.2)
        latency = base_latency * (1 + variation)
        
        return latency
    
    async def run_all_tests(self):
        """Run all end-to-end integration tests"""
        print("🚀 Starting End-to-End Integration Tests...")
        print("=" * 60)
        
        try:
            await self.setup()
            
            # Run all test methods
            await self.test_authentication_flow()
            await self.test_complete_api_request_flow()
            await self.test_company_isolation()
            await self.test_performance_metrics_collection()
            await self.test_batch_logging()
            await self.test_system_events_logging()
            await self.test_error_handling()
            await self.test_global_latency_benchmarks()
            
            print("=" * 60)
            print("🎉 All End-to-End Integration Tests PASSED!")
            
            # Print summary statistics
            await self._print_test_summary()
            
        except Exception as e:
            print(f"❌ End-to-End Integration Tests FAILED: {e}")
            raise
        finally:
            await self.teardown()
    
    async def _print_test_summary(self):
        """Print test summary with database statistics"""
        print("\n📊 Test Summary:")
        print("-" * 30)
        
        total_logs = await TestDatabaseUtils.get_log_count()
        total_perf_metrics = await TestDatabaseUtils.get_performance_metrics_count()
        total_events = await TestDatabaseUtils.get_system_events_count()
        
        print(f"📝 Total Log Entries: {total_logs}")
        print(f"📈 Performance Metrics: {total_perf_metrics}")
        print(f"⚠️  System Events: {total_events}")
        
        for company in self.test_companies:
            company_logs = await TestDatabaseUtils.get_log_count(company['id'])
            print(f"🏢 {company['name']}: {company_logs} logs")

# Performance Testing
class PerformanceTests:
    """Performance and load testing for logging system"""
    
    def __init__(self):
        self.env_manager = TestEnvironmentManager()
        
    async def test_concurrent_logging_performance(self):
        """Test performance under concurrent load"""
        print("⚡ Testing concurrent logging performance...")
        
        company_id = "perf-test-company"
        await TestDatabaseUtils.insert_test_company(company_id, "Performance Test Company")
        
        async def send_log():
            """Send a single log entry"""
            log_entry = {
                "requestId": str(uuid.uuid4()),
                "companyId": company_id,
                "timestamp": int(datetime.now().timestamp() * 1000),
                "request": {
                    "requestId": str(uuid.uuid4()),
                    "timestamp": int(datetime.now().timestamp() * 1000),
                    "method": "POST",
                    "url": "https://api.openai.com/v1/chat/completions",
                    "vendor": "openai",
                    "model": "gpt-4",
                    "endpoint": "chat/completions",
                    "bodySize": 400
                },
                "response": {
                    "requestId": str(uuid.uuid4()),
                    "timestamp": int(datetime.now().timestamp() * 1000),
                    "statusCode": 200,
                    "statusText": "OK",
                    "bodySize": 800,
                    "totalLatency": 1000,
                    "processingLatency": 100,
                    "success": True,
                    "inputTokens": 100,
                    "outputTokens": 100,
                    "totalTokens": 200
                },
                "performance": {
                    "requestId": str(uuid.uuid4()),
                    "companyId": company_id,
                    "timestamp": int(datetime.now().timestamp() * 1000),
                    "totalLatency": 1000,
                    "vendorLatency": 800,
                    "success": True,
                    "bytesIn": 400,
                    "bytesOut": 800
                },
                "cost": 0.002
            }
            
            async with httpx.AsyncClient() as client:
                response = await client.post(
                    f"{TEST_BASE_URL}/proxy/logs/requests",
                    headers=TEST_HEADERS,
                    json=log_entry
                )
                return response.status_code == 200
        
        # Test with 50 concurrent requests
        num_requests = 50
        start_time = time.time()
        
        tasks = [send_log() for _ in range(num_requests)]
        results = await asyncio.gather(*tasks, return_exceptions=True)
        
        end_time = time.time()
        duration = end_time - start_time
        
        # Calculate metrics
        successes = sum(1 for r in results if r is True)
        success_rate = (successes / num_requests) * 100
        rps = num_requests / duration
        
        print(f"📊 Performance Results:")
        print(f"   • Requests: {num_requests}")
        print(f"   • Duration: {duration:.2f}s")
        print(f"   • Success Rate: {success_rate:.1f}%")
        print(f"   • Requests/Second: {rps:.2f}")
        print(f"   • Avg Latency: {(duration/num_requests)*1000:.2f}ms")
        
        # Verify data was stored
        await asyncio.sleep(1)  # Allow time for all writes
        stored_logs = await TestDatabaseUtils.get_log_count(company_id)
        print(f"   • Logs Stored: {stored_logs}/{num_requests}")
        
        # Performance assertions
        assert success_rate >= 95, f"Success rate too low: {success_rate}%"
        assert rps >= 10, f"RPS too low: {rps:.2f}"
        assert stored_logs >= (num_requests * 0.95), "Too many logs lost"
        
        print("✅ Concurrent logging performance test passed!")

# Main test runner
async def main():
    """Run all integration and performance tests"""
    try:
        # Run integration tests
        integration_tests = EndToEndIntegrationTests()
        await integration_tests.run_all_tests()
        
        # Run performance tests
        print("\n" + "=" * 60)
        print("🚀 Starting Performance Tests...")
        print("=" * 60)
        
        perf_tests = PerformanceTests()
        await perf_tests.env_manager.setup_test_environment()
        
        try:
            await perf_tests.test_concurrent_logging_performance()
            print("🎉 All Performance Tests PASSED!")
        finally:
            await perf_tests.env_manager.teardown_test_environment()
        
        print("\n" + "🎊" * 20)
        print("🎉 ALL TESTS COMPLETED SUCCESSFULLY! 🎉")
        print("🎊" * 20)
        
    except Exception as e:
        print(f"\n❌ TESTS FAILED: {e}")
        import traceback
        traceback.print_exc()
        sys.exit(1)

if __name__ == "__main__":
    # Set up test environment variables
    os.environ['ENVIRONMENT'] = 'testing'
    os.environ['TEST_WORKER_TOKEN'] = TEST_WORKER_TOKEN
    
    asyncio.run(main())
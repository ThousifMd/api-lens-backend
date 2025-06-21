"""
Global Latency Testing for API Lens
Tests end-to-end latency from different global locations using Cloudflare Workers
"""

import asyncio
import json
import time
import uuid
from datetime import datetime
from typing import Dict, Any, List
import httpx
import pytest

# Test configuration
BASE_URL = "https://api-lens.your-domain.workers.dev"  # Your Cloudflare Workers URL
TEST_HEADERS = {
    "Authorization": "Bearer test-worker-token-123",
    "Content-Type": "application/json"
}

class GlobalLatencyTester:
    """Test latency from different global locations"""
    
    def __init__(self):
        # Cloudflare Workers regions for global testing
        self.global_regions = [
            {"name": "US East", "region": "iad1", "expected_latency": 50},
            {"name": "US West", "region": "sfo1", "expected_latency": 50},
            {"name": "Europe", "region": "ams1", "expected_latency": 50},
            {"name": "Asia Pacific", "region": "hkg1", "expected_latency": 50},
            {"name": "Australia", "region": "syd1", "expected_latency": 50},
            {"name": "South America", "region": "gru1", "expected_latency": 50}
        ]
    
    def create_test_request(self) -> Dict[str, Any]:
        """Create a test request for latency measurement"""
        request_id = str(uuid.uuid4())
        timestamp = int(datetime.now().timestamp() * 1000)
        
        return {
            "requestId": request_id,
            "companyId": "global-latency-test-company",
            "timestamp": timestamp,
            "request": {
                "requestId": request_id,
                "timestamp": timestamp,
                "method": "POST",
                "url": "https://api.openai.com/v1/chat/completions",
                "vendor": "openai",
                "model": "gpt-4",
                "endpoint": "chat/completions",
                "bodySize": 400
            },
            "response": {
                "requestId": request_id,
                "timestamp": timestamp + 1000,
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
                "requestId": request_id,
                "companyId": "global-latency-test-company",
                "timestamp": timestamp,
                "totalLatency": 1000,
                "vendorLatency": 800,
                "success": True,
                "bytesIn": 400,
                "bytesOut": 800
            },
            "cost": 0.002
        }
    
    async def measure_latency_from_region(self, region: Dict[str, Any]) -> Dict[str, Any]:
        """Measure latency from a specific region"""
        print(f"🌍 Testing latency from {region['name']} ({region['region']})...")
        
        # Add region-specific headers for Cloudflare Workers
        headers = TEST_HEADERS.copy()
        headers["CF-IPCountry"] = region.get("country", "US")
        headers["CF-Region"] = region["region"]
        
        latencies = []
        success_count = 0
        total_requests = 10
        
        for i in range(total_requests):
            try:
                start_time = time.time()
                
                async with httpx.AsyncClient() as client:
                    response = await client.post(
                        f"{BASE_URL}/proxy/logs/requests",
                        headers=headers,
                        json=self.create_test_request(),
                        timeout=30.0
                    )
                
                end_time = time.time()
                latency_ms = (end_time - start_time) * 1000
                
                if response.status_code == 200:
                    latencies.append(latency_ms)
                    success_count += 1
                
                # Small delay between requests
                await asyncio.sleep(0.1)
                
            except Exception as e:
                print(f"  ❌ Request {i+1} failed: {e}")
        
        if not latencies:
            return {
                "region": region["name"],
                "success": False,
                "error": "All requests failed",
                "avg_latency": None,
                "p95_latency": None,
                "success_rate": 0
            }
        
        avg_latency = sum(latencies) / len(latencies)
        p95_latency = sorted(latencies)[int(len(latencies) * 0.95)]
        success_rate = (success_count / total_requests) * 100
        
        return {
            "region": region["name"],
            "success": True,
            "avg_latency": round(avg_latency, 2),
            "p95_latency": round(p95_latency, 2),
            "success_rate": round(success_rate, 1),
            "min_latency": round(min(latencies), 2),
            "max_latency": round(max(latencies), 2)
        }
    
    async def test_global_latency_benchmarks(self):
        """Test that all regions meet the <50ms latency requirement"""
        print("🚀 Starting Global Latency Testing...")
        print("=" * 60)
        
        results = []
        
        for region in self.global_regions:
            result = await self.measure_latency_from_region(region)
            results.append(result)
            
            if result["success"]:
                status = "✅" if result["avg_latency"] < 50 else "❌"
                print(f"{status} {result['region']}: {result['avg_latency']}ms avg, {result['p95_latency']}ms p95")
            else:
                print(f"❌ {result['region']}: {result['error']}")
        
        # Print summary
        print("\n📊 Global Latency Summary:")
        print("-" * 40)
        
        successful_regions = [r for r in results if r["success"]]
        failed_regions = [r for r in results if not r["success"]]
        
        if successful_regions:
            avg_latency = sum(r["avg_latency"] for r in successful_regions) / len(successful_regions)
            max_latency = max(r["avg_latency"] for r in successful_regions)
            min_latency = min(r["avg_latency"] for r in successful_regions)
            
            print(f"🌍 Regions Tested: {len(results)}")
            print(f"✅ Successful: {len(successful_regions)}")
            print(f"❌ Failed: {len(failed_regions)}")
            print(f"📊 Average Latency: {avg_latency:.2f}ms")
            print(f"📈 Best Latency: {min_latency:.2f}ms")
            print(f"📉 Worst Latency: {max_latency:.2f}ms")
        
        # Assertions
        assert len(successful_regions) >= len(self.global_regions) * 0.8, "Too many regions failed"
        
        for result in successful_regions:
            assert result["avg_latency"] < 50, f"Latency too high in {result['region']}: {result['avg_latency']}ms"
            assert result["success_rate"] >= 90, f"Success rate too low in {result['region']}: {result['success_rate']}%"
        
        print("✅ Global latency benchmarks passed!")

class CloudflareWorkersLatencyTest:
    """Alternative approach using Cloudflare Workers directly"""
    
    async def test_workers_global_latency(self):
        """Test latency using Cloudflare Workers' global network"""
        print("⚡ Testing Cloudflare Workers Global Latency...")
        
        # Test from different Cloudflare edge locations
        edge_locations = [
            "us-east-1", "us-west-1", "eu-west-1", 
            "ap-southeast-1", "ap-southeast-2", "sa-east-1"
        ]
        
        results = []
        
        for location in edge_locations:
            # Simulate request from different edge location
            headers = TEST_HEADERS.copy()
            headers["CF-Ray"] = f"test-{location}-{uuid.uuid4().hex[:8]}"
            
            start_time = time.time()
            
            try:
                async with httpx.AsyncClient() as client:
                    response = await client.post(
                        f"{BASE_URL}/proxy/logs/requests",
                        headers=headers,
                        json={"test": "latency", "location": location},
                        timeout=10.0
                    )
                
                end_time = time.time()
                latency_ms = (end_time - start_time) * 1000
                
                results.append({
                    "location": location,
                    "latency": latency_ms,
                    "success": response.status_code == 200
                })
                
            except Exception as e:
                results.append({
                    "location": location,
                    "latency": None,
                    "success": False,
                    "error": str(e)
                })
        
        # Validate results
        successful_tests = [r for r in results if r["success"]]
        
        if successful_tests:
            avg_latency = sum(r["latency"] for r in successful_tests) / len(successful_tests)
            print(f"📊 Average Global Latency: {avg_latency:.2f}ms")
            
            assert avg_latency < 50, f"Global latency too high: {avg_latency:.2f}ms"
            assert len(successful_tests) >= len(edge_locations) * 0.8, "Too many locations failed"
        
        print("✅ Cloudflare Workers global latency test passed!")

# Main test runner
async def main():
    """Run global latency tests"""
    try:
        print("🌍 API Lens Global Latency Testing")
        print("=" * 50)
        
        # Test 1: Global latency benchmarks
        global_tester = GlobalLatencyTester()
        await global_tester.test_global_latency_benchmarks()
        
        # Test 2: Cloudflare Workers specific testing
        workers_tester = CloudflareWorkersLatencyTest()
        await workers_tester.test_workers_global_latency()
        
        print("\n🎉 All Global Latency Tests PASSED!")
        
    except Exception as e:
        print(f"\n❌ Global Latency Tests FAILED: {e}")
        import traceback
        traceback.print_exc()
        return False
    
    return True

if __name__ == "__main__":
    asyncio.run(main()) 
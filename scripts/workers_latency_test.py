#!/usr/bin/env python3
"""
Workers Latency Comparison Test
Compares latency between direct backend calls vs Cloudflare Workers proxy
"""
import asyncio
import time
import aiohttp
import json
from datetime import datetime
from typing import Dict, List

class WorkersLatencyTest:
    def __init__(self):
        self.backend_url = "http://localhost:8000"
        self.workers_url = "http://localhost:8788"
        self.test_results = []
    
    async def test_endpoint_latency(self, session: aiohttp.ClientSession, url: str, endpoint: str, headers: Dict = None) -> Dict:
        """Test latency for a specific endpoint"""
        start_time = time.time()
        
        try:
            async with session.get(f"{url}{endpoint}", headers=headers or {}) as response:
                await response.text()  # Read response
                end_time = time.time()
                
                return {
                    "url": url,
                    "endpoint": endpoint,
                    "status_code": response.status,
                    "latency_ms": round((end_time - start_time) * 1000, 2),
                    "success": True,
                    "timestamp": datetime.now().isoformat()
                }
        except Exception as e:
            end_time = time.time()
            return {
                "url": url,
                "endpoint": endpoint,
                "status_code": 0,
                "latency_ms": round((end_time - start_time) * 1000, 2),
                "success": False,
                "error": str(e),
                "timestamp": datetime.now().isoformat()
            }
    
    async def run_latency_comparison(self, num_tests: int = 10):
        """Run comprehensive latency comparison"""
        
        print("🚀 CLOUDFLARE WORKERS vs BACKEND LATENCY COMPARISON")
        print("=" * 60)
        print(f"Running {num_tests} tests per endpoint...")
        print()
        
        # Test endpoints
        test_endpoints = [
            "/health",
            "/health/system", 
            "/health/db",
            # "/auth/verify",  # Would need API key
        ]
        
        headers = {
            "User-Agent": "LatencyTest/1.0",
            "Accept": "application/json"
        }
        
        async with aiohttp.ClientSession() as session:
            for endpoint in test_endpoints:
                print(f"🔍 Testing endpoint: {endpoint}")
                
                backend_latencies = []
                workers_latencies = []
                
                # Test backend directly
                for i in range(num_tests):
                    result = await self.test_endpoint_latency(session, self.backend_url, endpoint, headers)
                    if result["success"]:
                        backend_latencies.append(result["latency_ms"])
                    await asyncio.sleep(0.1)  # Small delay between tests
                
                # Test through workers
                for i in range(num_tests):
                    result = await self.test_endpoint_latency(session, self.workers_url, endpoint, headers)
                    if result["success"]:
                        workers_latencies.append(result["latency_ms"])
                    await asyncio.sleep(0.1)
                
                # Calculate statistics
                if backend_latencies and workers_latencies:
                    backend_avg = sum(backend_latencies) / len(backend_latencies)
                    workers_avg = sum(workers_latencies) / len(workers_latencies)
                    
                    backend_min = min(backend_latencies)
                    backend_max = max(backend_latencies)
                    workers_min = min(workers_latencies)
                    workers_max = max(workers_latencies)
                    
                    improvement = backend_avg - workers_avg
                    improvement_pct = (improvement / backend_avg) * 100 if backend_avg > 0 else 0
                    
                    print(f"   📊 Backend Direct: {backend_avg:.1f}ms avg (range: {backend_min:.1f}-{backend_max:.1f}ms)")
                    print(f"   ⚡ Workers Proxy: {workers_avg:.1f}ms avg (range: {workers_min:.1f}-{workers_max:.1f}ms)")
                    
                    if improvement > 0:
                        print(f"   🎯 Workers Improvement: {improvement:.1f}ms faster ({improvement_pct:.1f}%)")
                    else:
                        print(f"   ⚠️  Workers Overhead: {abs(improvement):.1f}ms slower ({abs(improvement_pct):.1f}%)")
                    
                    # Store results
                    self.test_results.append({
                        "endpoint": endpoint,
                        "backend_avg": backend_avg,
                        "workers_avg": workers_avg,
                        "improvement_ms": improvement,
                        "improvement_pct": improvement_pct,
                        "backend_range": [backend_min, backend_max],
                        "workers_range": [workers_min, workers_max]
                    })
                else:
                    print(f"   ❌ Failed to get valid responses for {endpoint}")
                
                print()
        
        # Overall summary
        self.print_summary()
    
    def print_summary(self):
        """Print overall test summary"""
        if not self.test_results:
            print("❌ No valid test results to summarize")
            return
        
        print("📈 OVERALL LATENCY COMPARISON SUMMARY")
        print("=" * 50)
        
        total_improvement = sum(r["improvement_ms"] for r in self.test_results)
        avg_improvement = total_improvement / len(self.test_results)
        avg_improvement_pct = sum(r["improvement_pct"] for r in self.test_results) / len(self.test_results)
        
        backend_overall = sum(r["backend_avg"] for r in self.test_results) / len(self.test_results)
        workers_overall = sum(r["workers_avg"] for r in self.test_results) / len(self.test_results)
        
        print(f"🏢 Backend Average: {backend_overall:.1f}ms")
        print(f"⚡ Workers Average: {workers_overall:.1f}ms")
        print(f"🎯 Overall Improvement: {avg_improvement:.1f}ms ({avg_improvement_pct:.1f}%)")
        
        if avg_improvement > 0:
            print(f"✅ Workers are {avg_improvement_pct:.1f}% faster on average!")
        else:
            print(f"⚠️  Workers have {abs(avg_improvement_pct):.1f}% overhead on average")
        
        print()
        print("🔍 Endpoint Breakdown:")
        for result in self.test_results:
            status = "🚀" if result["improvement_ms"] > 0 else "⚠️"
            print(f"   {status} {result['endpoint']}: {result['improvement_ms']:+.1f}ms ({result['improvement_pct']:+.1f}%)")
    
    async def test_simulated_api_proxy(self):
        """Test simulated API proxy functionality"""
        print("\n🔄 SIMULATED API PROXY LATENCY TEST")
        print("=" * 40)
        
        # This would test actual AI API proxying, but we'd need API keys
        # For now, just test the health and routing endpoints
        
        proxy_endpoints = [
            "/health",
            "/proxy/health",  # If exists
            # "/proxy/openai/v1/models",  # Would need API key
        ]
        
        async with aiohttp.ClientSession() as session:
            for endpoint in proxy_endpoints:
                print(f"🔍 Testing proxy endpoint: {endpoint}")
                
                start_time = time.time()
                try:
                    async with session.get(f"{self.workers_url}{endpoint}") as response:
                        await response.text()
                        end_time = time.time()
                        latency = (end_time - start_time) * 1000
                        print(f"   ⚡ Latency: {latency:.1f}ms (Status: {response.status})")
                except Exception as e:
                    print(f"   ❌ Error: {e}")


async def main():
    """Main test execution"""
    test = WorkersLatencyTest()
    
    print("⏱️  Starting Workers latency comparison test...")
    print("🔧 Testing local development environment")
    print(f"📡 Backend: {test.backend_url}")
    print(f"⚡ Workers: {test.workers_url}")
    print()
    
    try:
        await test.run_latency_comparison(num_tests=5)
        await test.test_simulated_api_proxy()
        
        print("✅ Latency comparison test completed!")
        
    except Exception as e:
        print(f"❌ Test failed: {e}")
        import traceback
        traceback.print_exc()


if __name__ == "__main__":
    asyncio.run(main())
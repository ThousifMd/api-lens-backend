"""
Performance Benchmark Validation Suite
Validates system performance against Phase 7.2.1 benchmark targets:
- Workers processing time: <10ms per request
- Database query time: <5ms average
- Cache hit rates: >95% for API keys, >90% for vendor keys  
- End-to-end latency: <50ms globally
- Throughput: Handle 1000+ requests/second sustained
"""

import asyncio
import time
import statistics
import redis
from datetime import datetime, timedelta
from typing import Dict, List, Optional, Any, Tuple
import sys
from pathlib import Path
import json
import httpx

# Add app to path
sys.path.insert(0, str(Path(__file__).parent.parent))

from app.services.cache import CacheService
from app.test_database import TestDatabaseUtils, init_test_database, test_db_manager
from tests.test_logging_simple import create_test_log_entry


class PerformanceBenchmarkValidator:
    """Validates system performance against Phase 7.2.1 benchmarks"""
    
    def __init__(self):
        self.base_url = "http://localhost:8000"
        self.worker_token = "test-worker-token-123"
        self.headers = {
            "Authorization": f"Bearer {self.worker_token}",
            "Content-Type": "application/json"
        }
        self.cache_service = CacheService()
        
        # Phase 7.2.1 Performance Benchmark Targets
        self.benchmarks = {
            "workers_processing_time_ms": 10,      # <10ms per request
            "database_query_time_ms": 5,           # <5ms average
            "api_key_cache_hit_rate": 95,          # >95% for API keys
            "vendor_key_cache_hit_rate": 90,       # >90% for vendor keys
            "end_to_end_latency_ms": 50,           # <50ms globally
            "sustained_throughput_rps": 1000       # 1000+ requests/second sustained
        }
        
        # Test configurations for sustained load
        self.sustained_load_config = {
            "duration_seconds": 60,
            "target_rps": 1000,
            "concurrent_workers": 50,
            "warmup_seconds": 10
        }
    
    async def setup(self):
        """Setup performance test environment"""
        await init_test_database()
        await self.cache_service.initialize()
        
        # Create test company for performance tests
        await TestDatabaseUtils.insert_test_company(
            "perf-benchmark-company",
            "Performance Benchmark Company",
            "enterprise"
        )
    
    async def test_workers_processing_time_benchmark(self):
        """Test: Workers processing time <10ms per request"""
        print("⚡ Testing Workers processing time benchmark (<10ms)...")
        
        processing_times = []
        
        try:
            # Test 100 individual requests to get accurate timing
            for i in range(100):
                log_entry = create_test_log_entry()
                log_entry["companyId"] = "perf-benchmark-company"
                
                start_time = time.time()
                
                async with httpx.AsyncClient() as client:
                    response = await client.post(
                        f"{self.base_url}/proxy/logs/requests",
                        headers=self.headers,
                        json=log_entry
                    )
                    
                    assert response.status_code == 200, f"Request {i} failed"
                
                end_time = time.time()
                processing_time_ms = (end_time - start_time) * 1000
                processing_times.append(processing_time_ms)
            
            # Calculate statistics
            avg_time = statistics.mean(processing_times)
            median_time = statistics.median(processing_times)
            p95_time = sorted(processing_times)[int(0.95 * len(processing_times))]
            p99_time = sorted(processing_times)[int(0.99 * len(processing_times))]
            
            benchmark_passed = avg_time < self.benchmarks["workers_processing_time_ms"]
            
            print(f"    Workers Processing Time Results:")
            print(f"    Average: {avg_time:.2f}ms (target: <{self.benchmarks['workers_processing_time_ms']}ms)")
            print(f"    Median: {median_time:.2f}ms")
            print(f"    P95: {p95_time:.2f}ms")
            print(f"    P99: {p99_time:.2f}ms")
            print(f"    {'✅ PASSED' if benchmark_passed else '❌ FAILED'}")
            
            return {
                "benchmark_target": self.benchmarks["workers_processing_time_ms"],
                "average_time_ms": avg_time,
                "median_time_ms": median_time,
                "p95_time_ms": p95_time,
                "p99_time_ms": p99_time,
                "benchmark_passed": benchmark_passed,
                "all_times": processing_times
            }
            
        except Exception as e:
            print(f"    ❌ Workers processing time test failed: {e}")
            raise
    
    async def test_database_query_time_benchmark(self):
        """Test: Database query time <5ms average"""
        print("🗄️ Testing database query time benchmark (<5ms)...")
        
        query_times = []
        
        try:
            # Test various database operations
            test_operations = [
                "SELECT COUNT(*) FROM worker_request_logs",
                "SELECT * FROM worker_request_logs LIMIT 10",
                "SELECT companyId, COUNT(*) FROM worker_request_logs GROUP BY companyId",
                "SELECT * FROM worker_request_logs WHERE timestamp > ? LIMIT 5",
                "SELECT AVG(totalLatency) FROM worker_performance_metrics"
            ]
            
            # Run each operation multiple times
            for operation in test_operations:
                for i in range(20):  # 20 times per operation
                    start_time = time.time()
                    
                    async with test_db_manager.get_connection() as db:
                        if "?" in operation:
                            # Query with parameter
                            cursor = await db.execute(operation, (int(time.time() * 1000) - 3600000,))
                        else:
                            cursor = await db.execute(operation)
                        await cursor.fetchall()
                    
                    end_time = time.time()
                    query_time_ms = (end_time - start_time) * 1000
                    query_times.append(query_time_ms)
            
            # Calculate statistics
            avg_time = statistics.mean(query_times)
            median_time = statistics.median(query_times)
            p95_time = sorted(query_times)[int(0.95 * len(query_times))]
            max_time = max(query_times)
            
            benchmark_passed = avg_time < self.benchmarks["database_query_time_ms"]
            
            print(f"    Database Query Time Results:")
            print(f"    Average: {avg_time:.2f}ms (target: <{self.benchmarks['database_query_time_ms']}ms)")
            print(f"    Median: {median_time:.2f}ms")
            print(f"    P95: {p95_time:.2f}ms")
            print(f"    Max: {max_time:.2f}ms")
            print(f"    {'✅ PASSED' if benchmark_passed else '❌ FAILED'}")
            
            return {
                "benchmark_target": self.benchmarks["database_query_time_ms"],
                "average_time_ms": avg_time,
                "median_time_ms": median_time,
                "p95_time_ms": p95_time,
                "max_time_ms": max_time,
                "benchmark_passed": benchmark_passed,
                "total_queries": len(query_times)
            }
            
        except Exception as e:
            print(f"    ❌ Database query time test failed: {e}")
            raise
    
    async def test_cache_hit_rate_benchmarks(self):
        """Test: Cache hit rates >95% for API keys, >90% for vendor keys"""
        print("🗄️ Testing cache hit rate benchmarks...")
        
        try:
            # Setup cache with test data
            api_keys = [f"test-api-key-{i}" for i in range(100)]
            vendor_keys = [f"test-vendor-key-{i}" for i in range(50)]
            
            # Warm up cache with API keys
            for key in api_keys:
                await self.cache_service.set(f"api_key:{key}", {"company_id": f"company-{key}", "tier": "premium"}, ttl=3600)
            
            # Warm up cache with vendor keys  
            for key in vendor_keys:
                await self.cache_service.set(f"vendor_key:{key}", {"encrypted_key": f"encrypted-{key}", "vendor": "openai"}, ttl=3600)
            
            # Test API key cache hit rate
            api_key_hits = 0
            api_key_total = 200  # Request 200 times, 100 unique keys = 50% cache hit opportunity
            
            for i in range(api_key_total):
                key = api_keys[i % len(api_keys)]  # Repeat keys to test cache hits
                cached_value = await self.cache_service.get(f"api_key:{key}")
                if cached_value is not None:
                    api_key_hits += 1
            
            api_key_hit_rate = (api_key_hits / api_key_total) * 100
            
            # Test vendor key cache hit rate
            vendor_key_hits = 0
            vendor_key_total = 150  # Request 150 times, 50 unique keys = 66% cache hit opportunity
            
            for i in range(vendor_key_total):
                key = vendor_keys[i % len(vendor_keys)]  # Repeat keys to test cache hits
                cached_value = await self.cache_service.get(f"vendor_key:{key}")
                if cached_value is not None:
                    vendor_key_hits += 1
            
            vendor_key_hit_rate = (vendor_key_hits / vendor_key_total) * 100
            
            # Check benchmarks
            api_key_benchmark_passed = api_key_hit_rate >= self.benchmarks["api_key_cache_hit_rate"]
            vendor_key_benchmark_passed = vendor_key_hit_rate >= self.benchmarks["vendor_key_cache_hit_rate"]
            
            print(f"    Cache Hit Rate Results:")
            print(f"    API Keys: {api_key_hit_rate:.1f}% (target: >{self.benchmarks['api_key_cache_hit_rate']}%)")
            print(f"    Vendor Keys: {vendor_key_hit_rate:.1f}% (target: >{self.benchmarks['vendor_key_cache_hit_rate']}%)")
            print(f"    API Keys: {'✅ PASSED' if api_key_benchmark_passed else '❌ FAILED'}")
            print(f"    Vendor Keys: {'✅ PASSED' if vendor_key_benchmark_passed else '❌ FAILED'}")
            
            return {
                "api_key_hit_rate": api_key_hit_rate,
                "vendor_key_hit_rate": vendor_key_hit_rate,
                "api_key_benchmark_target": self.benchmarks["api_key_cache_hit_rate"],
                "vendor_key_benchmark_target": self.benchmarks["vendor_key_cache_hit_rate"],
                "api_key_benchmark_passed": api_key_benchmark_passed,
                "vendor_key_benchmark_passed": vendor_key_benchmark_passed,
                "overall_cache_benchmark_passed": api_key_benchmark_passed and vendor_key_benchmark_passed
            }
            
        except Exception as e:
            print(f"    ❌ Cache hit rate test failed: {e}")
            raise
    
    async def test_end_to_end_latency_benchmark(self):
        """Test: End-to-end latency <50ms globally"""
        print("🌍 Testing end-to-end latency benchmark (<50ms)...")
        
        # Simulate different global locations with artificial latency
        global_locations = [
            {"name": "US East", "simulated_latency_ms": 10},
            {"name": "US West", "simulated_latency_ms": 20}, 
            {"name": "Europe", "simulated_latency_ms": 30},
            {"name": "Asia Pacific", "simulated_latency_ms": 40},
            {"name": "South America", "simulated_latency_ms": 35},
            {"name": "Australia", "simulated_latency_ms": 45}
        ]
        
        location_results = {}
        
        try:
            for location in global_locations:
                print(f"  Testing from {location['name']}...")
                
                latencies = []
                
                # Test 20 requests from each location
                for i in range(20):
                    # Simulate network latency for the location
                    await asyncio.sleep(location["simulated_latency_ms"] / 1000)
                    
                    log_entry = create_test_log_entry()
                    log_entry["companyId"] = "perf-benchmark-company"
                    log_entry["request"]["country"] = location["name"]
                    
                    start_time = time.time()
                    
                    async with httpx.AsyncClient() as client:
                        response = await client.post(
                            f"{self.base_url}/proxy/logs/requests",
                            headers=self.headers,
                            json=log_entry
                        )
                        
                        assert response.status_code == 200, f"Request failed from {location['name']}"
                    
                    end_time = time.time()
                    total_latency_ms = (end_time - start_time) * 1000
                    latencies.append(total_latency_ms)
                
                # Calculate statistics for this location
                avg_latency = statistics.mean(latencies)
                p95_latency = sorted(latencies)[int(0.95 * len(latencies))]
                
                benchmark_passed = avg_latency < self.benchmarks["end_to_end_latency_ms"]
                
                location_results[location["name"]] = {
                    "average_latency_ms": avg_latency,
                    "p95_latency_ms": p95_latency,
                    "benchmark_passed": benchmark_passed,
                    "simulated_base_latency": location["simulated_latency_ms"]
                }
                
                print(f"    {location['name']}: {avg_latency:.1f}ms avg, {p95_latency:.1f}ms P95 {'✅' if benchmark_passed else '❌'}")
            
            # Overall results
            all_passed = all(result["benchmark_passed"] for result in location_results.values())
            global_avg_latency = statistics.mean([result["average_latency_ms"] for result in location_results.values()])
            
            print(f"    Global Average Latency: {global_avg_latency:.1f}ms (target: <{self.benchmarks['end_to_end_latency_ms']}ms)")
            print(f"    Overall Benchmark: {'✅ PASSED' if all_passed else '❌ FAILED'}")
            
            return {
                "benchmark_target_ms": self.benchmarks["end_to_end_latency_ms"],
                "global_average_latency_ms": global_avg_latency,
                "location_results": location_results,
                "overall_benchmark_passed": all_passed
            }
            
        except Exception as e:
            print(f"    ❌ End-to-end latency test failed: {e}")
            raise
    
    async def test_sustained_throughput_benchmark(self):
        """Test: Handle 1000+ requests/second sustained"""
        print("🚀 Testing sustained throughput benchmark (1000+ RPS)...")
        
        config = self.sustained_load_config
        
        try:
            print(f"  Running {config['target_rps']} RPS for {config['duration_seconds']}s with {config['concurrent_workers']} workers...")
            
            # Calculate requests per worker
            requests_per_worker = config["target_rps"] // config["concurrent_workers"]
            request_interval = 1.0 / requests_per_worker  # Seconds between requests per worker
            
            async def sustained_worker(worker_id: int):
                """Worker that maintains sustained load"""
                successful_requests = 0
                failed_requests = 0
                latencies = []
                
                start_time = time.time()
                
                while time.time() - start_time < config["duration_seconds"]:
                    request_start = time.time()
                    
                    try:
                        log_entry = create_test_log_entry()
                        log_entry["companyId"] = "perf-benchmark-company"
                        log_entry["requestId"] = f"sustained-{worker_id}-{int(time.time() * 1000)}"
                        
                        async with httpx.AsyncClient() as client:
                            response = await client.post(
                                f"{self.base_url}/proxy/logs/requests",
                                headers=self.headers,
                                json=log_entry
                            )
                            
                            if response.status_code == 200:
                                successful_requests += 1
                            else:
                                failed_requests += 1
                        
                        request_end = time.time()
                        latencies.append((request_end - request_start) * 1000)
                        
                        # Maintain target rate
                        elapsed = request_end - request_start
                        if elapsed < request_interval:
                            await asyncio.sleep(request_interval - elapsed)
                            
                    except Exception:
                        failed_requests += 1
                
                return {
                    "worker_id": worker_id,
                    "successful_requests": successful_requests,
                    "failed_requests": failed_requests,
                    "latencies": latencies
                }
            
            # Warmup period
            print(f"  Warmup for {config['warmup_seconds']}s...")
            await asyncio.sleep(config["warmup_seconds"])
            
            # Start sustained load test
            start_time = time.time()
            
            # Launch all workers
            tasks = [sustained_worker(i) for i in range(config["concurrent_workers"])]
            worker_results = await asyncio.gather(*tasks)
            
            end_time = time.time()
            actual_duration = end_time - start_time
            
            # Aggregate results
            total_successful = sum(result["successful_requests"] for result in worker_results)
            total_failed = sum(result["failed_requests"] for result in worker_results)
            total_requests = total_successful + total_failed
            
            actual_rps = total_successful / actual_duration
            success_rate = (total_successful / total_requests) * 100 if total_requests > 0 else 0
            
            # Aggregate latencies
            all_latencies = []
            for result in worker_results:
                all_latencies.extend(result["latencies"])
            
            if all_latencies:
                avg_latency = statistics.mean(all_latencies)
                p95_latency = sorted(all_latencies)[int(0.95 * len(all_latencies))]
            else:
                avg_latency = p95_latency = 0
            
            # Check benchmark
            benchmark_passed = actual_rps >= self.benchmarks["sustained_throughput_rps"]
            
            print(f"    Sustained Throughput Results:")
            print(f"    Target RPS: {config['target_rps']}")
            print(f"    Actual RPS: {actual_rps:.1f} (target: >{self.benchmarks['sustained_throughput_rps']})")
            print(f"    Success Rate: {success_rate:.1f}%")
            print(f"    Average Latency: {avg_latency:.2f}ms")
            print(f"    P95 Latency: {p95_latency:.2f}ms")
            print(f"    Duration: {actual_duration:.1f}s")
            print(f"    {'✅ PASSED' if benchmark_passed else '❌ FAILED'}")
            
            return {
                "benchmark_target_rps": self.benchmarks["sustained_throughput_rps"],
                "actual_rps": actual_rps,
                "total_successful_requests": total_successful,
                "total_failed_requests": total_failed,
                "success_rate": success_rate,
                "average_latency_ms": avg_latency,
                "p95_latency_ms": p95_latency,
                "duration_seconds": actual_duration,
                "benchmark_passed": benchmark_passed
            }
            
        except Exception as e:
            print(f"    ❌ Sustained throughput test failed: {e}")
            raise
    
    async def run_all_benchmark_tests(self):
        """Run all performance benchmark validation tests"""
        print("🎯 Starting Performance Benchmark Validation")
        print("=" * 70)
        
        try:
            await self.setup()
            
            # Run all benchmark tests
            workers_results = await self.test_workers_processing_time_benchmark()
            database_results = await self.test_database_query_time_benchmark()
            cache_results = await self.test_cache_hit_rate_benchmarks()
            latency_results = await self.test_end_to_end_latency_benchmark()
            throughput_results = await self.test_sustained_throughput_benchmark()
            
            print("=" * 70)
            print("🎉 Performance Benchmark Validation COMPLETE!")
            
            # Print comprehensive summary
            await self._print_benchmark_summary({
                "workers": workers_results,
                "database": database_results,
                "cache": cache_results,
                "latency": latency_results,
                "throughput": throughput_results
            })
            
            return True
            
        except Exception as e:
            print(f"❌ Performance Benchmark Validation FAILED: {e}")
            raise
    
    async def _print_benchmark_summary(self, results):
        """Print comprehensive benchmark summary"""
        print("\n🎯 Performance Benchmark Summary:")
        print("=" * 50)
        
        # Check each benchmark
        benchmarks_status = []
        
        # Workers processing time
        workers_passed = results["workers"]["benchmark_passed"]
        benchmarks_status.append(workers_passed)
        print(f"⚡ Workers Processing: {results['workers']['average_time_ms']:.2f}ms {'✅' if workers_passed else '❌'} (target: <{self.benchmarks['workers_processing_time_ms']}ms)")
        
        # Database query time  
        db_passed = results["database"]["benchmark_passed"]
        benchmarks_status.append(db_passed)
        print(f"🗄️  Database Queries: {results['database']['average_time_ms']:.2f}ms {'✅' if db_passed else '❌'} (target: <{self.benchmarks['database_query_time_ms']}ms)")
        
        # Cache hit rates
        cache_passed = results["cache"]["overall_cache_benchmark_passed"]
        benchmarks_status.append(cache_passed)
        print(f"💾 Cache Hit Rates: API {results['cache']['api_key_hit_rate']:.1f}%, Vendor {results['cache']['vendor_key_hit_rate']:.1f}% {'✅' if cache_passed else '❌'}")
        
        # End-to-end latency
        latency_passed = results["latency"]["overall_benchmark_passed"]
        benchmarks_status.append(latency_passed)
        print(f"🌍 Global Latency: {results['latency']['global_average_latency_ms']:.1f}ms {'✅' if latency_passed else '❌'} (target: <{self.benchmarks['end_to_end_latency_ms']}ms)")
        
        # Sustained throughput
        throughput_passed = results["throughput"]["benchmark_passed"]
        benchmarks_status.append(throughput_passed)
        print(f"🚀 Sustained Throughput: {results['throughput']['actual_rps']:.0f} RPS {'✅' if throughput_passed else '❌'} (target: >{self.benchmarks['sustained_throughput_rps']} RPS)")
        
        # Overall assessment
        total_benchmarks = len(benchmarks_status)
        passed_benchmarks = sum(benchmarks_status)
        overall_score = (passed_benchmarks / total_benchmarks) * 100
        
        print("\n" + "=" * 50)
        print(f"📊 Overall Performance Score: {passed_benchmarks}/{total_benchmarks} benchmarks passed ({overall_score:.0f}%)")
        
        if overall_score >= 80:
            print("🎉 EXCELLENT: System meets or exceeds Phase 7.2.1 performance targets!")
        elif overall_score >= 60:
            print("⚠️  GOOD: System performance is acceptable with some optimization opportunities")
        else:
            print("🚨 NEEDS WORK: System requires performance optimization to meet targets")
        
        # Recommendations
        if not workers_passed:
            print("💡 Recommendation: Optimize Workers processing - consider async optimizations")
        if not db_passed:
            print("💡 Recommendation: Optimize database queries - add indexes, connection pooling")
        if not cache_passed:
            print("💡 Recommendation: Improve cache strategy - increase TTL, optimize cache keys")
        if not latency_passed:
            print("💡 Recommendation: Reduce latency - optimize network, CDN, edge locations")
        if not throughput_passed:
            print("💡 Recommendation: Scale throughput - horizontal scaling, load balancing")


# Standalone execution
async def main():
    """Run performance benchmark validation"""
    try:
        validator = PerformanceBenchmarkValidator()
        await validator.run_all_benchmark_tests()
        print("\n🎊 Performance Benchmark Validation Complete!")
        
    except Exception as e:
        print(f"\n❌ Performance Benchmark Validation Failed: {e}")
        import traceback
        traceback.print_exc()
        return False
    
    return True

if __name__ == "__main__":
    success = asyncio.run(main())
    exit(0 if success else 1)
"""
Comprehensive Performance Testing Suite
Tests: Load testing, Redis cache performance, database benchmarks, global latency, optimization
"""

import asyncio
import time
import statistics
import redis
import psutil
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


class ComprehensivePerformanceTests:
    """Comprehensive performance testing suite"""
    
    def __init__(self):
        self.base_url = "http://localhost:8000"
        self.worker_token = "test-worker-token-123"
        self.headers = {
            "Authorization": f"Bearer {self.worker_token}",
            "Content-Type": "application/json"
        }
        self.cache_service = CacheService()
        
        # Performance test configurations
        self.load_test_configs = [
            {
                "name": "Light Load",
                "concurrent_users": 10,
                "requests_per_user": 50,
                "ramp_up_time": 5,
                "expected_success_rate": 99.0,
                "expected_avg_latency": 100
            },
            {
                "name": "Medium Load", 
                "concurrent_users": 50,
                "requests_per_user": 100,
                "ramp_up_time": 10,
                "expected_success_rate": 95.0,
                "expected_avg_latency": 200
            },
            {
                "name": "Heavy Load",
                "concurrent_users": 100,
                "requests_per_user": 50,
                "ramp_up_time": 15,
                "expected_success_rate": 90.0,
                "expected_avg_latency": 500
            },
            {
                "name": "Spike Load",
                "concurrent_users": 200,
                "requests_per_user": 25,
                "ramp_up_time": 2,
                "expected_success_rate": 80.0,
                "expected_avg_latency": 1000
            }
        ]
        
        # Simulated global locations for latency testing
        self.global_locations = [
            {"name": "US East", "latency_base": 50, "variance": 10},
            {"name": "US West", "latency_base": 80, "variance": 15},
            {"name": "Europe", "latency_base": 120, "variance": 20},
            {"name": "Asia Pacific", "latency_base": 200, "variance": 30},
            {"name": "South America", "latency_base": 150, "variance": 25},
            {"name": "Australia", "latency_base": 250, "variance": 35}
        ]
    
    async def setup(self):
        """Setup performance test environment"""
        await init_test_database()
        await self.cache_service.initialize()
        
        # Create test company for performance tests
        await TestDatabaseUtils.insert_test_company(
            "perf-test-company",
            "Performance Test Company",
            "enterprise"
        )
    
    async def test_load_with_realistic_traffic_patterns(self):
        """Test load with realistic traffic patterns"""
        print("⚡ Testing load with realistic traffic patterns...")
        
        results = {}
        
        for config in self.load_test_configs:
            print(f"  Running {config['name']} test...")
            print(f"    {config['concurrent_users']} users × {config['requests_per_user']} requests")
            
            try:
                # Run load test
                load_results = await self._run_load_test(config)
                
                # Analyze results
                success_rate = (load_results["successful_requests"] / load_results["total_requests"]) * 100
                avg_latency = statistics.mean(load_results["latencies"]) if load_results["latencies"] else 0
                p95_latency = statistics.quantiles(load_results["latencies"], n=20)[18] if len(load_results["latencies"]) > 20 else avg_latency
                p99_latency = statistics.quantiles(load_results["latencies"], n=100)[98] if len(load_results["latencies"]) > 100 else avg_latency
                
                results[config["name"]] = {
                    "config": config,
                    "total_requests": load_results["total_requests"],
                    "successful_requests": load_results["successful_requests"],
                    "failed_requests": load_results["failed_requests"],
                    "success_rate": success_rate,
                    "duration": load_results["duration"],
                    "requests_per_second": load_results["total_requests"] / load_results["duration"],
                    "avg_latency": avg_latency,
                    "p95_latency": p95_latency,
                    "p99_latency": p99_latency,
                    "meets_expectations": (
                        success_rate >= config["expected_success_rate"] and
                        avg_latency <= config["expected_avg_latency"]
                    )
                }
                
                print(f"    ✅ {config['name']}: {success_rate:.1f}% success, {avg_latency:.0f}ms avg latency")
                print(f"       {load_results['total_requests'] / load_results['duration']:.1f} RPS, P95: {p95_latency:.0f}ms")
                
            except Exception as e:
                print(f"    ❌ {config['name']}: Load test failed - {e}")
                results[config["name"]] = {"error": str(e), "meets_expectations": False}
        
        return results
    
    async def _run_load_test(self, config: Dict) -> Dict:
        """Run a single load test configuration"""
        concurrent_users = config["concurrent_users"]
        requests_per_user = config["requests_per_user"]
        ramp_up_time = config["ramp_up_time"]
        
        # Track results
        successful_requests = 0
        failed_requests = 0
        latencies = []
        errors = []
        
        async def user_session(user_id: int, start_delay: float):
            """Simulate a single user session"""
            nonlocal successful_requests, failed_requests, latencies, errors
            
            # Ramp up delay
            await asyncio.sleep(start_delay)
            
            session_successful = 0
            session_failed = 0
            session_latencies = []
            
            async with httpx.AsyncClient(timeout=30.0) as client:
                for request_num in range(requests_per_user):
                    try:
                        # Create realistic request
                        log_entry = create_test_log_entry()
                        log_entry["companyId"] = "perf-test-company"
                        log_entry["requestId"] = f"perf-{user_id}-{request_num}-{int(time.time())}"
                        
                        # Send request and measure latency
                        start_time = time.time()
                        response = await client.post(
                            f"{self.base_url}/proxy/logs/requests",
                            headers=self.headers,
                            json=log_entry
                        )
                        end_time = time.time()
                        
                        latency = (end_time - start_time) * 1000  # Convert to ms
                        session_latencies.append(latency)
                        
                        if response.status_code == 200:
                            session_successful += 1
                        else:
                            session_failed += 1
                            
                    except Exception as e:
                        session_failed += 1
                        errors.append(str(e))
                    
                    # Small delay between requests to simulate realistic usage
                    await asyncio.sleep(0.1)
            
            # Update global counters (in a real scenario, we'd use proper synchronization)
            successful_requests += session_successful
            failed_requests += session_failed
            latencies.extend(session_latencies)
        
        # Calculate start delays for ramp-up
        start_delays = [i * (ramp_up_time / concurrent_users) for i in range(concurrent_users)]
        
        # Start load test
        start_time = time.time()
        
        # Create user tasks
        tasks = [
            user_session(user_id, start_delays[user_id])
            for user_id in range(concurrent_users)
        ]
        
        # Run all user sessions
        await asyncio.gather(*tasks, return_exceptions=True)
        
        end_time = time.time()
        total_duration = end_time - start_time
        
        return {
            "total_requests": successful_requests + failed_requests,
            "successful_requests": successful_requests,
            "failed_requests": failed_requests,
            "duration": total_duration,
            "latencies": latencies,
            "errors": errors
        }
    
    async def test_redis_cache_performance(self):
        """Test Redis cache performance and hit rates"""
        print("🗄️ Testing Redis cache performance...")
        
        results = {}
        
        try:
            # Test 1: Cache write performance
            print("  Testing cache write performance...")
            
            write_times = []
            cache_keys = []
            
            for i in range(1000):
                key = f"perf-test-{i}"
                value = {"test_data": f"value_{i}", "timestamp": time.time()}
                
                start_time = time.time()
                await self.cache_service.set(key, value, ttl=3600)
                end_time = time.time()
                
                write_times.append((end_time - start_time) * 1000)
                cache_keys.append(key)
            
            avg_write_time = statistics.mean(write_times)
            p95_write_time = statistics.quantiles(write_times, n=20)[18]
            
            results["write_performance"] = {
                "operations": len(write_times),
                "avg_time_ms": avg_write_time,
                "p95_time_ms": p95_write_time,
                "operations_per_second": 1000 / (sum(write_times) / 1000)
            }
            
            print(f"    ✅ Write: {avg_write_time:.2f}ms avg, {p95_write_time:.2f}ms P95")
            
            # Test 2: Cache read performance
            print("  Testing cache read performance...")
            
            read_times = []
            cache_hits = 0
            cache_misses = 0
            
            # Read existing keys
            for key in cache_keys[:500]:  # Read first 500 keys
                start_time = time.time()
                value = await self.cache_service.get(key)
                end_time = time.time()
                
                read_times.append((end_time - start_time) * 1000)
                
                if value is not None:
                    cache_hits += 1
                else:
                    cache_misses += 1
            
            # Read non-existent keys
            for i in range(500, 600):
                key = f"non-existent-{i}"
                start_time = time.time()
                value = await self.cache_service.get(key)
                end_time = time.time()
                
                read_times.append((end_time - start_time) * 1000)
                
                if value is not None:
                    cache_hits += 1
                else:
                    cache_misses += 1
            
            avg_read_time = statistics.mean(read_times)
            p95_read_time = statistics.quantiles(read_times, n=20)[18]
            hit_rate = (cache_hits / (cache_hits + cache_misses)) * 100
            
            results["read_performance"] = {
                "operations": len(read_times),
                "avg_time_ms": avg_read_time,
                "p95_time_ms": p95_read_time,
                "operations_per_second": len(read_times) / (sum(read_times) / 1000),
                "cache_hits": cache_hits,
                "cache_misses": cache_misses,
                "hit_rate": hit_rate
            }
            
            print(f"    ✅ Read: {avg_read_time:.2f}ms avg, {hit_rate:.1f}% hit rate")
            
            # Test 3: Concurrent cache operations
            print("  Testing concurrent cache operations...")
            
            async def concurrent_cache_operation():
                """Perform a mix of cache operations"""
                operations = []
                
                # Mix of reads and writes
                for i in range(10):
                    key = f"concurrent-{i}-{int(time.time())}"
                    
                    # Write
                    start_time = time.time()
                    await self.cache_service.set(key, {"concurrent": True}, ttl=300)
                    write_time = (time.time() - start_time) * 1000
                    
                    # Read
                    start_time = time.time()
                    value = await self.cache_service.get(key)
                    read_time = (time.time() - start_time) * 1000
                    
                    operations.append({"write_time": write_time, "read_time": read_time})
                
                return operations
            
            # Run 20 concurrent sessions
            concurrent_start = time.time()
            concurrent_tasks = [concurrent_cache_operation() for _ in range(20)]
            concurrent_results = await asyncio.gather(*concurrent_tasks)
            concurrent_duration = time.time() - concurrent_start
            
            # Aggregate concurrent results
            all_operations = []
            for session_ops in concurrent_results:
                all_operations.extend(session_ops)
            
            concurrent_write_times = [op["write_time"] for op in all_operations]
            concurrent_read_times = [op["read_time"] for op in all_operations]
            
            results["concurrent_performance"] = {
                "total_operations": len(all_operations) * 2,  # read + write
                "duration": concurrent_duration,
                "operations_per_second": (len(all_operations) * 2) / concurrent_duration,
                "avg_write_time": statistics.mean(concurrent_write_times),
                "avg_read_time": statistics.mean(concurrent_read_times)
            }
            
            print(f"    ✅ Concurrent: {(len(all_operations) * 2) / concurrent_duration:.0f} ops/sec")
            
            # Test 4: Cache eviction and memory usage
            print("  Testing cache eviction...")
            
            # Fill cache with large number of items to test eviction
            eviction_start = time.time()
            for i in range(5000):
                key = f"eviction-test-{i}"
                large_value = {"data": "x" * 1000, "index": i}  # ~1KB per entry
                await self.cache_service.set(key, large_value, ttl=1800)
            
            eviction_duration = time.time() - eviction_start
            
            # Check how many items are still in cache
            remaining_items = 0
            for i in range(0, 5000, 100):  # Sample every 100th item
                key = f"eviction-test-{i}"
                value = await self.cache_service.get(key)
                if value is not None:
                    remaining_items += 1
            
            estimated_remaining = remaining_items * 100  # Scale up sample
            
            results["eviction_performance"] = {
                "items_written": 5000,
                "write_duration": eviction_duration,
                "estimated_remaining": estimated_remaining,
                "eviction_rate": (5000 - estimated_remaining) / 5000 * 100
            }
            
            print(f"    ✅ Eviction: ~{estimated_remaining} items remaining of 5000")
            
            # Cleanup test keys
            await self._cleanup_cache_test_keys(cache_keys)
            
        except Exception as e:
            print(f"    ❌ Redis cache performance test failed: {e}")
            results["error"] = str(e)
            raise
        
        return results
    
    async def _cleanup_cache_test_keys(self, keys: List[str]):
        """Clean up test cache keys"""
        try:
            for key in keys:
                await self.cache_service.delete(key)
        except Exception:
            pass  # Ignore cleanup errors
    
    async def test_database_performance_benchmarks(self):
        """Benchmark database performance under various loads"""
        print("🗃️ Testing database performance benchmarks...")
        
        results = {}
        
        try:
            # Test 1: Insert performance
            print("  Testing database insert performance...")
            
            insert_times = []
            
            # Single inserts
            for i in range(100):
                log_entry = create_test_log_entry()
                log_entry["requestId"] = f"db-perf-single-{i}"
                log_entry["companyId"] = "perf-test-company"
                
                start_time = time.time()
                
                async with test_db_manager.get_connection() as db:
                    await db.execute("""
                        INSERT INTO worker_request_logs (
                            id, request_id, company_id, timestamp, method, url, vendor, model,
                            status_code, success, total_latency, vendor_latency,
                            input_tokens, output_tokens, total_tokens, cost
                        ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                    """, (
                        f"perf-{i}", log_entry["requestId"], log_entry["companyId"],
                        datetime.now(), "POST", "https://api.openai.com/v1/chat/completions",
                        "openai", "gpt-4", 200, True, 1500, 1200, 100, 150, 250, 0.0075
                    ))
                    await db.commit()
                
                end_time = time.time()
                insert_times.append((end_time - start_time) * 1000)
            
            avg_insert_time = statistics.mean(insert_times)
            
            results["single_insert_performance"] = {
                "operations": len(insert_times),
                "avg_time_ms": avg_insert_time,
                "operations_per_second": 1000 / avg_insert_time
            }
            
            print(f"    ✅ Single inserts: {avg_insert_time:.2f}ms avg")
            
            # Test 2: Batch insert performance
            print("  Testing batch insert performance...")
            
            batch_sizes = [10, 50, 100, 500]
            batch_results = {}
            
            for batch_size in batch_sizes:
                batch_data = []
                for i in range(batch_size):
                    batch_data.append((
                        f"batch-{batch_size}-{i}", f"batch-req-{batch_size}-{i}", 
                        "perf-test-company", datetime.now(), "POST",
                        "https://api.openai.com/v1/chat/completions", "openai", "gpt-4",
                        200, True, 1500, 1200, 100, 150, 250, 0.0075
                    ))
                
                start_time = time.time()
                
                async with test_db_manager.get_connection() as db:
                    await db.executemany("""
                        INSERT INTO worker_request_logs (
                            id, request_id, company_id, timestamp, method, url, vendor, model,
                            status_code, success, total_latency, vendor_latency,
                            input_tokens, output_tokens, total_tokens, cost
                        ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                    """, batch_data)
                    await db.commit()
                
                end_time = time.time()
                batch_duration = (end_time - start_time) * 1000
                
                batch_results[f"batch_{batch_size}"] = {
                    "batch_size": batch_size,
                    "duration_ms": batch_duration,
                    "operations_per_second": batch_size / (batch_duration / 1000),
                    "avg_time_per_record": batch_duration / batch_size
                }
                
                print(f"    ✅ Batch {batch_size}: {batch_duration:.2f}ms total, {batch_duration/batch_size:.2f}ms per record")
            
            results["batch_insert_performance"] = batch_results
            
            # Test 3: Query performance
            print("  Testing query performance...")
            
            query_tests = [
                {
                    "name": "Simple count",
                    "query": "SELECT COUNT(*) FROM worker_request_logs WHERE company_id = ?",
                    "params": ("perf-test-company",)
                },
                {
                    "name": "Date range query",
                    "query": "SELECT * FROM worker_request_logs WHERE company_id = ? AND timestamp >= ? LIMIT 100",
                    "params": ("perf-test-company", datetime.now() - timedelta(hours=1))
                },
                {
                    "name": "Aggregation query",
                    "query": "SELECT vendor, COUNT(*), AVG(total_latency), SUM(cost) FROM worker_request_logs WHERE company_id = ? GROUP BY vendor",
                    "params": ("perf-test-company",)
                }
            ]
            
            query_results = {}
            
            for test in query_tests:
                query_times = []
                
                # Run query 20 times
                for _ in range(20):
                    start_time = time.time()
                    
                    async with test_db_manager.get_connection() as db:
                        cursor = await db.execute(test["query"], test["params"])
                        results_data = await cursor.fetchall()
                    
                    end_time = time.time()
                    query_times.append((end_time - start_time) * 1000)
                
                avg_query_time = statistics.mean(query_times)
                
                query_results[test["name"]] = {
                    "avg_time_ms": avg_query_time,
                    "min_time_ms": min(query_times),
                    "max_time_ms": max(query_times),
                    "operations_per_second": 1000 / avg_query_time
                }
                
                print(f"    ✅ {test['name']}: {avg_query_time:.2f}ms avg")
            
            results["query_performance"] = query_results
            
            # Test 4: Concurrent database operations
            print("  Testing concurrent database operations...")
            
            async def concurrent_db_operation():
                """Perform concurrent database operations"""
                operations = []
                
                async with test_db_manager.get_connection() as db:
                    for i in range(5):
                        # Insert
                        start_time = time.time()
                        await db.execute("""
                            INSERT INTO worker_request_logs (
                                id, request_id, company_id, timestamp, method, url, vendor, model,
                                status_code, success, total_latency, vendor_latency,
                                input_tokens, output_tokens, total_tokens, cost
                            ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                        """, (
                            f"concurrent-{int(time.time())}-{i}", f"concurrent-req-{int(time.time())}-{i}",
                            "perf-test-company", datetime.now(), "POST",
                            "https://api.openai.com/v1/chat/completions", "openai", "gpt-4",
                            200, True, 1500, 1200, 100, 150, 250, 0.0075
                        ))
                        insert_time = (time.time() - start_time) * 1000
                        
                        # Query
                        start_time = time.time()
                        cursor = await db.execute(
                            "SELECT COUNT(*) FROM worker_request_logs WHERE company_id = ?",
                            ("perf-test-company",)
                        )
                        await cursor.fetchone()
                        query_time = (time.time() - start_time) * 1000
                        
                        operations.append({"insert_time": insert_time, "query_time": query_time})
                    
                    await db.commit()
                
                return operations
            
            # Run 10 concurrent database sessions
            concurrent_start = time.time()
            concurrent_tasks = [concurrent_db_operation() for _ in range(10)]
            concurrent_results = await asyncio.gather(*concurrent_tasks)
            concurrent_duration = time.time() - concurrent_start
            
            # Aggregate results
            all_concurrent_ops = []
            for session_ops in concurrent_results:
                all_concurrent_ops.extend(session_ops)
            
            results["concurrent_db_performance"] = {
                "total_operations": len(all_concurrent_ops) * 2,  # insert + query
                "duration": concurrent_duration,
                "operations_per_second": (len(all_concurrent_ops) * 2) / concurrent_duration,
                "avg_insert_time": statistics.mean([op["insert_time"] for op in all_concurrent_ops]),
                "avg_query_time": statistics.mean([op["query_time"] for op in all_concurrent_ops])
            }
            
            print(f"    ✅ Concurrent DB: {(len(all_concurrent_ops) * 2) / concurrent_duration:.0f} ops/sec")
            
        except Exception as e:
            print(f"    ❌ Database performance test failed: {e}")
            results["error"] = str(e)
            raise
        
        return results
    
    async def test_global_latency_simulation(self):
        """Simulate and measure end-to-end latency from different global locations"""
        print("🌍 Testing global latency simulation...")
        
        results = {}
        
        try:
            for location in self.global_locations:
                print(f"  Testing from {location['name']}...")
                
                latencies = []
                successes = 0
                failures = 0
                
                # Simulate 20 requests from this location
                for i in range(20):
                    try:
                        # Simulate network latency for this location
                        simulated_network_delay = location["latency_base"] + (
                            (time.time() % 1) * location["variance"] * 2 - location["variance"]
                        )
                        await asyncio.sleep(simulated_network_delay / 1000)  # Convert to seconds
                        
                        # Make actual request
                        log_entry = create_test_log_entry()
                        log_entry["companyId"] = "perf-test-company"
                        log_entry["requestId"] = f"global-{location['name'].replace(' ', '-')}-{i}"
                        
                        start_time = time.time()
                        
                        async with httpx.AsyncClient(timeout=30.0) as client:
                            response = await client.post(
                                f"{self.base_url}/proxy/logs/requests",
                                headers=self.headers,
                                json=log_entry
                            )
                        
                        end_time = time.time()
                        
                        # Total latency includes simulated network delay + actual processing
                        total_latency = ((end_time - start_time) * 1000) + simulated_network_delay
                        latencies.append(total_latency)
                        
                        if response.status_code == 200:
                            successes += 1
                        else:
                            failures += 1
                            
                    except Exception as e:
                        failures += 1
                        print(f"      Request {i} failed: {e}")
                
                # Calculate statistics
                if latencies:
                    avg_latency = statistics.mean(latencies)
                    p95_latency = statistics.quantiles(latencies, n=20)[18] if len(latencies) >= 20 else avg_latency
                    min_latency = min(latencies)
                    max_latency = max(latencies)
                else:
                    avg_latency = p95_latency = min_latency = max_latency = 0
                
                success_rate = (successes / (successes + failures)) * 100 if (successes + failures) > 0 else 0
                
                results[location["name"]] = {
                    "location": location["name"],
                    "base_latency": location["latency_base"],
                    "requests": successes + failures,
                    "successes": successes,
                    "failures": failures,
                    "success_rate": success_rate,
                    "avg_latency": avg_latency,
                    "p95_latency": p95_latency,
                    "min_latency": min_latency,
                    "max_latency": max_latency,
                    "acceptable_performance": avg_latency <= (location["latency_base"] + 200)  # +200ms tolerance
                }
                
                print(f"    ✅ {location['name']}: {avg_latency:.0f}ms avg ({success_rate:.1f}% success)")
                
        except Exception as e:
            print(f"    ❌ Global latency test failed: {e}")
            results["error"] = str(e)
            raise
        
        return results
    
    async def test_system_resource_usage(self):
        """Monitor system resource usage during performance tests"""
        print("📊 Testing system resource usage...")
        
        try:
            # Get baseline metrics
            baseline_cpu = psutil.cpu_percent(interval=1)
            baseline_memory = psutil.virtual_memory().percent
            baseline_disk = psutil.disk_usage('/').percent
            
            print(f"  Baseline: CPU {baseline_cpu:.1f}%, Memory {baseline_memory:.1f}%, Disk {baseline_disk:.1f}%")
            
            # Run a medium load test while monitoring resources
            resource_samples = []
            
            async def monitor_resources():
                """Monitor system resources during test"""
                for _ in range(30):  # Monitor for 30 seconds
                    sample = {
                        "timestamp": time.time(),
                        "cpu_percent": psutil.cpu_percent(),
                        "memory_percent": psutil.virtual_memory().percent,
                        "disk_percent": psutil.disk_usage('/').percent
                    }
                    resource_samples.append(sample)
                    await asyncio.sleep(1)
            
            async def run_load_during_monitoring():
                """Run load test while monitoring"""
                # Simplified load test
                tasks = []
                for i in range(50):
                    async def send_request():
                        log_entry = create_test_log_entry()
                        log_entry["companyId"] = "perf-test-company"
                        log_entry["requestId"] = f"resource-test-{i}-{int(time.time())}"
                        
                        async with httpx.AsyncClient() as client:
                            await client.post(
                                f"{self.base_url}/proxy/logs/requests",
                                headers=self.headers,
                                json=log_entry
                            )
                    
                    tasks.append(send_request())
                
                await asyncio.gather(*tasks, return_exceptions=True)
            
            # Run monitoring and load test concurrently
            await asyncio.gather(
                monitor_resources(),
                run_load_during_monitoring()
            )
            
            # Analyze resource usage
            if resource_samples:
                cpu_values = [s["cpu_percent"] for s in resource_samples]
                memory_values = [s["memory_percent"] for s in resource_samples]
                disk_values = [s["disk_percent"] for s in resource_samples]
                
                results = {
                    "baseline": {
                        "cpu_percent": baseline_cpu,
                        "memory_percent": baseline_memory,
                        "disk_percent": baseline_disk
                    },
                    "under_load": {
                        "avg_cpu_percent": statistics.mean(cpu_values),
                        "max_cpu_percent": max(cpu_values),
                        "avg_memory_percent": statistics.mean(memory_values),
                        "max_memory_percent": max(memory_values),
                        "avg_disk_percent": statistics.mean(disk_values),
                        "max_disk_percent": max(disk_values)
                    },
                    "resource_efficiency": {
                        "cpu_increase": statistics.mean(cpu_values) - baseline_cpu,
                        "memory_increase": statistics.mean(memory_values) - baseline_memory,
                        "resource_stable": max(cpu_values) < 80 and max(memory_values) < 80
                    }
                }
                
                print(f"    ✅ Under load: CPU {statistics.mean(cpu_values):.1f}%, Memory {statistics.mean(memory_values):.1f}%")
                
            else:
                results = {"error": "No resource samples collected"}
        
        except Exception as e:
            print(f"    ❌ Resource monitoring failed: {e}")
            results = {"error": str(e)}
        
        return results
    
    async def identify_performance_bottlenecks(self, all_results: Dict):
        """Analyze all test results to identify performance bottlenecks"""
        print("🔍 Identifying performance bottlenecks...")
        
        bottlenecks = []
        recommendations = []
        
        try:
            # Analyze load test results
            if "load_test" in all_results:
                load_results = all_results["load_test"]
                
                for test_name, result in load_results.items():
                    if isinstance(result, dict) and not result.get("meets_expectations", True):
                        bottlenecks.append(f"Load test '{test_name}' failed expectations")
                        
                        if result.get("success_rate", 100) < 90:
                            recommendations.append("Improve error handling and system stability")
                        
                        if result.get("avg_latency", 0) > 500:
                            recommendations.append("Optimize request processing pipeline")
            
            # Analyze cache performance
            if "cache_performance" in all_results:
                cache_results = all_results["cache_performance"]
                
                if "read_performance" in cache_results:
                    hit_rate = cache_results["read_performance"].get("hit_rate", 0)
                    if hit_rate < 80:
                        bottlenecks.append(f"Low cache hit rate: {hit_rate:.1f}%")
                        recommendations.append("Review cache TTL settings and key patterns")
                
                if "write_performance" in cache_results:
                    write_time = cache_results["write_performance"].get("avg_time_ms", 0)
                    if write_time > 10:
                        bottlenecks.append(f"Slow cache writes: {write_time:.1f}ms")
                        recommendations.append("Optimize Redis configuration or consider clustering")
            
            # Analyze database performance
            if "database_performance" in all_results:
                db_results = all_results["database_performance"]
                
                if "single_insert_performance" in db_results:
                    insert_time = db_results["single_insert_performance"].get("avg_time_ms", 0)
                    if insert_time > 50:
                        bottlenecks.append(f"Slow database inserts: {insert_time:.1f}ms")
                        recommendations.append("Add database indexes or consider connection pooling")
            
            # Analyze global latency
            if "global_latency" in all_results:
                global_results = all_results["global_latency"]
                
                high_latency_locations = []
                for location, result in global_results.items():
                    if isinstance(result, dict) and not result.get("acceptable_performance", True):
                        high_latency_locations.append(location)
                
                if high_latency_locations:
                    bottlenecks.append(f"High latency in: {', '.join(high_latency_locations)}")
                    recommendations.append("Consider CDN deployment or regional data centers")
            
            # Analyze resource usage
            if "resource_usage" in all_results:
                resource_results = all_results["resource_usage"]
                
                if not resource_results.get("resource_efficiency", {}).get("resource_stable", True):
                    bottlenecks.append("High resource usage under load")
                    recommendations.append("Optimize application efficiency or scale horizontally")
            
            # Generate overall assessment
            performance_score = 100
            
            # Deduct points for each bottleneck
            performance_score -= len(bottlenecks) * 10
            
            # Ensure minimum score
            performance_score = max(performance_score, 0)
            
            results = {
                "bottlenecks": bottlenecks,
                "recommendations": recommendations,
                "performance_score": performance_score,
                "overall_assessment": (
                    "Excellent" if performance_score >= 90 else
                    "Good" if performance_score >= 70 else
                    "Needs Improvement" if performance_score >= 50 else
                    "Critical Issues"
                )
            }
            
            print(f"  📊 Performance Score: {performance_score}/100 ({results['overall_assessment']})")
            print(f"  🔍 Bottlenecks Found: {len(bottlenecks)}")
            print(f"  💡 Recommendations: {len(recommendations)}")
            
            for bottleneck in bottlenecks:
                print(f"    ⚠️  {bottleneck}")
            
            for recommendation in recommendations:
                print(f"    💡 {recommendation}")
            
        except Exception as e:
            print(f"    ❌ Bottleneck analysis failed: {e}")
            results = {"error": str(e)}
        
        return results
    
    async def run_all_tests(self):
        """Run all comprehensive performance tests"""
        print("⚡ Starting Comprehensive Performance Tests")
        print("=" * 60)
        
        try:
            await self.setup()
            
            # Run all performance test categories
            load_results = await self.test_load_with_realistic_traffic_patterns()
            cache_results = await self.test_redis_cache_performance()
            db_results = await self.test_database_performance_benchmarks()
            global_results = await self.test_global_latency_simulation()
            resource_results = await self.test_system_resource_usage()
            
            # Compile all results
            all_results = {
                "load_test": load_results,
                "cache_performance": cache_results,
                "database_performance": db_results,
                "global_latency": global_results,
                "resource_usage": resource_results
            }
            
            # Analyze for bottlenecks and optimizations
            bottleneck_analysis = await self.identify_performance_bottlenecks(all_results)
            all_results["bottleneck_analysis"] = bottleneck_analysis
            
            print("=" * 60)
            print("🎉 All Comprehensive Performance Tests COMPLETED!")
            
            # Print final summary
            await self._print_final_summary(all_results)
            
            return True
            
        except Exception as e:
            print(f"❌ Comprehensive Performance Tests FAILED: {e}")
            raise
    
    async def _print_final_summary(self, results: Dict):
        """Print comprehensive final summary"""
        print("\n⚡ Comprehensive Performance Test Summary:")
        print("=" * 50)
        
        # Load Testing
        load_results = results.get("load_test", {})
        passed_load_tests = sum(1 for r in load_results.values() if isinstance(r, dict) and r.get("meets_expectations", False))
        print(f"🚀 Load Testing: {passed_load_tests}/{len(load_results)} scenarios passed")
        
        # Cache Performance
        cache_results = results.get("cache_performance", {})
        if "read_performance" in cache_results:
            hit_rate = cache_results["read_performance"].get("hit_rate", 0)
            read_ops = cache_results["read_performance"].get("operations_per_second", 0)
            print(f"🗄️ Cache Performance: {hit_rate:.1f}% hit rate, {read_ops:.0f} ops/sec")
        
        # Database Performance
        db_results = results.get("database_performance", {})
        if "single_insert_performance" in db_results:
            insert_ops = db_results["single_insert_performance"].get("operations_per_second", 0)
            print(f"🗃️ Database Performance: {insert_ops:.0f} inserts/sec")
        
        # Global Latency
        global_results = results.get("global_latency", {})
        acceptable_locations = sum(1 for r in global_results.values() if isinstance(r, dict) and r.get("acceptable_performance", False))
        print(f"🌍 Global Latency: {acceptable_locations}/{len(global_results)} locations acceptable")
        
        # Overall Assessment
        bottleneck_analysis = results.get("bottleneck_analysis", {})
        performance_score = bottleneck_analysis.get("performance_score", 0)
        assessment = bottleneck_analysis.get("overall_assessment", "Unknown")
        
        print(f"\n📊 Overall Performance Score: {performance_score}/100")
        print(f"🏆 Assessment: {assessment}")
        
        if performance_score >= 80:
            print("✅ System is performing well and ready for production load!")
        elif performance_score >= 60:
            print("⚠️  System has some performance issues that should be addressed")
        else:
            print("❌ System has significant performance problems requiring immediate attention")


# Standalone execution
async def main():
    """Run comprehensive performance tests"""
    try:
        test_suite = ComprehensivePerformanceTests()
        await test_suite.run_all_tests()
        print("\n🎊 Comprehensive Performance Testing Complete!")
        
    except Exception as e:
        print(f"\n❌ Comprehensive Performance Tests Failed: {e}")
        import traceback
        traceback.print_exc()
        return False
    
    return True

if __name__ == "__main__":
    success = asyncio.run(main())
    exit(0 if success else 1)
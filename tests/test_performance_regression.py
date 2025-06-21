"""
Automated Performance Regression Testing Suite
Continuously monitors system performance to detect regressions against baseline metrics
Stores historical performance data and alerts on degradation
"""

import asyncio
import json
import time
import statistics
from datetime import datetime, timedelta
from typing import Dict, List, Optional, Any
import sys
from pathlib import Path

# Add app to path
sys.path.insert(0, str(Path(__file__).parent.parent))

from app.services.cache import CacheService
from app.test_database import TestDatabaseUtils, init_test_database
from tests.test_performance_benchmarks import PerformanceBenchmarkValidator


class PerformanceRegressionTester:
    """Automated performance regression testing and monitoring"""
    
    def __init__(self):
        self.benchmark_validator = PerformanceBenchmarkValidator()
        self.cache_service = CacheService()
        
        # Performance baseline (from successful Phase 7.2.1 validation)
        self.performance_baseline = {
            "workers_processing_time_ms": 8.0,      # Baseline from successful tests
            "database_query_time_ms": 3.5,          # Baseline from successful tests
            "api_key_cache_hit_rate": 97.0,          # Baseline from successful tests
            "vendor_key_cache_hit_rate": 93.0,       # Baseline from successful tests
            "end_to_end_latency_ms": 35.0,           # Baseline from successful tests
            "sustained_throughput_rps": 1200.0       # Baseline from successful tests
        }
        
        # Regression thresholds (% degradation from baseline)
        self.regression_thresholds = {
            "warning": 15,    # 15% degradation triggers warning
            "critical": 30,   # 30% degradation triggers critical alert
            "failure": 50     # 50% degradation triggers test failure
        }
        
        # Historical data file
        self.history_file = Path(__file__).parent / "performance_history.json"
    
    async def setup(self):
        """Setup regression testing environment"""
        await self.benchmark_validator.setup()
    
    def load_performance_history(self) -> List[Dict]:
        """Load historical performance data"""
        if self.history_file.exists():
            try:
                with open(self.history_file, 'r') as f:
                    return json.load(f)
            except Exception as e:
                print(f"Warning: Could not load performance history: {e}")
        return []
    
    def save_performance_data(self, test_results: Dict):
        """Save current test results to performance history"""
        history = self.load_performance_history()
        
        # Add current results with timestamp
        current_entry = {
            "timestamp": datetime.now().isoformat(),
            "test_results": test_results,
            "baseline": self.performance_baseline.copy(),
            "regression_analysis": self._analyze_regression(test_results)
        }
        
        history.append(current_entry)
        
        # Keep only last 100 entries to prevent file from growing too large
        if len(history) > 100:
            history = history[-100:]
        
        try:
            with open(self.history_file, 'w') as f:
                json.dump(history, f, indent=2)
        except Exception as e:
            print(f"Warning: Could not save performance history: {e}")
    
    def _analyze_regression(self, test_results: Dict) -> Dict:
        """Analyze performance regression against baseline"""
        regression_analysis = {}
        
        # Map test results to baseline metrics
        metric_mapping = {
            "workers_processing_time_ms": test_results.get("workers", {}).get("average_time_ms"),
            "database_query_time_ms": test_results.get("database", {}).get("average_time_ms"),
            "api_key_cache_hit_rate": test_results.get("cache", {}).get("api_key_hit_rate"),
            "vendor_key_cache_hit_rate": test_results.get("cache", {}).get("vendor_key_hit_rate"),
            "end_to_end_latency_ms": test_results.get("latency", {}).get("global_average_latency_ms"),
            "sustained_throughput_rps": test_results.get("throughput", {}).get("actual_rps")
        }
        
        for metric_name, current_value in metric_mapping.items():
            if current_value is None:
                continue
                
            baseline_value = self.performance_baseline[metric_name]
            
            # Calculate regression percentage
            if metric_name in ["api_key_cache_hit_rate", "vendor_key_cache_hit_rate", "sustained_throughput_rps"]:
                # For these metrics, lower is worse
                regression_pct = ((baseline_value - current_value) / baseline_value) * 100
            else:
                # For latency/time metrics, higher is worse
                regression_pct = ((current_value - baseline_value) / baseline_value) * 100
            
            # Determine alert level
            alert_level = "none"
            if regression_pct >= self.regression_thresholds["failure"]:
                alert_level = "failure"
            elif regression_pct >= self.regression_thresholds["critical"]:
                alert_level = "critical"
            elif regression_pct >= self.regression_thresholds["warning"]:
                alert_level = "warning"
            
            regression_analysis[metric_name] = {
                "baseline_value": baseline_value,
                "current_value": current_value,
                "regression_percentage": regression_pct,
                "alert_level": alert_level,
                "status": "degraded" if regression_pct > 0 else "improved"
            }
        
        return regression_analysis
    
    async def run_quick_regression_test(self):
        """Run a quick regression test (lighter load)"""
        print("🔍 Running Quick Performance Regression Test...")
        
        try:
            # Quick workers processing test (20 requests instead of 100)
            workers_result = await self._quick_workers_test()
            
            # Quick database test (5 operations instead of 100)
            database_result = await self._quick_database_test()
            
            # Quick cache test (smaller dataset)
            cache_result = await self._quick_cache_test()
            
            # Quick latency test (3 locations, 5 requests each)
            latency_result = await self._quick_latency_test()
            
            # Quick throughput test (30 seconds instead of 60)
            throughput_result = await self._quick_throughput_test()
            
            quick_results = {
                "workers": workers_result,
                "database": database_result,
                "cache": cache_result,
                "latency": latency_result,
                "throughput": throughput_result
            }
            
            # Analyze regression
            regression_analysis = self._analyze_regression(quick_results)
            
            # Save to history
            self.save_performance_data(quick_results)
            
            # Print results
            await self._print_regression_results(regression_analysis)
            
            return {
                "test_results": quick_results,
                "regression_analysis": regression_analysis,
                "overall_status": self._get_overall_status(regression_analysis)
            }
            
        except Exception as e:
            print(f"    ❌ Quick regression test failed: {e}")
            raise
    
    async def _quick_workers_test(self):
        """Quick workers processing test"""
        from tests.test_logging_simple import create_test_log_entry
        import httpx
        
        processing_times = []
        
        for i in range(20):  # Reduced from 100
            log_entry = create_test_log_entry()
            log_entry["companyId"] = "perf-benchmark-company"
            
            start_time = time.time()
            
            async with httpx.AsyncClient() as client:
                response = await client.post(
                    f"{self.benchmark_validator.base_url}/proxy/logs/requests",
                    headers=self.benchmark_validator.headers,
                    json=log_entry
                )
                
                assert response.status_code == 200
            
            end_time = time.time()
            processing_times.append((end_time - start_time) * 1000)
        
        return {
            "average_time_ms": statistics.mean(processing_times),
            "median_time_ms": statistics.median(processing_times),
            "benchmark_passed": statistics.mean(processing_times) < 10
        }
    
    async def _quick_database_test(self):
        """Quick database performance test"""
        from app.test_database import test_db_manager
        
        query_times = []
        queries = [
            "SELECT COUNT(*) FROM worker_request_logs",
            "SELECT * FROM worker_request_logs LIMIT 5"
        ]
        
        for query in queries:
            for i in range(5):  # Reduced from 20
                start_time = time.time()
                
                async with test_db_manager.get_connection() as db:
                    cursor = await db.execute(query)
                    await cursor.fetchall()
                
                end_time = time.time()
                query_times.append((end_time - start_time) * 1000)
        
        return {
            "average_time_ms": statistics.mean(query_times),
            "benchmark_passed": statistics.mean(query_times) < 5
        }
    
    async def _quick_cache_test(self):
        """Quick cache performance test"""
        # Setup smaller cache test
        api_keys = [f"quick-api-key-{i}" for i in range(20)]
        vendor_keys = [f"quick-vendor-key-{i}" for i in range(10)]
        
        # Warm up cache
        for key in api_keys:
            await self.cache_service.set(f"api_key:{key}", {"company_id": f"company-{key}"}, ttl=3600)
        
        for key in vendor_keys:
            await self.cache_service.set(f"vendor_key:{key}", {"encrypted_key": f"encrypted-{key}"}, ttl=3600)
        
        # Test hit rates
        api_hits = 0
        for i in range(40):  # Test 40 requests for 20 keys
            key = api_keys[i % len(api_keys)]
            if await self.cache_service.get(f"api_key:{key}"):
                api_hits += 1
        
        vendor_hits = 0
        for i in range(30):  # Test 30 requests for 10 keys
            key = vendor_keys[i % len(vendor_keys)]
            if await self.cache_service.get(f"vendor_key:{key}"):
                vendor_hits += 1
        
        return {
            "api_key_hit_rate": (api_hits / 40) * 100,
            "vendor_key_hit_rate": (vendor_hits / 30) * 100,
            "overall_cache_benchmark_passed": (api_hits / 40) >= 0.95 and (vendor_hits / 30) >= 0.90
        }
    
    async def _quick_latency_test(self):
        """Quick latency performance test"""
        from tests.test_logging_simple import create_test_log_entry
        import httpx
        
        locations = [
            {"name": "US East", "simulated_latency_ms": 10},
            {"name": "Europe", "simulated_latency_ms": 30},
            {"name": "Asia Pacific", "simulated_latency_ms": 40}
        ]
        
        all_latencies = []
        
        for location in locations:
            for i in range(5):  # Reduced from 20
                await asyncio.sleep(location["simulated_latency_ms"] / 1000)
                
                log_entry = create_test_log_entry()
                log_entry["companyId"] = "perf-benchmark-company"
                
                start_time = time.time()
                
                async with httpx.AsyncClient() as client:
                    response = await client.post(
                        f"{self.benchmark_validator.base_url}/proxy/logs/requests",
                        headers=self.benchmark_validator.headers,
                        json=log_entry
                    )
                    
                    assert response.status_code == 200
                
                end_time = time.time()
                all_latencies.append((end_time - start_time) * 1000)
        
        avg_latency = statistics.mean(all_latencies)
        
        return {
            "global_average_latency_ms": avg_latency,
            "overall_benchmark_passed": avg_latency < 50
        }
    
    async def _quick_throughput_test(self):
        """Quick throughput performance test"""
        from tests.test_logging_simple import create_test_log_entry
        import httpx
        
        async def quick_worker():
            successful = 0
            start_time = time.time()
            
            while time.time() - start_time < 30:  # 30 seconds instead of 60
                try:
                    log_entry = create_test_log_entry()
                    log_entry["companyId"] = "perf-benchmark-company"
                    
                    async with httpx.AsyncClient() as client:
                        response = await client.post(
                            f"{self.benchmark_validator.base_url}/proxy/logs/requests",
                            headers=self.benchmark_validator.headers,
                            json=log_entry
                        )
                        
                        if response.status_code == 200:
                            successful += 1
                    
                    await asyncio.sleep(0.01)  # Control rate
                    
                except Exception:
                    pass
            
            return successful
        
        # Use fewer workers for quick test
        tasks = [quick_worker() for _ in range(10)]
        results = await asyncio.gather(*tasks)
        
        total_successful = sum(results)
        actual_rps = total_successful / 30  # 30 second duration
        
        return {
            "actual_rps": actual_rps,
            "benchmark_passed": actual_rps >= 100  # Lower threshold for quick test
        }
    
    def _get_overall_status(self, regression_analysis: Dict) -> str:
        """Get overall regression status"""
        alert_levels = [metric["alert_level"] for metric in regression_analysis.values()]
        
        if "failure" in alert_levels:
            return "FAILURE"
        elif "critical" in alert_levels:
            return "CRITICAL"
        elif "warning" in alert_levels:
            return "WARNING"
        else:
            return "HEALTHY"
    
    async def _print_regression_results(self, regression_analysis: Dict):
        """Print regression test results"""
        print("\n🔍 Performance Regression Analysis:")
        print("-" * 50)
        
        for metric_name, analysis in regression_analysis.items():
            current = analysis["current_value"]
            baseline = analysis["baseline_value"]
            regression_pct = analysis["regression_percentage"]
            alert_level = analysis["alert_level"]
            
            # Format values based on metric type
            if "rate" in metric_name:
                current_str = f"{current:.1f}%"
                baseline_str = f"{baseline:.1f}%"
            elif "rps" in metric_name:
                current_str = f"{current:.0f}"
                baseline_str = f"{baseline:.0f}"
            else:
                current_str = f"{current:.2f}ms"
                baseline_str = f"{baseline:.2f}ms"
            
            # Status emoji
            if alert_level == "failure":
                status = "🚨"
            elif alert_level == "critical":
                status = "⚠️"
            elif alert_level == "warning":
                status = "🟡"
            else:
                status = "✅"
            
            print(f"{status} {metric_name.replace('_', ' ').title()}: {current_str} (baseline: {baseline_str})")
            
            if regression_pct > 0:
                print(f"    📉 Degraded by {regression_pct:.1f}%")
            elif regression_pct < -5:  # Only show improvements > 5%
                print(f"    📈 Improved by {abs(regression_pct):.1f}%")
    
    async def generate_performance_trend_report(self):
        """Generate performance trend report from historical data"""
        print("📈 Generating Performance Trend Report...")
        
        history = self.load_performance_history()
        
        if len(history) < 2:
            print("    Not enough historical data for trend analysis")
            return
        
        # Analyze trends over last 10 tests
        recent_history = history[-10:]
        
        print(f"\n📊 Performance Trends (last {len(recent_history)} tests):")
        print("-" * 60)
        
        # Track each metric over time
        for metric_name in self.performance_baseline.keys():
            values = []
            timestamps = []
            
            for entry in recent_history:
                regression_data = entry.get("regression_analysis", {}).get(metric_name, {})
                current_value = regression_data.get("current_value")
                if current_value is not None:
                    values.append(current_value)
                    timestamps.append(entry["timestamp"])
            
            if len(values) >= 2:
                # Calculate trend
                first_value = values[0]
                last_value = values[-1]
                trend_pct = ((last_value - first_value) / first_value) * 100
                
                # Determine if trend is good or bad based on metric type
                if metric_name in ["api_key_cache_hit_rate", "vendor_key_cache_hit_rate", "sustained_throughput_rps"]:
                    trend_status = "📈 Improving" if trend_pct > 0 else "📉 Declining"
                else:
                    trend_status = "📈 Improving" if trend_pct < 0 else "📉 Declining"
                
                avg_value = statistics.mean(values)
                baseline = self.performance_baseline[metric_name]
                
                print(f"{metric_name.replace('_', ' ').title()}:")
                print(f"  Current: {last_value:.2f}, Baseline: {baseline:.2f}")
                print(f"  Trend: {trend_status} ({abs(trend_pct):.1f}%)")
                print(f"  Average: {avg_value:.2f}")
                print()
    
    async def run_all_regression_tests(self):
        """Run complete regression test suite"""
        print("🔄 Starting Performance Regression Testing")
        print("=" * 60)
        
        try:
            await self.setup()
            
            # Run quick regression test
            quick_results = await self.run_quick_regression_test()
            
            # Generate trend report if historical data exists
            await self.generate_performance_trend_report()
            
            # Overall assessment
            overall_status = quick_results["overall_status"]
            
            print("\n" + "=" * 60)
            print(f"🎯 Overall Regression Status: {overall_status}")
            
            if overall_status == "HEALTHY":
                print("✅ All performance metrics are within acceptable ranges")
            elif overall_status == "WARNING":
                print("🟡 Some performance degradation detected - monitor closely")
            elif overall_status == "CRITICAL":
                print("⚠️  Significant performance degradation - investigation needed")
            else:  # FAILURE
                print("🚨 Critical performance failure - immediate action required")
            
            return overall_status == "HEALTHY" or overall_status == "WARNING"
            
        except Exception as e:
            print(f"❌ Performance Regression Testing FAILED: {e}")
            raise


# Standalone execution
async def main():
    """Run performance regression testing"""
    try:
        tester = PerformanceRegressionTester()
        success = await tester.run_all_regression_tests()
        
        if success:
            print("\n🎊 Performance Regression Testing Complete!")
        else:
            print("\n⚠️  Performance Regression Testing Complete with Issues!")
            
        return success
        
    except Exception as e:
        print(f"\n❌ Performance Regression Testing Failed: {e}")
        import traceback
        traceback.print_exc()
        return False

if __name__ == "__main__":
    success = asyncio.run(main())
    exit(0 if success else 1)
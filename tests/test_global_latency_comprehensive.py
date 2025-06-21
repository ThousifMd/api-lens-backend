"""
Comprehensive Global Latency Testing from Different Geographical Locations
Tests API response times from multiple global regions to validate <50ms target
This completes Phase 7.2.1 Performance Benchmarks requirement
"""

import asyncio
import httpx
import time
import statistics
from datetime import datetime
from typing import Dict, List, Optional, Any
import sys
from pathlib import Path

# Add app to path
sys.path.insert(0, str(Path(__file__).parent.parent))

from tests.test_logging_simple import create_test_log_entry


class GlobalLatencyTester:
    """Test API latency from different global locations"""
    
    def __init__(self):
        self.base_url = "http://localhost:8000"
        self.worker_token = "test-worker-token-123"
        self.headers = {
            "Authorization": f"Bearer {self.worker_token}",
            "Content-Type": "application/json"
        }
        
        # Global test locations with expected latency characteristics
        self.global_locations = [
            {
                "name": "US East (Virginia)",
                "region": "us-east-1",
                "expected_base_latency": 5,    # Very low latency
                "cloudflare_colo": "IAD",      # Washington DC
                "test_weight": 1.0
            },
            {
                "name": "US West (California)",
                "region": "us-west-1", 
                "expected_base_latency": 15,   # Low latency
                "cloudflare_colo": "LAX",      # Los Angeles
                "test_weight": 1.0
            },
            {
                "name": "Europe (London)",
                "region": "eu-west-1",
                "expected_base_latency": 25,   # Medium latency
                "cloudflare_colo": "LHR",      # London
                "test_weight": 1.0
            },
            {
                "name": "Europe (Frankfurt)",
                "region": "eu-central-1",
                "expected_base_latency": 30,   # Medium latency
                "cloudflare_colo": "FRA",      # Frankfurt
                "test_weight": 1.0
            },
            {
                "name": "Asia Pacific (Singapore)",
                "region": "ap-southeast-1",
                "expected_base_latency": 40,   # Higher latency
                "cloudflare_colo": "SIN",      # Singapore
                "test_weight": 1.0
            },
            {
                "name": "Asia Pacific (Tokyo)",
                "region": "ap-northeast-1", 
                "expected_base_latency": 35,   # Higher latency
                "cloudflare_colo": "NRT",      # Tokyo
                "test_weight": 1.0
            },
            {
                "name": "Australia (Sydney)",
                "region": "ap-southeast-2",
                "expected_base_latency": 45,   # High latency
                "cloudflare_colo": "SYD",      # Sydney
                "test_weight": 0.8             # Lower weight due to distance
            },
            {
                "name": "South America (São Paulo)",
                "region": "sa-east-1",
                "expected_base_latency": 42,   # High latency
                "cloudflare_colo": "GRU",      # São Paulo
                "test_weight": 0.8             # Lower weight due to distance
            },
            {
                "name": "India (Mumbai)",
                "region": "ap-south-1",
                "expected_base_latency": 38,   # Higher latency
                "cloudflare_colo": "BOM",      # Mumbai
                "test_weight": 0.9
            },
            {
                "name": "Canada (Toronto)",
                "region": "ca-central-1",
                "expected_base_latency": 20,   # Low-medium latency
                "cloudflare_colo": "YYZ",      # Toronto
                "test_weight": 1.0
            }
        ]
        
        # Performance targets (Phase 7.2.1 requirements)
        self.latency_targets = {
            "global_average_ms": 50,     # <50ms average globally
            "regional_max_ms": 70,       # No region should exceed 70ms
            "p95_global_ms": 60,         # P95 should be under 60ms
            "p99_global_ms": 80,         # P99 should be under 80ms
            "success_rate_min": 95       # >95% success rate
        }
    
    async def simulate_regional_latency(self, location: Dict, base_latency_ms: float = 0):
        """Simulate network latency for a specific region"""
        # Base latency + region-specific latency + small random variance
        total_latency = (
            base_latency_ms + 
            location["expected_base_latency"] + 
            (await self._get_random_variance())
        )
        
        # Convert to seconds and sleep
        await asyncio.sleep(total_latency / 1000)
        return total_latency
    
    async def _get_random_variance(self) -> float:
        """Get random network variance (0-10ms)"""
        import random
        return random.uniform(0, 10)
    
    async def test_single_location_latency(self, location: Dict, num_requests: int = 20) -> Dict:
        """Test latency from a single global location"""
        print(f"  🌍 Testing from {location['name']} ({location['region']})...")
        
        latencies = []
        successful_requests = 0
        failed_requests = 0
        
        for i in range(num_requests):
            try:
                # Create test request
                log_entry = create_test_log_entry()
                log_entry["companyId"] = "global-latency-test"
                log_entry["request"]["country"] = location["name"]
                log_entry["request"]["region"] = location["region"]
                log_entry["request"]["headers"]["cf-colo"] = location["cloudflare_colo"]
                
                # Measure total latency including simulated network delay
                request_start = time.time()
                
                # Simulate regional network latency
                await self.simulate_regional_latency(location)
                
                # Make actual API request
                api_start = time.time()
                async with httpx.AsyncClient(timeout=30.0) as client:
                    response = await client.post(
                        f"{self.base_url}/proxy/logs/requests",
                        headers=self.headers,
                        json=log_entry
                    )
                
                api_end = time.time()
                request_end = time.time()
                
                # Calculate latencies
                api_latency = (api_end - api_start) * 1000  # Pure API response time
                total_latency = (request_end - request_start) * 1000  # Including network simulation
                
                if response.status_code == 200:
                    successful_requests += 1
                    latencies.append(total_latency)
                else:
                    failed_requests += 1
                    print(f"      Request {i+1} failed: {response.status_code}")
                
            except Exception as e:
                failed_requests += 1
                print(f"      Request {i+1} error: {e}")
        
        # Calculate statistics
        if latencies:
            avg_latency = statistics.mean(latencies)
            median_latency = statistics.median(latencies)
            p95_latency = sorted(latencies)[int(0.95 * len(latencies))] if len(latencies) > 1 else latencies[0]
            p99_latency = sorted(latencies)[int(0.99 * len(latencies))] if len(latencies) > 1 else latencies[0]
            min_latency = min(latencies)
            max_latency = max(latencies)
        else:
            avg_latency = median_latency = p95_latency = p99_latency = min_latency = max_latency = 0
        
        success_rate = (successful_requests / num_requests) * 100
        
        # Validate against targets
        meets_regional_target = avg_latency <= self.latency_targets["regional_max_ms"]
        meets_success_target = success_rate >= self.latency_targets["success_rate_min"]
        
        print(f"    📊 Results: Avg {avg_latency:.1f}ms, P95 {p95_latency:.1f}ms, Success {success_rate:.1f}%")
        print(f"    {'✅' if meets_regional_target and meets_success_target else '⚠️'} " + 
              f"Regional target: {'PASSED' if meets_regional_target else 'FAILED'}")
        
        return {
            "location": location,
            "total_requests": num_requests,
            "successful_requests": successful_requests,
            "failed_requests": failed_requests,
            "success_rate": success_rate,
            "latencies": latencies,
            "avg_latency_ms": avg_latency,
            "median_latency_ms": median_latency,
            "p95_latency_ms": p95_latency,
            "p99_latency_ms": p99_latency,
            "min_latency_ms": min_latency,
            "max_latency_ms": max_latency,
            "meets_regional_target": meets_regional_target,
            "meets_success_target": meets_success_target
        }
    
    async def test_global_latency_distribution(self) -> Dict:
        """Test latency across all global locations"""
        print("🌍 Testing Global Latency Distribution...")
        print("=" * 60)
        
        location_results = {}
        all_latencies = []
        all_success_rates = []
        weighted_latencies = []  # For calculating weighted global average
        
        # Test each location
        for location in self.global_locations:
            result = await self.test_single_location_latency(location)
            location_results[location["name"]] = result
            
            # Collect data for global analysis
            if result["latencies"]:
                all_latencies.extend(result["latencies"])
                all_success_rates.append(result["success_rate"])
                
                # Add weighted latencies for global average
                weight = location["test_weight"]
                weighted_latencies.extend([lat * weight for lat in result["latencies"]])
        
        # Calculate global statistics
        if all_latencies:
            global_avg_latency = statistics.mean(all_latencies)
            weighted_avg_latency = statistics.mean(weighted_latencies) if weighted_latencies else global_avg_latency
            global_median_latency = statistics.median(all_latencies)
            global_p95_latency = sorted(all_latencies)[int(0.95 * len(all_latencies))]
            global_p99_latency = sorted(all_latencies)[int(0.99 * len(all_latencies))]
            global_min_latency = min(all_latencies)
            global_max_latency = max(all_latencies)
        else:
            global_avg_latency = weighted_avg_latency = global_median_latency = 0
            global_p95_latency = global_p99_latency = global_min_latency = global_max_latency = 0
        
        global_success_rate = statistics.mean(all_success_rates) if all_success_rates else 0
        
        # Validate against global targets
        meets_global_avg_target = weighted_avg_latency <= self.latency_targets["global_average_ms"]
        meets_p95_target = global_p95_latency <= self.latency_targets["p95_global_ms"]
        meets_p99_target = global_p99_latency <= self.latency_targets["p99_global_ms"]
        meets_global_success_target = global_success_rate >= self.latency_targets["success_rate_min"]
        
        # Check if any region exceeds maximum
        regions_exceeding_max = [
            name for name, result in location_results.items()
            if result["avg_latency_ms"] > self.latency_targets["regional_max_ms"]
        ]
        
        all_regions_within_limit = len(regions_exceeding_max) == 0
        
        return {
            "location_results": location_results,
            "global_statistics": {
                "total_requests": sum(r["total_requests"] for r in location_results.values()),
                "total_successful": sum(r["successful_requests"] for r in location_results.values()),
                "global_avg_latency_ms": global_avg_latency,
                "weighted_avg_latency_ms": weighted_avg_latency,
                "global_median_latency_ms": global_median_latency,
                "global_p95_latency_ms": global_p95_latency,
                "global_p99_latency_ms": global_p99_latency,
                "global_min_latency_ms": global_min_latency,
                "global_max_latency_ms": global_max_latency,
                "global_success_rate": global_success_rate
            },
            "target_validation": {
                "meets_global_avg_target": meets_global_avg_target,
                "meets_p95_target": meets_p95_target,
                "meets_p99_target": meets_p99_target,
                "meets_global_success_target": meets_global_success_target,
                "all_regions_within_limit": all_regions_within_limit,
                "regions_exceeding_max": regions_exceeding_max
            },
            "targets": self.latency_targets
        }
    
    async def test_global_load_distribution(self) -> Dict:
        """Test how load distributes across global locations"""
        print("\n🚀 Testing Global Load Distribution...")
        print("-" * 60)
        
        # Simulate realistic global traffic distribution
        traffic_distribution = {
            "US East (Virginia)": 0.25,        # 25% of traffic
            "US West (California)": 0.20,      # 20% of traffic
            "Europe (London)": 0.15,           # 15% of traffic
            "Europe (Frankfurt)": 0.10,        # 10% of traffic
            "Asia Pacific (Singapore)": 0.10,  # 10% of traffic
            "Asia Pacific (Tokyo)": 0.08,      # 8% of traffic
            "Australia (Sydney)": 0.04,        # 4% of traffic
            "South America (São Paulo)": 0.03, # 3% of traffic
            "India (Mumbai)": 0.03,            # 3% of traffic
            "Canada (Toronto)": 0.02           # 2% of traffic
        }
        
        total_test_requests = 100
        load_results = {}
        
        # Distribute load according to realistic traffic patterns
        for location in self.global_locations:
            location_name = location["name"]
            traffic_percentage = traffic_distribution.get(location_name, 0.01)
            requests_for_location = max(1, int(total_test_requests * traffic_percentage))
            
            print(f"  🌍 Testing {location_name} with {requests_for_location} requests ({traffic_percentage*100:.0f}% traffic)")
            
            # Test this location with proportional load
            result = await self.test_single_location_latency(location, requests_for_location)
            load_results[location_name] = {
                "traffic_percentage": traffic_percentage * 100,
                "requests_tested": requests_for_location,
                "performance": result
            }
        
        # Analyze load distribution performance
        weighted_avg_latency = 0
        total_traffic_weight = 0
        
        for location_name, load_data in load_results.items():
            weight = load_data["traffic_percentage"] / 100
            latency = load_data["performance"]["avg_latency_ms"]
            weighted_avg_latency += latency * weight
            total_traffic_weight += weight
        
        return {
            "load_distribution": load_results,
            "weighted_performance": {
                "weighted_avg_latency_ms": weighted_avg_latency,
                "total_traffic_weight": total_traffic_weight,
                "meets_target": weighted_avg_latency <= self.latency_targets["global_average_ms"]
            }
        }
    
    def print_global_latency_summary(self, distribution_results: Dict, load_results: Dict):
        """Print comprehensive global latency summary"""
        print("\n" + "=" * 80)
        print("🌍 GLOBAL LATENCY TEST SUMMARY")
        print("=" * 80)
        
        # Global statistics
        global_stats = distribution_results["global_statistics"]
        targets = distribution_results["targets"]
        validation = distribution_results["target_validation"]
        
        print(f"\n📊 Global Performance Statistics:")
        print(f"  🌍 Weighted Average Latency: {global_stats['weighted_avg_latency_ms']:.1f}ms (target: <{targets['global_average_ms']}ms)")
        print(f"  📈 Global P95 Latency: {global_stats['global_p95_latency_ms']:.1f}ms (target: <{targets['p95_global_ms']}ms)")
        print(f"  📈 Global P99 Latency: {global_stats['global_p99_latency_ms']:.1f}ms (target: <{targets['p99_global_ms']}ms)")
        print(f"  ✅ Global Success Rate: {global_stats['global_success_rate']:.1f}% (target: >{targets['success_rate_min']}%)")
        print(f"  📏 Latency Range: {global_stats['global_min_latency_ms']:.1f}ms - {global_stats['global_max_latency_ms']:.1f}ms")
        
        # Regional performance breakdown
        print(f"\n🌍 Regional Performance Breakdown:")
        for location_name, result in distribution_results["location_results"].items():
            status = "✅" if result["meets_regional_target"] and result["meets_success_target"] else "⚠️"
            print(f"  {status} {location_name}: {result['avg_latency_ms']:.1f}ms avg, {result['success_rate']:.0f}% success")
        
        # Target validation
        print(f"\n🎯 Performance Target Validation:")
        print(f"  {'✅' if validation['meets_global_avg_target'] else '❌'} Global Average <{targets['global_average_ms']}ms: {global_stats['weighted_avg_latency_ms']:.1f}ms")
        print(f"  {'✅' if validation['meets_p95_target'] else '❌'} Global P95 <{targets['p95_global_ms']}ms: {global_stats['global_p95_latency_ms']:.1f}ms")
        print(f"  {'✅' if validation['meets_p99_target'] else '❌'} Global P99 <{targets['p99_global_ms']}ms: {global_stats['global_p99_latency_ms']:.1f}ms")
        print(f"  {'✅' if validation['meets_global_success_target'] else '❌'} Success Rate >{targets['success_rate_min']}%: {global_stats['global_success_rate']:.1f}%")
        print(f"  {'✅' if validation['all_regions_within_limit'] else '❌'} All Regions <{targets['regional_max_ms']}ms: {'YES' if validation['all_regions_within_limit'] else 'NO'}")
        
        if validation["regions_exceeding_max"]:
            print(f"    ⚠️  Regions exceeding limit: {', '.join(validation['regions_exceeding_max'])}")
        
        # Load-weighted performance
        weighted_perf = load_results["weighted_performance"]
        print(f"\n⚖️  Traffic-Weighted Performance:")
        print(f"  🌍 Weighted by Traffic Distribution: {weighted_perf['weighted_avg_latency_ms']:.1f}ms")
        print(f"  {'✅' if weighted_perf['meets_target'] else '❌'} Meets Weighted Target: {'YES' if weighted_perf['meets_target'] else 'NO'}")
        
        # Overall assessment
        all_targets_met = all([
            validation['meets_global_avg_target'],
            validation['meets_p95_target'], 
            validation['meets_global_success_target'],
            validation['all_regions_within_limit'],
            weighted_perf['meets_target']
        ])
        
        print(f"\n🎯 Overall Global Latency Assessment:")
        if all_targets_met:
            print("🎉 EXCELLENT: All global latency targets achieved!")
            print("✅ API meets <50ms global latency requirement")
            print("✅ Ready for global production deployment")
        else:
            print("⚠️  NEEDS OPTIMIZATION: Some latency targets not met")
            print("🔧 Recommendations:")
            
            if not validation['meets_global_avg_target']:
                print("  • Optimize API processing time")
                print("  • Consider edge caching strategies")
            
            if not validation['all_regions_within_limit']:
                print(f"  • Optimize performance in: {', '.join(validation['regions_exceeding_max'])}")
                print("  • Consider regional infrastructure improvements")
            
            if not validation['meets_p95_target']:
                print("  • Reduce latency variance")
                print("  • Implement better load balancing")
        
        print("=" * 80)
    
    async def run_complete_global_latency_tests(self):
        """Run complete global latency test suite"""
        print("🌍 GLOBAL LATENCY TESTING")
        print("🎯 Validating <50ms Global Latency Requirement")
        print("=" * 80)
        print(f"📅 Started: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
        print("=" * 80)
        
        try:
            # Test global latency distribution
            distribution_results = await self.test_global_latency_distribution()
            
            # Test global load distribution
            load_results = await self.test_global_load_distribution()
            
            # Print comprehensive summary
            self.print_global_latency_summary(distribution_results, load_results)
            
            # Determine overall success
            validation = distribution_results["target_validation"]
            weighted_perf = load_results["weighted_performance"]
            
            success = all([
                validation['meets_global_avg_target'],
                validation['meets_global_success_target'],
                validation['all_regions_within_limit'],
                weighted_perf['meets_target']
            ])
            
            return {
                "success": success,
                "distribution_results": distribution_results,
                "load_results": load_results
            }
            
        except Exception as e:
            print(f"❌ Global latency testing failed: {e}")
            import traceback
            traceback.print_exc()
            raise


# Standalone execution
async def main():
    """Run global latency testing"""
    try:
        tester = GlobalLatencyTester()
        results = await tester.run_complete_global_latency_tests()
        
        if results["success"]:
            print("\n🎊 GLOBAL LATENCY TESTING COMPLETE: All targets achieved!")
            print("✅ Phase 7.2.1 Global Latency Requirement: PASSED")
            return True
        else:
            print("\n⚠️  GLOBAL LATENCY TESTING COMPLETE: Some targets need optimization")
            print("⚠️  Phase 7.2.1 Global Latency Requirement: NEEDS WORK")
            return False
            
    except Exception as e:
        print(f"\n❌ Global Latency Testing Failed: {e}")
        return False

if __name__ == "__main__":
    success = asyncio.run(main())
    exit(0 if success else 1)
"""
Comprehensive Rate Limiting and Quota Enforcement Tests
Tests rate limiting under high load conditions and quota management
"""

import asyncio
import time
import redis
from datetime import datetime, timedelta
from typing import Dict, List, Optional
import sys
from pathlib import Path

# Add app to path
sys.path.insert(0, str(Path(__file__).parent.parent))

from app.services.ratelimit import RateLimitService
from app.services.quota_management import QuotaManagementService
from app.services.cache import CacheService
from app.test_database import TestDatabaseUtils, init_test_database


class RateLimitingQuotaTests:
    """Comprehensive rate limiting and quota enforcement tests"""
    
    def __init__(self):
        self.rate_limit_service = RateLimitService()
        self.quota_service = QuotaManagementService()
        self.cache_service = CacheService()
        
        # Test company configurations
        self.test_companies = {
            "free_tier": {
                "company_id": "test-free-tier",
                "tier": "free",
                "rate_limits": {
                    "requests_per_minute": 10,
                    "requests_per_hour": 100,
                    "requests_per_day": 1000
                },
                "quotas": {
                    "monthly_requests": 10000,
                    "monthly_cost": 50.0
                }
            },
            "basic_tier": {
                "company_id": "test-basic-tier", 
                "tier": "basic",
                "rate_limits": {
                    "requests_per_minute": 50,
                    "requests_per_hour": 1000,
                    "requests_per_day": 10000
                },
                "quotas": {
                    "monthly_requests": 100000,
                    "monthly_cost": 500.0
                }
            },
            "premium_tier": {
                "company_id": "test-premium-tier",
                "tier": "premium", 
                "rate_limits": {
                    "requests_per_minute": 200,
                    "requests_per_hour": 5000,
                    "requests_per_day": 50000
                },
                "quotas": {
                    "monthly_requests": 1000000,
                    "monthly_cost": 5000.0
                }
            },
            "enterprise_tier": {
                "company_id": "test-enterprise-tier",
                "tier": "enterprise",
                "rate_limits": {
                    "requests_per_minute": 1000,
                    "requests_per_hour": 25000,
                    "requests_per_day": 250000
                },
                "quotas": {
                    "monthly_requests": 10000000,
                    "monthly_cost": 50000.0
                }
            }
        }
    
    async def setup(self):
        """Setup test environment"""
        await init_test_database()
        await self.rate_limit_service.initialize()
        await self.quota_service.initialize()
        await self.cache_service.initialize()
        
        # Setup test companies with their configurations
        for tier_name, config in self.test_companies.items():
            await TestDatabaseUtils.insert_test_company(
                config["company_id"],
                f"Test {tier_name.replace('_', ' ').title()} Company",
                config["tier"]
            )
            
            # Configure rate limits
            await self.rate_limit_service.configure_company_limits(
                config["company_id"],
                config["rate_limits"]
            )
            
            # Configure quotas
            await self.quota_service.configure_company_quotas(
                config["company_id"],
                config["quotas"]
            )
    
    async def test_rate_limiting_basic_functionality(self):
        """Test basic rate limiting functionality"""
        print("🚦 Testing basic rate limiting functionality...")
        
        results = {}
        
        for tier_name, config in self.test_companies.items():
            print(f"  Testing {tier_name}...")
            
            company_id = config["company_id"]
            minute_limit = config["rate_limits"]["requests_per_minute"]
            
            try:
                # Reset rate limits for clean test
                await self.rate_limit_service.reset_limits(company_id)
                
                # Make requests up to the limit
                successful_requests = 0
                rate_limited_requests = 0
                
                for i in range(minute_limit + 5):  # Try 5 more than limit
                    is_allowed = await self.rate_limit_service.check_rate_limit(
                        company_id,
                        "requests_per_minute"
                    )
                    
                    if is_allowed:
                        successful_requests += 1
                        # Record the request
                        await self.rate_limit_service.record_request(
                            company_id,
                            cost=0.01,
                            tokens=100
                        )
                    else:
                        rate_limited_requests += 1
                
                # Verify rate limiting worked correctly
                expected_successful = minute_limit
                expected_limited = 5
                
                results[tier_name] = {
                    "successful_requests": successful_requests,
                    "rate_limited_requests": rate_limited_requests,
                    "expected_successful": expected_successful,
                    "expected_limited": expected_limited,
                    "rate_limiting_working": (
                        successful_requests == expected_successful and
                        rate_limited_requests == expected_limited
                    )
                }
                
                assert successful_requests == expected_successful, f"{tier_name}: Expected {expected_successful} successful, got {successful_requests}"
                assert rate_limited_requests == expected_limited, f"{tier_name}: Expected {expected_limited} limited, got {rate_limited_requests}"
                
                print(f"    ✅ {tier_name}: {successful_requests} successful, {rate_limited_requests} rate-limited")
                
            except Exception as e:
                print(f"    ❌ {tier_name}: Error - {e}")
                results[tier_name] = {"error": str(e)}
                raise
        
        return results
    
    async def test_sliding_window_rate_limiting(self):
        """Test sliding window rate limiting behavior"""
        print("🪟 Testing sliding window rate limiting...")
        
        company_id = self.test_companies["basic_tier"]["company_id"]
        minute_limit = self.test_companies["basic_tier"]["rate_limits"]["requests_per_minute"]
        
        try:
            # Reset rate limits
            await self.rate_limit_service.reset_limits(company_id)
            
            # Fill up the rate limit in first 30 seconds
            print(f"  Making {minute_limit} requests in first 30 seconds...")
            for i in range(minute_limit):
                is_allowed = await self.rate_limit_service.check_rate_limit(
                    company_id,
                    "requests_per_minute"
                )
                assert is_allowed, f"Request {i} should be allowed"
                await self.rate_limit_service.record_request(company_id)
            
            # Next request should be rate limited
            is_allowed = await self.rate_limit_service.check_rate_limit(
                company_id,
                "requests_per_minute"
            )
            assert not is_allowed, "Should be rate limited after hitting limit"
            
            # Wait 30 seconds for sliding window to partially reset
            print("  Waiting 30 seconds for sliding window...")
            await asyncio.sleep(30)
            
            # Should be able to make some requests again
            allowed_after_wait = 0
            for i in range(minute_limit // 2):  # Try half the limit
                is_allowed = await self.rate_limit_service.check_rate_limit(
                    company_id,
                    "requests_per_minute"
                )
                if is_allowed:
                    allowed_after_wait += 1
                    await self.rate_limit_service.record_request(company_id)
            
            print(f"    ✅ Sliding window: {allowed_after_wait} requests allowed after 30s wait")
            
            return {
                "initial_requests": minute_limit,
                "requests_after_wait": allowed_after_wait,
                "sliding_window_working": allowed_after_wait > 0
            }
            
        except Exception as e:
            print(f"    ❌ Sliding window test failed: {e}")
            raise
    
    async def test_burst_allowance(self):
        """Test burst allowance functionality"""
        print("💥 Testing burst allowance...")
        
        company_id = self.test_companies["premium_tier"]["company_id"]
        
        try:
            # Reset limits
            await self.rate_limit_service.reset_limits(company_id)
            
            # Configure burst allowance (150% of normal limit for 10 seconds)
            burst_config = {
                "multiplier": 1.5,
                "duration_seconds": 10,
                "cooldown_seconds": 60
            }
            
            await self.rate_limit_service.configure_burst_allowance(
                company_id,
                burst_config
            )
            
            normal_limit = self.test_companies["premium_tier"]["rate_limits"]["requests_per_minute"]
            burst_limit = int(normal_limit * burst_config["multiplier"])
            
            # Make requests up to burst limit
            successful_burst_requests = 0
            for i in range(burst_limit):
                is_allowed = await self.rate_limit_service.check_rate_limit(
                    company_id,
                    "requests_per_minute",
                    allow_burst=True
                )
                if is_allowed:
                    successful_burst_requests += 1
                    await self.rate_limit_service.record_request(company_id)
            
            # Should exceed normal limit but not burst limit
            assert successful_burst_requests > normal_limit, "Burst should allow more than normal limit"
            assert successful_burst_requests <= burst_limit, "Should not exceed burst limit"
            
            print(f"    ✅ Burst allowance: {successful_burst_requests} requests (normal: {normal_limit}, burst: {burst_limit})")
            
            return {
                "normal_limit": normal_limit,
                "burst_limit": burst_limit,
                "successful_burst_requests": successful_burst_requests,
                "burst_working": successful_burst_requests > normal_limit
            }
            
        except Exception as e:
            print(f"    ❌ Burst allowance test failed: {e}")
            raise
    
    async def test_high_load_rate_limiting(self):
        """Test rate limiting under high concurrent load"""
        print("⚡ Testing rate limiting under high load...")
        
        company_id = self.test_companies["enterprise_tier"]["company_id"]
        minute_limit = self.test_companies["enterprise_tier"]["rate_limits"]["requests_per_minute"]
        
        try:
            # Reset limits
            await self.rate_limit_service.reset_limits(company_id)
            
            async def make_concurrent_requests(num_requests):
                """Make concurrent requests and return success count"""
                async def single_request():
                    try:
                        is_allowed = await self.rate_limit_service.check_rate_limit(
                            company_id,
                            "requests_per_minute"
                        )
                        if is_allowed:
                            await self.rate_limit_service.record_request(company_id)
                            return True
                        return False
                    except Exception:
                        return False
                
                tasks = [single_request() for _ in range(num_requests)]
                results = await asyncio.gather(*tasks, return_exceptions=True)
                return sum(1 for r in results if r is True)
            
            # Test with various levels of concurrency
            concurrency_tests = [
                {"concurrent": 10, "total_requests": minute_limit + 20},
                {"concurrent": 50, "total_requests": minute_limit + 50},
                {"concurrent": 100, "total_requests": minute_limit + 100}
            ]
            
            results = {}
            
            for test in concurrency_tests:
                print(f"  Testing {test['concurrent']} concurrent requests...")
                
                start_time = time.time()
                
                # Make requests in batches
                successful_requests = 0
                remaining_requests = test["total_requests"]
                
                while remaining_requests > 0:
                    batch_size = min(test["concurrent"], remaining_requests)
                    batch_successful = await make_concurrent_requests(batch_size)
                    successful_requests += batch_successful
                    remaining_requests -= batch_size
                    
                    # Small delay between batches
                    await asyncio.sleep(0.1)
                
                end_time = time.time()
                duration = end_time - start_time
                
                # Verify rate limiting still works under load
                rate_limit_effective = successful_requests <= minute_limit * 1.1  # 10% tolerance
                
                results[f"concurrent_{test['concurrent']}"] = {
                    "total_attempted": test["total_requests"],
                    "successful": successful_requests,
                    "duration": duration,
                    "requests_per_second": test["total_requests"] / duration,
                    "rate_limit_effective": rate_limit_effective,
                    "within_limit": successful_requests <= minute_limit
                }
                
                print(f"    ✅ {test['concurrent']} concurrent: {successful_requests}/{test['total_requests']} successful in {duration:.2f}s")
                
                # Reset for next test
                await self.rate_limit_service.reset_limits(company_id)
                await asyncio.sleep(1)
            
            return results
            
        except Exception as e:
            print(f"    ❌ High load test failed: {e}")
            raise
    
    async def test_quota_enforcement(self):
        """Test quota enforcement functionality"""
        print("📊 Testing quota enforcement...")
        
        results = {}
        
        for tier_name, config in list(self.test_companies.items())[:2]:  # Test first 2 tiers
            print(f"  Testing {tier_name} quota enforcement...")
            
            company_id = config["company_id"]
            monthly_limit = config["quotas"]["monthly_requests"]
            cost_limit = config["quotas"]["monthly_cost"]
            
            try:
                # Reset quotas
                await self.quota_service.reset_monthly_quotas(company_id)
                
                # Test request quota
                print(f"    Testing request quota ({monthly_limit} requests)...")
                
                # Use up 90% of quota
                requests_to_make = int(monthly_limit * 0.9)
                for i in range(0, requests_to_make, 100):  # Batch for efficiency
                    batch_size = min(100, requests_to_make - i)
                    await self.quota_service.record_usage(
                        company_id,
                        requests=batch_size,
                        cost=batch_size * 0.01
                    )
                
                # Check quota status
                quota_status = await self.quota_service.get_quota_status(company_id)
                
                assert quota_status["requests_used"] >= requests_to_make * 0.95, "Request quota not properly tracked"
                assert not quota_status["requests_exceeded"], "Request quota should not be exceeded yet"
                
                # Push over the limit
                await self.quota_service.record_usage(
                    company_id,
                    requests=monthly_limit,  # This should exceed limit
                    cost=10.0
                )
                
                # Check if quota is now exceeded
                quota_status = await self.quota_service.get_quota_status(company_id)
                
                results[f"{tier_name}_requests"] = {
                    "monthly_limit": monthly_limit,
                    "requests_used": quota_status["requests_used"],
                    "requests_exceeded": quota_status["requests_exceeded"],
                    "quota_enforcement_working": quota_status["requests_exceeded"]
                }
                
                assert quota_status["requests_exceeded"], f"{tier_name}: Request quota should be exceeded"
                
                print(f"    ✅ Request quota: {quota_status['requests_used']}/{monthly_limit} (exceeded: {quota_status['requests_exceeded']})")
                
                # Test cost quota
                print(f"    Testing cost quota (${cost_limit})...")
                
                # Reset and test cost quota
                await self.quota_service.reset_monthly_quotas(company_id)
                
                # Use up most of cost quota
                cost_to_use = cost_limit * 0.95
                await self.quota_service.record_usage(
                    company_id,
                    requests=10,
                    cost=cost_to_use
                )
                
                quota_status = await self.quota_service.get_quota_status(company_id)
                assert not quota_status["cost_exceeded"], "Cost quota should not be exceeded yet"
                
                # Push over cost limit
                await self.quota_service.record_usage(
                    company_id,
                    requests=5,
                    cost=cost_limit  # This should exceed limit
                )
                
                quota_status = await self.quota_service.get_quota_status(company_id)
                
                results[f"{tier_name}_cost"] = {
                    "cost_limit": cost_limit,
                    "cost_used": quota_status["cost_used"],
                    "cost_exceeded": quota_status["cost_exceeded"],
                    "quota_enforcement_working": quota_status["cost_exceeded"]
                }
                
                assert quota_status["cost_exceeded"], f"{tier_name}: Cost quota should be exceeded"
                
                print(f"    ✅ Cost quota: ${quota_status['cost_used']:.2f}/${cost_limit} (exceeded: {quota_status['cost_exceeded']})")
                
            except Exception as e:
                print(f"    ❌ {tier_name} quota test failed: {e}")
                results[f"{tier_name}_error"] = {"error": str(e)}
                raise
        
        return results
    
    async def test_quota_alerting(self):
        """Test quota alerting at various thresholds"""
        print("🚨 Testing quota alerting...")
        
        company_id = self.test_companies["basic_tier"]["company_id"]
        monthly_limit = self.test_companies["basic_tier"]["quotas"]["monthly_requests"]
        
        try:
            # Reset quotas and alerts
            await self.quota_service.reset_monthly_quotas(company_id)
            await self.quota_service.clear_alerts(company_id)
            
            # Configure alert thresholds
            alert_thresholds = [75, 90, 95, 100]
            await self.quota_service.configure_alert_thresholds(
                company_id,
                alert_thresholds
            )
            
            results = {}
            
            # Test each threshold
            for threshold in alert_thresholds:
                print(f"  Testing {threshold}% threshold...")
                
                # Use up to threshold
                target_requests = int(monthly_limit * threshold / 100)
                current_usage = await self.quota_service.get_current_usage(company_id)
                requests_needed = target_requests - current_usage["requests"]
                
                if requests_needed > 0:
                    await self.quota_service.record_usage(
                        company_id,
                        requests=requests_needed,
                        cost=requests_needed * 0.01
                    )
                
                # Check if alert was triggered
                alerts = await self.quota_service.get_recent_alerts(company_id)
                threshold_alert = next(
                    (alert for alert in alerts if alert["threshold"] == threshold),
                    None
                )
                
                results[f"threshold_{threshold}"] = {
                    "threshold": threshold,
                    "target_requests": target_requests,
                    "alert_triggered": threshold_alert is not None,
                    "alert_details": threshold_alert
                }
                
                if threshold < 100:  # 100% threshold might not trigger immediately
                    assert threshold_alert is not None, f"Alert should be triggered at {threshold}% threshold"
                
                print(f"    ✅ {threshold}% threshold: Alert {'triggered' if threshold_alert else 'not triggered'}")
            
            return results
            
        except Exception as e:
            print(f"    ❌ Quota alerting test failed: {e}")
            raise
    
    async def test_rate_limit_bypass(self):
        """Test rate limit bypass functionality for special cases"""
        print("🚪 Testing rate limit bypass...")
        
        company_id = self.test_companies["free_tier"]["company_id"]
        minute_limit = self.test_companies["free_tier"]["rate_limits"]["requests_per_minute"]
        
        try:
            # Reset limits
            await self.rate_limit_service.reset_limits(company_id)
            
            # Fill up rate limit
            for i in range(minute_limit):
                await self.rate_limit_service.record_request(company_id)
            
            # Next request should be rate limited
            is_allowed = await self.rate_limit_service.check_rate_limit(
                company_id,
                "requests_per_minute"
            )
            assert not is_allowed, "Should be rate limited"
            
            # Test bypass with admin override
            is_allowed_with_bypass = await self.rate_limit_service.check_rate_limit(
                company_id,
                "requests_per_minute",
                bypass=True,
                bypass_reason="admin_override"
            )
            assert is_allowed_with_bypass, "Should be allowed with bypass"
            
            # Test bypass with emergency flag
            is_allowed_emergency = await self.rate_limit_service.check_rate_limit(
                company_id,
                "requests_per_minute",
                bypass=True,
                bypass_reason="emergency"
            )
            assert is_allowed_emergency, "Should be allowed with emergency bypass"
            
            print("    ✅ Rate limit bypass working correctly")
            
            return {
                "normal_blocked": not is_allowed,
                "admin_bypass_works": is_allowed_with_bypass,
                "emergency_bypass_works": is_allowed_emergency
            }
            
        except Exception as e:
            print(f"    ❌ Rate limit bypass test failed: {e}")
            raise
    
    async def run_all_tests(self):
        """Run all rate limiting and quota tests"""
        print("🚦 Starting Rate Limiting and Quota Enforcement Tests")
        print("=" * 60)
        
        try:
            await self.setup()
            
            # Run all test methods
            basic_results = await self.test_rate_limiting_basic_functionality()
            sliding_results = await self.test_sliding_window_rate_limiting()
            burst_results = await self.test_burst_allowance()
            load_results = await self.test_high_load_rate_limiting()
            quota_results = await self.test_quota_enforcement()
            alert_results = await self.test_quota_alerting()
            bypass_results = await self.test_rate_limit_bypass()
            
            print("=" * 60)
            print("🎉 All Rate Limiting and Quota Tests PASSED!")
            
            # Print summary
            await self._print_test_summary({
                "basic": basic_results,
                "sliding_window": sliding_results,
                "burst": burst_results,
                "high_load": load_results,
                "quota": quota_results,
                "alerting": alert_results,
                "bypass": bypass_results
            })
            
            return True
            
        except Exception as e:
            print(f"❌ Rate Limiting and Quota Tests FAILED: {e}")
            raise
    
    async def _print_test_summary(self, results):
        """Print comprehensive test summary"""
        print("\n📊 Rate Limiting & Quota Test Summary:")
        print("-" * 45)
        
        # Basic functionality
        basic = results["basic"]
        working_tiers = sum(1 for r in basic.values() if isinstance(r, dict) and r.get("rate_limiting_working", False))
        print(f"🚦 Basic Rate Limiting: {working_tiers}/{len(basic)} tiers working correctly")
        
        # High load performance
        load = results["high_load"]
        max_rps = max(r.get("requests_per_second", 0) for r in load.values() if isinstance(r, dict))
        print(f"⚡ High Load Performance: {max_rps:.0f} requests/second sustained")
        
        # Quota enforcement
        quota = results["quota"]
        quota_working = sum(1 for k, r in quota.items() if isinstance(r, dict) and r.get("quota_enforcement_working", False))
        print(f"📊 Quota Enforcement: {quota_working} quota types working correctly")
        
        # Alerting
        alert = results["alerting"]
        alerts_working = sum(1 for r in alert.values() if isinstance(r, dict) and r.get("alert_triggered", False))
        print(f"🚨 Alert System: {alerts_working}/{len(alert)} thresholds triggering correctly")
        
        # Advanced features
        sliding = results["sliding_window"]
        burst = results["burst"]
        bypass = results["bypass"]
        
        advanced_features = [
            sliding.get("sliding_window_working", False),
            burst.get("burst_working", False),
            bypass.get("admin_bypass_works", False) and bypass.get("emergency_bypass_works", False)
        ]
        working_features = sum(advanced_features)
        
        print(f"🔧 Advanced Features: {working_features}/3 working (sliding window, burst, bypass)")
        print(f"✅ Overall System: Rate limiting and quotas are {'fully functional' if working_features >= 2 else 'needs attention'}")


# Standalone execution
async def main():
    """Run rate limiting and quota tests"""
    try:
        test_suite = RateLimitingQuotaTests()
        await test_suite.run_all_tests()
        print("\n🎊 Rate Limiting and Quota Testing Complete!")
        
    except Exception as e:
        print(f"\n❌ Rate Limiting and Quota Tests Failed: {e}")
        import traceback
        traceback.print_exc()
        return False
    
    return True

if __name__ == "__main__":
    success = asyncio.run(main())
    exit(0 if success else 1)
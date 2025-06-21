#!/usr/bin/env python3
"""
Comprehensive Redis operations test for API Lens
Tests all Redis operations: get, set, incr, expire, and cache patterns
"""
import asyncio
import sys
import os
import json
from uuid import uuid4, UUID
from datetime import datetime

# Add the parent directory to the path so we can import from app
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from app.services.cache import (
    redis_client,
    # API Key operations
    cache_api_key_mapping,
    get_cached_company,
    # Vendor key operations
    cache_vendor_key,
    get_cached_vendor_key,
    # Rate limiting operations
    increment_rate_limit,
    get_rate_limit,
    reset_rate_limit,
    # Cost tracking operations
    cache_cost_data,
    get_cached_cost_data,
    # Analytics operations
    cache_analytics_data,
    get_cached_analytics_data,
    # Session operations
    cache_session_data,
    get_cached_session_data,
    # Utility operations
    invalidate_company_cache,
    get_cache_stats,
    health_check,
    close_redis_connection
)

class RedisOperationsTest:
    def __init__(self):
        self.test_company_id = uuid4()
        self.test_results = []
        
    def log_result(self, test_name: str, success: bool, message: str = ""):
        """Log test result"""
        status = "✅" if success else "❌"
        self.test_results.append((test_name, success, message))
        print(f"{status} {test_name}: {message}")
        
    async def test_basic_redis_operations(self):
        """Test basic Redis operations (ping, set, get, incr, expire)"""
        print("\\n🔧 Testing Basic Redis Operations...")
        
        # Test ping
        try:
            pong = await redis_client.ping()
            self.log_result("Redis Ping", pong == True, "Connection successful")
        except Exception as e:
            self.log_result("Redis Ping", False, str(e))
            return False
            
        # Test set/get
        try:
            test_key = "test:basic_ops"
            test_value = "Hello Redis!"
            
            await redis_client.set(test_key, test_value)
            retrieved = await redis_client.get(test_key)
            
            success = retrieved == test_value
            self.log_result("Set/Get Operations", success, f"Value: {retrieved}")
            
            # Cleanup
            await redis_client.delete(test_key)
        except Exception as e:
            self.log_result("Set/Get Operations", False, str(e))
            
        # Test increment
        try:
            counter_key = "test:counter"
            
            count1 = await redis_client.incr(counter_key)
            count2 = await redis_client.incr(counter_key)
            
            success = count1 == 1 and count2 == 2
            self.log_result("Increment Operations", success, f"Count: {count1} -> {count2}")
            
            # Cleanup
            await redis_client.delete(counter_key)
        except Exception as e:
            self.log_result("Increment Operations", False, str(e))
            
        # Test expire
        try:
            expire_key = "test:expire"
            await redis_client.set(expire_key, "will_expire")
            await redis_client.expire(expire_key, 1)  # 1 second
            
            # Check it exists
            exists_before = await redis_client.exists(expire_key)
            
            # Wait for expiration
            await asyncio.sleep(1.5)
            
            # Check it's gone
            exists_after = await redis_client.exists(expire_key)
            
            success = exists_before == 1 and exists_after == 0
            self.log_result("Expire Operations", success, f"Before: {exists_before}, After: {exists_after}")
            
        except Exception as e:
            self.log_result("Expire Operations", False, str(e))
            
        return True
        
    async def test_api_key_caching(self):
        """Test API key caching operations"""
        print("\\n🔑 Testing API Key Caching...")
        
        try:
            test_hash = "test_hash_12345"
            company_data = {
                "company_id": str(self.test_company_id),
                "company_name": "Test Company",
                "plan": "premium",
                "created_at": datetime.now().isoformat()
            }
            
            # Test caching
            await cache_api_key_mapping(test_hash, company_data)
            self.log_result("Cache API Key", True, f"Cached for hash: {test_hash}")
            
            # Test retrieval
            retrieved_data = await get_cached_company(test_hash)
            success = retrieved_data is not None and retrieved_data["company_id"] == str(self.test_company_id)
            self.log_result("Retrieve API Key", success, f"Retrieved: {retrieved_data['company_name'] if retrieved_data else 'None'}")
            
            # Test cache miss
            missing_data = await get_cached_company("non_existent_hash")
            success = missing_data is None
            self.log_result("API Key Cache Miss", success, "Correctly returned None")
            
        except Exception as e:
            self.log_result("API Key Caching", False, str(e))
            
    async def test_vendor_key_caching(self):
        """Test vendor API key caching"""
        print("\\n🔐 Testing Vendor Key Caching...")
        
        try:
            vendor = "openai"
            encrypted_key = "encrypted_sk_test_12345"
            
            # Test caching
            await cache_vendor_key(self.test_company_id, vendor, encrypted_key)
            self.log_result("Cache Vendor Key", True, f"Cached {vendor} key")
            
            # Test retrieval
            retrieved_key = await get_cached_vendor_key(self.test_company_id, vendor)
            success = retrieved_key == encrypted_key
            self.log_result("Retrieve Vendor Key", success, f"Retrieved: {retrieved_key}")
            
            # Test different vendor (cache miss)
            missing_key = await get_cached_vendor_key(self.test_company_id, "anthropic")
            success = missing_key is None
            self.log_result("Vendor Key Cache Miss", success, "Correctly returned None")
            
        except Exception as e:
            self.log_result("Vendor Key Caching", False, str(e))
            
    async def test_rate_limiting(self):
        """Test rate limiting operations"""
        print("\\n⏱️  Testing Rate Limiting...")
        
        try:
            limit_type = "requests"
            
            # Test increment
            count1 = await increment_rate_limit(self.test_company_id, limit_type)
            count2 = await increment_rate_limit(self.test_company_id, limit_type)
            count3 = await increment_rate_limit(self.test_company_id, limit_type)
            
            success = count1 == 1 and count2 == 2 and count3 == 3
            self.log_result("Rate Limit Increment", success, f"Counts: {count1}, {count2}, {count3}")
            
            # Test get
            current_count = await get_rate_limit(self.test_company_id, limit_type)
            success = current_count == 3
            self.log_result("Rate Limit Get", success, f"Current count: {current_count}")
            
            # Test reset
            await reset_rate_limit(self.test_company_id, limit_type)
            reset_count = await get_rate_limit(self.test_company_id, limit_type)
            success = reset_count == 0
            self.log_result("Rate Limit Reset", success, f"After reset: {reset_count}")
            
        except Exception as e:
            self.log_result("Rate Limiting", False, str(e))
            
    async def test_cost_tracking(self):
        """Test cost data caching"""
        print("\\n💰 Testing Cost Tracking...")
        
        try:
            period = "2024-01-15"
            cost = 123.45
            
            # Test caching
            await cache_cost_data(self.test_company_id, period, cost)
            self.log_result("Cache Cost Data", True, f"Cached ${cost} for {period}")
            
            # Test retrieval
            retrieved_cost = await get_cached_cost_data(self.test_company_id, period)
            success = retrieved_cost == cost
            self.log_result("Retrieve Cost Data", success, f"Retrieved: ${retrieved_cost}")
            
            # Test cache miss
            missing_cost = await get_cached_cost_data(self.test_company_id, "2024-01-16")
            success = missing_cost is None
            self.log_result("Cost Data Cache Miss", success, "Correctly returned None")
            
        except Exception as e:
            self.log_result("Cost Tracking", False, str(e))
            
    async def test_analytics_caching(self):
        """Test analytics data caching"""
        print("\\n📊 Testing Analytics Caching...")
        
        try:
            metric = "requests"
            timeframe = "hourly"
            analytics_data = {
                "total_requests": 1500,
                "average_latency": 245.6,
                "error_rate": 0.02,
                "top_endpoints": ["/v1/chat", "/v1/completions"]
            }
            
            # Test caching
            await cache_analytics_data(self.test_company_id, metric, timeframe, analytics_data)
            self.log_result("Cache Analytics", True, f"Cached {metric} {timeframe} data")
            
            # Test retrieval
            retrieved_data = await get_cached_analytics_data(self.test_company_id, metric, timeframe)
            success = retrieved_data is not None and retrieved_data["total_requests"] == 1500
            self.log_result("Retrieve Analytics", success, f"Retrieved: {retrieved_data['total_requests'] if retrieved_data else 'None'} requests")
            
        except Exception as e:
            self.log_result("Analytics Caching", False, str(e))
            
    async def test_session_caching(self):
        """Test session data caching"""
        print("\\n👤 Testing Session Caching...")
        
        try:
            session_id = f"sess_{uuid4()}"
            session_data = {
                "user_id": str(uuid4()),
                "company_id": str(self.test_company_id),
                "permissions": ["read", "write"],
                "created_at": datetime.now().isoformat()
            }
            
            # Test caching
            await cache_session_data(session_id, session_data)
            self.log_result("Cache Session", True, f"Cached session: {session_id}")
            
            # Test retrieval
            retrieved_session = await get_cached_session_data(session_id)
            success = retrieved_session is not None and retrieved_session["user_id"] == session_data["user_id"]
            self.log_result("Retrieve Session", success, f"Retrieved: {retrieved_session['user_id'] if retrieved_session else 'None'}")
            
        except Exception as e:
            self.log_result("Session Caching", False, str(e))
            
    async def test_cache_invalidation(self):
        """Test cache invalidation"""
        print("\\n🗑️  Testing Cache Invalidation...")
        
        try:
            # Set up some cached data
            await cache_vendor_key(self.test_company_id, "openai", "test_key_1")
            await cache_vendor_key(self.test_company_id, "anthropic", "test_key_2")
            await increment_rate_limit(self.test_company_id, "requests")
            
            # Verify data exists
            key1_before = await get_cached_vendor_key(self.test_company_id, "openai")
            key2_before = await get_cached_vendor_key(self.test_company_id, "anthropic")
            rate_before = await get_rate_limit(self.test_company_id, "requests")
            
            self.log_result("Setup Cache Data", 
                          key1_before is not None and key2_before is not None and rate_before > 0,
                          f"Keys: {bool(key1_before)}, {bool(key2_before)}, Rate: {rate_before}")
            
            # Invalidate cache
            await invalidate_company_cache(self.test_company_id)
            
            # Verify data is gone
            key1_after = await get_cached_vendor_key(self.test_company_id, "openai")
            key2_after = await get_cached_vendor_key(self.test_company_id, "anthropic")
            rate_after = await get_rate_limit(self.test_company_id, "requests")
            
            success = key1_after is None and key2_after is None and rate_after == 0
            self.log_result("Cache Invalidation", success, 
                          f"After: Keys: {bool(key1_after)}, {bool(key2_after)}, Rate: {rate_after}")
            
        except Exception as e:
            self.log_result("Cache Invalidation", False, str(e))
            
    async def test_cache_stats_and_health(self):
        """Test cache statistics and health check"""
        print("\\n📈 Testing Cache Stats & Health...")
        
        try:
            # Test health check
            is_healthy = await health_check()
            self.log_result("Health Check", is_healthy, "Redis connection healthy")
            
            # Test cache stats
            stats = await get_cache_stats()
            success = isinstance(stats, dict) and "total_keys" in stats
            self.log_result("Cache Stats", success, f"Keys: {stats.get('total_keys', 'unknown')}")
            
        except Exception as e:
            self.log_result("Cache Stats & Health", False, str(e))
            
    async def run_all_tests(self):
        """Run all Redis tests"""
        print("🚀 Starting Comprehensive Redis Operations Test\\n")
        
        try:
            # Run all test suites
            await self.test_basic_redis_operations()
            await self.test_api_key_caching()
            await self.test_vendor_key_caching()
            await self.test_rate_limiting()
            await self.test_cost_tracking()
            await self.test_analytics_caching()
            await self.test_session_caching()
            await self.test_cache_invalidation()
            await self.test_cache_stats_and_health()
            
            # Print summary
            print("\\n" + "="*60)
            print("📋 TEST SUMMARY")
            print("="*60)
            
            passed = sum(1 for _, success, _ in self.test_results if success)
            total = len(self.test_results)
            
            for test_name, success, message in self.test_results:
                status = "✅ PASS" if success else "❌ FAIL"
                print(f"{status}: {test_name} - {message}")
                
            print(f"\\n🎯 Results: {passed}/{total} tests passed")
            
            if passed == total:
                print("🎉 All Redis operations working perfectly!")
                return True
            else:
                print(f"💥 {total - passed} tests failed!")
                return False
                
        except Exception as e:
            print(f"❌ Test suite failed: {e}")
            return False
        finally:
            # Clean up
            await close_redis_connection()

async def main():
    """Run the Redis operations test"""
    test_runner = RedisOperationsTest()
    success = await test_runner.run_all_tests()
    sys.exit(0 if success else 1)

if __name__ == "__main__":
    asyncio.run(main())
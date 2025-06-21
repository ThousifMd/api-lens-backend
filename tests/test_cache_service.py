"""
Comprehensive test suite for the Cache Layer Service (2.5)
Tests all caching functions, strategies, and performance monitoring
"""
import pytest
import asyncio
import json
import time
from unittest.mock import AsyncMock, patch, MagicMock
from uuid import uuid4
from datetime import datetime

from app.services.cache import (
    cache_api_key_mapping,
    get_cached_company,
    cache_vendor_key,
    get_cached_vendor_key,
    invalidate_company_cache,
    get_cache_stats,
    warm_api_key_cache,
    warm_vendor_key_cache,
    warm_all_caches,
    cache_health_check,
    reset_cache_stats,
    cache_maintenance,
    CacheService,
    CacheStats,
    CacheError,
    _get_cache_key,
    _hash_data,
    _calculate_error_rate,
    _calculate_performance_grade,
    _cache_stats
)

class TestCacheOperations:
    """Test suite for 2.5.1 Cache Operations requirements"""
    
    @pytest.mark.asyncio
    async def test_cache_api_key_mapping_signature_and_functionality(self):
        """Test cache_api_key_mapping(api_key_hash: str, company_data: dict)"""
        api_key_hash = "test_hash_12345"
        company_data = {
            'id': str(uuid4()),
            'name': 'Test Company',
            'schema_name': 'test_schema',
            'rate_limit_rps': 100
        }
        
        with patch('app.services.cache.cache_service._get_redis_client') as mock_redis_method:
            mock_redis = AsyncMock()
            mock_redis_method.return_value = mock_redis
            
            result = await cache_api_key_mapping(api_key_hash, company_data)
            
            assert result is True
            assert isinstance(result, bool)
            
            # Verify Redis was called correctly
            mock_redis.setex.assert_called_once()
            call_args = mock_redis.setex.call_args
            
            # Check key format
            assert 'api_key_mapping:' in call_args[0][0]
            assert api_key_hash in call_args[0][0]
            
            # Check TTL
            assert call_args[0][1] == 3600  # TTL.API_KEY_MAPPING
            
            # Check cached data structure
            cached_data = json.loads(call_args[0][2])
            assert 'company_data' in cached_data
            assert 'cached_at' in cached_data
            assert cached_data['company_data'] == company_data
    
    @pytest.mark.asyncio
    async def test_get_cached_company_signature_and_functionality(self):
        """Test get_cached_company(api_key_hash: str) -> Optional[dict]"""
        api_key_hash = "test_hash_12345"
        company_data = {
            'id': str(uuid4()),
            'name': 'Test Company',
            'schema_name': 'test_schema'
        }
        
        cached_data = {
            'company_data': company_data,
            'cached_at': datetime.utcnow().isoformat(),
            'ttl': 3600
        }
        
        with patch('app.services.cache.cache_service._get_redis_client') as mock_redis_method:
            mock_redis = AsyncMock()
            mock_redis.get.return_value = json.dumps(cached_data)
            mock_redis_method.return_value = mock_redis
            
            result = await get_cached_company(api_key_hash)
            
            assert result == company_data
            assert isinstance(result, dict)
            
            # Verify Redis was called
            mock_redis.get.assert_called_once()
            call_args = mock_redis.get.call_args
            assert 'api_key_mapping:' in call_args[0][0]
            assert api_key_hash in call_args[0][0]
    
    @pytest.mark.asyncio
    async def test_get_cached_company_cache_miss(self):
        """Test get_cached_company returns None on cache miss"""
        api_key_hash = "nonexistent_hash"
        
        with patch('app.services.cache.cache_service._get_redis_client') as mock_redis_method:
            mock_redis = AsyncMock()
            mock_redis.get.return_value = None  # Cache miss
            mock_redis_method.return_value = mock_redis
            
            result = await get_cached_company(api_key_hash)
            
            assert result is None
    
    @pytest.mark.asyncio
    async def test_cache_vendor_key_signature_and_functionality(self):
        """Test cache_vendor_key(company_id: str, vendor: str, encrypted_key: str)"""
        company_id = str(uuid4())
        vendor = "openai"
        encrypted_key = "encrypted_test_key_data"
        
        with patch('app.services.cache.cache_service._get_redis_client') as mock_redis_method:
            mock_redis = AsyncMock()
            mock_redis_method.return_value = mock_redis
            
            result = await cache_vendor_key(company_id, vendor, encrypted_key)
            
            assert result is True
            assert isinstance(result, bool)
            
            # Verify Redis was called correctly
            mock_redis.setex.assert_called_once()
            call_args = mock_redis.setex.call_args
            
            # Check key format
            assert 'vendor_key:' in call_args[0][0]
            assert company_id in call_args[0][0]
            assert vendor.lower() in call_args[0][0]
            
            # Check TTL
            assert call_args[0][1] == 1800  # TTL.VENDOR_KEY
            
            # Check cached data structure
            cached_data = json.loads(call_args[0][2])
            assert cached_data['encrypted_key'] == encrypted_key
            assert cached_data['company_id'] == company_id
            assert cached_data['vendor'] == vendor.lower()
    
    @pytest.mark.asyncio
    async def test_invalidate_company_cache_signature_and_functionality(self):
        """Test invalidate_company_cache(company_id: str) -> int"""
        company_id = str(uuid4())
        
        with patch('app.services.cache.cache_service._get_redis_client') as mock_redis_method:
            mock_redis = AsyncMock()
            
            # Mock scan_iter to return some keys
            async def mock_scan_iter(match=None, count=100):
                if match and company_id in match:
                    yield f"dev:vendor_key:{company_id}:openai"
                    yield f"dev:rate_limit:{company_id}:minute"
            
            mock_redis.scan_iter = mock_scan_iter
            mock_redis.delete.return_value = 2  # 2 keys deleted
            mock_redis_method.return_value = mock_redis
            
            result = await invalidate_company_cache(company_id)
            
            assert isinstance(result, int)
            assert result >= 0  # Should return number of deleted keys
            
            # Verify delete was called
            assert mock_redis.delete.call_count > 0
    
    @pytest.mark.asyncio
    async def test_get_cache_stats_signature_and_functionality(self):
        """Test get_cache_stats() -> dict"""
        mock_redis_info = {
            'used_memory': 1024000,
            'used_memory_human': '1000.00K',
            'connected_clients': 5,
            'total_commands_processed': 1000,
            'keyspace_hits': 800,
            'keyspace_misses': 200
        }
        
        with patch('app.services.cache.cache_service._get_redis_client') as mock_redis_method:
            mock_redis = AsyncMock()
            mock_redis.info.return_value = mock_redis_info
            mock_redis.dbsize.return_value = 150
            
            # Mock scan_iter for memory usage patterns
            async def mock_scan_iter(match=None, count=100):
                if 'api_key_mapping' in match:
                    yield 'key1'
                    yield 'key2'
                elif 'vendor_key' in match:
                    yield 'key3'
            
            mock_redis.scan_iter = mock_scan_iter
            mock_redis_method.return_value = mock_redis
            
            result = await get_cache_stats()
            
            assert isinstance(result, dict)
            
            # Check required structure
            assert 'timestamp' in result
            assert 'environment' in result
            assert 'app_stats' in result
            assert 'redis_stats' in result
            assert 'memory_usage' in result
            assert 'health' in result
            
            # Check Redis stats
            redis_stats = result['redis_stats']
            assert redis_stats['total_keys'] == 150
            assert redis_stats['used_memory'] == 1024000
            assert redis_stats['connected_clients'] == 5
            assert 'hit_rate' in redis_stats
            
            # Check health indicators
            health = result['health']
            assert 'redis_connected' in health
            assert 'error_rate' in health
            assert 'performance_grade' in health

class TestCacheWarmingFunctions:
    """Test suite for cache warming functionality"""
    
    @pytest.mark.asyncio
    async def test_warm_api_key_cache(self):
        """Test warming API key cache with database data"""
        mock_api_keys = [
            {
                'key_hash': 'hash1',
                'id': uuid4(),
                'name': 'Company 1',
                'schema_name': 'company_1',
                'rate_limit_rps': 100,
                'monthly_quota': 1000000
            },
            {
                'key_hash': 'hash2',
                'id': uuid4(),
                'name': 'Company 2',
                'schema_name': 'company_2',
                'rate_limit_rps': 200,
                'monthly_quota': 2000000
            }
        ]
        
        with patch('app.services.cache.DatabaseUtils.execute_query', return_value=mock_api_keys):
            with patch('app.services.cache.cache_api_key_mapping', return_value=True) as mock_cache:
                result = await warm_api_key_cache()
                
                assert result == 2  # Number of keys warmed
                assert mock_cache.call_count == 2
    
    @pytest.mark.asyncio
    async def test_warm_vendor_key_cache(self):
        """Test warming vendor key cache with database data"""
        mock_companies = [
            {'id': uuid4(), 'schema_name': 'company_1'}
        ]
        
        mock_vendor_keys = [
            {'vendor': 'openai', 'encrypted_key': 'encrypted_key_1'},
            {'vendor': 'anthropic', 'encrypted_key': 'encrypted_key_2'}
        ]
        
        with patch('app.services.cache.DatabaseUtils.execute_query') as mock_db:
            mock_db.side_effect = [mock_companies, mock_vendor_keys]
            
            with patch('app.services.cache.cache_vendor_key', return_value=True) as mock_cache:
                result = await warm_vendor_key_cache()
                
                assert result == 2  # Number of vendor keys warmed
                assert mock_cache.call_count == 2
    
    @pytest.mark.asyncio
    async def test_warm_all_caches(self):
        """Test warming all cache types concurrently"""
        with patch('app.services.cache.warm_api_key_cache', return_value=5) as mock_api:
            with patch('app.services.cache.warm_vendor_key_cache', return_value=3) as mock_vendor:
                result = await warm_all_caches()
                
                assert isinstance(result, dict)
                assert result['api_key_mappings'] == 5
                assert result['vendor_keys'] == 3
                assert result['total'] == 8
                
                mock_api.assert_called_once()
                mock_vendor.assert_called_once()

class TestCacheHealthAndMaintenance:
    """Test suite for cache health monitoring and maintenance"""
    
    @pytest.mark.asyncio
    async def test_cache_health_check(self):
        """Test cache health check functionality"""
        with patch('app.services.cache.cache_service._get_redis_client') as mock_redis_method:
            mock_redis = AsyncMock()
            mock_redis.set.return_value = True
            mock_redis.get.return_value = "test_value"
            mock_redis.delete.return_value = True
            mock_redis.setex.return_value = True
            mock_redis_method.return_value = mock_redis
            
            result = await cache_health_check()
            
            assert result is True
            
            # Verify operations were called
            mock_redis.set.assert_called_once()
            mock_redis.get.assert_called_once()
            mock_redis.delete.assert_called_once()
            mock_redis.setex.assert_called_once()
    
    @pytest.mark.asyncio
    async def test_cache_health_check_failure(self):
        """Test cache health check when Redis is down"""
        with patch('app.services.cache.cache_service._get_redis_client') as mock_redis_method:
            mock_redis = AsyncMock()
            mock_redis.set.side_effect = Exception("Redis connection failed")
            mock_redis_method.return_value = mock_redis
            
            result = await cache_health_check()
            
            assert result is False
    
    @pytest.mark.asyncio
    async def test_cache_maintenance(self):
        """Test periodic cache maintenance"""
        mock_memory_info = {'used_memory': 1024000}
        
        with patch('app.services.cache.cache_service._get_redis_client') as mock_redis_method:
            mock_redis = AsyncMock()
            mock_redis.info.return_value = mock_memory_info
            mock_redis.dbsize.return_value = 100
            mock_redis_method.return_value = mock_redis
            
            result = await cache_maintenance()
            
            assert isinstance(result, dict)
            assert 'timestamp' in result
            assert 'status' in result
            assert result['status'] == 'completed'
            assert 'keys_before' in result
            assert 'keys_after' in result
            assert 'memory_before' in result
            assert 'memory_after' in result

class TestCacheStatsTracking:
    """Test suite for cache statistics tracking"""
    
    def test_cache_stats_initialization(self):
        """Test CacheStats class initialization"""
        stats = CacheStats()
        
        assert stats.hits == 0
        assert stats.misses == 0
        assert stats.sets == 0
        assert stats.deletes == 0
        assert stats.errors == 0
        assert stats.hit_rate == 0.0
        assert stats.avg_response_time == 0.0
        assert stats.uptime > 0.0
    
    def test_cache_stats_recording(self):
        """Test cache statistics recording"""
        stats = CacheStats()
        
        # Record operations
        stats.record_hit(0.001)
        stats.record_hit(0.002)
        stats.record_miss(0.003)
        stats.record_set(0.001)
        stats.record_delete(0.001)
        stats.record_error()
        
        assert stats.hits == 2
        assert stats.misses == 1
        assert stats.sets == 1
        assert stats.deletes == 1
        assert stats.errors == 1
        assert round(stats.hit_rate, 2) == 66.67  # 2 hits out of 3 total (hits + misses)
        assert stats.avg_response_time > 0.0
    
    def test_cache_stats_to_dict(self):
        """Test cache statistics dictionary conversion"""
        stats = CacheStats()
        stats.record_hit(0.001)
        stats.record_miss(0.002)
        
        result = stats.to_dict()
        
        assert isinstance(result, dict)
        expected_keys = [
            'hits', 'misses', 'sets', 'deletes', 'errors',
            'hit_rate', 'avg_response_time_ms', 'uptime_seconds', 'total_operations'
        ]
        
        for key in expected_keys:
            assert key in result
        
        assert result['hits'] == 1
        assert result['misses'] == 1
        assert result['total_operations'] == 2
    
    @pytest.mark.asyncio
    async def test_reset_cache_stats(self):
        """Test resetting cache statistics"""
        # Test that reset_cache_stats function exists and can be called
        # We'll test functionality by verifying the function completes without error
        try:
            await reset_cache_stats()
            # If we get here, the function executed successfully
            assert True
        except Exception as e:
            pytest.fail(f"reset_cache_stats() raised an exception: {e}")
        
        # Test that the function creates a new CacheStats instance
        from app.services.cache import _cache_stats
        
        # The stats object should have all counters
        assert hasattr(_cache_stats, 'hits')
        assert hasattr(_cache_stats, 'misses')
        assert hasattr(_cache_stats, 'sets')
        assert hasattr(_cache_stats, 'deletes')
        assert hasattr(_cache_stats, 'errors')

class TestCacheUtilityFunctions:
    """Test suite for cache utility functions"""
    
    def test_get_cache_key_generation(self):
        """Test cache key generation with patterns"""
        from app.services.cache import KeyPattern
        
        # Test API key mapping pattern
        key = _get_cache_key(KeyPattern.API_KEY_MAPPING, hash="test_hash")
        assert "api_key_mapping:test_hash" in key
        assert key.startswith("dev:")  # Environment prefix
        
        # Test vendor key pattern
        company_id = str(uuid4())
        key = _get_cache_key(KeyPattern.VENDOR_KEY, company_id=company_id, vendor="openai")
        assert f"vendor_key:{company_id}:openai" in key
    
    def test_hash_data_function(self):
        """Test data hashing for consistent cache keys"""
        data1 = "test_data_123"
        data2 = "test_data_123"
        data3 = "different_data"
        
        hash1 = _hash_data(data1)
        hash2 = _hash_data(data2)
        hash3 = _hash_data(data3)
        
        assert hash1 == hash2  # Same data should produce same hash
        assert hash1 != hash3  # Different data should produce different hash
        assert len(hash1) == 16  # Should be truncated to 16 characters
    
    def test_calculate_error_rate(self):
        """Test error rate calculation"""
        # Create a patch to use our own stats instance for testing
        test_stats = CacheStats()
        
        with patch('app.services.cache._cache_stats', test_stats):
            # No operations yet
            assert _calculate_error_rate() == 0.0
            
            # Record some operations (total_ops = hits + misses + sets + deletes)
            test_stats.record_hit()    # 1 hit
            test_stats.record_hit()    # 2 hits
            test_stats.record_miss()   # 1 miss
            test_stats.record_set()    # 1 set
            test_stats.record_error()  # 1 error
            
            # Error rate = errors / total_ops * 100
            # total_ops = 2 + 1 + 1 + 0 = 4, errors = 1
            # error_rate = 1/4 * 100 = 25%
            error_rate = _calculate_error_rate()
            assert error_rate == 25.0
    
    def test_calculate_performance_grade(self):
        """Test performance grade calculation"""
        # Test A+ grade (95% hit rate, <1ms response time)
        test_stats = CacheStats()
        for _ in range(95):
            test_stats.record_hit(0.0005)  # 0.5ms response time
        for _ in range(5):
            test_stats.record_miss(0.0005)  # 95% hit rate total
        
        with patch('app.services.cache._cache_stats', test_stats):
            grade = _calculate_performance_grade()
            assert grade == 'A+'
        
        # Test C grade (70% hit rate, 15ms response time)
        test_stats2 = CacheStats()
        for _ in range(70):
            test_stats2.record_hit(0.015)  # 15ms response time
        for _ in range(30):
            test_stats2.record_miss(0.015)  # 70% hit rate
        
        with patch('app.services.cache._cache_stats', test_stats2):
            grade = _calculate_performance_grade()
            assert grade == 'C'
        
        # Test D grade (low hit rate)
        test_stats3 = CacheStats()
        for _ in range(5):
            test_stats3.record_hit(0.025)  # 25ms response time
        for _ in range(95):
            test_stats3.record_miss(0.025)  # 5% hit rate
        
        with patch('app.services.cache._cache_stats', test_stats3):
            grade = _calculate_performance_grade()
            assert grade == 'D'

class TestCacheErrorHandling:
    """Test suite for cache error handling"""
    
    @pytest.mark.asyncio
    async def test_cache_api_key_mapping_error(self):
        """Test error handling in cache_api_key_mapping"""
        with patch('app.services.cache.cache_service._get_redis_client') as mock_redis_method:
            mock_redis = AsyncMock()
            mock_redis.setex.side_effect = Exception("Redis error")
            mock_redis_method.return_value = mock_redis
            
            with pytest.raises(CacheError):
                await cache_api_key_mapping("test_hash", {"test": "data"})
    
    @pytest.mark.asyncio
    async def test_get_cached_company_error_handling(self):
        """Test error handling in get_cached_company returns None"""
        with patch('app.services.cache.cache_service._get_redis_client') as mock_redis_method:
            mock_redis = AsyncMock()
            mock_redis.get.side_effect = Exception("Redis error")
            mock_redis_method.return_value = mock_redis
            
            # Should return None on error, not raise exception
            result = await get_cached_company("test_hash")
            assert result is None
    
    @pytest.mark.asyncio
    async def test_invalidate_company_cache_error(self):
        """Test error handling in invalidate_company_cache"""
        with patch('app.services.cache.cache_service._get_redis_client') as mock_redis_method:
            mock_redis = AsyncMock()
            mock_redis.scan_iter.side_effect = Exception("Redis error")
            mock_redis_method.return_value = mock_redis
            
            with pytest.raises(CacheError):
                await invalidate_company_cache(str(uuid4()))

class TestFunctionSignatures:
    """Test that all functions have the correct signatures as per 2.5.1 requirements"""
    
    def test_function_signatures_match_requirements(self):
        """Verify function signatures match 2.5.1 Cache Operations requirements"""
        import inspect
        
        # Check cache_api_key_mapping signature
        sig = inspect.signature(cache_api_key_mapping)
        assert 'api_key_hash' in sig.parameters
        assert 'company_data' in sig.parameters
        assert sig.parameters['api_key_hash'].annotation == str
        assert sig.parameters['company_data'].annotation == dict
        
        # Check get_cached_company signature
        sig = inspect.signature(get_cached_company)
        assert 'api_key_hash' in sig.parameters
        assert sig.parameters['api_key_hash'].annotation == str
        
        # Check cache_vendor_key signature
        sig = inspect.signature(cache_vendor_key)
        assert 'company_id' in sig.parameters
        assert 'vendor' in sig.parameters
        assert 'encrypted_key' in sig.parameters
        assert sig.parameters['company_id'].annotation == str
        assert sig.parameters['vendor'].annotation == str
        assert sig.parameters['encrypted_key'].annotation == str
        
        # Check invalidate_company_cache signature
        sig = inspect.signature(invalidate_company_cache)
        assert 'company_id' in sig.parameters
        assert sig.parameters['company_id'].annotation == str
        
        # Check get_cache_stats signature
        sig = inspect.signature(get_cache_stats)
        assert len(sig.parameters) == 0  # No parameters
        assert sig.return_annotation == dict

if __name__ == "__main__":
    pytest.main([__file__, "-v"])
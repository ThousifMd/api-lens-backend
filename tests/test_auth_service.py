"""
Comprehensive test suite for the Authentication Service
Tests all API key management functionality with mocking
"""
import pytest
import secrets
from unittest.mock import AsyncMock, patch, MagicMock
from uuid import UUID, uuid4
from datetime import datetime

from app.services.auth import (
    hash_api_key,
    generate_secure_api_key,
    generate_api_key,
    validate_api_key,
    revoke_api_key,
    list_company_api_keys,
    get_auth_performance_stats,
    reset_auth_performance_stats,
    API_KEY_PREFIX,
    API_KEY_LENGTH
)
from models.api_key import APIKey, APIKeyWithSecret
from models.company import Company

class TestAPIKeyHashing:
    """Test suite for API key hashing functionality"""
    
    def test_hash_api_key_success(self):
        """Test successful API key hashing"""
        api_key = "als_test_key_12345"
        
        with patch('app.services.auth._get_api_key_salt', return_value=b'test_salt'):
            hash1 = hash_api_key(api_key)
            hash2 = hash_api_key(api_key)
            
            # Same input should produce same hash
            assert hash1 == hash2
            assert isinstance(hash1, str)
            assert len(hash1) == 64  # SHA256 hex length
    
    def test_hash_api_key_empty_input(self):
        """Test hashing with empty API key"""
        with pytest.raises(ValueError, match="API key cannot be empty"):
            hash_api_key("")
    
    def test_hash_api_key_none_input(self):
        """Test hashing with None input"""
        with pytest.raises(ValueError, match="API key cannot be empty"):
            hash_api_key(None)
    
    def test_hash_api_key_different_inputs(self):
        """Test that different inputs produce different hashes"""
        with patch('app.services.auth._get_api_key_salt', return_value=b'test_salt'):
            hash1 = hash_api_key("als_key1")
            hash2 = hash_api_key("als_key2")
            
            assert hash1 != hash2

class TestAPIKeyGeneration:
    """Test suite for secure API key generation"""
    
    def test_generate_secure_api_key_format(self):
        """Test API key generation format and structure"""
        api_key = generate_secure_api_key()
        
        assert api_key.startswith(API_KEY_PREFIX)
        assert len(api_key) == API_KEY_LENGTH
        assert isinstance(api_key, str)
    
    def test_generate_secure_api_key_uniqueness(self):
        """Test that generated API keys are unique"""
        keys = {generate_secure_api_key() for _ in range(100)}
        assert len(keys) == 100  # All should be unique
    
    def test_generate_secure_api_key_entropy(self):
        """Test that generated API keys have sufficient entropy"""
        api_key = generate_secure_api_key()
        
        # Remove prefix and check entropy of the random part
        random_part = api_key[len(API_KEY_PREFIX):]
        
        # Should contain alphanumeric characters and URL-safe chars
        assert all(c.isalnum() or c in '-_' for c in random_part)
        assert len(random_part) == 43  # 32 bytes base64url encoded

class TestAPIKeyManagement:
    """Test suite for API key management functions"""
    
    @pytest.mark.asyncio
    async def test_generate_api_key_success(self):
        """Test successful API key generation"""
        company_id = str(uuid4())
        name = "Test API Key"
        
        mock_result = {
            'id': uuid4(),
            'company_id': UUID(company_id),
            'key_hash': 'mock_hash',
            'name': name,
            'is_active': True,
            'created_at': datetime.now(),
            'last_used_at': None
        }
        
        with patch('app.services.auth.DatabaseUtils.execute_query', return_value=mock_result):
            with patch('app.services.auth.generate_secure_api_key', return_value='als_mock_key_12345'):
                with patch('app.services.auth.hash_api_key', return_value='mock_hash'):
                    
                    result = await generate_api_key(company_id, name)
                    
                    assert isinstance(result, APIKeyWithSecret)
                    assert result.name == name
                    assert result.company_id == UUID(company_id)
                    assert result.secret_key == 'als_mock_key_12345'
                    assert result.is_active is True
    
    @pytest.mark.asyncio
    async def test_generate_api_key_invalid_company_id(self):
        """Test API key generation with invalid company ID"""
        with pytest.raises(ValueError, match="Invalid company ID format"):
            await generate_api_key("invalid-uuid", "Test Key")
    
    @pytest.mark.asyncio
    async def test_generate_api_key_empty_name(self):
        """Test API key generation with empty name"""
        company_id = str(uuid4())
        
        with pytest.raises(ValueError, match="API key name is required"):
            await generate_api_key(company_id, "")
    
    @pytest.mark.asyncio
    async def test_validate_api_key_cache_hit(self):
        """Test API key validation with cache hit"""
        api_key = "als_test_key_12345"
        mock_company_data = Company(
            id=uuid4(),
            name="Test Company",
            schema_name="test_company",
            rate_limit_rps=100,
            monthly_quota=1000,
            created_at=datetime.now(),
            updated_at=datetime.now()
        )
        
        mock_cached_data = {
            'id': uuid4(),
            'company_id': mock_company_data.id,
            'key_hash': 'mock_hash',
            'name': 'Test Key',
            'is_active': True
        }
        
        with patch('app.services.auth.get_cached_company', return_value=mock_cached_data):
            with patch('app.services.auth._get_company_by_id', return_value=mock_company_data):
                with patch('app.services.auth.hash_api_key', return_value='mock_hash'):
                    
                    result = await validate_api_key(api_key)
                    
                    assert result == mock_company_data
    
    @pytest.mark.asyncio
    async def test_validate_api_key_cache_miss_db_hit(self):
        """Test API key validation with cache miss and database hit"""
        api_key = "als_test_key_12345"
        
        mock_db_result = {
            'id': uuid4(),
            'company_id': uuid4(),
            'key_hash': 'mock_hash',
            'name': 'Test Key',
            'is_active': True,
            'created_at': datetime.now(),
            'last_used_at': None,
            'company_name': 'Test Company',
            'schema_name': 'test_company',
            'rate_limit_rps': 100,
            'monthly_quota': 1000,
            'company_created_at': datetime.now(),
            'company_updated_at': datetime.now()
        }
        
        with patch('app.services.auth.get_cached_company', return_value=None):
            with patch('app.services.auth.DatabaseUtils.execute_query', return_value=mock_db_result):
                with patch('app.services.auth._update_last_used_timestamp'):
                    with patch('app.services.auth.cache_api_key_mapping'):
                        with patch('app.services.auth.hash_api_key', return_value='mock_hash'):
                            
                            result = await validate_api_key(api_key)
                            
                            assert isinstance(result, Company)
                            assert result.name == 'Test Company'
                            assert result.id == mock_db_result['company_id']
    
    @pytest.mark.asyncio
    async def test_validate_api_key_invalid_prefix(self):
        """Test API key validation with invalid prefix"""
        result = await validate_api_key("invalid_key_format")
        assert result is None
    
    @pytest.mark.asyncio
    async def test_validate_api_key_empty_key(self):
        """Test API key validation with empty key"""
        result = await validate_api_key("")
        assert result is None
    
    @pytest.mark.asyncio
    async def test_validate_api_key_not_found(self):
        """Test API key validation when key not found"""
        api_key = "als_nonexistent_key"
        
        with patch('app.services.auth.get_cached_company', return_value=None):
            with patch('app.services.auth.DatabaseUtils.execute_query', return_value=None):
                with patch('app.services.auth.hash_api_key', return_value='mock_hash'):
                    
                    result = await validate_api_key(api_key)
                    assert result is None
    
    @pytest.mark.asyncio
    async def test_revoke_api_key_success(self):
        """Test successful API key revocation"""
        api_key_id = str(uuid4())
        
        mock_key_data = {
            'key_hash': 'mock_hash',
            'company_id': uuid4()
        }
        
        with patch('app.services.auth.DatabaseUtils.execute_query') as mock_query:
            mock_query.side_effect = [mock_key_data, None]  # First for select, second for update
            with patch('app.services.auth.invalidate_company_cache'):
                
                result = await revoke_api_key(api_key_id)
                assert result is True
    
    @pytest.mark.asyncio
    async def test_revoke_api_key_not_found(self):
        """Test API key revocation when key not found"""
        api_key_id = str(uuid4())
        
        with patch('app.services.auth.DatabaseUtils.execute_query', return_value=None):
            result = await revoke_api_key(api_key_id)
            assert result is False
    
    @pytest.mark.asyncio
    async def test_revoke_api_key_empty_id(self):
        """Test API key revocation with empty ID"""
        result = await revoke_api_key("")
        assert result is False
    
    @pytest.mark.asyncio
    async def test_list_company_api_keys_success(self):
        """Test successful listing of company API keys"""
        company_id = str(uuid4())
        
        mock_results = [
            {
                'id': uuid4(),
                'company_id': UUID(company_id),
                'key_hash': 'hash1',
                'name': 'Key 1',
                'is_active': True,
                'created_at': datetime.now(),
                'last_used_at': None
            },
            {
                'id': uuid4(),
                'company_id': UUID(company_id),
                'key_hash': 'hash2',
                'name': 'Key 2',
                'is_active': False,
                'created_at': datetime.now(),
                'last_used_at': datetime.now()
            }
        ]
        
        with patch('app.services.auth.DatabaseUtils.execute_query', return_value=mock_results):
            result = await list_company_api_keys(company_id)
            
            assert len(result) == 2
            assert all(isinstance(key, APIKey) for key in result)
            assert result[0].name == 'Key 1'
            assert result[1].name == 'Key 2'
    
    @pytest.mark.asyncio
    async def test_list_company_api_keys_empty_company_id(self):
        """Test listing API keys with empty company ID"""
        result = await list_company_api_keys("")
        assert result == []
    
    @pytest.mark.asyncio
    async def test_list_company_api_keys_no_results(self):
        """Test listing API keys when no keys exist"""
        company_id = str(uuid4())
        
        with patch('app.services.auth.DatabaseUtils.execute_query', return_value=[]):
            result = await list_company_api_keys(company_id)
            assert result == []

class TestPerformanceTracking:
    """Test suite for performance tracking functionality"""
    
    def test_get_auth_performance_stats_initial(self):
        """Test getting performance stats when no operations performed"""
        reset_auth_performance_stats()
        stats = get_auth_performance_stats()
        
        expected_keys = [
            'total_validations', 'cache_hits', 'cache_misses',
            'cache_hit_rate', 'db_queries', 'validation_errors', 'error_rate'
        ]
        
        for key in expected_keys:
            assert key in stats
        
        assert stats['total_validations'] == 0
        assert stats['cache_hit_rate'] == 0
        assert stats['error_rate'] == 0
    
    def test_reset_auth_performance_stats(self):
        """Test resetting performance statistics"""
        # Manually modify stats
        from app.services.auth import _performance_stats
        _performance_stats['cache_hits'] = 10
        _performance_stats['db_queries'] = 5
        
        # Reset and verify
        reset_auth_performance_stats()
        stats = get_auth_performance_stats()
        
        assert stats['total_validations'] == 0
        assert stats['cache_hits'] == 0
        assert stats['db_queries'] == 0

class TestEdgeCases:
    """Test suite for edge cases and error conditions"""
    
    @pytest.mark.asyncio
    async def test_validate_api_key_exception_handling(self):
        """Test API key validation when database throws exception"""
        api_key = "als_test_key"
        
        with patch('app.services.auth.get_cached_company', return_value=None):
            with patch('app.services.auth.DatabaseUtils.execute_query', side_effect=Exception("DB Error")):
                with patch('app.services.auth.hash_api_key', return_value='mock_hash'):
                    
                    result = await validate_api_key(api_key)
                    assert result is None
    
    @pytest.mark.asyncio
    async def test_generate_api_key_database_error(self):
        """Test API key generation when database operation fails"""
        company_id = str(uuid4())
        
        with patch('app.services.auth.DatabaseUtils.execute_query', side_effect=Exception("DB Error")):
            with patch('app.services.auth.generate_secure_api_key', return_value='als_mock_key'):
                with patch('app.services.auth.hash_api_key', return_value='mock_hash'):
                    
                    with pytest.raises(Exception):
                        await generate_api_key(company_id, "Test Key")
    
    def test_hash_api_key_with_special_characters(self):
        """Test hashing API keys with special characters"""
        special_key = "als_key_with_@#$%^&*()_+={[}]|\\:;\"'<,>.?/"
        
        with patch('app.services.auth._get_api_key_salt', return_value=b'test_salt'):
            hash_result = hash_api_key(special_key)
            assert isinstance(hash_result, str)
            assert len(hash_result) == 64

class TestSecurityFeatures:
    """Test suite for security-related functionality"""
    
    def test_api_key_salt_handling(self):
        """Test API key salt handling"""
        from app.services.auth import _get_api_key_salt
        
        # Test with mock settings
        with patch('app.services.auth.settings.API_KEY_SALT', 'test_salt_123'):
            salt = _get_api_key_salt()
            assert salt == b'test_salt_123'
    
    def test_pbkdf2_security_parameters(self):
        """Test that PBKDF2 uses secure parameters"""
        api_key = "als_test_key"
        
        with patch('app.services.auth._get_api_key_salt', return_value=b'test_salt'):
            with patch('hashlib.pbkdf2_hmac') as mock_pbkdf2:
                mock_pbkdf2.return_value = b'mock_hash'
                
                hash_api_key(api_key)
                
                # Verify PBKDF2 called with secure parameters
                mock_pbkdf2.assert_called_once_with(
                    'sha256',
                    api_key.encode('utf-8'),
                    b'test_salt',
                    100000  # 100k iterations
                )
    
    def test_api_key_generation_entropy(self):
        """Test that API key generation uses sufficient entropy"""
        with patch('secrets.token_bytes') as mock_token_bytes:
            with patch('secrets.token_urlsafe') as mock_token_urlsafe:
                mock_token_urlsafe.return_value = 'A' * 43  # Mock 43-char string
                
                api_key = generate_secure_api_key()
                
                # Verify 32 bytes (256 bits) of entropy requested
                mock_token_bytes.assert_called_once_with(32)
                mock_token_urlsafe.assert_called_once_with(32)
                
                assert api_key == f"{API_KEY_PREFIX}{'A' * 43}"

if __name__ == "__main__":
    pytest.main([__file__, "-v"])
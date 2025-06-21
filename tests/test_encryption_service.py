"""
Comprehensive test suite for the BYOK Vault Service (2.4)
Tests all encryption functions and enterprise-grade security features
"""
import pytest
import asyncio
import base64
import hashlib
from unittest.mock import AsyncMock, patch, MagicMock
from uuid import uuid4

from app.services.encryption import (
    derive_company_key,
    encrypt_vendor_key,
    decrypt_vendor_key,
    store_vendor_key,
    get_vendor_key,
    list_vendor_keys,
    delete_vendor_key,
    rotate_vendor_key,
    EncryptionService,
    EncryptionError,
    KeyValidationError,
    _validate_vendor_key,
    get_encryption_performance_stats,
    reset_encryption_performance_stats
)

class TestEncryptionFunctions:
    """Test suite for 2.4.1 Encryption Functions requirements"""
    
    def test_derive_company_key_signature_and_functionality(self):
        """Test derive_company_key(company_id: str) -> bytes"""
        company_id = str(uuid4())
        
        with patch('app.services.encryption.settings') as mock_settings:
            mock_settings.MASTER_ENCRYPTION_KEY = "test_master_key_that_is_long_enough_for_testing"
            
            result = derive_company_key(company_id)
            
            # Should return bytes (32 bytes for AES-256)
            assert isinstance(result, bytes)
            assert len(result) == 32
            
            # Same company_id should produce same key (deterministic)
            result2 = derive_company_key(company_id)
            assert result == result2
            
            # Different company_id should produce different key
            different_company_id = str(uuid4())
            result3 = derive_company_key(different_company_id)
            assert result != result3
    
    @pytest.mark.asyncio
    async def test_encrypt_vendor_key_signature_and_functionality(self):
        """Test encrypt_vendor_key(company_id: str, vendor_key: str) -> str"""
        company_id = str(uuid4())
        vendor_key = "sk-test123456789012345678901234567890123456789012345678"
        
        with patch('app.services.encryption.settings') as mock_settings:
            mock_settings.MASTER_ENCRYPTION_KEY = "test_master_key_that_is_long_enough_for_testing"
            
            result = await encrypt_vendor_key(company_id, vendor_key)
            
            # Should return base64 encoded string
            assert isinstance(result, str)
            
            # Should be valid base64
            decoded = base64.b64decode(result.encode('utf-8'))
            assert len(decoded) > 0
            
            # Should be different each time (due to random IV)
            result2 = await encrypt_vendor_key(company_id, vendor_key)
            assert result != result2
    
    @pytest.mark.asyncio
    async def test_decrypt_vendor_key_signature_and_functionality(self):
        """Test decrypt_vendor_key(company_id: str, encrypted_key: str) -> str"""
        company_id = str(uuid4())
        original_key = "sk-test123456789012345678901234567890123456789012345678"
        
        with patch('app.services.encryption.settings') as mock_settings:
            mock_settings.MASTER_ENCRYPTION_KEY = "test_master_key_that_is_long_enough_for_testing"
            
            # Encrypt then decrypt
            encrypted = await encrypt_vendor_key(company_id, original_key)
            decrypted = await decrypt_vendor_key(company_id, encrypted)
            
            # Should match original
            assert decrypted == original_key
            assert isinstance(decrypted, str)
    
    @pytest.mark.asyncio
    async def test_store_vendor_key_signature_and_functionality(self):
        """Test store_vendor_key(company_id: str, vendor: str, key: str) -> bool"""
        company_id = str(uuid4())
        vendor = "openai"
        vendor_key = "sk-test123456789012345678901234567890123456789012345678"
        
        mock_company_result = {
            'schema_name': 'test_company_schema'
        }
        
        with patch('app.services.encryption.settings') as mock_settings:
            mock_settings.MASTER_ENCRYPTION_KEY = "test_master_key_that_is_long_enough_for_testing"
            mock_settings.REDIS_URL = "redis://localhost:6379/0"
            
            with patch('app.services.encryption.DatabaseUtils.execute_query') as mock_db:
                mock_db.side_effect = [mock_company_result, None]  # Company exists, insert succeeds
                
                with patch('app.services.encryption.EncryptionService._get_redis_client') as mock_redis_method:
                    mock_redis = AsyncMock()
                    mock_redis_method.return_value = mock_redis
                    
                    result = await store_vendor_key(company_id, vendor, vendor_key)
                    
                    assert result is True
                    assert isinstance(result, bool)
                    
                    # Verify database was called
                    assert mock_db.call_count == 2
                    
                    # Verify Redis was called
                    mock_redis.setex.assert_called_once()
    
    @pytest.mark.asyncio
    async def test_get_vendor_key_signature_and_functionality(self):
        """Test get_vendor_key(company_id: str, vendor: str) -> Optional[str]"""
        company_id = str(uuid4())
        vendor = "openai"
        original_key = "sk-test123456789012345678901234567890123456789012345678"
        
        # Mock encrypted key from database
        encrypted_key = "dGVzdF9lbmNyeXB0ZWRfa2V5X2RhdGE="  # Mock base64 encrypted data
        
        mock_company_result = {'schema_name': 'test_company_schema'}
        mock_key_result = {'encrypted_key': encrypted_key}
        
        with patch('app.services.encryption.settings') as mock_settings:
            mock_settings.MASTER_ENCRYPTION_KEY = "test_master_key_that_is_long_enough_for_testing"
            mock_settings.REDIS_URL = "redis://localhost:6379/0"
            
            with patch('app.services.encryption.DatabaseUtils.execute_query') as mock_db:
                mock_db.side_effect = [mock_company_result, mock_key_result]
                
                with patch('app.services.encryption.EncryptionService._get_redis_client') as mock_redis_method:
                    mock_redis = AsyncMock()
                    mock_redis.get.return_value = None  # Cache miss
                    mock_redis_method.return_value = mock_redis
                    
                    with patch('app.services.encryption.decrypt_vendor_key', return_value=original_key) as mock_decrypt:
                        result = await get_vendor_key(company_id, vendor)
                        
                        assert result == original_key
                        assert isinstance(result, str)
                        
                        # Verify decrypt was called with correct parameters
                        mock_decrypt.assert_called_once_with(company_id, encrypted_key)
    
    @pytest.mark.asyncio
    async def test_get_vendor_key_not_found(self):
        """Test get_vendor_key returns None when key doesn't exist"""
        company_id = str(uuid4())
        vendor = "nonexistent"
        
        mock_company_result = {'schema_name': 'test_company_schema'}
        
        with patch('app.services.encryption.settings') as mock_settings:
            mock_settings.MASTER_ENCRYPTION_KEY = "test_master_key_that_is_long_enough_for_testing"
            mock_settings.REDIS_URL = "redis://localhost:6379/0"
            
            with patch('app.services.encryption.DatabaseUtils.execute_query') as mock_db:
                mock_db.side_effect = [mock_company_result, None]  # Company exists, key doesn't
                
                with patch('app.services.encryption.EncryptionService._get_redis_client') as mock_redis_method:
                    mock_redis = AsyncMock()
                    mock_redis.get.return_value = None  # Cache miss
                    mock_redis_method.return_value = mock_redis
                    
                    result = await get_vendor_key(company_id, vendor)
                    
                    assert result is None

class TestVendorKeyValidation:
    """Test suite for vendor key validation"""
    
    def test_validate_openai_key_valid(self):
        """Test valid OpenAI key format"""
        valid_key = "sk-" + "a" * 48
        assert _validate_vendor_key("openai", valid_key) is True
    
    def test_validate_openai_key_invalid(self):
        """Test invalid OpenAI key format"""
        invalid_key = "invalid_key"
        assert _validate_vendor_key("openai", invalid_key) is False
    
    def test_validate_anthropic_key_valid(self):
        """Test valid Anthropic key format"""
        valid_key = "sk-ant-api03-" + "a" * 95
        assert _validate_vendor_key("anthropic", valid_key) is True
    
    def test_validate_anthropic_key_invalid(self):
        """Test invalid Anthropic key format"""
        invalid_key = "sk-ant-api03-short"
        assert _validate_vendor_key("anthropic", invalid_key) is False
    
    def test_validate_unknown_vendor(self):
        """Test unknown vendor allows any key (with warning)"""
        unknown_key = "any_format_key"
        assert _validate_vendor_key("unknown_vendor", unknown_key) is True

class TestKeyRotation:
    """Test suite for key rotation functionality"""
    
    @pytest.mark.asyncio
    async def test_rotate_vendor_key_success(self):
        """Test successful key rotation"""
        company_id = str(uuid4())
        vendor = "openai"
        new_key = "sk-" + "b" * 48
        
        with patch('app.services.encryption.store_vendor_key', return_value=True) as mock_store:
            result = await rotate_vendor_key(company_id, vendor, new_key)
            
            assert result is True
            mock_store.assert_called_once_with(company_id, vendor, new_key)
    
    @pytest.mark.asyncio
    async def test_rotate_vendor_key_invalid_format(self):
        """Test key rotation with invalid key format"""
        company_id = str(uuid4())
        vendor = "openai"
        invalid_key = "invalid_format"
        
        with pytest.raises(EncryptionError):  # rotate_vendor_key wraps KeyValidationError in EncryptionError
            await rotate_vendor_key(company_id, vendor, invalid_key)

class TestListAndDeleteOperations:
    """Test suite for list and delete operations"""
    
    @pytest.mark.asyncio
    async def test_list_vendor_keys_success(self):
        """Test successful vendor key listing"""
        company_id = str(uuid4())
        
        from datetime import datetime
        
        mock_company_result = {'schema_name': 'test_company_schema'}
        mock_keys_result = [
            {
                'vendor': 'openai',
                'is_active': True,
                'created_at': datetime(2024, 1, 1),  # Use datetime objects, not strings
                'updated_at': datetime(2024, 1, 1)
            }
        ]
        
        with patch('app.services.encryption.DatabaseUtils.execute_query') as mock_db:
            mock_db.side_effect = [mock_company_result, mock_keys_result]
            
            result = await list_vendor_keys(company_id)
            
            assert len(result) == 1
            assert result[0]['vendor'] == 'openai'
            assert result[0]['is_active'] is True
    
    @pytest.mark.asyncio
    async def test_delete_vendor_key_success(self):
        """Test successful vendor key deletion"""
        company_id = str(uuid4())
        vendor = "openai"
        
        mock_company_result = {'schema_name': 'test_company_schema'}
        
        with patch('app.services.encryption.DatabaseUtils.execute_query') as mock_db:
            mock_db.side_effect = [mock_company_result, None]  # Company exists, delete succeeds
            
            with patch('app.services.encryption.EncryptionService._get_redis_client') as mock_redis_method:
                mock_redis = AsyncMock()
                mock_redis_method.return_value = mock_redis
                
                result = await delete_vendor_key(company_id, vendor)
                
                assert result is True
                mock_redis.delete.assert_called_once()

class TestEncryptionServiceClass:
    """Test suite for EncryptionService class"""
    
    def test_encryption_service_initialization(self):
        """Test EncryptionService initialization"""
        with patch('app.services.encryption.settings') as mock_settings:
            mock_settings.MASTER_ENCRYPTION_KEY = "test_master_key_that_is_long_enough_for_testing"
            
            service = EncryptionService()
            
            assert service._redis_client is None
            assert len(service._master_key) == 32
    
    def test_encryption_service_master_key_error(self):
        """Test EncryptionService raises error when master key not configured"""
        with patch('app.services.encryption.settings') as mock_settings:
            mock_settings.MASTER_ENCRYPTION_KEY = ""
            
            with pytest.raises(EncryptionError):
                EncryptionService()
    
    def test_vendor_key_patterns_coverage(self):
        """Test vendor key patterns cover major providers"""
        patterns = EncryptionService.VENDOR_KEY_PATTERNS
        
        expected_vendors = [
            'openai', 'anthropic', 'google', 'azure', 'cohere',
            'together', 'perplexity', 'mistral', 'groq', 'fireworks'
        ]
        
        for vendor in expected_vendors:
            assert vendor in patterns

class TestErrorHandling:
    """Test suite for error handling"""
    
    @pytest.mark.asyncio
    async def test_store_vendor_key_invalid_format(self):
        """Test storing vendor key with invalid format raises error"""
        company_id = str(uuid4())
        vendor = "openai"
        invalid_key = "invalid_format"
        
        with pytest.raises(KeyValidationError):
            await store_vendor_key(company_id, vendor, invalid_key)
    
    @pytest.mark.asyncio
    async def test_store_vendor_key_company_not_found(self):
        """Test storing vendor key when company doesn't exist"""
        company_id = str(uuid4())
        vendor = "openai"
        vendor_key = "sk-" + "a" * 48
        
        with patch('app.services.encryption.settings') as mock_settings:
            mock_settings.MASTER_ENCRYPTION_KEY = "test_master_key_that_is_long_enough_for_testing"
            
            with patch('app.services.encryption.DatabaseUtils.execute_query', return_value=None):
                with pytest.raises(EncryptionError, match="Company not found"):
                    await store_vendor_key(company_id, vendor, vendor_key)
    
    def test_derive_company_key_error_handling(self):
        """Test derive_company_key error handling"""
        with patch('app.services.encryption.EncryptionService') as mock_service_class:
            mock_service_class.side_effect = Exception("Test error")
            
            with pytest.raises(EncryptionError):
                derive_company_key(str(uuid4()))

class TestPerformanceMonitoring:
    """Test suite for performance monitoring"""
    
    def test_get_performance_stats(self):
        """Test getting performance statistics"""
        stats = get_encryption_performance_stats()
        
        expected_keys = [
            'keys_encrypted', 'keys_decrypted', 'keys_stored',
            'keys_retrieved', 'cache_hits', 'cache_misses', 'validation_failures'
        ]
        
        for key in expected_keys:
            assert key in stats
            assert isinstance(stats[key], int)
    
    def test_reset_performance_stats(self):
        """Test resetting performance statistics"""
        reset_encryption_performance_stats()
        stats = get_encryption_performance_stats()
        
        for value in stats.values():
            assert value == 0

class TestFunctionSignatures:
    """Test that all functions have the correct signatures as per 2.4.1 requirements"""
    
    def test_function_signatures_match_requirements(self):
        """Verify function signatures match 2.4.1 Encryption Functions requirements"""
        import inspect
        
        # Check derive_company_key signature
        sig = inspect.signature(derive_company_key)
        assert 'company_id' in sig.parameters
        assert sig.parameters['company_id'].annotation == str
        assert sig.return_annotation == bytes
        
        # Check encrypt_vendor_key signature
        sig = inspect.signature(encrypt_vendor_key)
        assert 'company_id' in sig.parameters
        assert 'vendor_key' in sig.parameters
        assert sig.parameters['company_id'].annotation == str
        assert sig.parameters['vendor_key'].annotation == str
        assert sig.return_annotation == str
        
        # Check decrypt_vendor_key signature
        sig = inspect.signature(decrypt_vendor_key)
        assert 'company_id' in sig.parameters
        assert 'encrypted_key' in sig.parameters
        assert sig.parameters['company_id'].annotation == str
        assert sig.parameters['encrypted_key'].annotation == str
        assert sig.return_annotation == str
        
        # Check store_vendor_key signature
        sig = inspect.signature(store_vendor_key)
        assert 'company_id' in sig.parameters
        assert 'vendor' in sig.parameters
        assert 'key' in sig.parameters
        assert sig.parameters['company_id'].annotation == str
        assert sig.parameters['vendor'].annotation == str
        assert sig.parameters['key'].annotation == str
        assert sig.return_annotation == bool
        
        # Check get_vendor_key signature
        sig = inspect.signature(get_vendor_key)
        assert 'company_id' in sig.parameters
        assert 'vendor' in sig.parameters
        assert sig.parameters['company_id'].annotation == str
        assert sig.parameters['vendor'].annotation == str

if __name__ == "__main__":
    pytest.main([__file__, "-v"])
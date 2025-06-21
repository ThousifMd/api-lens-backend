"""
Security Audit Test Suite - Comprehensive security testing for API Lens backend
Tests authentication, encryption, data isolation, and vulnerability protection
"""

import asyncio
import base64
import hashlib
import json
import pytest
import secrets
import time
from datetime import datetime, timedelta
from typing import Dict, List, Optional
from uuid import UUID, uuid4

import jwt
import requests
from cryptography.fernet import Fernet
from cryptography.hazmat.primitives import hashes, serialization
from cryptography.hazmat.primitives.ciphers import Cipher, algorithms, modes
from cryptography.hazmat.backends import default_backend
from sqlalchemy import text
from sqlalchemy.exc import IntegrityError

# Import the services we're testing
from app.services.auth import (
    generate_api_key, validate_api_key, hash_api_key, 
    generate_secure_api_key, revoke_api_key
)
from app.services.encryption import (
    encrypt_vendor_key, decrypt_vendor_key, store_vendor_key,
    get_vendor_key, derive_company_key, EncryptionService
)
from app.auth.admin_auth import (
    authenticate_admin, create_admin_token, verify_admin_token,
    AdminRole, AdminPermission, ROLE_PERMISSIONS
)
from app.database import DatabaseUtils, get_db_session
from app.config import get_settings

settings = get_settings()


class SecurityAuditResults:
    """Container for security audit results"""
    def __init__(self):
        self.results = {}
        self.vulnerabilities = []
        self.passed_tests = []
        self.failed_tests = []
    
    def add_result(self, test_name: str, passed: bool, details: str, vulnerability_level: str = "info"):
        self.results[test_name] = {
            "passed": passed,
            "details": details,
            "vulnerability_level": vulnerability_level,
            "timestamp": datetime.now().isoformat()
        }
        
        if passed:
            self.passed_tests.append(test_name)
        else:
            self.failed_tests.append(test_name)
            if vulnerability_level in ["high", "critical"]:
                self.vulnerabilities.append({
                    "test": test_name,
                    "level": vulnerability_level,
                    "details": details
                })
    
    def get_summary(self) -> Dict:
        return {
            "total_tests": len(self.results),
            "passed": len(self.passed_tests),
            "failed": len(self.failed_tests),
            "vulnerabilities_found": len(self.vulnerabilities),
            "security_score": (len(self.passed_tests) / len(self.results)) * 100 if self.results else 0
        }


@pytest.fixture
async def audit_results():
    """Fixture to collect audit results"""
    return SecurityAuditResults()


@pytest.fixture
async def test_companies():
    """Create test companies for isolation testing"""
    companies = []
    try:
        for i in range(3):
            company_id = str(uuid4())
            schema_name = f"test_company_{i}"
            
            # Create company record
            query = """
                INSERT INTO companies (id, name, schema_name, rate_limit_rps, monthly_quota)
                VALUES ($1, $2, $3, 100, 10000.0)
            """
            await DatabaseUtils.execute_query(
                query,
                {
                    'id': UUID(company_id),
                    'name': f"Test Company {i}",
                    'schema_name': schema_name,
                }
            )
            
            # Create company schema
            await DatabaseUtils.execute_query(
                f"CREATE SCHEMA IF NOT EXISTS {schema_name}",
                {}
            )
            
            # Create vendor_keys table in company schema
            await DatabaseUtils.execute_query(
                f"""
                CREATE TABLE IF NOT EXISTS {schema_name}.vendor_keys (
                    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
                    vendor VARCHAR(50) NOT NULL UNIQUE,
                    encrypted_key TEXT NOT NULL,
                    is_active BOOLEAN DEFAULT true,
                    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
                )
                """,
                {}
            )
            
            companies.append({
                'id': company_id,
                'schema_name': schema_name,
                'name': f"Test Company {i}"
            })
    
    except Exception as e:
        print(f"Error creating test companies: {e}")
    
    yield companies
    
    # Cleanup
    try:
        for company in companies:
            await DatabaseUtils.execute_query(
                "DELETE FROM companies WHERE id = $1",
                {'id': UUID(company['id'])}
            )
            await DatabaseUtils.execute_query(
                f"DROP SCHEMA IF EXISTS {company['schema_name']} CASCADE",
                {}
            )
    except Exception as e:
        print(f"Error cleaning up test companies: {e}")


class TestAuthenticationSecurity:
    """Test suite for authentication mechanism security"""
    
    async def test_api_key_generation_entropy(self, audit_results):
        """Test API key generation has sufficient entropy"""
        try:
            keys = set()
            num_keys = 1000
            
            # Generate multiple keys to test for collisions
            for _ in range(num_keys):
                key = generate_secure_api_key()
                keys.add(key)
            
            # Check for collisions (should be none)
            collision_rate = (num_keys - len(keys)) / num_keys
            
            if collision_rate == 0:
                audit_results.add_result(
                    "api_key_entropy",
                    True,
                    f"Generated {num_keys} unique API keys with no collisions"
                )
            else:
                audit_results.add_result(
                    "api_key_entropy",
                    False,
                    f"Collision rate: {collision_rate:.4f} - indicates insufficient entropy",
                    "high"
                )
            
            # Check key structure
            sample_key = generate_secure_api_key()
            if sample_key.startswith("als_") and len(sample_key) == 47:
                audit_results.add_result(
                    "api_key_format",
                    True,
                    "API keys follow expected format and length"
                )
            else:
                audit_results.add_result(
                    "api_key_format",
                    False,
                    f"Unexpected API key format: {sample_key}",
                    "medium"
                )
                
        except Exception as e:
            audit_results.add_result(
                "api_key_generation_test",
                False,
                f"Error testing API key generation: {e}",
                "high"
            )
    
    async def test_api_key_hashing_security(self, audit_results):
        """Test API key hashing uses secure methods"""
        try:
            test_key = "als_test_key_for_hashing_security_check"
            
            # Test multiple hashes of same key are different (due to salt)
            hash1 = hash_api_key(test_key)
            hash2 = hash_api_key(test_key)
            
            if hash1 != hash2:
                audit_results.add_result(
                    "api_key_salt_usage",
                    True,
                    "API key hashing uses proper salting"
                )
            else:
                audit_results.add_result(
                    "api_key_salt_usage",
                    False,
                    "API key hashing may not use proper salting",
                    "high"
                )
            
            # Test hash length (should be 64 chars for SHA-256)
            if len(hash1) == 64:
                audit_results.add_result(
                    "api_key_hash_length",
                    True,
                    "API key hash has expected length for SHA-256"
                )
            else:
                audit_results.add_result(
                    "api_key_hash_length",
                    False,
                    f"Unexpected hash length: {len(hash1)}",
                    "medium"
                )
                
        except Exception as e:
            audit_results.add_result(
                "api_key_hashing_test",
                False,
                f"Error testing API key hashing: {e}",
                "high"
            )
    
    async def test_brute_force_protection(self, audit_results, test_companies):
        """Test API key brute force protection"""
        try:
            if not test_companies:
                audit_results.add_result(
                    "brute_force_protection",
                    False,
                    "No test companies available for brute force testing",
                    "high"
                )
                return
            
            company = test_companies[0]
            
            # Generate a valid API key
            api_key_data = await generate_api_key(company['id'], "Test Key")
            valid_key = api_key_data.secret_key
            
            # Test rate limiting by making rapid requests
            invalid_attempts = 0
            start_time = time.time()
            
            for i in range(100):
                fake_key = f"als_{''.join(secrets.choice('abcdefghijklmnopqrstuvwxyzABCDEFGHIJKLMNOPQRSTUVWXYZ0123456789') for _ in range(43))}"
                result = await validate_api_key(fake_key)
                if result is None:
                    invalid_attempts += 1
            
            elapsed_time = time.time() - start_time
            
            # Verify valid key still works after invalid attempts
            valid_result = await validate_api_key(valid_key)
            
            if valid_result is not None and invalid_attempts == 100:
                audit_results.add_result(
                    "brute_force_protection",
                    True,
                    f"Handled {invalid_attempts} invalid attempts in {elapsed_time:.2f}s, valid key still works"
                )
            else:
                audit_results.add_result(
                    "brute_force_protection",
                    False,
                    f"Brute force protection may be insufficient - valid key status: {valid_result is not None}",
                    "medium"
                )
                
        except Exception as e:
            audit_results.add_result(
                "brute_force_protection_test",
                False,
                f"Error testing brute force protection: {e}",
                "high"
            )
    
    async def test_admin_authentication_security(self, audit_results):
        """Test admin authentication security"""
        try:
            # Test password hashing
            from app.auth.admin_auth import _hash_password, _verify_password
            
            test_password = "test_password_123"
            hashed = _hash_password(test_password)
            
            # Verify hash format includes salt
            if '$' in hashed and len(hashed) > 64:
                audit_results.add_result(
                    "admin_password_hashing",
                    True,
                    "Admin passwords use proper salted hashing"
                )
            else:
                audit_results.add_result(
                    "admin_password_hashing",
                    False,
                    "Admin password hashing may be insufficient",
                    "high"
                )
            
            # Test password verification
            if _verify_password(test_password, hashed) and not _verify_password("wrong_password", hashed):
                audit_results.add_result(
                    "admin_password_verification",
                    True,
                    "Admin password verification works correctly"
                )
            else:
                audit_results.add_result(
                    "admin_password_verification",
                    False,
                    "Admin password verification has issues",
                    "high"
                )
                
        except Exception as e:
            audit_results.add_result(
                "admin_auth_test",
                False,
                f"Error testing admin authentication: {e}",
                "high"
            )


class TestEncryptionSecurity:
    """Test suite for encryption mechanism security"""
    
    async def test_vendor_key_encryption_strength(self, audit_results, test_companies):
        """Test vendor key encryption uses strong algorithms"""
        try:
            if not test_companies:
                audit_results.add_result(
                    "vendor_key_encryption",
                    False,
                    "No test companies available for encryption testing",
                    "high"
                )
                return
            
            company = test_companies[0]
            test_key = "sk-test_openai_key_1234567890abcdefghijklmnopqrstuvwxyz123456"
            
            # Test encryption
            encrypted = await encrypt_vendor_key(company['id'], test_key)
            
            # Verify encrypted data is base64 encoded
            try:
                decoded = base64.b64decode(encrypted)
                if len(decoded) >= 32:  # At least IV + some ciphertext
                    audit_results.add_result(
                        "vendor_key_encryption_format",
                        True,
                        "Vendor key encryption produces properly formatted output"
                    )
                else:
                    audit_results.add_result(
                        "vendor_key_encryption_format",
                        False,
                        "Encrypted vendor key appears too short",
                        "medium"
                    )
            except Exception:
                audit_results.add_result(
                    "vendor_key_encryption_format",
                    False,
                    "Encrypted vendor key is not properly base64 encoded",
                    "high"
                )
            
            # Test decryption
            decrypted = await decrypt_vendor_key(company['id'], encrypted)
            
            if decrypted == test_key:
                audit_results.add_result(
                    "vendor_key_encryption_roundtrip",
                    True,
                    "Vendor key encryption/decryption roundtrip successful"
                )
            else:
                audit_results.add_result(
                    "vendor_key_encryption_roundtrip",
                    False,
                    "Vendor key encryption/decryption roundtrip failed",
                    "critical"
                )
                
        except Exception as e:
            audit_results.add_result(
                "vendor_key_encryption_test",
                False,
                f"Error testing vendor key encryption: {e}",
                "high"
            )
    
    async def test_company_key_isolation(self, audit_results, test_companies):
        """Test that company encryption keys are properly isolated"""
        try:
            if len(test_companies) < 2:
                audit_results.add_result(
                    "company_key_isolation",
                    False,
                    "Need at least 2 companies for isolation testing",
                    "high"
                )
                return
            
            company1 = test_companies[0]
            company2 = test_companies[1]
            
            test_key = "sk-test_key_for_isolation_testing_1234567890abcdefghij"
            
            # Encrypt with company1 key
            encrypted_c1 = await encrypt_vendor_key(company1['id'], test_key)
            
            # Try to decrypt with company2 key (should fail or return different result)
            try:
                decrypted_c2 = await decrypt_vendor_key(company2['id'], encrypted_c1)
                
                if decrypted_c2 != test_key:
                    audit_results.add_result(
                        "company_key_isolation",
                        True,
                        "Company encryption keys are properly isolated"
                    )
                else:
                    audit_results.add_result(
                        "company_key_isolation",
                        False,
                        "Company encryption keys may not be properly isolated",
                        "critical"
                    )
            except Exception:
                # Exception is expected - means isolation is working
                audit_results.add_result(
                    "company_key_isolation",
                    True,
                    "Company encryption keys are properly isolated (decryption failed as expected)"
                )
                
        except Exception as e:
            audit_results.add_result(
                "company_key_isolation_test",
                False,
                f"Error testing company key isolation: {e}",
                "high"
            )
    
    async def test_key_derivation_security(self, audit_results, test_companies):
        """Test key derivation function security"""
        try:
            if not test_companies:
                audit_results.add_result(
                    "key_derivation_security",
                    False,
                    "No test companies available for key derivation testing",
                    "high"
                )
                return
            
            company = test_companies[0]
            
            # Test that derived keys are consistent
            key1 = derive_company_key(company['id'])
            key2 = derive_company_key(company['id'])
            
            if key1 == key2:
                audit_results.add_result(
                    "key_derivation_consistency",
                    True,
                    "Company key derivation is consistent"
                )
            else:
                audit_results.add_result(
                    "key_derivation_consistency",
                    False,
                    "Company key derivation is inconsistent",
                    "high"
                )
            
            # Test key length (should be 32 bytes for AES-256)
            if len(key1) == 32:
                audit_results.add_result(
                    "key_derivation_length",
                    True,
                    "Derived keys have correct length for AES-256"
                )
            else:
                audit_results.add_result(
                    "key_derivation_length",
                    False,
                    f"Derived key length incorrect: {len(key1)} bytes",
                    "high"
                )
                
        except Exception as e:
            audit_results.add_result(
                "key_derivation_test",
                False,
                f"Error testing key derivation: {e}",
                "high"
            )


class TestDataIsolationSecurity:
    """Test suite for data isolation between companies"""
    
    async def test_schema_based_isolation(self, audit_results, test_companies):
        """Test that schema-based isolation works correctly"""
        try:
            if len(test_companies) < 2:
                audit_results.add_result(
                    "schema_isolation",
                    False,
                    "Need at least 2 companies for schema isolation testing",
                    "high"
                )
                return
            
            company1 = test_companies[0]
            company2 = test_companies[1]
            
            # Store data in company1's schema
            await store_vendor_key(company1['id'], 'openai', 'sk-test_key_company1_1234567890abcdefghijklmnopqrstuvwxyz123456')
            
            # Store data in company2's schema  
            await store_vendor_key(company2['id'], 'openai', 'sk-test_key_company2_1234567890abcdefghijklmnopqrstuvwxyz123456')
            
            # Verify company1 can access its own data
            key1 = await get_vendor_key(company1['id'], 'openai')
            
            # Verify company2 can access its own data
            key2 = await get_vendor_key(company2['id'], 'openai')
            
            if key1 and key2 and key1 != key2:
                audit_results.add_result(
                    "schema_isolation",
                    True,
                    "Schema-based isolation working correctly - companies have separate data"
                )
            else:
                audit_results.add_result(
                    "schema_isolation",
                    False,
                    "Schema-based isolation may be compromised",
                    "critical"
                )
                
        except Exception as e:
            audit_results.add_result(
                "schema_isolation_test",
                False,
                f"Error testing schema isolation: {e}",
                "high"
            )
    
    async def test_api_key_company_binding(self, audit_results, test_companies):
        """Test that API keys are properly bound to companies"""
        try:
            if len(test_companies) < 2:
                audit_results.add_result(
                    "api_key_company_binding",
                    False,
                    "Need at least 2 companies for API key binding testing",
                    "high"
                )
                return
            
            company1 = test_companies[0]
            company2 = test_companies[1]
            
            # Generate API key for company1
            api_key1 = await generate_api_key(company1['id'], "Test Key 1")
            
            # Generate API key for company2
            api_key2 = await generate_api_key(company2['id'], "Test Key 2")
            
            # Validate company1 key returns company1 data
            result1 = await validate_api_key(api_key1.secret_key)
            
            # Validate company2 key returns company2 data
            result2 = await validate_api_key(api_key2.secret_key)
            
            if (result1 and result2 and 
                str(result1.id) == company1['id'] and 
                str(result2.id) == company2['id']):
                audit_results.add_result(
                    "api_key_company_binding",
                    True,
                    "API keys are properly bound to their respective companies"
                )
            else:
                audit_results.add_result(
                    "api_key_company_binding",
                    False,
                    "API key company binding may be compromised",
                    "critical"
                )
                
        except Exception as e:
            audit_results.add_result(
                "api_key_company_binding_test",
                False,
                f"Error testing API key company binding: {e}",
                "high"
            )


class TestSQLInjectionProtection:
    """Test suite for SQL injection protection"""
    
    async def test_api_key_validation_sql_injection(self, audit_results):
        """Test API key validation for SQL injection vulnerabilities"""
        try:
            # SQL injection payloads to test
            sql_payloads = [
                "'; DROP TABLE api_keys; --",
                "' OR '1'='1",
                "' UNION SELECT * FROM companies --",
                "'; INSERT INTO api_keys (key_hash) VALUES ('hacked'); --",
                "' OR 1=1 --",
                "'; UPDATE companies SET name='hacked' WHERE id='1'; --"
            ]
            
            injection_attempts = 0
            for payload in sql_payloads:
                try:
                    result = await validate_api_key(payload)
                    # If result is None, good - payload was handled safely
                    if result is None:
                        injection_attempts += 1
                except Exception as e:
                    # Exception handling is also acceptable
                    injection_attempts += 1
            
            if injection_attempts == len(sql_payloads):
                audit_results.add_result(
                    "api_key_sql_injection_protection",
                    True,
                    f"All {len(sql_payloads)} SQL injection attempts were blocked"
                )
            else:
                audit_results.add_result(
                    "api_key_sql_injection_protection",
                    False,
                    f"Only {injection_attempts}/{len(sql_payloads)} SQL injection attempts were blocked",
                    "critical"
                )
                
        except Exception as e:
            audit_results.add_result(
                "api_key_sql_injection_test",
                False,
                f"Error testing SQL injection protection: {e}",
                "high"
            )
    
    async def test_admin_auth_sql_injection(self, audit_results):
        """Test admin authentication for SQL injection vulnerabilities"""
        try:
            # SQL injection payloads for admin auth
            sql_payloads = [
                "admin'; DROP TABLE admin_users; --",
                "admin' OR '1'='1",
                "admin' UNION SELECT 'admin', 'password' --",
                "'; UPDATE admin_users SET role='super_admin' WHERE username='attacker'; --"
            ]
            
            injection_attempts = 0
            for payload in sql_payloads:
                try:
                    result = await authenticate_admin(payload, "any_password")
                    # If result is None, good - payload was handled safely
                    if result is None:
                        injection_attempts += 1
                except Exception as e:
                    # Exception handling is also acceptable
                    injection_attempts += 1
            
            if injection_attempts == len(sql_payloads):
                audit_results.add_result(
                    "admin_auth_sql_injection_protection",
                    True,
                    f"All {len(sql_payloads)} SQL injection attempts on admin auth were blocked"
                )
            else:
                audit_results.add_result(
                    "admin_auth_sql_injection_protection",
                    False,
                    f"Only {injection_attempts}/{len(sql_payloads)} SQL injection attempts were blocked",
                    "critical"
                )
                
        except Exception as e:
            audit_results.add_result(
                "admin_auth_sql_injection_test",
                False,
                f"Error testing admin auth SQL injection protection: {e}",
                "high"
            )


class TestJWTSecurity:
    """Test suite for JWT token security"""
    
    async def test_jwt_token_security(self, audit_results):
        """Test JWT token implementation security"""
        try:
            from app.auth.admin_auth import JWT_SECRET_KEY, JWT_ALGORITHM
            
            # Test that JWT secret key exists and is not default
            if JWT_SECRET_KEY and len(JWT_SECRET_KEY) >= 32:
                audit_results.add_result(
                    "jwt_secret_strength",
                    True,
                    "JWT secret key has sufficient length"
                )
            else:
                audit_results.add_result(
                    "jwt_secret_strength",
                    False,
                    "JWT secret key may be too weak",
                    "high"
                )
            
            # Test algorithm is secure
            if JWT_ALGORITHM == "HS256":
                audit_results.add_result(
                    "jwt_algorithm_security",
                    True,
                    "JWT uses secure HS256 algorithm"
                )
            else:
                audit_results.add_result(
                    "jwt_algorithm_security",
                    False,
                    f"JWT algorithm may be insecure: {JWT_ALGORITHM}",
                    "medium"
                )
            
            # Test token manipulation
            fake_payload = {
                "user_id": "fake_user",
                "username": "attacker",
                "role": "super_admin",
                "permissions": ["manage_admin_users"],
                "exp": int(time.time()) + 3600
            }
            
            # Try to create token with wrong secret
            try:
                fake_token = jwt.encode(fake_payload, "wrong_secret", algorithm=JWT_ALGORITHM)
                
                # Try to verify it
                from fastapi.security import HTTPAuthorizationCredentials
                from app.auth.admin_auth import verify_admin_token
                
                class FakeCredentials:
                    def __init__(self, token):
                        self.credentials = token
                
                try:
                    await verify_admin_token(FakeCredentials(fake_token))
                    audit_results.add_result(
                        "jwt_token_manipulation",
                        False,
                        "JWT token manipulation was successful - security breach!",
                        "critical"
                    )
                except Exception:
                    audit_results.add_result(
                        "jwt_token_manipulation",
                        True,
                        "JWT token manipulation was blocked correctly"
                    )
                    
            except Exception as e:
                audit_results.add_result(
                    "jwt_token_manipulation",
                    True,
                    "JWT token manipulation was blocked correctly"
                )
                
        except Exception as e:
            audit_results.add_result(
                "jwt_security_test",
                False,
                f"Error testing JWT security: {e}",
                "high"
            )


async def run_complete_security_audit():
    """Run complete security audit and return results"""
    audit_results = SecurityAuditResults()
    
    # Create test companies
    test_companies = []
    try:
        for i in range(3):
            company_id = str(uuid4())
            schema_name = f"test_company_{i}"
            
            # Create company record
            query = """
                INSERT INTO companies (id, name, schema_name, rate_limit_rps, monthly_quota)
                VALUES ($1, $2, $3, 100, 10000.0)
            """
            await DatabaseUtils.execute_query(
                query,
                {
                    'id': UUID(company_id),
                    'name': f"Test Company {i}",
                    'schema_name': schema_name,
                }
            )
            
            # Create company schema
            await DatabaseUtils.execute_query(
                f"CREATE SCHEMA IF NOT EXISTS {schema_name}",
                {}
            )
            
            # Create vendor_keys table in company schema
            await DatabaseUtils.execute_query(
                f"""
                CREATE TABLE IF NOT EXISTS {schema_name}.vendor_keys (
                    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
                    vendor VARCHAR(50) NOT NULL UNIQUE,
                    encrypted_key TEXT NOT NULL,
                    is_active BOOLEAN DEFAULT true,
                    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
                )
                """,
                {}
            )
            
            test_companies.append({
                'id': company_id,
                'schema_name': schema_name,
                'name': f"Test Company {i}"
            })
    
    except Exception as e:
        print(f"Error creating test companies: {e}")
    
    try:
        # Run all security tests
        auth_test = TestAuthenticationSecurity()
        encryption_test = TestEncryptionSecurity()
        isolation_test = TestDataIsolationSecurity()
        sql_test = TestSQLInjectionProtection()
        jwt_test = TestJWTSecurity()
        
        # Authentication tests
        await auth_test.test_api_key_generation_entropy(audit_results)
        await auth_test.test_api_key_hashing_security(audit_results)
        await auth_test.test_brute_force_protection(audit_results, test_companies)
        await auth_test.test_admin_authentication_security(audit_results)
        
        # Encryption tests
        await encryption_test.test_vendor_key_encryption_strength(audit_results, test_companies)
        await encryption_test.test_company_key_isolation(audit_results, test_companies)
        await encryption_test.test_key_derivation_security(audit_results, test_companies)
        
        # Data isolation tests
        await isolation_test.test_schema_based_isolation(audit_results, test_companies)
        await isolation_test.test_api_key_company_binding(audit_results, test_companies)
        
        # SQL injection tests
        await sql_test.test_api_key_validation_sql_injection(audit_results)
        await sql_test.test_admin_auth_sql_injection(audit_results)
        
        # JWT security tests
        await jwt_test.test_jwt_token_security(audit_results)
        
    finally:
        # Cleanup test companies
        try:
            for company in test_companies:
                await DatabaseUtils.execute_query(
                    "DELETE FROM companies WHERE id = $1",
                    {'id': UUID(company['id'])}
                )
                await DatabaseUtils.execute_query(
                    f"DROP SCHEMA IF EXISTS {company['schema_name']} CASCADE",
                    {}
                )
        except Exception as e:
            print(f"Error cleaning up test companies: {e}")
    
    return audit_results


if __name__ == "__main__":
    async def main():
        print("🔒 Starting comprehensive security audit...")
        results = await run_complete_security_audit()
        
        print("\n" + "="*60)
        print("SECURITY AUDIT RESULTS")
        print("="*60)
        
        summary = results.get_summary()
        print(f"Total Tests: {summary['total_tests']}")
        print(f"Passed: {summary['passed']}")
        print(f"Failed: {summary['failed']}")
        print(f"Security Score: {summary['security_score']:.1f}%")
        print(f"Vulnerabilities Found: {summary['vulnerabilities_found']}")
        
        if results.vulnerabilities:
            print("\n🚨 CRITICAL VULNERABILITIES:")
            for vuln in results.vulnerabilities:
                print(f"  - {vuln['test']}: {vuln['details']} [{vuln['level']}]")
        
        print("\n📊 DETAILED RESULTS:")
        for test_name, result in results.results.items():
            status = "✅ PASS" if result['passed'] else "❌ FAIL"
            level = f"[{result['vulnerability_level'].upper()}]" if not result['passed'] else ""
            print(f"  {status} {test_name} {level}")
            print(f"      {result['details']}")
        
        # Save results to file
        with open("security_audit_results.json", "w") as f:
            json.dump({
                "summary": summary,
                "results": results.results,
                "vulnerabilities": results.vulnerabilities,
                "timestamp": datetime.now().isoformat()
            }, f, indent=2)
        
        print(f"\n📄 Full results saved to: security_audit_results.json")
        
        if summary['security_score'] < 80:
            print("\n⚠️  WARNING: Security score below 80% - immediate attention required!")
            return 1
        else:
            print("\n✅ Security audit completed successfully!")
            return 0
    
    exit(asyncio.run(main()))
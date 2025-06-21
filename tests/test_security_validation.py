"""
Security Validation Test - Quick validation of security testing framework
Tests that our security tests can run and detect basic issues
"""

import asyncio
import sys
from pathlib import Path
from typing import Dict, Any

# Add the parent directory to the Python path
sys.path.insert(0, str(Path(__file__).parent.parent))

from app.services.auth import hash_api_key, generate_secure_api_key
from app.services.encryption import derive_company_key


async def test_basic_security_functions():
    """Test basic security functions work correctly"""
    print("🔧 Testing basic security functions...")
    
    results = {
        "api_key_generation": False,
        "api_key_hashing": False,
        "key_derivation": False,
        "errors": []
    }
    
    try:
        # Test API key generation
        api_key = generate_secure_api_key()
        if api_key.startswith("als_") and len(api_key) == 47:
            results["api_key_generation"] = True
            print("✅ API key generation working")
        else:
            results["errors"].append(f"API key format incorrect: {api_key}")
            print("❌ API key generation failed")
    except Exception as e:
        results["errors"].append(f"API key generation error: {e}")
        print(f"❌ API key generation error: {e}")
    
    try:
        # Test API key hashing
        test_key = "als_test_key_1234567890abcdefghijklmnopqrstuvwxyz123"
        hash1 = hash_api_key(test_key)
        hash2 = hash_api_key(test_key)
        
        if len(hash1) == 64 and hash1 != hash2:  # Different due to salt
            results["api_key_hashing"] = True
            print("✅ API key hashing working (salted)")
        else:
            results["errors"].append(f"API key hashing issue - hash1: {len(hash1)} chars, same: {hash1 == hash2}")
            print("❌ API key hashing failed")
    except Exception as e:
        results["errors"].append(f"API key hashing error: {e}")
        print(f"❌ API key hashing error: {e}")
    
    try:
        # Test key derivation
        test_company_id = "550e8400-e29b-41d4-a716-446655440000"
        key1 = derive_company_key(test_company_id)
        key2 = derive_company_key(test_company_id)
        
        if len(key1) == 32 and key1 == key2:  # Should be consistent
            results["key_derivation"] = True
            print("✅ Key derivation working (consistent)")
        else:
            results["errors"].append(f"Key derivation issue - length: {len(key1)}, consistent: {key1 == key2}")
            print("❌ Key derivation failed")
    except Exception as e:
        results["errors"].append(f"Key derivation error: {e}")
        print(f"❌ Key derivation error: {e}")
    
    return results


async def test_security_vulnerability_detection():
    """Test that our security tests can detect vulnerabilities"""
    print("\n🔍 Testing vulnerability detection capabilities...")
    
    # Test SQL injection detection
    sql_payloads = [
        "'; DROP TABLE test; --",
        "' OR '1'='1",
        "' UNION SELECT password FROM users --"
    ]
    
    print("🔍 SQL injection payload detection:")
    for payload in sql_payloads:
        # Simulate checking if payload contains dangerous patterns
        dangerous_patterns = ["DROP", "UNION", "OR '1'='1", "--", "/*", "*/"]
        is_dangerous = any(pattern in payload.upper() for pattern in dangerous_patterns)
        
        if is_dangerous:
            print(f"✅ Detected dangerous SQL pattern: {payload[:30]}...")
        else:
            print(f"❌ Missed dangerous SQL pattern: {payload[:30]}...")
    
    # Test XSS detection
    xss_payloads = [
        "<script>alert('xss')</script>",
        "javascript:alert('xss')",
        "<img src=x onerror=alert('xss')>"
    ]
    
    print("\n🔍 XSS payload detection:")
    for payload in xss_payloads:
        dangerous_patterns = ["<script", "javascript:", "onerror=", "onload="]
        is_dangerous = any(pattern in payload.lower() for pattern in dangerous_patterns)
        
        if is_dangerous:
            print(f"✅ Detected dangerous XSS pattern: {payload[:30]}...")
        else:
            print(f"❌ Missed dangerous XSS pattern: {payload[:30]}...")


def analyze_code_security_features():
    """Analyze the security features in the codebase"""
    print("\n🔎 Analyzing code security features...")
    
    security_features = {
        "PBKDF2 key derivation": False,
        "AES encryption": False,
        "Salt usage": False,
        "JWT implementation": False,
        "Rate limiting": False,
        "Schema isolation": False
    }
    
    try:
        # Check authentication service
        from app.services.auth import hash_api_key
        import inspect
        auth_source = inspect.getsource(hash_api_key)
        
        if "pbkdf2_hmac" in auth_source:
            security_features["PBKDF2 key derivation"] = True
            print("✅ PBKDF2 key derivation found")
        
        if "salt" in auth_source.lower():
            security_features["Salt usage"] = True
            print("✅ Salt usage found")
        
    except Exception as e:
        print(f"⚠️  Could not analyze auth service: {e}")
    
    try:
        # Check encryption service
        from app.services.encryption import encrypt_vendor_key
        import inspect
        encryption_source = inspect.getsource(encrypt_vendor_key)
        
        if "AES" in encryption_source:
            security_features["AES encryption"] = True
            print("✅ AES encryption found")
        
    except Exception as e:
        print(f"⚠️  Could not analyze encryption service: {e}")
    
    try:
        # Check admin auth
        from app.auth.admin_auth import create_admin_token
        import inspect
        jwt_source = inspect.getsource(create_admin_token)
        
        if "jwt" in jwt_source:
            security_features["JWT implementation"] = True
            print("✅ JWT implementation found")
        
    except Exception as e:
        print(f"⚠️  Could not analyze JWT implementation: {e}")
    
    return security_features


async def main():
    """Run security validation tests"""
    print("🔒 API Lens Security Validation")
    print("=" * 50)
    
    # Test basic security functions
    basic_results = await test_basic_security_functions()
    
    # Test vulnerability detection
    await test_security_vulnerability_detection()
    
    # Analyze security features
    security_features = analyze_code_security_features()
    
    # Summary
    print("\n" + "=" * 50)
    print("📊 VALIDATION SUMMARY")
    print("=" * 50)
    
    basic_tests_passed = sum(basic_results[key] for key in ["api_key_generation", "api_key_hashing", "key_derivation"])
    security_features_found = sum(security_features.values())
    
    print(f"Basic Security Functions: {basic_tests_passed}/3 working")
    print(f"Security Features Found: {security_features_found}/{len(security_features)}")
    
    if basic_results["errors"]:
        print(f"\n❌ Errors found: {len(basic_results['errors'])}")
        for error in basic_results["errors"]:
            print(f"  - {error}")
    
    if basic_tests_passed == 3 and security_features_found >= 4:
        print("\n✅ Security validation PASSED - framework ready for comprehensive testing")
        return 0
    else:
        print("\n⚠️  Security validation FAILED - issues need to be resolved before testing")
        return 1


if __name__ == "__main__":
    exit(asyncio.run(main()))
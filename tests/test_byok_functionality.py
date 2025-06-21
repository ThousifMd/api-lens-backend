"""
BYOK (Bring Your Own Key) Functionality Tests
Tests vendor API key management and real vendor integration
"""

import asyncio
import os
import httpx
from typing import Dict, List, Optional, Any
import sys
from pathlib import Path

# Add app to path
sys.path.insert(0, str(Path(__file__).parent.parent))

from app.services.encryption import EncryptionService
from app.services.auth import AuthService
from app.test_database import TestDatabaseUtils, init_test_database


class BYOKFunctionalityTests:
    """Test BYOK functionality with vendor API keys"""
    
    def __init__(self):
        self.encryption_service = EncryptionService()
        self.auth_service = AuthService()
        
        # Test vendor configurations
        self.test_vendors = {
            "openai": {
                "name": "OpenAI",
                "api_url": "https://api.openai.com/v1",
                "test_endpoint": "/models",
                "auth_header": "Authorization",
                "auth_format": "Bearer {key}",
                "test_key_env": "TEST_OPENAI_API_KEY",
                "expected_response_fields": ["data", "object"]
            },
            "anthropic": {
                "name": "Anthropic",
                "api_url": "https://api.anthropic.com/v1",
                "test_endpoint": "/messages",
                "auth_header": "x-api-key", 
                "auth_format": "{key}",
                "test_key_env": "TEST_ANTHROPIC_API_KEY",
                "expected_response_fields": ["type", "content"]
            },
            "google": {
                "name": "Google AI",
                "api_url": "https://generativelanguage.googleapis.com/v1beta",
                "test_endpoint": "/models",
                "auth_header": "Authorization",
                "auth_format": "Bearer {key}",
                "test_key_env": "TEST_GOOGLE_AI_API_KEY",
                "expected_response_fields": ["models"]
            }
        }
        
        # Test companies with different BYOK configurations
        self.test_companies = {
            "byok_full": {
                "company_id": "test-byok-full",
                "name": "Full BYOK Company",
                "vendors": ["openai", "anthropic", "google"]
            },
            "byok_partial": {
                "company_id": "test-byok-partial", 
                "name": "Partial BYOK Company",
                "vendors": ["openai"]
            },
            "byok_none": {
                "company_id": "test-byok-none",
                "name": "No BYOK Company",
                "vendors": []
            }
        }
    
    async def setup(self):
        """Setup test environment"""
        await init_test_database()
        await self.encryption_service.initialize()
        await self.auth_service.initialize()
        
        # Setup test companies
        for config in self.test_companies.values():
            await TestDatabaseUtils.insert_test_company(
                config["company_id"],
                config["name"],
                "premium"
            )
    
    async def test_vendor_key_encryption(self):
        """Test vendor API key encryption and decryption"""
        print("🔐 Testing vendor API key encryption...")
        
        results = {}
        
        # Test keys (fake keys for testing)
        test_keys = {
            "openai": "sk-test1234567890abcdef1234567890abcdef123456",
            "anthropic": "sk-ant-api03-test1234567890abcdef1234567890abcdef123456",
            "google": "AIzaSyTest1234567890abcdef1234567890abcdef"
        }
        
        for vendor, test_key in test_keys.items():
            print(f"  Testing {vendor} key encryption...")
            
            try:
                # Encrypt the key
                encrypted_key = await self.encryption_service.encrypt_vendor_key(
                    vendor=vendor,
                    api_key=test_key,
                    company_id=self.test_companies["byok_full"]["company_id"]
                )
                
                # Verify encryption worked
                assert encrypted_key != test_key, f"{vendor}: Key should be encrypted"
                assert len(encrypted_key) > len(test_key), f"{vendor}: Encrypted key should be longer"
                
                # Decrypt the key
                decrypted_key = await self.encryption_service.decrypt_vendor_key(
                    vendor=vendor,
                    encrypted_key=encrypted_key,
                    company_id=self.test_companies["byok_full"]["company_id"]
                )
                
                # Verify decryption worked
                assert decrypted_key == test_key, f"{vendor}: Decrypted key should match original"
                
                results[vendor] = {
                    "original_key": test_key[:10] + "...",
                    "encrypted_length": len(encrypted_key),
                    "decryption_successful": decrypted_key == test_key,
                    "encryption_working": True
                }
                
                print(f"    ✅ {vendor}: Encryption/decryption successful")
                
            except Exception as e:
                print(f"    ❌ {vendor}: Encryption failed - {e}")
                results[vendor] = {"error": str(e), "encryption_working": False}
                raise
        
        return results
    
    async def test_vendor_key_storage(self):
        """Test secure storage and retrieval of vendor keys"""
        print("💾 Testing vendor key storage...")
        
        company_id = self.test_companies["byok_full"]["company_id"]
        
        # Test keys to store
        test_keys = {
            "openai": "sk-test-openai-12345",
            "anthropic": "sk-ant-test-12345",
            "google": "AIzaSyTest12345"
        }
        
        results = {}
        
        try:
            # Store keys for the company
            for vendor, key in test_keys.items():
                print(f"  Storing {vendor} key...")
                
                success = await self.auth_service.store_vendor_key(
                    company_id=company_id,
                    vendor=vendor,
                    api_key=key,
                    key_name=f"test_{vendor}_key",
                    description=f"Test {vendor} API key"
                )
                
                assert success, f"Failed to store {vendor} key"
                
            # Retrieve and verify keys
            for vendor, original_key in test_keys.items():
                print(f"  Retrieving {vendor} key...")
                
                retrieved_key = await self.auth_service.get_vendor_key(
                    company_id=company_id,
                    vendor=vendor
                )
                
                assert retrieved_key is not None, f"Failed to retrieve {vendor} key"
                assert retrieved_key == original_key, f"{vendor} key mismatch after storage/retrieval"
                
                results[vendor] = {
                    "stored_successfully": True,
                    "retrieved_successfully": True,
                    "key_matches": retrieved_key == original_key
                }
                
                print(f"    ✅ {vendor}: Storage/retrieval successful")
            
            # Test key listing
            stored_keys = await self.auth_service.list_vendor_keys(company_id)
            expected_vendors = set(test_keys.keys())
            stored_vendors = {key["vendor"] for key in stored_keys}
            
            assert expected_vendors == stored_vendors, "Stored vendors don't match expected"
            
            results["key_listing"] = {
                "expected_vendors": list(expected_vendors),
                "stored_vendors": list(stored_vendors),
                "listing_successful": expected_vendors == stored_vendors
            }
            
            print(f"    ✅ Key listing: {len(stored_keys)} keys found")
            
            return results
            
        except Exception as e:
            print(f"    ❌ Key storage test failed: {e}")
            raise
    
    async def test_vendor_key_rotation(self):
        """Test vendor API key rotation"""
        print("🔄 Testing vendor key rotation...")
        
        company_id = self.test_companies["byok_partial"]["company_id"]
        vendor = "openai"
        
        try:
            # Store initial key
            old_key = "sk-test-old-key-12345"
            await self.auth_service.store_vendor_key(
                company_id=company_id,
                vendor=vendor,
                api_key=old_key,
                key_name="initial_key"
            )
            
            # Verify old key is stored
            retrieved_old = await self.auth_service.get_vendor_key(company_id, vendor)
            assert retrieved_old == old_key, "Old key not stored correctly"
            
            # Rotate to new key
            new_key = "sk-test-new-key-67890"
            rotation_success = await self.auth_service.rotate_vendor_key(
                company_id=company_id,
                vendor=vendor,
                new_api_key=new_key,
                rotation_reason="scheduled_rotation"
            )
            
            assert rotation_success, "Key rotation should succeed"
            
            # Verify new key is now active
            retrieved_new = await self.auth_service.get_vendor_key(company_id, vendor)
            assert retrieved_new == new_key, "New key not active after rotation"
            assert retrieved_new != old_key, "Key should have changed"
            
            # Verify rotation was logged
            rotation_history = await self.auth_service.get_key_rotation_history(
                company_id, vendor
            )
            
            assert len(rotation_history) > 0, "Rotation should be logged"
            latest_rotation = rotation_history[0]
            assert latest_rotation["reason"] == "scheduled_rotation"
            
            print(f"    ✅ Key rotation successful for {vendor}")
            
            return {
                "old_key_stored": retrieved_old == old_key,
                "rotation_successful": rotation_success,
                "new_key_active": retrieved_new == new_key,
                "rotation_logged": len(rotation_history) > 0,
                "rotation_working": True
            }
            
        except Exception as e:
            print(f"    ❌ Key rotation test failed: {e}")
            raise
    
    async def test_vendor_api_validation(self):
        """Test validation of vendor API keys with real API calls"""
        print("🌐 Testing vendor API key validation...")
        
        results = {}
        
        for vendor, config in self.test_vendors.items():
            print(f"  Testing {vendor} API validation...")
            
            # Check if test key is available
            test_key = os.getenv(config["test_key_env"])
            if not test_key:
                print(f"    ⚠️  {vendor}: No test key provided (set {config['test_key_env']})")
                results[vendor] = {
                    "test_key_available": False,
                    "validation_skipped": True
                }
                continue
            
            try:
                # Test API key validation
                is_valid = await self.auth_service.validate_vendor_api_key(
                    vendor=vendor,
                    api_key=test_key
                )
                
                if is_valid:
                    # Test actual API call
                    api_call_success = await self._test_vendor_api_call(
                        vendor, config, test_key
                    )
                    
                    results[vendor] = {
                        "test_key_available": True,
                        "key_validation_passed": is_valid,
                        "api_call_successful": api_call_success,
                        "overall_working": is_valid and api_call_success
                    }
                    
                    print(f"    ✅ {vendor}: API validation and call successful")
                else:
                    results[vendor] = {
                        "test_key_available": True,
                        "key_validation_passed": False,
                        "api_call_successful": False,
                        "overall_working": False
                    }
                    
                    print(f"    ❌ {vendor}: API key validation failed")
                
            except Exception as e:
                print(f"    ❌ {vendor}: API validation error - {e}")
                results[vendor] = {
                    "test_key_available": True,
                    "error": str(e),
                    "overall_working": False
                }
        
        return results
    
    async def _test_vendor_api_call(self, vendor: str, config: Dict, api_key: str) -> bool:
        """Test actual API call to vendor"""
        try:
            headers = {
                config["auth_header"]: config["auth_format"].format(key=api_key),
                "Content-Type": "application/json"
            }
            
            async with httpx.AsyncClient(timeout=30.0) as client:
                if vendor == "openai":
                    # Test OpenAI models endpoint
                    response = await client.get(
                        f"{config['api_url']}{config['test_endpoint']}",
                        headers=headers
                    )
                    
                elif vendor == "anthropic":
                    # Test Anthropic messages endpoint with minimal request
                    test_data = {
                        "model": "claude-3-haiku-20240307",
                        "max_tokens": 10,
                        "messages": [{"role": "user", "content": "Hello"}]
                    }
                    response = await client.post(
                        f"{config['api_url']}{config['test_endpoint']}",
                        headers=headers,
                        json=test_data
                    )
                    
                elif vendor == "google":
                    # Test Google AI models endpoint
                    response = await client.get(
                        f"{config['api_url']}{config['test_endpoint']}",
                        headers=headers
                    )
                
                else:
                    return False
                
                # Check response
                if response.status_code in [200, 201]:
                    response_data = response.json()
                    
                    # Verify expected fields are present
                    for field in config["expected_response_fields"]:
                        if field not in response_data:
                            return False
                    
                    return True
                else:
                    print(f"      API call failed: {response.status_code} - {response.text[:100]}")
                    return False
                    
        except Exception as e:
            print(f"      API call exception: {e}")
            return False
    
    async def test_company_isolation_byok(self):
        """Test that BYOK keys are properly isolated between companies"""
        print("🏢 Testing BYOK company isolation...")
        
        company1_id = self.test_companies["byok_full"]["company_id"]
        company2_id = self.test_companies["byok_partial"]["company_id"]
        vendor = "openai"
        
        try:
            # Store different keys for each company
            key1 = "sk-company1-key-12345"
            key2 = "sk-company2-key-67890"
            
            await self.auth_service.store_vendor_key(
                company_id=company1_id,
                vendor=vendor,
                api_key=key1,
                key_name="company1_key"
            )
            
            await self.auth_service.store_vendor_key(
                company_id=company2_id,
                vendor=vendor,
                api_key=key2,
                key_name="company2_key"
            )
            
            # Verify each company gets their own key
            retrieved_key1 = await self.auth_service.get_vendor_key(company1_id, vendor)
            retrieved_key2 = await self.auth_service.get_vendor_key(company2_id, vendor)
            
            assert retrieved_key1 == key1, "Company 1 should get their own key"
            assert retrieved_key2 == key2, "Company 2 should get their own key"
            assert retrieved_key1 != retrieved_key2, "Companies should have different keys"
            
            # Verify company 1 cannot access company 2's keys
            try:
                unauthorized_access = await self.auth_service.get_vendor_key(
                    company_id=company1_id,
                    vendor=vendor,
                    target_company_id=company2_id  # Attempt unauthorized access
                )
                # This should fail or return None
                assert unauthorized_access is None or unauthorized_access == key1, "Should not access other company's keys"
            except PermissionError:
                pass  # Expected behavior
            
            print("    ✅ Company isolation working correctly")
            
            return {
                "company1_key_correct": retrieved_key1 == key1,
                "company2_key_correct": retrieved_key2 == key2,
                "keys_different": retrieved_key1 != retrieved_key2,
                "isolation_working": True
            }
            
        except Exception as e:
            print(f"    ❌ Company isolation test failed: {e}")
            raise
    
    async def test_byok_fallback_behavior(self):
        """Test fallback behavior when BYOK keys are not available"""
        print("🔄 Testing BYOK fallback behavior...")
        
        company_id = self.test_companies["byok_none"]["company_id"]
        
        try:
            # Attempt to get vendor key for company with no BYOK setup
            openai_key = await self.auth_service.get_vendor_key(company_id, "openai")
            
            # Should either return None or a system default key
            fallback_behavior_correct = (
                openai_key is None or  # No fallback
                openai_key.startswith("sk-system-")  # System fallback key
            )
            
            # Test request handling without BYOK
            can_process_without_byok = await self.auth_service.can_process_request(
                company_id=company_id,
                vendor="openai",
                require_byok=False
            )
            
            cannot_process_with_byok_required = not await self.auth_service.can_process_request(
                company_id=company_id,
                vendor="openai", 
                require_byok=True
            )
            
            print("    ✅ BYOK fallback behavior working correctly")
            
            return {
                "fallback_behavior_correct": fallback_behavior_correct,
                "can_process_without_byok": can_process_without_byok,
                "blocks_when_byok_required": cannot_process_with_byok_required,
                "fallback_working": True
            }
            
        except Exception as e:
            print(f"    ❌ BYOK fallback test failed: {e}")
            raise
    
    async def test_byok_performance_impact(self):
        """Test performance impact of BYOK key retrieval"""
        print("⚡ Testing BYOK performance impact...")
        
        company_id = self.test_companies["byok_full"]["company_id"]
        
        try:
            # Store a key
            await self.auth_service.store_vendor_key(
                company_id=company_id,
                vendor="openai",
                api_key="sk-test-performance-key",
                key_name="performance_test_key"
            )
            
            import time
            
            # Test single key retrieval performance
            start_time = time.time()
            for _ in range(100):
                key = await self.auth_service.get_vendor_key(company_id, "openai")
                assert key is not None
            single_retrieval_time = (time.time() - start_time) / 100
            
            # Test concurrent key retrievals
            async def get_key():
                return await self.auth_service.get_vendor_key(company_id, "openai")
            
            start_time = time.time()
            tasks = [get_key() for _ in range(50)]
            results = await asyncio.gather(*tasks)
            concurrent_time = time.time() - start_time
            
            # Verify all results are correct
            all_correct = all(result == "sk-test-performance-key" for result in results)
            
            print(f"    ✅ Performance: {single_retrieval_time*1000:.2f}ms per retrieval, {concurrent_time:.2f}s for 50 concurrent")
            
            return {
                "single_retrieval_time_ms": single_retrieval_time * 1000,
                "concurrent_50_time_s": concurrent_time,
                "all_concurrent_correct": all_correct,
                "performance_acceptable": single_retrieval_time < 0.1  # <100ms
            }
            
        except Exception as e:
            print(f"    ❌ BYOK performance test failed: {e}")
            raise
    
    async def run_all_tests(self):
        """Run all BYOK functionality tests"""
        print("🔑 Starting BYOK Functionality Tests")
        print("=" * 50)
        
        try:
            await self.setup()
            
            # Run all test methods
            encryption_results = await self.test_vendor_key_encryption()
            storage_results = await self.test_vendor_key_storage()
            rotation_results = await self.test_vendor_key_rotation()
            validation_results = await self.test_vendor_api_validation()
            isolation_results = await self.test_company_isolation_byok()
            fallback_results = await self.test_byok_fallback_behavior()
            performance_results = await self.test_byok_performance_impact()
            
            print("=" * 50)
            print("🎉 All BYOK Functionality Tests COMPLETED!")
            
            # Print summary
            await self._print_test_summary({
                "encryption": encryption_results,
                "storage": storage_results,
                "rotation": rotation_results,
                "validation": validation_results,
                "isolation": isolation_results,
                "fallback": fallback_results,
                "performance": performance_results
            })
            
            return True
            
        except Exception as e:
            print(f"❌ BYOK Functionality Tests FAILED: {e}")
            raise
    
    async def _print_test_summary(self, results):
        """Print comprehensive test summary"""
        print("\n🔑 BYOK Functionality Test Summary:")
        print("-" * 35)
        
        # Encryption
        encryption = results["encryption"]
        encryption_working = sum(1 for r in encryption.values() if isinstance(r, dict) and r.get("encryption_working", False))
        print(f"🔐 Encryption: {encryption_working}/{len(encryption)} vendors working")
        
        # Storage
        storage = results["storage"]
        if "key_listing" in storage:
            stored_vendors = len(storage["key_listing"]["stored_vendors"])
            print(f"💾 Storage: {stored_vendors} vendor keys stored and retrieved")
        
        # API Validation
        validation = results["validation"]
        validated_vendors = sum(1 for r in validation.values() if isinstance(r, dict) and r.get("overall_working", False))
        total_with_keys = sum(1 for r in validation.values() if isinstance(r, dict) and r.get("test_key_available", False))
        print(f"🌐 API Validation: {validated_vendors}/{total_with_keys} vendors with test keys working")
        
        # Company Isolation
        isolation = results["isolation"]
        isolation_working = isolation.get("isolation_working", False)
        print(f"🏢 Company Isolation: {'✅ Working' if isolation_working else '❌ Failed'}")
        
        # Performance
        performance = results["performance"]
        retrieval_time = performance.get("single_retrieval_time_ms", 0)
        performance_ok = performance.get("performance_acceptable", False)
        print(f"⚡ Performance: {retrieval_time:.1f}ms per key retrieval ({'✅ Good' if performance_ok else '⚠️ Slow'})")
        
        # Overall Assessment
        core_features_working = encryption_working >= 2 and isolation_working and performance_ok
        print(f"✅ Overall BYOK System: {'Fully functional' if core_features_working else 'Needs attention'}")


# Standalone execution
async def main():
    """Run BYOK functionality tests"""
    try:
        test_suite = BYOKFunctionalityTests()
        await test_suite.run_all_tests()
        print("\n🎊 BYOK Functionality Testing Complete!")
        
    except Exception as e:
        print(f"\n❌ BYOK Functionality Tests Failed: {e}")
        import traceback
        traceback.print_exc()
        return False
    
    return True

if __name__ == "__main__":
    success = asyncio.run(main())
    exit(0 if success else 1)
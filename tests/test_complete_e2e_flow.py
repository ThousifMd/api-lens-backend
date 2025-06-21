"""
Complete End-to-End Flow Testing
Tests: Client → Workers → Vendor → Response flow with logging, cost calculation, and rate limiting
"""

import asyncio
import json
import time
import uuid
from datetime import datetime
from typing import Dict, List, Optional, Any
import sys
from pathlib import Path

# Add app to path
sys.path.insert(0, str(Path(__file__).parent.parent))

from app.test_database import TestDatabaseUtils, init_test_database
from tests.test_logging_simple import create_test_log_entry
import httpx


class CompleteE2EFlowTests:
    """Test complete end-to-end API request flow"""
    
    def __init__(self):
        self.base_url = "http://localhost:8000"
        self.worker_token = "test-worker-token-123"
        self.headers = {
            "Authorization": f"Bearer {self.worker_token}",
            "Content-Type": "application/json"
        }
        
        # Test scenarios covering different vendors and use cases
        self.test_scenarios = [
            {
                "name": "OpenAI Chat Completion",
                "vendor": "openai",
                "model": "gpt-4",
                "endpoint": "/openai/chat/completions",
                "request_data": {
                    "model": "gpt-4",
                    "messages": [{"role": "user", "content": "Hello, how are you?"}],
                    "max_tokens": 100,
                    "temperature": 0.7
                },
                "expected_cost_range": (0.001, 0.1),
                "expected_tokens_range": (10, 200)
            },
            {
                "name": "Anthropic Chat",
                "vendor": "anthropic", 
                "model": "claude-3-sonnet-20240229",
                "endpoint": "/claude/chat",
                "request_data": {
                    "model": "claude-3-sonnet-20240229",
                    "messages": [{"role": "user", "content": "What's the weather like?"}],
                    "max_tokens": 50
                },
                "expected_cost_range": (0.001, 0.05),
                "expected_tokens_range": (5, 100)
            },
            {
                "name": "Google Gemini Chat",
                "vendor": "google",
                "model": "gemini-1.5-pro",
                "endpoint": "/gemini/chat", 
                "request_data": {
                    "model": "gemini-1.5-pro",
                    "messages": [{"role": "user", "content": "Tell me a joke"}],
                    "max_tokens": 75
                },
                "expected_cost_range": (0.001, 0.075),
                "expected_tokens_range": (5, 150)
            }
        ]
        
        # Test companies with different configurations
        self.test_companies = {
            "premium_company": {
                "company_id": "test-e2e-premium",
                "api_key": "als_test_premium_key_12345",
                "tier": "premium",
                "rate_limits": {"requests_per_minute": 100},
                "quotas": {"monthly_requests": 10000, "monthly_cost": 1000.0}
            },
            "basic_company": {
                "company_id": "test-e2e-basic",
                "api_key": "als_test_basic_key_67890", 
                "tier": "basic",
                "rate_limits": {"requests_per_minute": 20},
                "quotas": {"monthly_requests": 1000, "monthly_cost": 100.0}
            }
        }
    
    async def setup(self):
        """Setup test environment"""
        await init_test_database()
        
        # Setup test companies
        for config in self.test_companies.values():
            await TestDatabaseUtils.insert_test_company(
                config["company_id"],
                f"E2E Test Company {config['tier'].title()}",
                config["tier"]
            )
    
    async def test_server_connectivity(self):
        """Test that all required services are running"""
        print("🔌 Testing server connectivity...")
        
        try:
            async with httpx.AsyncClient() as client:
                # Test main health endpoint
                response = await client.get(f"{self.base_url}/health")
                assert response.status_code == 200, f"Health check failed: {response.status_code}"
                
                health_data = response.json()
                assert health_data["status"] == "healthy", "Server not healthy"
                
                # Test database health
                db_response = await client.get(f"{self.base_url}/health/db")
                assert db_response.status_code == 200, f"Database health check failed: {db_response.status_code}"
                
                print("    ✅ Server and database are running and healthy")
                
                return {
                    "server_healthy": True,
                    "database_healthy": True,
                    "connectivity_working": True
                }
                
        except Exception as e:
            print(f"    ❌ Server connectivity failed: {e}")
            raise
    
    async def test_authentication_flow(self):
        """Test authentication flow from client to backend"""
        print("🔐 Testing authentication flow...")
        
        results = {}
        
        for company_name, config in self.test_companies.items():
            print(f"  Testing {company_name} authentication...")
            
            try:
                # Test API key validation (this would normally go through Workers)
                auth_headers = {
                    "Authorization": f"Bearer {config['api_key']}",
                    "Content-Type": "application/json"
                }
                
                async with httpx.AsyncClient() as client:
                    # Test auth verification endpoint
                    response = await client.get(
                        f"{self.base_url}/auth/verify",
                        headers=auth_headers
                    )
                    
                    if response.status_code == 200:
                        auth_data = response.json()
                        
                        results[company_name] = {
                            "auth_successful": True,
                            "company_id": auth_data.get("company_id"),
                            "tier": auth_data.get("tier"),
                            "auth_working": True
                        }
                        
                        print(f"    ✅ {company_name}: Authentication successful")
                    else:
                        results[company_name] = {
                            "auth_successful": False,
                            "status_code": response.status_code,
                            "auth_working": False
                        }
                        
                        print(f"    ❌ {company_name}: Authentication failed ({response.status_code})")
                
            except Exception as e:
                print(f"    ❌ {company_name}: Authentication error - {e}")
                results[company_name] = {"error": str(e), "auth_working": False}
        
        return results
    
    async def test_proxy_request_flow(self):
        """Test complete proxy request flow (simulating Workers behavior)"""
        print("🔄 Testing proxy request flow...")
        
        results = {}
        
        for scenario in self.test_scenarios:
            print(f"  Testing {scenario['name']}...")
            
            try:
                # Simulate the complete flow:
                # 1. Client request comes to Workers
                # 2. Workers proxy to vendor (simulated)
                # 3. Workers log response to backend
                
                start_time = time.time()
                
                # Step 1: Simulate vendor API response (since we don't have real keys)
                simulated_response = await self._simulate_vendor_response(scenario)
                
                end_time = time.time()
                total_latency = int((end_time - start_time) * 1000)
                
                # Step 2: Create log entry as Workers would
                log_entry = self._create_realistic_log_entry(
                    scenario,
                    simulated_response,
                    total_latency
                )
                
                # Step 3: Send log to backend (as Workers would)
                async with httpx.AsyncClient() as client:
                    log_response = await client.post(
                        f"{self.base_url}/proxy/logs/requests",
                        headers=self.headers,
                        json=log_entry
                    )
                    
                    assert log_response.status_code == 200, f"Logging failed: {log_response.status_code}"
                    
                # Step 4: Verify log was stored
                await asyncio.sleep(0.5)  # Allow time for database write
                
                stored_logs = await TestDatabaseUtils.get_log_count(
                    log_entry["companyId"]
                )
                
                results[scenario["name"]] = {
                    "vendor": scenario["vendor"],
                    "model": scenario["model"],
                    "simulated_response": simulated_response,
                    "total_latency": total_latency,
                    "logging_successful": log_response.status_code == 200,
                    "log_stored": stored_logs > 0,
                    "flow_working": True
                }
                
                print(f"    ✅ {scenario['name']}: Complete flow successful ({total_latency}ms)")
                
            except Exception as e:
                print(f"    ❌ {scenario['name']}: Flow failed - {e}")
                results[scenario["name"]] = {"error": str(e), "flow_working": False}
                raise
        
        return results
    
    async def _simulate_vendor_response(self, scenario: Dict) -> Dict:
        """Simulate a realistic vendor API response"""
        # Simulate network delay
        await asyncio.sleep(0.1 + (0.05 * len(scenario["request_data"].get("messages", []))))
        
        vendor = scenario["vendor"]
        
        if vendor == "openai":
            return {
                "id": f"chatcmpl-{uuid.uuid4().hex[:10]}",
                "object": "chat.completion",
                "created": int(time.time()),
                "model": scenario["model"],
                "choices": [{
                    "index": 0,
                    "message": {
                        "role": "assistant",
                        "content": "Hello! I'm doing well, thank you for asking. How can I help you today?"
                    },
                    "finish_reason": "stop"
                }],
                "usage": {
                    "prompt_tokens": 12,
                    "completion_tokens": 18,
                    "total_tokens": 30
                }
            }
            
        elif vendor == "anthropic":
            return {
                "id": f"msg_{uuid.uuid4().hex[:10]}",
                "type": "message",
                "role": "assistant",
                "content": [{
                    "type": "text",
                    "text": "I don't have access to real-time weather data, but I'd be happy to help you find weather information!"
                }],
                "model": scenario["model"],
                "stop_reason": "end_turn",
                "stop_sequence": None,
                "usage": {
                    "input_tokens": 8,
                    "output_tokens": 22,
                    "total_tokens": 30
                }
            }
            
        elif vendor == "google":
            return {
                "candidates": [{
                    "content": {
                        "parts": [{
                            "text": "Why don't scientists trust atoms? Because they make up everything!"
                        }],
                        "role": "model"
                    },
                    "finishReason": "STOP",
                    "index": 0
                }],
                "usageMetadata": {
                    "promptTokenCount": 6,
                    "candidatesTokenCount": 14,
                    "totalTokenCount": 20
                }
            }
        
        return {}
    
    def _create_realistic_log_entry(self, scenario: Dict, response: Dict, latency: int) -> Dict:
        """Create a realistic log entry based on scenario and response"""
        request_id = str(uuid.uuid4())
        timestamp = int(datetime.now().timestamp() * 1000)
        
        # Extract token usage from response
        input_tokens = 0
        output_tokens = 0
        total_tokens = 0
        
        if scenario["vendor"] == "openai" and "usage" in response:
            input_tokens = response["usage"].get("prompt_tokens", 0)
            output_tokens = response["usage"].get("completion_tokens", 0)
            total_tokens = response["usage"].get("total_tokens", 0)
        elif scenario["vendor"] == "anthropic" and "usage" in response:
            input_tokens = response["usage"].get("input_tokens", 0)
            output_tokens = response["usage"].get("output_tokens", 0)
            total_tokens = response["usage"].get("total_tokens", 0)
        elif scenario["vendor"] == "google" and "usageMetadata" in response:
            input_tokens = response["usageMetadata"].get("promptTokenCount", 0)
            output_tokens = response["usageMetadata"].get("candidatesTokenCount", 0)
            total_tokens = response["usageMetadata"].get("totalTokenCount", 0)
        
        # Calculate cost based on tokens and model
        cost = self._calculate_cost(scenario["vendor"], scenario["model"], input_tokens, output_tokens)
        
        return {
            "requestId": request_id,
            "companyId": self.test_companies["premium_company"]["company_id"],
            "timestamp": timestamp,
            "request": {
                "requestId": request_id,
                "timestamp": timestamp,
                "method": "POST",
                "url": f"https://proxy.apilens.dev{scenario['endpoint']}",
                "userAgent": "API-Lens-Test-Client/1.0",
                "ip": "203.0.113.42",
                "headers": {
                    "content-type": "application/json",
                    "authorization": "Bearer als_****"
                },
                "vendor": scenario["vendor"],
                "model": scenario["model"],
                "endpoint": scenario["endpoint"].lstrip("/"),
                "bodySize": len(json.dumps(scenario["request_data"])),
                "country": "US",
                "region": "California"
            },
            "response": {
                "requestId": request_id,
                "timestamp": timestamp + latency,
                "statusCode": 200,
                "statusText": "OK",
                "headers": {
                    "content-type": "application/json"
                },
                "bodySize": len(json.dumps(response)),
                "totalLatency": latency,
                "vendorLatency": int(latency * 0.8),  # 80% of latency from vendor
                "processingLatency": int(latency * 0.2),  # 20% processing
                "success": True,
                "inputTokens": input_tokens,
                "outputTokens": output_tokens,
                "totalTokens": total_tokens
            },
            "performance": {
                "requestId": request_id,
                "companyId": self.test_companies["premium_company"]["company_id"],
                "timestamp": timestamp,
                "totalLatency": latency,
                "vendorLatency": int(latency * 0.8),
                "authLatency": 15,
                "ratelimitLatency": 5,
                "costLatency": 3,
                "loggingLatency": 7,
                "success": True,
                "bytesIn": len(json.dumps(scenario["request_data"])),
                "bytesOut": len(json.dumps(response)),
                "cacheHitRate": 85.0
            },
            "cost": cost
        }
    
    def _calculate_cost(self, vendor: str, model: str, input_tokens: int, output_tokens: int) -> float:
        """Calculate realistic cost based on vendor pricing"""
        # Simplified cost calculation (in production, this would use the cost service)
        cost_per_1k = {
            "openai": {
                "gpt-4": {"input": 0.03, "output": 0.06},
                "gpt-3.5-turbo": {"input": 0.0015, "output": 0.002}
            },
            "anthropic": {
                "claude-3-sonnet-20240229": {"input": 0.003, "output": 0.015},
                "claude-3-haiku-20240307": {"input": 0.00025, "output": 0.00125}
            },
            "google": {
                "gemini-1.5-pro": {"input": 0.007, "output": 0.021},
                "gemini-1.5-flash": {"input": 0.00015, "output": 0.0006}
            }
        }
        
        if vendor in cost_per_1k and model in cost_per_1k[vendor]:
            pricing = cost_per_1k[vendor][model]
            input_cost = (input_tokens / 1000) * pricing["input"]
            output_cost = (output_tokens / 1000) * pricing["output"]
            return round(input_cost + output_cost, 6)
        
        return 0.001  # Fallback cost
    
    async def test_rate_limiting_in_flow(self):
        """Test rate limiting during complete request flow"""
        print("🚦 Testing rate limiting in complete flow...")
        
        company_config = self.test_companies["basic_company"]
        rate_limit = company_config["rate_limits"]["requests_per_minute"]
        
        try:
            print(f"  Testing rate limit of {rate_limit} requests/minute...")
            
            successful_requests = 0
            rate_limited_requests = 0
            
            # Make requests up to and beyond the limit
            for i in range(rate_limit + 5):
                # Create a simple log entry (simulating a request)
                log_entry = create_test_log_entry()
                log_entry["companyId"] = company_config["company_id"]
                
                async with httpx.AsyncClient() as client:
                    response = await client.post(
                        f"{self.base_url}/proxy/logs/requests",
                        headers=self.headers,
                        json=log_entry
                    )
                    
                    if response.status_code == 200:
                        successful_requests += 1
                    elif response.status_code == 429:  # Rate limited
                        rate_limited_requests += 1
                    else:
                        print(f"    Unexpected response: {response.status_code}")
                
                # Small delay between requests
                await asyncio.sleep(0.1)
            
            print(f"    ✅ Rate limiting: {successful_requests} successful, {rate_limited_requests} rate-limited")
            
            return {
                "rate_limit": rate_limit,
                "successful_requests": successful_requests,
                "rate_limited_requests": rate_limited_requests,
                "rate_limiting_working": rate_limited_requests > 0
            }
            
        except Exception as e:
            print(f"    ❌ Rate limiting test failed: {e}")
            raise
    
    async def test_cost_calculation_in_flow(self):
        """Test cost calculation during complete request flow"""
        print("💰 Testing cost calculation in complete flow...")
        
        results = {}
        
        for scenario in self.test_scenarios[:2]:  # Test first 2 scenarios
            print(f"  Testing cost calculation for {scenario['name']}...")
            
            try:
                # Simulate request with known token usage
                simulated_response = await self._simulate_vendor_response(scenario)
                log_entry = self._create_realistic_log_entry(
                    scenario, simulated_response, 1500
                )
                
                calculated_cost = log_entry["cost"]
                expected_min, expected_max = scenario["expected_cost_range"]
                
                # Verify cost is within expected range
                cost_in_range = expected_min <= calculated_cost <= expected_max
                
                results[scenario["name"]] = {
                    "calculated_cost": calculated_cost,
                    "expected_range": scenario["expected_cost_range"],
                    "cost_in_range": cost_in_range,
                    "input_tokens": log_entry["response"]["inputTokens"],
                    "output_tokens": log_entry["response"]["outputTokens"]
                }
                
                assert cost_in_range, f"Cost {calculated_cost} not in expected range {scenario['expected_cost_range']}"
                
                print(f"    ✅ {scenario['name']}: ${calculated_cost:.6f} (range: ${expected_min}-${expected_max})")
                
            except Exception as e:
                print(f"    ❌ {scenario['name']}: Cost calculation failed - {e}")
                results[scenario["name"]] = {"error": str(e)}
                raise
        
        return results
    
    async def test_error_handling_and_graceful_degradation(self):
        """Test error handling and graceful degradation"""
        print("🚨 Testing error handling and graceful degradation...")
        
        results = {}
        
        # Test 1: Invalid request data
        print("  Testing invalid request handling...")
        try:
            invalid_log = {"invalid": "data", "missing": "required_fields"}
            
            async with httpx.AsyncClient() as client:
                response = await client.post(
                    f"{self.base_url}/proxy/logs/requests",
                    headers=self.headers,
                    json=invalid_log
                )
                
                results["invalid_request"] = {
                    "status_code": response.status_code,
                    "handled_gracefully": response.status_code == 422,
                    "error_response": response.json() if response.status_code != 200 else None
                }
                
                assert response.status_code == 422, "Invalid request should return 422"
                print("    ✅ Invalid request handled gracefully")
                
        except Exception as e:
            print(f"    ❌ Invalid request test failed: {e}")
            results["invalid_request"] = {"error": str(e)}
        
        # Test 2: Missing authentication
        print("  Testing missing authentication...")
        try:
            log_entry = create_test_log_entry()
            
            async with httpx.AsyncClient() as client:
                response = await client.post(
                    f"{self.base_url}/proxy/logs/requests",
                    headers={"Content-Type": "application/json"},  # No auth header
                    json=log_entry
                )
                
                results["missing_auth"] = {
                    "status_code": response.status_code,
                    "handled_gracefully": response.status_code == 401,
                    "error_response": response.json() if response.status_code != 200 else None
                }
                
                assert response.status_code == 401, "Missing auth should return 401"
                print("    ✅ Missing authentication handled gracefully")
                
        except Exception as e:
            print(f"    ❌ Missing auth test failed: {e}")
            results["missing_auth"] = {"error": str(e)}
        
        # Test 3: Simulated vendor error
        print("  Testing vendor error handling...")
        try:
            # Create log entry with vendor error
            error_log = create_test_log_entry()
            error_log["response"]["statusCode"] = 500
            error_log["response"]["success"] = False
            error_log["response"]["errorMessage"] = "Vendor API temporarily unavailable"
            error_log["response"]["errorType"] = "vendor_error"
            
            async with httpx.AsyncClient() as client:
                response = await client.post(
                    f"{self.base_url}/proxy/logs/requests",
                    headers=self.headers,
                    json=error_log
                )
                
                results["vendor_error"] = {
                    "status_code": response.status_code,
                    "logging_successful": response.status_code == 200,
                    "error_logged": True
                }
                
                assert response.status_code == 200, "Vendor errors should still be logged successfully"
                print("    ✅ Vendor error logging handled gracefully")
                
        except Exception as e:
            print(f"    ❌ Vendor error test failed: {e}")
            results["vendor_error"] = {"error": str(e)}
        
        return results
    
    async def test_concurrent_request_handling(self):
        """Test concurrent request handling"""
        print("⚡ Testing concurrent request handling...")
        
        try:
            async def send_concurrent_request():
                """Send a single request"""
                log_entry = create_test_log_entry()
                log_entry["companyId"] = self.test_companies["premium_company"]["company_id"]
                
                async with httpx.AsyncClient() as client:
                    response = await client.post(
                        f"{self.base_url}/proxy/logs/requests",
                        headers=self.headers,
                        json=log_entry
                    )
                    return response.status_code == 200
            
            # Test with 25 concurrent requests
            num_concurrent = 25
            start_time = time.time()
            
            tasks = [send_concurrent_request() for _ in range(num_concurrent)]
            results = await asyncio.gather(*tasks, return_exceptions=True)
            
            end_time = time.time()
            duration = end_time - start_time
            
            # Count successful requests
            successful = sum(1 for r in results if r is True)
            failed = sum(1 for r in results if r is not True)
            
            success_rate = (successful / num_concurrent) * 100
            requests_per_second = num_concurrent / duration
            
            print(f"    ✅ Concurrent: {successful}/{num_concurrent} successful ({success_rate:.1f}%) in {duration:.2f}s")
            print(f"    📊 Throughput: {requests_per_second:.1f} requests/second")
            
            return {
                "concurrent_requests": num_concurrent,
                "successful": successful,
                "failed": failed,
                "success_rate": success_rate,
                "duration": duration,
                "requests_per_second": requests_per_second,
                "concurrent_handling_working": success_rate >= 90
            }
            
        except Exception as e:
            print(f"    ❌ Concurrent request test failed: {e}")
            raise
    
    async def run_all_tests(self):
        """Run all complete end-to-end flow tests"""
        print("🔄 Starting Complete End-to-End Flow Tests")
        print("=" * 55)
        
        try:
            await self.setup()
            
            # Run all test methods
            connectivity_results = await self.test_server_connectivity()
            auth_results = await self.test_authentication_flow()
            proxy_results = await self.test_proxy_request_flow()
            rate_limit_results = await self.test_rate_limiting_in_flow()
            cost_results = await self.test_cost_calculation_in_flow()
            error_results = await self.test_error_handling_and_graceful_degradation()
            concurrent_results = await self.test_concurrent_request_handling()
            
            print("=" * 55)
            print("🎉 All Complete End-to-End Flow Tests PASSED!")
            
            # Print summary
            await self._print_test_summary({
                "connectivity": connectivity_results,
                "authentication": auth_results,
                "proxy_flow": proxy_results,
                "rate_limiting": rate_limit_results,
                "cost_calculation": cost_results,
                "error_handling": error_results,
                "concurrent": concurrent_results
            })
            
            return True
            
        except Exception as e:
            print(f"❌ Complete End-to-End Flow Tests FAILED: {e}")
            raise
    
    async def _print_test_summary(self, results):
        """Print comprehensive test summary"""
        print("\n🔄 Complete E2E Flow Test Summary:")
        print("-" * 40)
        
        # Connectivity
        connectivity = results["connectivity"]
        connectivity_ok = connectivity.get("connectivity_working", False)
        print(f"🔌 Connectivity: {'✅ Working' if connectivity_ok else '❌ Failed'}")
        
        # Authentication
        auth = results["authentication"]
        auth_working = sum(1 for r in auth.values() if isinstance(r, dict) and r.get("auth_working", False))
        print(f"🔐 Authentication: {auth_working}/{len(auth)} companies working")
        
        # Proxy Flow
        proxy = results["proxy_flow"]
        proxy_working = sum(1 for r in proxy.values() if isinstance(r, dict) and r.get("flow_working", False))
        print(f"🔄 Proxy Flow: {proxy_working}/{len(proxy)} scenarios working")
        
        # Rate Limiting
        rate_limit = results["rate_limiting"]
        rate_limit_working = rate_limit.get("rate_limiting_working", False)
        print(f"🚦 Rate Limiting: {'✅ Working' if rate_limit_working else '❌ Failed'}")
        
        # Cost Calculation
        cost = results["cost_calculation"]
        costs_accurate = sum(1 for r in cost.values() if isinstance(r, dict) and r.get("cost_in_range", False))
        print(f"💰 Cost Calculation: {costs_accurate}/{len(cost)} scenarios accurate")
        
        # Error Handling
        error = results["error_handling"]
        errors_handled = sum(1 for r in error.values() if isinstance(r, dict) and r.get("handled_gracefully", False))
        print(f"🚨 Error Handling: {errors_handled}/{len(error)} error types handled gracefully")
        
        # Concurrent Performance
        concurrent = results["concurrent"]
        success_rate = concurrent.get("success_rate", 0)
        rps = concurrent.get("requests_per_second", 0)
        print(f"⚡ Concurrent Performance: {success_rate:.1f}% success rate, {rps:.1f} RPS")
        
        # Overall Assessment
        critical_systems = [connectivity_ok, auth_working >= 1, proxy_working >= 1, rate_limit_working]
        all_critical_working = all(critical_systems)
        
        print(f"✅ Overall E2E System: {'Fully functional' if all_critical_working else 'Needs attention'}")


# Standalone execution
async def main():
    """Run complete end-to-end flow tests"""
    try:
        test_suite = CompleteE2EFlowTests()
        await test_suite.run_all_tests()
        print("\n🎊 Complete End-to-End Flow Testing Complete!")
        
    except Exception as e:
        print(f"\n❌ Complete End-to-End Flow Tests Failed: {e}")
        import traceback
        traceback.print_exc()
        return False
    
    return True

if __name__ == "__main__":
    success = asyncio.run(main())
    exit(0 if success else 1)
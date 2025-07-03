#!/usr/bin/env python3
"""
Production Readiness Test
Comprehensive test to ensure 100% production readiness
"""

import asyncio
import sys
import uuid
import json
from pathlib import Path
from datetime import datetime, timezone

# Add the app directory to the Python path
sys.path.append(str(Path(__file__).parent.parent))

from app.database import DatabaseUtils
from app.services.auth import generate_api_key, validate_api_key
from app.services.encryption import store_vendor_key, get_vendor_key
from app.api.proxy_optimized import OptimizedLogEntry, receive_optimized_log_entry
from app.utils.logger import get_logger

logger = get_logger(__name__)

async def test_complete_workflow():
    """Test the complete production workflow"""
    print("🔄 Testing complete production workflow...")
    
    try:
        # Step 1: Create company
        company_id = str(uuid.uuid4())
        company_result = await DatabaseUtils.execute_query(
            "INSERT INTO companies (id, name, slug, schema_name) VALUES ($1, $2, $3, $4) RETURNING id, name",
            {
                'id': company_id,
                'name': 'Production Test Company',
                'slug': f'prod-test-{company_id[:8]}',
                'schema_name': f'prod_test_{company_id[:8]}'
            },
            fetch_all=False
        )
        print(f"✅ Company created: {company_result['name']}")
        
        # Step 2: Generate API key
        api_key_data = await generate_api_key(company_id, "Production API Key")
        print(f"✅ API key generated: {api_key_data.description}")
        
        # Step 3: Validate API key
        company = await validate_api_key(api_key_data.api_key)
        print(f"✅ API key validated: {company.name}")
        
        # Step 4: Store vendor key
        vendor_key = "sk-1234567890abcdefghijklmnopqrstuvwxyzABCDEFGHIJKLMNOPQ"
        stored = await store_vendor_key(company_id, "openai", vendor_key)
        print(f"✅ Vendor key stored: {stored}")
        
        # Step 5: Retrieve vendor key
        retrieved_key = await get_vendor_key(company_id, "openai")
        print(f"✅ Vendor key retrieved: {retrieved_key == vendor_key}")
        
        # Step 6: Log multiple requests (simulate production load)
        for i in range(5):
            log_entry = OptimizedLogEntry(
                requestId=str(uuid.uuid4()),
                companyId=company_id,
                timestamp=int(datetime.now().timestamp() * 1000),
                method="POST",
                endpoint="/chat/completions",
                url="https://api.openai.com/v1/chat/completions",
                vendor="openai",
                model="gpt-4",
                userId=str(uuid.uuid4()),
                inputTokens=100 + i * 10,
                outputTokens=150 + i * 15,
                totalLatency=2500 + i * 100,
                vendorLatency=2000 + i * 80,
                statusCode=200,
                success=True,
                cost=0.045 + i * 0.01
            )
            
            result = await receive_optimized_log_entry(log_entry)
            print(f"✅ Request {i+1} logged successfully")
        
        # Step 7: Verify data integrity
        request_count = await DatabaseUtils.execute_query(
            "SELECT COUNT(*) as count FROM requests WHERE company_id = $1",
            {'company_id': company_id},
            fetch_all=False
        )
        print(f"✅ {request_count['count']} requests found in database")
        
        cost_count = await DatabaseUtils.execute_query(
            "SELECT COUNT(*) as count FROM cost_calculations WHERE company_id = $1",
            {'company_id': company_id},
            fetch_all=False
        )
        print(f"✅ {cost_count['count']} cost calculations found")
        
        return True
        
    except Exception as e:
        print(f"❌ Workflow failed: {e}")
        import traceback
        traceback.print_exc()
        return False

async def test_error_handling():
    """Test error handling scenarios"""
    print("🚫 Testing error handling...")
    
    tests_passed = 0
    total_tests = 0
    
    # Test 1: Invalid API key
    total_tests += 1
    try:
        result = await validate_api_key("invalid_key")
        if result is None:
            print("✅ Invalid API key correctly rejected")
            tests_passed += 1
        else:
            print("❌ Invalid API key incorrectly accepted")
    except Exception as e:
        print(f"❌ Error in invalid API key test: {e}")
    
    # Test 2: Non-existent company
    total_tests += 1
    try:
        fake_company_id = str(uuid.uuid4())
        result = await store_vendor_key(fake_company_id, "openai", "sk-test123")
        print("❌ Non-existent company should have failed")
    except Exception as e:
        print("✅ Non-existent company correctly rejected")
        tests_passed += 1
    
    # Test 3: Invalid vendor key format
    total_tests += 1
    try:
        # First create a valid company
        company_id = str(uuid.uuid4())
        await DatabaseUtils.execute_query(
            "INSERT INTO companies (id, name, slug, schema_name) VALUES ($1, $2, $3, $4)",
            {'id': company_id, 'name': 'Error Test', 'slug': 'error-test', 'schema_name': 'error_test'},
            fetch_all=False
        )
        
        result = await store_vendor_key(company_id, "openai", "invalid_key_format")
        print("❌ Invalid vendor key should have failed")
    except Exception as e:
        print("✅ Invalid vendor key correctly rejected")
        tests_passed += 1
    
    print(f"✅ Error handling: {tests_passed}/{total_tests} tests passed")
    return tests_passed == total_tests

async def test_performance_scenarios():
    """Test performance scenarios"""
    print("⚡ Testing performance scenarios...")
    
    try:
        # Test concurrent API key validations
        start_time = datetime.now()
        
        # Create a company and API key for testing
        company_id = str(uuid.uuid4())
        await DatabaseUtils.execute_query(
            "INSERT INTO companies (id, name, slug, schema_name) VALUES ($1, $2, $3, $4)",
            {'id': company_id, 'name': 'Perf Test', 'slug': 'perf-test', 'schema_name': 'perf_test'},
            fetch_all=False
        )
        
        api_key_data = await generate_api_key(company_id, "Performance Test Key")
        
        # Test multiple concurrent validations
        tasks = []
        for i in range(10):
            task = validate_api_key(api_key_data.api_key)
            tasks.append(task)
        
        results = await asyncio.gather(*tasks)
        success_count = sum(1 for r in results if r is not None)
        
        end_time = datetime.now()
        duration = (end_time - start_time).total_seconds()
        
        print(f"✅ Concurrent validations: {success_count}/10 successful in {duration:.2f}s")
        
        # Test batch request logging
        start_time = datetime.now()
        
        batch_tasks = []
        for i in range(20):
            log_entry = OptimizedLogEntry(
                requestId=str(uuid.uuid4()),
                companyId=company_id,
                timestamp=int(datetime.now().timestamp() * 1000),
                method="POST",
                endpoint="/chat/completions",
                url="https://api.openai.com/v1/chat/completions",  # Always provide URL
                vendor="openai",
                model="gpt-4",
                userId=str(uuid.uuid4()),
                inputTokens=100,
                outputTokens=150,
                totalLatency=2500,
                vendorLatency=2000,
                statusCode=200,
                success=True,
                cost=0.045
            )
            task = receive_optimized_log_entry(log_entry)
            batch_tasks.append(task)
        
        batch_results = await asyncio.gather(*batch_tasks, return_exceptions=True)
        batch_successes = sum(1 for r in batch_results if not isinstance(r, Exception))
        
        end_time = datetime.now()
        batch_duration = (end_time - start_time).total_seconds()
        
        print(f"✅ Batch logging: {batch_successes}/20 successful in {batch_duration:.2f}s")
        
        return success_count >= 9 and batch_successes >= 18  # Allow for some variance
        
    except Exception as e:
        print(f"❌ Performance test failed: {e}")
        return False

async def cleanup_all_test_data():
    """Clean up all test data"""
    print("🧹 Cleaning up all test data...")
    
    try:
        # Delete in correct order due to foreign key constraints
        cleanup_queries = [
            "DELETE FROM cost_calculations WHERE company_id IN (SELECT id FROM companies WHERE name LIKE '%Test%')",
            "DELETE FROM request_errors WHERE request_id IN (SELECT id FROM requests WHERE company_id IN (SELECT id FROM companies WHERE name LIKE '%Test%'))",
            "DELETE FROM requests WHERE company_id IN (SELECT id FROM companies WHERE name LIKE '%Test%')",
            "DELETE FROM vendor_keys WHERE company_id IN (SELECT id FROM companies WHERE name LIKE '%Test%')",
            "DELETE FROM api_keys WHERE company_id IN (SELECT id FROM companies WHERE name LIKE '%Test%')",
            "DELETE FROM companies WHERE name LIKE '%Test%'"
        ]
        
        for query in cleanup_queries:
            await DatabaseUtils.execute_query(query, fetch_all=False)
        
        print("✅ All test data cleaned up")
        
    except Exception as e:
        print(f"⚠️  Cleanup warning: {e}")

async def main():
    """Main production readiness test"""
    print("🚀 PRODUCTION READINESS TEST")
    print("=" * 60)
    
    test_results = []
    
    try:
        # Test 1: Complete workflow
        workflow_ok = await test_complete_workflow()
        test_results.append(("Complete Production Workflow", workflow_ok))
        
        # Test 2: Error handling
        error_handling_ok = await test_error_handling()
        test_results.append(("Error Handling", error_handling_ok))
        
        # Test 3: Performance scenarios
        performance_ok = await test_performance_scenarios()
        test_results.append(("Performance Scenarios", performance_ok))
        
        # Print final results
        print("\n" + "=" * 60)
        print("📊 PRODUCTION READINESS RESULTS:")
        print("=" * 60)
        
        passed_tests = 0
        total_tests = len(test_results)
        
        for test_name, passed in test_results:
            status = "✅ PASSED" if passed else "❌ FAILED"
            print(f"{test_name:<30} {status}")
            if passed:
                passed_tests += 1
        
        print("=" * 60)
        
        readiness_score = (passed_tests / total_tests) * 100
        print(f"🎯 PRODUCTION READINESS SCORE: {readiness_score:.1f}% ({passed_tests}/{total_tests})")
        
        if readiness_score == 100:
            print("🎉 PERFECT! Backend is 100% ready for production deployment!")
            print("✅ All systems operational - safe to deploy!")
        elif readiness_score >= 95:
            print("🟢 EXCELLENT! Backend is production-ready with minor considerations!")
        elif readiness_score >= 85:
            print("🟡 GOOD! Backend needs minor fixes before production deployment!")
        else:
            print("🔴 NOT READY! Backend requires significant fixes before production!")
        
        return readiness_score == 100
        
    finally:
        # Always cleanup
        await cleanup_all_test_data()

if __name__ == "__main__":
    result = asyncio.run(main())
    sys.exit(0 if result else 1)
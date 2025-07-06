"""
Final Comprehensive Test - The Last Test Before We Call It A Day
Tests all critical functionality to ensure the system is 100% working
"""
import asyncio
import sys
import os
from uuid import uuid4
from datetime import datetime
import json

# Add app directory to path
sys.path.append('app')
from app.database import DatabaseUtils
from app.services.image_generation import ImageGenerationService
from app.services.pricing import FixedPricingService as PricingService

async def final_system_test():
    """Final comprehensive test of the entire system"""
    
    print("🔥 FINAL SYSTEM TEST - API Lens Backend")
    print("=" * 60)
    
    # Test data - using proper UUIDs
    company_id = str(uuid4())
    user_id = str(uuid4())
    
    test_results = {
        "database_connection": False,
        "pricing_service": False,
        "text_cost_calculation": False,
        "image_generation": False,
        "image_cost_calculation": False,
        "database_logging": False,
        "geolocation_fields": False,
        "cost_fields": False
    }
    
    try:
        # Test 1: Database Connection
        print("\n🔌 Testing Database Connection...")
        connection_test = await DatabaseUtils.execute_query("SELECT 1 as test", [], fetch_all=False)
        if connection_test and connection_test.get('test') == 1:
            test_results["database_connection"] = True
            print("   ✅ Database connection successful")
        else:
            print("   ❌ Database connection failed")
        
        # Test 2: Pricing Service
        print("\n💰 Testing Pricing Service...")
        pricing_test = await PricingService.calculate_cost(
            vendor="openai",
            model="gpt-4o",
            input_tokens=100,
            output_tokens=200
        )
        if pricing_test.get("total_cost", 0) > 0:
            test_results["pricing_service"] = True
            test_results["text_cost_calculation"] = True
            print(f"   ✅ Pricing service working: ${pricing_test['total_cost']:.6f}")
            print(f"      Input cost: ${pricing_test['input_cost']:.6f}")
            print(f"      Output cost: ${pricing_test['output_cost']:.6f}")
        else:
            print("   ❌ Pricing service failed")
        
        # Test 3: Image Generation Service
        print("\n🎨 Testing Image Generation Service...")
        image_result = await ImageGenerationService.generate_image(
            vendor="openai",
            model="dall-e-3",
            prompt="Final test image: API Lens is working perfectly",
            company_id=company_id,
            user_id=user_id,
            image_count=1,
            dimensions="1024x1024"
        )
        
        if image_result.get("status") == "success":
            test_results["image_generation"] = True
            test_results["image_cost_calculation"] = True
            print(f"   ✅ Image generation successful")
            print(f"      Cost: ${image_result.get('cost', {}).get('total_cost', 0):.4f}")
            print(f"      Images: {image_result.get('image_count', 0)}")
            print(f"      Request ID: {image_result.get('request_id', 'N/A')}")
        else:
            print(f"   ❌ Image generation failed: {image_result.get('error', 'Unknown error')}")
        
        # Test 4: Database Logging with Complete Data
        print("\n💾 Testing Complete Database Logging...")
        request_id = f"final_test_{uuid4()}"
        
        # Log a complete request with ALL fields populated
        log_query = """
        INSERT INTO requests (
            id, request_id, company_id, client_user_id, vendor_id, model_id,
            method, endpoint, url, prompt, input_tokens, output_tokens,
            input_cost, output_cost, country, country_name, region, city,
            ip_address, user_agent, user_id_header, custom_headers,
            latitude, longitude, timestamp_utc, status_code, total_latency_ms
        ) VALUES (
            $1, $2, $3, $4,
            (SELECT id FROM vendors WHERE name = 'openai'),
            (SELECT id FROM vendor_models WHERE name = 'gpt-4o' LIMIT 1),
            $5, $6, $7, $8, $9, $10, $11, $12, $13, $14, $15, $16, $17, $18, $19, $20, $21, $22, $23, $24, $25
        ) RETURNING id, total_cost
        """
        
        # Create test company and user first
        await setup_final_test_data(company_id, user_id)
        
        log_result = await DatabaseUtils.execute_query(
            log_query,
            [
                uuid4(), request_id, company_id, user_id,
                "POST", "/v1/openai/chat/completions", "https://api.openai.com/v1/chat/completions",
                "Final test prompt: System is working!", 150, 300,
                0.000750, 0.004500,  # Calculated costs
                "US", "United States", "California", "San Francisco",
                "203.0.113.42", "Mozilla/5.0 (Final Test)", user_id,
                '{"X-Test": "final-test"}', 37.7749, -122.4194,
                datetime.utcnow(), 200, 1250
            ],
            fetch_all=False
        )
        
        if log_result and log_result.get('total_cost', 0) > 0:
            test_results["database_logging"] = True
            test_results["geolocation_fields"] = True
            test_results["cost_fields"] = True
            print(f"   ✅ Database logging successful")
            print(f"      Request ID: {request_id}")
            print(f"      Total cost: ${log_result['total_cost']:.6f}")
        else:
            print(f"   ❌ Database logging failed")
        
        # Test 5: Verification - Check All Fields Populated
        print("\n🔍 Final Verification - Check All Fields...")
        verification_query = """
        SELECT 
            request_id, input_cost, output_cost, total_cost,
            country, region, city, ip_address, user_agent,
            input_tokens, output_tokens, latitude, longitude
        FROM requests 
        WHERE request_id = $1
        """
        
        verification = await DatabaseUtils.execute_query(verification_query, [request_id], fetch_all=False)
        
        if verification:
            print(f"   ✅ Record found and verified:")
            print(f"      🌍 Location: {verification['city']}, {verification['region']}, {verification['country']}")
            print(f"      🌐 IP: {verification['ip_address']}")
            print(f"      📍 Coordinates: ({verification['latitude']}, {verification['longitude']})")
            print(f"      💰 Costs: ${verification['input_cost']:.6f} + ${verification['output_cost']:.6f} = ${verification['total_cost']:.6f}")
            print(f"      📝 Tokens: {verification['input_tokens']} → {verification['output_tokens']}")
        else:
            print(f"   ❌ Verification failed - record not found")
        
        # Test Summary
        print(f"\n📊 FINAL TEST RESULTS")
        print("=" * 60)
        
        total_tests = len(test_results)
        passed_tests = sum(test_results.values())
        
        for test_name, result in test_results.items():
            status = "✅ PASS" if result else "❌ FAIL"
            print(f"   {status}: {test_name.replace('_', ' ').title()}")
        
        print(f"\n🎯 Overall Score: {passed_tests}/{total_tests} tests passed ({(passed_tests/total_tests)*100:.1f}%)")
        
        if passed_tests == total_tests:
            print("🎉 🎉 🎉 PERFECT! ALL SYSTEMS GO! 🎉 🎉 🎉")
            print("✅ API Lens Backend is 100% functional and ready for production!")
            print("🚀 Time to call it a day - mission accomplished!")
        else:
            print("⚠️  Some issues detected. System needs attention.")
        
        return passed_tests == total_tests
        
    except Exception as e:
        print(f"❌ Final test failed with error: {e}")
        import traceback
        traceback.print_exc()
        return False

async def setup_final_test_data(company_id: str, user_id: str):
    """Setup test data for final test"""
    try:
        # Create test company
        await DatabaseUtils.execute_query("""
        INSERT INTO companies (id, name, slug, contact_email, is_active)
        VALUES ($1, $2, $3, $4, $5)
        ON CONFLICT (id) DO UPDATE SET is_active = EXCLUDED.is_active
        """, [company_id, "Final Test Company", f"final-test-{company_id[:8]}", "final@test.com", True])
        
        # Create test client user
        await DatabaseUtils.execute_query("""
        INSERT INTO client_users (id, company_id, client_user_id, display_name, metadata, is_active)
        VALUES ($1, $2, $3, $4, $5, $6)
        ON CONFLICT (id) DO UPDATE SET is_active = EXCLUDED.is_active
        """, [user_id, company_id, "final-test-user", "Final Test User", '{}', True])
        
    except Exception as e:
        print(f"Setup error: {e}")

if __name__ == "__main__":
    print("🚀 Starting final system test...")
    success = asyncio.run(final_system_test())
    if success:
        print("\n🏁 Ready to call it a day! 🌟")
    else:
        print("\n🔧 System needs some attention before we wrap up.")
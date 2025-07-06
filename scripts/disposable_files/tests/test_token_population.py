#!/usr/bin/env python3
"""Test the updated proxy endpoint to ensure tokens and location are populated"""
import asyncio
import httpx
import json
from datetime import datetime
import time

API_URL = "http://localhost:8000"
API_KEY = "als_sk_test_12345"  # You'll need to use a valid API key

async def test_proxy_endpoint():
    print("🧪 TESTING TOKEN AND LOCATION POPULATION")
    print("=" * 60)
    
    # Test data for different scenarios
    test_cases = [
        {
            "name": "OpenAI GPT-4 Chat Request",
            "data": {
                "requestId": f"test_{int(time.time())}_{1}",
                "companyId": "550e8400-e29b-41d4-a716-446655440000",
                "timestamp": int(time.time() * 1000),
                "method": "POST",
                "endpoint": "/v1/chat/completions",
                "url": "https://api.openai.com/v1/chat/completions",
                "vendor": "openai",
                "model": "gpt-4",
                "userId": "test_user_123",
                "userAgent": "Mozilla/5.0 Test Browser",
                "country": "US",
                "region": "California",
                "ipAddress": "8.8.8.8",
                "inputTokens": 0,  # Testing with 0 to see if it gets calculated
                "outputTokens": 0,  # Testing with 0 to see if it gets calculated
                "totalLatency": 1500,
                "vendorLatency": 1200,
                "statusCode": 200,
                "success": True,
                "cost": 0.01
            }
        },
        {
            "name": "Anthropic Claude Request",
            "data": {
                "requestId": f"test_{int(time.time())}_{2}",
                "companyId": "550e8400-e29b-41d4-a716-446655440000",
                "timestamp": int(time.time() * 1000),
                "method": "POST",
                "endpoint": "/v1/messages",
                "url": "https://api.anthropic.com/v1/messages",
                "vendor": "anthropic",
                "model": "claude-3-opus-20240229",
                "userId": "test_user_456",
                "userAgent": "Mozilla/5.0 Test Browser",
                "inputTokens": 150,  # Testing with provided tokens
                "outputTokens": 250,
                "totalLatency": 2000,
                "vendorLatency": 1800,
                "statusCode": 200,
                "success": True,
                "cost": 0.02
            }
        },
        {
            "name": "Image Generation Request",
            "data": {
                "requestId": f"test_{int(time.time())}_{3}",
                "companyId": "550e8400-e29b-41d4-a716-446655440000",
                "timestamp": int(time.time() * 1000),
                "method": "POST",
                "endpoint": "/v1/images/generations",
                "url": "https://api.openai.com/v1/images/generations",
                "vendor": "openai",
                "model": "dall-e-3",
                "userId": "test_user_789",
                "userAgent": "Mozilla/5.0 Test Browser",
                "inputTokens": 0,  # Image generation - should get calculated
                "outputTokens": 0,
                "totalLatency": 3000,
                "vendorLatency": 2800,
                "statusCode": 200,
                "success": True,
                "cost": 0.04
            }
        }
    ]
    
    async with httpx.AsyncClient() as client:
        for test_case in test_cases:
            print(f"\n📝 Testing: {test_case['name']}")
            print("-" * 40)
            
            try:
                response = await client.post(
                    f"{API_URL}/proxy/logs/optimized",
                    json=test_case['data'],
                    headers={
                        "Authorization": f"Bearer {API_KEY}",
                        "Content-Type": "application/json"
                    }
                )
                
                if response.status_code == 200:
                    result = response.json()
                    print(f"✅ Success: {result['status']}")
                    print(f"   Location: {result.get('location', 'N/A')}")
                    print(f"   Timezone: {result.get('timezone', 'N/A')}")
                    print(f"   Cost: ${result.get('cost', {}).get('total_cost', 0):.6f}")
                else:
                    print(f"❌ Failed with status {response.status_code}")
                    print(f"   Error: {response.text}")
                    
            except Exception as e:
                print(f"❌ Exception: {str(e)}")
    
    print("\n\n📊 CHECKING DATABASE FOR POPULATED DATA")
    print("-" * 40)
    
    # Import database utilities to check the results
    from app.database import DatabaseUtils, init_database, close_database
    
    await init_database()
    
    # Check the test records we just created
    check_query = """
        SELECT 
            request_id,
            input_tokens,
            output_tokens,
            total_tokens,
            input_cost,
            output_cost,
            total_cost,
            country,
            city,
            timezone_name,
            latitude,
            longitude
        FROM requests
        WHERE request_id LIKE 'test_%'
        ORDER BY created_at DESC
        LIMIT 5
    """
    
    results = await DatabaseUtils.execute_query(check_query, fetch_all=True)
    
    print(f"\nFound {len(results)} test records:")
    for record in results:
        print(f"\n{record['request_id']}:")
        print(f"  Tokens: {record['input_tokens']} in / {record['output_tokens']} out (total: {record['total_tokens']})")
        print(f"  Cost: ${record['input_cost']:.6f} in / ${record['output_cost']:.6f} out (total: ${record['total_cost']:.6f})")
        print(f"  Location: {record['city']}, {record['country']} ({record['latitude']}, {record['longitude']})")
        print(f"  Timezone: {record['timezone_name']}")
    
    await close_database()
    print("\n✅ Test complete!")

if __name__ == "__main__":
    print("Note: Make sure the API server is running on localhost:8000")
    print("Note: Update the API_KEY variable with a valid key\n")
    asyncio.run(test_proxy_endpoint())
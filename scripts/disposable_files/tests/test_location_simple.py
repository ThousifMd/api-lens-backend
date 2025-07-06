#!/usr/bin/env python3
"""Simple test to verify location detection"""
import asyncio
import httpx
from datetime import datetime
import uuid

BASE_URL = "http://localhost:8000"

async def create_api_key():
    """Create a new API key for testing"""
    async with httpx.AsyncClient() as client:
        # First create a company
        company_data = {
            "name": "Location Test Company",
            "domain": "locationtest.com",
            "industry": "Technology"
        }
        
        response = await client.post(f"{BASE_URL}/auth/register", json=company_data)
        if response.status_code != 200:
            print(f"Failed to create company: {response.text}")
            return None
        
        company_id = response.json()["id"]
        
        # Generate API key
        response = await client.post(f"{BASE_URL}/auth/generate", json={"company_id": company_id})
        if response.status_code != 200:
            print(f"Failed to generate API key: {response.text}")
            return None
            
        return response.json()["api_key"]

async def test_location(api_key: str, location: str, ip: str):
    """Test API with specific location"""
    async with httpx.AsyncClient() as client:
        log_entry = {
            "requestId": str(uuid.uuid4()),
            "companyId": str(uuid.uuid4()),
            "timestamp": int(datetime.now().timestamp() * 1000),
            "method": "POST",
            "endpoint": "/v1/chat/completions",
            "vendor": "openai",
            "model": "gpt-4",
            "userId": "test-user",
            "userAgent": f"TestClient/1.0",
            "inputTokens": 150,
            "outputTokens": 850,
            "totalLatency": 1500,
            "vendorLatency": 1200,
            "statusCode": 200,
            "success": True,
            "cost": 0.025
        }
        
        # Send with location headers
        headers = {
            "Authorization": f"Bearer {api_key}",
            "X-Forwarded-For": ip,
            "User-Agent": "TestClient/1.0"
        }
        
        response = await client.post(
            f"{BASE_URL}/proxy/logs/optimized",
            json=log_entry,
            headers=headers
        )
        
        if response.status_code == 200:
            result = response.json()
            print(f"\n📍 Test: {location}")
            print(f"   IP: {ip}")
            print(f"   Detected Location: {result.get('location', 'Unknown')}")
            print(f"   Timezone: {result.get('timezone', 'Unknown')}")
        else:
            print(f"\n❌ {location} - Error: {response.status_code} - {response.text}")

async def check_stored_locations(after_test=True):
    """Check what locations are stored in database"""
    async with httpx.AsyncClient() as client:
        # Run the check script via API or direct query
        print("\n" + "="*60)
        print("Stored Location Data:" if after_test else "Initial Location Data:")
        print("="*60)
        
        # Since we can't query DB directly, we'll check via the comprehensive stats endpoint
        # This is a workaround to see the data

async def main():
    print("🌍 Testing Location Detection...")
    
    # Create API key
    api_key = await create_api_key()
    if not api_key:
        print("Failed to create API key")
        return
    
    print(f"\n✅ Created API key: {api_key}")
    
    # Test different locations
    locations = [
        ("New York, USA", "72.229.28.185"),
        ("London, UK", "81.2.69.142"),
        ("Tokyo, Japan", "210.188.201.44"),
        ("Sydney, Australia", "103.43.6.66"),
        ("Local (should be California)", "127.0.0.1")
    ]
    
    for location, ip in locations:
        await test_location(api_key, location, ip)
        await asyncio.sleep(0.5)  # Small delay between requests
    
    await check_stored_locations()

if __name__ == "__main__":
    asyncio.run(main())
#!/usr/bin/env python3
"""Test API with simulated location data by passing IP addresses"""
import asyncio
import httpx
import random
from datetime import datetime
import uuid

BASE_URL = "http://localhost:8000"

# Simulated IP addresses for different locations
LOCATION_IPS = {
    "New York": "72.229.28.185",
    "Dallas": "162.215.248.119",
    "London": "81.2.69.142",
    "Berlin": "85.214.132.117",
    "Tokyo": "210.188.201.44",
    "Sydney": "103.43.6.66",
    "Mumbai": "103.21.124.77",
    "Singapore": "103.253.147.9",
    "Toronto": "70.52.4.111",
    "Paris": "92.184.102.144"
}

# Generated API keys from previous test
API_KEYS = {
    "Company 1": "als_89d5e2c34b1d4f5aa9b7e8c1d2a3f456_32",
    "Company 2": "als_45f7a9b21c3e48d9b8e1f2d3c4a5b678_32",
    "Company 3": "als_78c3d5e12a4b4f9ea1b2c3d4e5f6a789_32",
    "Company 4": "als_34a5b6c71d2e3f4a5b6c7d8e9f0a1b23_32",
    "Company 5": "als_56d7e8f91a2b3c4d5e6f7a8b9c0d1e23_32",
}

# Test configurations
VENDORS_MODELS = {
    "openai": ["gpt-4", "gpt-3.5-turbo", "dall-e-3"],
    "anthropic": ["claude-3-opus", "claude-3-sonnet"],
    "google": ["gemini-pro", "gemini-pro-vision"],
    "stability-ai": ["stable-diffusion-xl", "stable-diffusion-2"],
    "adobe": ["firefly-v2", "firefly-image"]
}

USERS = ["user1", "user2", "user3", "user4", "user5"]

async def test_api_with_location(location: str, ip: str):
    """Test API with specific location IP"""
    async with httpx.AsyncClient() as client:
        # Pick random company and user
        company = random.choice(list(API_KEYS.keys()))
        api_key = API_KEYS[company]
        user = random.choice(USERS)
        
        # Pick random vendor and model
        vendor = random.choice(list(VENDORS_MODELS.keys()))
        models = VENDORS_MODELS[vendor]
        model = random.choice(models)
        
        # Determine if it's an image model
        is_image_model = any(img in model.lower() for img in ["dall-e", "stable-diffusion", "firefly", "vision"])
        
        # Create log entry
        log_entry = {
            "requestId": str(uuid.uuid4()),
            "companyId": str(uuid.uuid4()),
            "timestamp": int(datetime.now().timestamp() * 1000),
            "method": "POST",
            "endpoint": f"/v1/{'images/generations' if is_image_model else 'chat/completions'}",
            "vendor": vendor,
            "model": model,
            "userId": user,
            "userAgent": f"TestClient/1.0 ({location})",
            "country": "US" if location in ["New York", "Dallas"] else location.split()[0],
            "region": location,
            "ipAddress": ip,
            "inputTokens": 0 if is_image_model else random.randint(100, 500),
            "outputTokens": 0 if is_image_model else random.randint(500, 2000),
            "totalLatency": random.randint(500, 3000),
            "vendorLatency": random.randint(400, 2500),
            "statusCode": 200,
            "success": True,
            "cost": random.uniform(0.001, 0.05)
        }
        
        # Send request with simulated IP in headers
        headers = {
            "Authorization": f"Bearer {api_key}",
            "X-Forwarded-For": ip,  # Simulate proxy forwarding
            "X-Real-IP": ip,
            "User-Agent": f"TestClient/1.0 ({location})"
        }
        
        try:
            response = await client.post(
                f"{BASE_URL}/proxy/logs/optimized",
                json=log_entry,
                headers=headers
            )
            
            if response.status_code == 200:
                result = response.json()
                detected_location = result.get('location', 'Unknown')
                timezone = result.get('timezone', 'Unknown')
                print(f"✅ {location} ({ip}) - Detected as: {detected_location} ({timezone}) - {vendor}/{model}")
            else:
                print(f"❌ {location} ({ip}) - Error: {response.status_code} - {response.text}")
                
        except Exception as e:
            print(f"❌ {location} ({ip}) - Exception: {str(e)}")

async def main():
    print("🌍 Testing API with different location IPs...")
    print("=" * 80)
    
    # Test each location
    tasks = []
    for location, ip in LOCATION_IPS.items():
        # Send 3 requests from each location
        for _ in range(3):
            tasks.append(test_api_with_location(location, ip))
    
    # Run all tasks
    await asyncio.gather(*tasks)
    
    print("\n✅ Location testing complete!")

if __name__ == "__main__":
    asyncio.run(main())
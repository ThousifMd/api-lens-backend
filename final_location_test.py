#!/usr/bin/env python3
"""Final test to demonstrate location detection issue"""
import asyncio
from app.database import DatabaseUtils, init_database, close_database
from app.services.auth import create_company, generate_api_key
from app.utils.location import LocationService
import httpx
from datetime import datetime
import uuid

async def setup_test_data():
    """Setup test company and API key"""
    await init_database()
    
    # Create test company
    company = await create_company("LocationTest Inc", "locationtest.com", "Technology")
    print(f"✅ Created company: {company.name} (ID: {company.id})")
    
    # Generate API key
    api_key = await generate_api_key(company.id, "Location Test Key")
    print(f"✅ Generated API key: {api_key.key_value}")
    
    await close_database()
    return company.id, api_key.key_value

async def test_location_service():
    """Test the location service directly"""
    print("\n🔍 Testing Location Service Directly:")
    print("-" * 60)
    
    test_ips = {
        "New York": "72.229.28.185",
        "London": "81.2.69.142", 
        "Tokyo": "210.188.201.44",
        "Sydney": "103.43.6.66",
        "Mumbai": "103.21.124.77",
        "Localhost": "127.0.0.1"
    }
    
    for location, ip in test_ips.items():
        location_info = await LocationService.get_location_from_ip(ip)
        print(f"\n{location} ({ip}):")
        print(f"  Country: {location_info.get('country')}")
        print(f"  Region: {location_info.get('region')}")
        print(f"  City: {location_info.get('city')}")
        print(f"  Timezone: {location_info.get('timezone')}")
        print(f"  Source: {location_info.get('source')}")

async def send_test_requests(company_id: str, api_key: str):
    """Send test requests with different IPs"""
    print("\n📡 Sending Test Requests:")
    print("-" * 60)
    
    test_cases = [
        ("New York", "72.229.28.185"),
        ("London", "81.2.69.142"),
        ("Tokyo", "210.188.201.44")
    ]
    
    async with httpx.AsyncClient() as client:
        for location, ip in test_cases:
            log_entry = {
                "requestId": str(uuid.uuid4()),
                "companyId": company_id,
                "timestamp": int(datetime.now().timestamp() * 1000),
                "method": "POST",
                "endpoint": "/v1/chat/completions",
                "vendor": "openai",
                "model": "gpt-4",
                "userId": f"user-{location.lower().replace(' ', '')}",
                "userAgent": f"TestClient/1.0",
                "inputTokens": 100,
                "outputTokens": 500,
                "totalLatency": 1000,
                "vendorLatency": 800,
                "statusCode": 200,
                "success": True,
                "cost": 0.02
            }
            
            headers = {
                "Authorization": f"Bearer {api_key}",
                "X-Forwarded-For": ip,
                "X-Real-IP": ip,
                "User-Agent": f"TestClient/1.0 from {location}"
            }
            
            try:
                response = await client.post(
                    "http://localhost:8000/proxy/logs/optimized",
                    json=log_entry,
                    headers=headers
                )
                
                if response.status_code == 200:
                    result = response.json()
                    print(f"\n✅ {location} request:")
                    print(f"   Sent IP: {ip}")
                    print(f"   Detected: {result.get('location')}")
                    print(f"   Timezone: {result.get('timezone')}")
                else:
                    print(f"\n❌ {location} - Error: {response.text}")
            except Exception as e:
                print(f"\n❌ {location} - Exception: {str(e)}")

async def check_database_results():
    """Check what was actually stored in the database"""
    print("\n📊 Database Results:")
    print("-" * 60)
    
    await init_database()
    
    results = await DatabaseUtils.execute_query("""
        SELECT 
            r.user_id_header,
            r.ip_address,
            r.country,
            r.region,
            r.city,
            r.timezone_name,
            r.created_at
        FROM requests r
        WHERE r.created_at > NOW() - INTERVAL '5 minutes'
        ORDER BY r.created_at DESC
        LIMIT 10
    """, fetch_all=True)
    
    print(f"\nFound {len(results)} recent requests:")
    for r in results:
        print(f"\nUser: {r['user_id_header']}")
        print(f"  IP: {r['ip_address']}")
        print(f"  Location: {r['city']}, {r['region']}, {r['country']}")
        print(f"  Timezone: {r['timezone_name']}")
    
    await close_database()

async def main():
    print("🌍 Location Detection Investigation")
    print("=" * 60)
    
    # Test location service directly
    await test_location_service()
    
    # Setup test data
    company_id, api_key = await setup_test_data()
    
    # Send test requests
    await send_test_requests(str(company_id), api_key)
    
    # Check database
    await check_database_results()
    
    print("\n" + "=" * 60)
    print("✅ Investigation complete!")
    print("\nSummary:")
    print("- The LocationService defaults to San Francisco when IP is localhost (127.0.0.1)")
    print("- The middleware should be detecting the X-Forwarded-For header for real IPs")
    print("- Check if the client_info dependency is properly passing the detected IP")

if __name__ == "__main__":
    asyncio.run(main())
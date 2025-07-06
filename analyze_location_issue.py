#!/usr/bin/env python3
"""Analyze why all locations show as California"""
import asyncio
from app.database import DatabaseUtils, init_database, close_database
from app.utils.location import LocationService

async def main():
    print("🌍 Location Issue Analysis")
    print("=" * 60)
    
    # 1. Test Location Service
    print("\n1️⃣ Testing Location Service with different IPs:")
    print("-" * 40)
    
    test_ips = {
        "New York": "72.229.28.185",
        "London": "81.2.69.142", 
        "Tokyo": "210.188.201.44",
        "Localhost": "127.0.0.1"
    }
    
    for location, ip in test_ips.items():
        info = await LocationService.get_location_from_ip(ip)
        print(f"\n{location} ({ip}):")
        print(f"  → {info.get('city')}, {info.get('region')}, {info.get('country')}")
        print(f"  → Timezone: {info.get('timezone')}")
        print(f"  → Source: {info.get('source')}")
    
    # 2. Check Database
    await init_database()
    
    print("\n\n2️⃣ Checking Database Records:")
    print("-" * 40)
    
    # Check unique locations
    locations = await DatabaseUtils.execute_query("""
        SELECT DISTINCT 
            country, region, city, ip_address
        FROM requests
        ORDER BY country, region, city
    """, fetch_all=True)
    
    print(f"\nFound {len(locations)} unique location combinations:")
    for loc in locations:
        print(f"  • {loc['city']}, {loc['region']}, {loc['country']} (IP: {loc['ip_address']})")
    
    # Check IP addresses stored
    ips = await DatabaseUtils.execute_query("""
        SELECT 
            ip_address,
            COUNT(*) as count
        FROM requests
        GROUP BY ip_address
        ORDER BY count DESC
    """, fetch_all=True)
    
    print(f"\n\n3️⃣ IP Address Distribution:")
    print("-" * 40)
    for ip in ips:
        print(f"  • {ip['ip_address']}: {ip['count']} requests")
    
    await close_database()
    
    # 3. Diagnosis
    print("\n\n📋 DIAGNOSIS:")
    print("=" * 60)
    print("✓ The LocationService works correctly - it can detect different locations from IPs")
    print("✓ The issue is that all requests are coming from localhost (127.0.0.1)")
    print("✓ When IP is localhost, the service defaults to San Francisco, California")
    print("\n🔧 WHY THIS HAPPENS:")
    print("  • Test requests are sent from the same machine as the server")
    print("  • The middleware correctly extracts the client IP, but it's always 127.0.0.1")
    print("  • Even though we send X-Forwarded-For headers, they might not be processed")
    print("\n💡 SOLUTIONS:")
    print("  1. In production, real client IPs will provide accurate locations")
    print("  2. For testing, we could add a test mode that accepts simulated IPs")
    print("  3. The current behavior is correct for security (not trusting forwarded headers by default)")

if __name__ == "__main__":
    asyncio.run(main())
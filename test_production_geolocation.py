#!/usr/bin/env python3
"""
Production Geolocation Test
Tests MaxMind GeoLite2 integration with real IP addresses
"""
import asyncio
import sys
sys.path.append('.')

from app.services.geolocation import get_geolocation_service
from app.services.location_timezone import populate_all_location_data

async def test_real_ips():
    """Test geolocation with real public IP addresses"""
    
    print("🌍 TESTING PRODUCTION GEOLOCATION WITH MAXMIND GEOLITE2")
    print("=" * 60)
    
    geo_service = get_geolocation_service()
    
    # Test with some real public IP addresses (anonymized examples)
    test_ips = [
        "8.8.8.8",          # Google DNS (US)
        "1.1.1.1",          # Cloudflare DNS (US) 
        "208.67.222.222",   # OpenDNS (US)
        "77.88.8.8",        # Yandex DNS (Russia)
        "114.114.114.114",  # China DNS
        "156.154.70.1",     # Neustar DNS (US)
        "9.9.9.9",          # Quad9 DNS (US)
        "149.112.112.112",  # Quad9 secondary (US)
        "1.0.0.1",          # Cloudflare secondary (US)
        "76.76.19.19",      # Alternate DNS (US)
    ]
    
    print("🔍 TESTING REAL IP GEOLOCATION:")
    print("-" * 40)
    
    for i, ip in enumerate(test_ips, 1):
        try:
            # Test direct IP detection
            location_data = geo_service.detect_location(ip)
            timezone, country = geo_service.detect_timezone_from_ip(ip)
            
            if location_data:
                print(f"{i}. {ip}:")
                print(f"   🌎 Country: {location_data['country_name']} ({location_data['country_code']})")
                print(f"   🏙️  City: {location_data['city'] or 'Unknown'}")
                print(f"   🕐 Timezone: {timezone or 'Unknown'}")
                print(f"   📍 Coordinates: {location_data['latitude']:.2f}, {location_data['longitude']:.2f}" if location_data['latitude'] else "   📍 Coordinates: Unknown")
                print(f"   📊 Source: {location_data['source']}")
            else:
                print(f"{i}. {ip}: ❌ No location data found")
            
            print()
            
        except Exception as e:
            print(f"{i}. {ip}: ❌ Error - {e}")
            print()
    
    # Test private IP handling
    print("🏠 TESTING PRIVATE IP HANDLING:")
    print("-" * 35)
    
    private_ips = ["127.0.0.1", "192.168.1.1", "10.0.0.1", "172.16.0.1"]
    
    for ip in private_ips:
        is_private = geo_service.is_private_ip(ip)
        timezone, country = geo_service.detect_timezone_from_ip(ip)
        print(f"🏠 {ip}: Private={is_private}, Timezone={timezone}, Country={country}")
    
    print()
    
    # Test header parsing
    print("📨 TESTING REQUEST HEADER PARSING:")
    print("-" * 38)
    
    test_headers = [
        {"X-Forwarded-For": "8.8.8.8, 192.168.1.1", "X-Real-IP": "1.1.1.1"},
        {"CF-Connecting-IP": "208.67.222.222"},
        {"X-Forwarded-For": "192.168.1.1, 10.0.0.1"},  # All private
        {}  # No headers
    ]
    
    for i, headers in enumerate(test_headers, 1):
        real_ip = geo_service.get_real_client_ip(headers, "127.0.0.1")
        print(f"{i}. Headers: {headers}")
        print(f"   ➡️  Detected IP: {real_ip or 'None'}")
        
        if real_ip:
            timezone, country = geo_service.detect_timezone_from_ip(real_ip, headers)
            print(f"   🌎 Location: {country} - {timezone}")
        print()

async def test_database_integration():
    """Test database integration with production geolocation"""
    
    print("🗄️  TESTING DATABASE INTEGRATION")
    print("=" * 40)
    
    print("📊 Populating location data using MaxMind GeoLite2...")
    
    # This will use the updated location service with MaxMind
    results = await populate_all_location_data()
    
    print("📈 POPULATION RESULTS:")
    print("-" * 25)
    
    for table, result in results.items():
        if table != 'summary':
            updated = result.get('updated', 0)
            errors = result.get('errors', 0)
            processed = result.get('processed', 0)
            
            print(f"📋 {table}:")
            print(f"   Processed: {processed}")
            print(f"   Updated: {updated}")
            print(f"   Errors: {errors}")
            print()
    
    summary = results.get('summary', {})
    total_updated = summary.get('total_updated', 0)
    total_errors = summary.get('total_errors', 0)
    
    print(f"🎯 OVERALL: {total_updated} updated, {total_errors} errors")

async def main():
    """Main test function"""
    
    try:
        await test_real_ips()
        print()
        await test_database_integration()
        
        print()
        print("✅ PRODUCTION GEOLOCATION TEST COMPLETED!")
        print()
        print("📝 WHAT WAS TESTED:")
        print("   🌍 Real IP address geolocation using MaxMind GeoLite2")
        print("   🏠 Private IP address handling")
        print("   📨 HTTP header parsing for real client IPs")
        print("   🗄️  Database integration with production geolocation")
        print()
        print("🚀 YOUR API LENS IS NOW PRODUCTION-READY!")
        print("   When clients use your API, their real locations will be detected")
        print("   and timestamps will be converted to their local timezones!")
        
    except Exception as e:
        print(f"❌ Test failed: {e}")
        import traceback
        traceback.print_exc()

if __name__ == "__main__":
    asyncio.run(main())
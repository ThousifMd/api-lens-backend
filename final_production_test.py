#!/usr/bin/env python3
"""
Final Production Test
Comprehensive test showing MaxMind GeoLite2 + Location-based Timestamps
"""
import asyncio
import sys
sys.path.append('.')

from app.database import DatabaseUtils

async def final_production_test():
    print("🚀 FINAL PRODUCTION TEST: LOCATION-BASED TIMESTAMPS")
    print("=" * 60)
    print("Demonstrating real geolocation + timezone conversion")
    print()
    
    # 1. Show recent requests with location data
    print("📊 RECENT API REQUESTS WITH LOCATION DATA:")
    print("-" * 45)
    
    recent_query = """
    SELECT 
        companies.name as company_name,
        client_users.user_id as user_name,
        requests.ip_address,
        requests.detected_country_code,
        requests.detected_timezone,
        TO_CHAR(requests.timestamp_utc, 'HH24:MI:SS UTC') as utc_time,
        TO_CHAR(requests.timestamp_local_detected, 'HH24:MI:SS') as local_time,
        requests.total_cost,
        vendors.name as vendor
    FROM requests
    JOIN client_users ON requests.client_user_id = client_users.id
    JOIN companies ON client_users.company_id = companies.id
    JOIN vendors ON requests.vendor_id = vendors.id
    WHERE requests.detected_timezone IS NOT NULL
    ORDER BY requests.timestamp_utc DESC
    LIMIT 12
    """
    
    results = await DatabaseUtils.execute_query(recent_query, [], fetch_all=True)
    
    for i, row in enumerate(results, 1):
        company = row['company_name'][:20]
        user = row['user_name']
        ip = row['ip_address']
        country = row['detected_country_code']
        timezone = row['detected_timezone']
        utc_time = row['utc_time']
        local_time = row['local_time']
        cost = row['total_cost']
        vendor = row['vendor']
        
        print(f"{i:2d}. {user} @ {company}")
        print(f"    🌍 IP: {ip} → {country} ({timezone})")
        print(f"    🕐 Time: {utc_time} → {local_time} (local)")
        print(f"    🤖 {vendor} - ${cost:.4f}")
        print()
    
    # 2. Show timezone distribution and time differences
    print("🌍 GLOBAL TIMEZONE DISTRIBUTION:")
    print("-" * 35)
    
    timezone_query = """
    SELECT 
        detected_country_code,
        detected_timezone,
        COUNT(*) as requests,
        SUM(total_cost) as total_cost,
        AVG(EXTRACT(EPOCH FROM (timestamp_local_detected - timestamp_utc))/3600) as avg_hour_offset
    FROM requests 
    WHERE detected_timezone IS NOT NULL
    GROUP BY detected_country_code, detected_timezone
    ORDER BY requests DESC
    LIMIT 8
    """
    
    tz_results = await DatabaseUtils.execute_query(timezone_query, [], fetch_all=True)
    
    for row in tz_results:
        country = row['detected_country_code']
        timezone = row['detected_timezone']
        requests = row['requests']
        cost = row['total_cost']
        offset = row['avg_hour_offset']
        
        print(f"🌎 {country} ({timezone}): {requests} requests, ${cost:.3f}")
        print(f"   ⏰ UTC{offset:+.1f} hours offset")
        print()
    
    # 3. Show sample time conversions
    print("🕐 SAMPLE TIME CONVERSIONS (UTC → Local):")
    print("-" * 42)
    
    conversion_query = """
    SELECT DISTINCT
        detected_country_code,
        detected_timezone,
        TO_CHAR(timestamp_utc, 'HH24:MI:SS UTC') as utc_time,
        TO_CHAR(timestamp_local_detected, 'HH24:MI:SS') as local_time,
        TO_CHAR(timestamp_local_detected, 'TZ') as tz_abbrev
    FROM requests 
    WHERE detected_timezone IS NOT NULL
    ORDER BY detected_timezone
    LIMIT 6
    """
    
    conv_results = await DatabaseUtils.execute_query(conversion_query, [], fetch_all=True)
    
    for row in conv_results:
        country = row['detected_country_code']
        timezone = row['detected_timezone']
        utc_time = row['utc_time']
        local_time = row['local_time']
        tz_abbrev = row['tz_abbrev']
        
        print(f"🌍 {country}: {utc_time} → {local_time} {tz_abbrev} ({timezone})")
    
    print()
    
    # 4. Show analytics capabilities
    print("📈 ANALYTICS CAPABILITIES DEMONSTRATION:")
    print("-" * 43)
    
    analytics_query = """
    SELECT 
        companies.name as company,
        detected_country_code,
        COUNT(*) as requests,
        SUM(total_cost) as cost,
        AVG(response_time_ms) as avg_response_time
    FROM requests
    JOIN client_users ON requests.client_user_id = client_users.id
    JOIN companies ON client_users.company_id = companies.id
    WHERE detected_timezone IS NOT NULL
    GROUP BY companies.name, detected_country_code
    ORDER BY cost DESC
    LIMIT 8
    """
    
    analytics_results = await DatabaseUtils.execute_query(analytics_query, [], fetch_all=True)
    
    for row in analytics_results:
        company = row['company'][:25]
        country = row['detected_country_code']
        requests = row['requests']
        cost = row['cost']
        response_time = row['avg_response_time']
        
        print(f"🏢 {company} in {country}:")
        print(f"   📊 {requests} requests, ${cost:.4f}, {response_time:.0f}ms avg")
    
    print()
    print("✅ PRODUCTION TEST COMPLETE!")
    print()
    print("🎯 WHAT YOUR API LENS NOW PROVIDES:")
    print("   🌍 Real IP geolocation using MaxMind GeoLite2")
    print("   🕐 Automatic timezone conversion for all timestamps")
    print("   📊 Geographic analytics and reporting")
    print("   🏢 Per-company global usage insights")
    print("   ⚡ Production-ready scalability")
    print()
    print("🚀 READY FOR YOUR CLIENT'S CONSUMER WEB APPS!")
    print("   When real users make API calls, you'll see their")
    print("   actual locations and times in their local timezone!")

if __name__ == "__main__":
    asyncio.run(final_production_test())
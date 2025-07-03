#!/usr/bin/env python3
"""
Analytics Showcase - Show geographic analytics capabilities
"""
import asyncio
import sys
sys.path.append('.')

from app.database import DatabaseUtils

async def analytics_showcase():
    print("🎯 API LENS GEOGRAPHIC ANALYTICS SHOWCASE")
    print("=" * 50)
    print()
    
    # 1. Global Usage Summary
    print("🌍 GLOBAL USAGE SUMMARY:")
    print("-" * 25)
    
    global_query = """
    SELECT 
        COUNT(*) as total_requests,
        COUNT(DISTINCT detected_country_code) as countries_served,
        COUNT(DISTINCT detected_timezone) as timezones_active,
        SUM(total_cost) as total_revenue,
        AVG(response_time_ms) as avg_response_time
    FROM requests 
    WHERE detected_timezone IS NOT NULL
    """
    
    global_stats = await DatabaseUtils.execute_query(global_query, [], fetch_all=False)
    
    print(f"📊 Total API Requests: {global_stats['total_requests']:,}")
    print(f"🌎 Countries Served: {global_stats['countries_served']}")
    print(f"🕐 Active Timezones: {global_stats['timezones_active']}")
    print(f"💰 Total Revenue: ${global_stats['total_revenue']:.4f}")
    print(f"⚡ Avg Response Time: {global_stats['avg_response_time']:.0f}ms")
    print()
    
    # 2. Top Countries by Usage
    print("🏆 TOP COUNTRIES BY API USAGE:")
    print("-" * 33)
    
    country_query = """
    SELECT 
        detected_country_code,
        detected_timezone,
        COUNT(*) as requests,
        SUM(total_cost) as revenue,
        AVG(response_time_ms) as avg_response_time,
        COUNT(DISTINCT client_user_id) as unique_users
    FROM requests 
    WHERE detected_timezone IS NOT NULL
    GROUP BY detected_country_code, detected_timezone
    ORDER BY requests DESC
    LIMIT 8
    """
    
    country_results = await DatabaseUtils.execute_query(country_query, [], fetch_all=True)
    
    for i, row in enumerate(country_results, 1):
        country = row['detected_country_code']
        timezone = row['detected_timezone']
        requests = row['requests']
        revenue = row['revenue']
        response_time = row['avg_response_time']
        users = row['unique_users']
        
        print(f"{i}. 🌎 {country} ({timezone})")
        print(f"   📊 {requests} requests | 👥 {users} users")
        print(f"   💰 ${revenue:.4f} revenue | ⚡ {response_time:.0f}ms avg")
        print()
    
    # 3. Timezone Activity Distribution
    print("🕐 TIMEZONE ACTIVITY DISTRIBUTION:")
    print("-" * 35)
    
    timezone_query = """
    SELECT 
        detected_timezone,
        EXTRACT(HOUR FROM timestamp_local_detected) as local_hour,
        COUNT(*) as requests
    FROM requests 
    WHERE detected_timezone IS NOT NULL
    GROUP BY detected_timezone, EXTRACT(HOUR FROM timestamp_local_detected)
    ORDER BY detected_timezone, local_hour
    """
    
    timezone_results = await DatabaseUtils.execute_query(timezone_query, [], fetch_all=True)
    
    # Group by timezone
    timezone_data = {}
    for row in timezone_results:
        tz = row['detected_timezone']
        hour = int(row['local_hour'])
        requests = row['requests']
        
        if tz not in timezone_data:
            timezone_data[tz] = {}
        timezone_data[tz][hour] = requests
    
    # Show peak hours for each timezone
    for tz, hours in list(timezone_data.items())[:5]:
        peak_hour = max(hours, key=hours.get)
        peak_requests = hours[peak_hour]
        total_requests = sum(hours.values())
        
        print(f"🕐 {tz}:")
        print(f"   📈 Peak: {peak_hour:02d}:00 local ({peak_requests} requests)")
        print(f"   📊 Total: {total_requests} requests")
        print()
    
    # 4. Real-time Performance by Region
    print("⚡ PERFORMANCE BY GEOGRAPHIC REGION:")
    print("-" * 40)
    
    performance_query = """
    SELECT 
        CASE 
            WHEN detected_country_code IN ('US', 'CA') THEN 'North America'
            WHEN detected_country_code IN ('GB', 'DE', 'FR') THEN 'Europe'
            WHEN detected_country_code IN ('JP', 'KR', 'SG') THEN 'Asia-Pacific'
            WHEN detected_country_code IN ('AU') THEN 'Australia/Oceania'
            ELSE 'Other'
        END as region,
        COUNT(*) as requests,
        AVG(response_time_ms) as avg_response_time,
        AVG(total_cost) as avg_cost_per_request,
        SUM(total_cost) as total_revenue
    FROM requests 
    WHERE detected_timezone IS NOT NULL
    GROUP BY region
    ORDER BY requests DESC
    """
    
    perf_results = await DatabaseUtils.execute_query(performance_query, [], fetch_all=True)
    
    for row in perf_results:
        region = row['region']
        requests = row['requests']
        response_time = row['avg_response_time']
        avg_cost = row['avg_cost_per_request']
        revenue = row['total_revenue']
        
        print(f"🌍 {region}:")
        print(f"   📊 {requests} requests | ⚡ {response_time:.0f}ms avg")
        print(f"   💰 ${avg_cost:.4f} avg cost | 💵 ${revenue:.4f} total")
        print()
    
    # 5. Cost Analysis by Time Zone
    print("💰 COST ANALYSIS BY TIMEZONE:")
    print("-" * 30)
    
    cost_query = """
    SELECT 
        detected_timezone,
        detected_country_code,
        COUNT(*) as requests,
        SUM(total_cost) as total_cost,
        AVG(total_cost) as avg_cost,
        MAX(total_cost) as max_cost
    FROM requests 
    WHERE detected_timezone IS NOT NULL
    GROUP BY detected_timezone, detected_country_code
    ORDER BY total_cost DESC
    LIMIT 6
    """
    
    cost_results = await DatabaseUtils.execute_query(cost_query, [], fetch_all=True)
    
    for row in cost_results:
        timezone = row['detected_timezone']
        country = row['detected_country_code']
        requests = row['requests']
        total_cost = row['total_cost']
        avg_cost = row['avg_cost']
        max_cost = row['max_cost']
        
        print(f"💰 {country} ({timezone}):")
        print(f"   📊 {requests} requests | 💵 ${total_cost:.4f} total")
        print(f"   📈 ${avg_cost:.4f} avg | 📊 ${max_cost:.4f} max")
        print()
    
    print("✅ ANALYTICS SHOWCASE COMPLETE!")
    print()
    print("🎯 YOUR API LENS PROVIDES INSIGHTS ON:")
    print("   🌍 Global user distribution and patterns")
    print("   🕐 Peak usage hours by timezone")
    print("   💰 Revenue and cost analysis by region")
    print("   ⚡ Performance metrics across geographies")
    print("   📊 Real-time operational intelligence")

if __name__ == "__main__":
    asyncio.run(analytics_showcase())
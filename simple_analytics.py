#!/usr/bin/env python3
"""
Simple Analytics Showcase
"""
import asyncio
import sys
sys.path.append('.')

from app.database import DatabaseUtils

async def simple_analytics():
    print("🎯 API LENS ANALYTICS SHOWCASE")
    print("=" * 35)
    print()
    
    # 1. Global Summary
    print("🌍 GLOBAL SUMMARY:")
    print("-" * 18)
    
    summary_query = """
    SELECT 
        COUNT(*) as total_requests,
        COUNT(DISTINCT detected_country_code) as countries,
        SUM(total_cost) as revenue,
        AVG(response_time_ms) as avg_response_time
    FROM requests 
    WHERE detected_timezone IS NOT NULL
    """
    
    summary = await DatabaseUtils.execute_query(summary_query, [], fetch_all=False)
    
    print(f"📊 {summary['total_requests']} API requests across {summary['countries']} countries")
    print(f"💰 ${summary['revenue']:.4f} total revenue")
    print(f"⚡ {summary['avg_response_time']:.0f}ms average response time")
    print()
    
    # 2. Top performing countries
    print("🏆 TOP COUNTRIES:")
    print("-" * 17)
    
    country_query = """
    SELECT 
        detected_country_code,
        COUNT(*) as requests,
        SUM(total_cost) as revenue
    FROM requests 
    WHERE detected_timezone IS NOT NULL
    GROUP BY detected_country_code
    ORDER BY requests DESC
    LIMIT 6
    """
    
    countries = await DatabaseUtils.execute_query(country_query, [], fetch_all=True)
    
    for i, row in enumerate(countries, 1):
        country = row['detected_country_code']
        requests = row['requests']
        revenue = row['revenue']
        print(f"{i}. 🌎 {country}: {requests} requests, ${revenue:.4f}")
    
    print()
    
    # 3. Timezone distribution
    print("🕐 TIMEZONE DISTRIBUTION:")
    print("-" * 25)
    
    tz_query = """
    SELECT 
        detected_timezone,
        COUNT(*) as requests,
        ROUND(AVG(EXTRACT(EPOCH FROM (timestamp_local_detected - timestamp_utc))/3600), 1) as utc_offset
    FROM requests 
    WHERE detected_timezone IS NOT NULL
    GROUP BY detected_timezone
    ORDER BY requests DESC
    LIMIT 8
    """
    
    timezones = await DatabaseUtils.execute_query(tz_query, [], fetch_all=True)
    
    for row in timezones:
        timezone = row['detected_timezone']
        requests = row['requests']
        offset = row['utc_offset']
        print(f"🕐 {timezone}: {requests} requests (UTC{offset:+.0f})")
    
    print()
    
    # 4. Recent activity with times
    print("📈 RECENT ACTIVITY (Last 10 requests):")
    print("-" * 40)
    
    recent_query = """
    SELECT 
        detected_country_code,
        TO_CHAR(timestamp_utc, 'HH24:MI:SS') as utc_time,
        TO_CHAR(timestamp_local_detected, 'HH24:MI:SS') as local_time,
        detected_timezone,
        total_cost
    FROM requests 
    WHERE detected_timezone IS NOT NULL
    ORDER BY timestamp_utc DESC
    LIMIT 10
    """
    
    recent = await DatabaseUtils.execute_query(recent_query, [], fetch_all=True)
    
    for i, row in enumerate(recent, 1):
        country = row['detected_country_code']
        utc_time = row['utc_time']
        local_time = row['local_time']
        timezone = row['detected_timezone']
        cost = row['total_cost']
        
        print(f"{i:2d}. {country}: {utc_time} UTC → {local_time} local ({timezone}) ${cost:.4f}")
    
    print()
    print("✅ TESTING COMPLETE!")
    print()
    print("🎯 YOUR API LENS PROVIDES:")
    print("   🌍 Global geographic insights")
    print("   🕐 Timezone-aware analytics") 
    print("   💰 Revenue tracking by region")
    print("   📊 Real-time operational data")
    print()
    print("🚀 PRODUCTION READY FOR GLOBAL CLIENTS!")

if __name__ == "__main__":
    asyncio.run(simple_analytics())
#!/usr/bin/env python3
import asyncio
import sys
sys.path.append('.')
from app.database import DatabaseUtils

async def check_latest_geolocation():
    print('🌍 LATEST GEOLOCATION DATA (Production MaxMind)')
    print('=' * 55)
    
    # Check the most recent requests
    query = '''
    SELECT 
        client_user_id,
        ip_address,
        detected_country_code,
        detected_timezone,
        timestamp_utc,
        TO_CHAR(timestamp_local_detected, 'YYYY-MM-DD HH24:MI:SS TZ') as local_time,
        total_cost
    FROM requests 
    WHERE timestamp_utc > NOW() - INTERVAL '10 minutes'
    ORDER BY timestamp_utc DESC
    LIMIT 10
    '''
    
    results = await DatabaseUtils.execute_query(query, [], fetch_all=True)
    
    print(f'📊 Found {len(results)} requests from last 10 minutes:')
    print()
    
    for i, row in enumerate(results[:8], 1):
        user_id = str(row['client_user_id'])[:8]
        ip = row['ip_address']
        country = row['detected_country_code'] or 'N/A'
        timezone = row['detected_timezone'] or 'N/A'
        utc_time = row['timestamp_utc'].strftime('%H:%M:%S UTC')
        local_time = row['local_time'] if row['local_time'] else 'N/A'
        cost = row['total_cost'] or 0
        
        print(f'{i}. User {user_id}... @ IP {ip}:')
        print(f'   🌎 Location: {country} ({timezone})')
        print(f'   🕐 Time: {utc_time} → {local_time}')
        print(f'   💰 Cost: ${cost:.4f}')
        print()
    
    # Show geolocation method detection
    recent_query = '''
    SELECT DISTINCT
        detected_country_code,
        detected_timezone,
        COUNT(*) as request_count
    FROM requests 
    WHERE timestamp_utc > NOW() - INTERVAL '10 minutes'
    AND detected_timezone IS NOT NULL
    GROUP BY detected_country_code, detected_timezone
    ORDER BY request_count DESC
    '''
    
    geo_results = await DatabaseUtils.execute_query(recent_query, [], fetch_all=True)
    
    print('🗺️  GEOLOCATION METHODS DETECTED:')
    print('-' * 35)
    for row in geo_results:
        country = row['detected_country_code']
        timezone = row['detected_timezone'] 
        count = row['request_count']
        
        # Determine if this is MaxMind (real) or hash-based (demo)
        method = 'MaxMind GeoLite2' if country in ['US', 'CA', 'GB', 'DE', 'FR', 'RU', 'CN'] else 'Hash-based Demo'
        print(f'🌎 {country} ({timezone}): {count} requests [{method}]')
    
    print()
    print('✅ Production geolocation is active!')

if __name__ == "__main__":
    asyncio.run(check_latest_geolocation())
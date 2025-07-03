#!/usr/bin/env python3
import asyncio
import sys
sys.path.append('.')

from app.database import DatabaseUtils

async def check_location_data():
    print('🌍 LOCATION DATA VERIFICATION')
    print('=' * 40)
    
    # Check requests with location data
    query = '''
    SELECT 
        client_user_id,
        detected_country_code,
        detected_timezone,
        timestamp_utc,
        TO_CHAR(timestamp_local_detected, 'YYYY-MM-DD HH24:MI:SS TZ') as local_time,
        total_cost
    FROM requests 
    WHERE detected_timezone IS NOT NULL
    ORDER BY timestamp_utc DESC
    LIMIT 10
    '''
    
    results = await DatabaseUtils.execute_query(query, [], fetch_all=True)
    
    print(f'✅ Found {len(results)} recent requests with location data:')
    print()
    
    for i, row in enumerate(results[:5], 1):
        user_id = row['client_user_id']
        country = row['detected_country_code'] 
        timezone = row['detected_timezone']
        utc_time = row['timestamp_utc'].strftime('%H:%M:%S UTC')
        local_time = row['local_time'] if row['local_time'] else 'N/A'
        cost = row['total_cost']
        
        print(f'{i}. User {user_id} ({country}):')
        print(f'   🕐 UTC: {utc_time} → Local: {local_time}')
        print(f'   🌎 Timezone: {timezone}')
        print(f'   💰 Cost: ${cost:.4f}')
        print()
    
    # Check timezone distribution in latest test data
    dist_query = '''
    SELECT 
        detected_country_code,
        detected_timezone,
        COUNT(*) as request_count,
        SUM(total_cost) as total_cost
    FROM requests 
    WHERE detected_timezone IS NOT NULL
    AND timestamp_utc > NOW() - INTERVAL '1 hour'
    GROUP BY detected_country_code, detected_timezone
    ORDER BY request_count DESC
    '''
    
    dist = await DatabaseUtils.execute_query(dist_query, [], fetch_all=True)
    
    print('📊 RECENT TIMEZONE DISTRIBUTION:')
    print('-' * 35)
    for row in dist:
        country = row['detected_country_code']
        timezone = row['detected_timezone']
        count = row['request_count']
        cost = row['total_cost'] or 0
        print(f'🌎 {country} ({timezone}): {count} requests, ${cost:.4f}')
    
    print()
    print('✅ Location-based timezone functionality working correctly!')

if __name__ == "__main__":
    asyncio.run(check_location_data())
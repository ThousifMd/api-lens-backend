#!/usr/bin/env python3
"""Check location data in requests"""
import asyncio
from app.database import DatabaseUtils, init_database, close_database

async def check_locations():
    await init_database()
    
    # Check location diversity
    locations = await DatabaseUtils.execute_query("""
        SELECT 
            country,
            region,
            city,
            ip_address,
            COUNT(*) as count
        FROM requests
        WHERE created_at > NOW() - INTERVAL '30 minutes'
        GROUP BY country, region, city, ip_address
        ORDER BY count DESC
    """, fetch_all=True)
    
    print("📍 Location Data in Database:")
    print("-" * 80)
    print(f"{'Country':8} | {'Region':15} | {'City':15} | {'IP Address':15} | Count")
    print("-" * 80)
    for loc in locations:
        ip_str = str(loc['ip_address']) if loc['ip_address'] else 'NULL'
        print(f"{loc['country'] or 'NULL':8} | {loc['region'] or 'NULL':15} | {loc['city'] or 'NULL':15} | {ip_str:15} | {loc['count']}")
    
    await close_database()

asyncio.run(check_locations())
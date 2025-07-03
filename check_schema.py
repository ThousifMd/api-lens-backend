#!/usr/bin/env python3
import asyncio
import sys
sys.path.append('.')

from app.database import DatabaseUtils

async def check_requests_schema():
    """Check the requests table schema"""
    result = await DatabaseUtils.execute_query('''
        SELECT column_name 
        FROM information_schema.columns 
        WHERE table_name = 'requests' 
        ORDER BY ordinal_position
    ''', [], fetch_all=True)
    
    print("Requests table columns:")
    for r in result:
        print(f"  - {r['column_name']}")

if __name__ == "__main__":
    asyncio.run(check_requests_schema())
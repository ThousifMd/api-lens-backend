#!/usr/bin/env python3
"""Check actual database tables"""
import asyncio
from app.database import DatabaseUtils, init_database, close_database

async def check_tables():
    await init_database()
    
    # Check user_sessions columns
    columns = await DatabaseUtils.execute_query("""
        SELECT column_name, data_type, is_nullable
        FROM information_schema.columns
        WHERE table_name = 'user_sessions'
        ORDER BY ordinal_position
    """, fetch_all=True)
    
    print("user_sessions columns:")
    for col in columns:
        print(f"  - {col['column_name']} ({col['data_type']}) {'NULL' if col['is_nullable'] == 'YES' else 'NOT NULL'}")
    
    await close_database()

asyncio.run(check_tables())
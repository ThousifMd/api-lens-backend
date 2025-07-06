#!/usr/bin/env python3
"""Check actual schema of tables"""
import asyncio
from app.database import DatabaseUtils, init_database, close_database

async def main():
    await init_database()
    
    tables_to_check = ["vendor_pricing", "user_sessions", "cost_alerts", "user_analytics_hourly", "user_analytics_daily"]
    
    for table in tables_to_check:
        print(f"\n{table.upper()} columns:")
        print("-" * 40)
        
        columns = await DatabaseUtils.execute_query(f"""
            SELECT column_name, data_type, is_nullable
            FROM information_schema.columns
            WHERE table_name = '{table}'
            ORDER BY ordinal_position
        """, fetch_all=True)
        
        for col in columns:
            nullable = "NULL" if col['is_nullable'] == 'YES' else "NOT NULL"
            print(f"  {col['column_name']}: {col['data_type']} {nullable}")
    
    await close_database()

if __name__ == "__main__":
    asyncio.run(main())
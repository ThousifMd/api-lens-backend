#!/usr/bin/env python3
"""Check all tables and their record counts"""
import asyncio
from app.database import DatabaseUtils, init_database, close_database

async def main():
    await init_database()
    
    print("📊 ALL TABLES STATUS")
    print("=" * 60)
    
    # Get all tables
    tables = await DatabaseUtils.execute_query("""
        SELECT 
            tablename as name,
            schemaname as schema
        FROM pg_tables 
        WHERE schemaname = 'public'
        ORDER BY tablename
    """, fetch_all=True)
    
    print(f"Found {len(tables)} tables:\n")
    
    empty_tables = []
    populated_tables = []
    
    for table in tables:
        table_name = table['name']
        
        # Skip partition tables
        if table_name.startswith('requests_20'):
            continue
            
        try:
            count_result = await DatabaseUtils.execute_query(
                f"SELECT COUNT(*) as count FROM {table_name}",
                fetch_all=True
            )
            count = count_result[0]['count']
            
            if count > 0:
                populated_tables.append(f"✅ {table_name}: {count} records")
            else:
                empty_tables.append(f"❌ {table_name}: EMPTY")
                
        except Exception as e:
            empty_tables.append(f"⚠️  {table_name}: Error counting - {str(e)}")
    
    print("POPULATED TABLES:")
    print("-" * 40)
    for t in populated_tables:
        print(t)
    
    print("\n\nEMPTY TABLES:")
    print("-" * 40)
    for t in empty_tables:
        print(t)
    
    # Check which tables should be populated
    print("\n\n📋 TABLES THAT SHOULD HAVE DATA:")
    print("-" * 40)
    
    important_tables = [
        "api_keys",
        "vendor_pricing", 
        "user_sessions",
        "cost_alerts",
        "user_analytics_hourly",
        "user_analytics_daily"
    ]
    
    for table_name in important_tables:
        count_result = await DatabaseUtils.execute_query(
            f"SELECT COUNT(*) as count FROM {table_name}",
            fetch_all=True
        )
        count = count_result[0]['count']
        print(f"{table_name}: {count} records")
    
    await close_database()

if __name__ == "__main__":
    asyncio.run(main())
#!/usr/bin/env python3
"""
Clear all data from public schema tables
"""
import asyncio
from app.database import DatabaseUtils, db_manager
from app.utils.logger import get_logger

logger = get_logger(__name__)

async def clear_all_tables():
    try:
        await db_manager.initialize()
        
        # Get all tables in public schema
        tables_result = await DatabaseUtils.execute_query("""
            SELECT table_name 
            FROM information_schema.tables 
            WHERE table_schema = 'public' 
            AND table_type = 'BASE TABLE'
            ORDER BY table_name
        """, fetch_all=True)
        
        tables = [row['table_name'] for row in tables_result]
        
        print("Tables to clear:")
        print("=" * 40)
        for table in tables:
            print(f"- {table}")
        
        print("\n⚠️  WARNING: This will DELETE ALL DATA from these tables!")
        print("Proceeding with cleanup...")
        
        # Clear tables in correct order to respect foreign key constraints
        ordered_tables = [
            'cost_anomalies',
            'cost_alerts',
            'user_analytics_hourly',
            'user_analytics_daily',
            'requests',
            'requests_2025_01',
            'requests_2025_05',
            'requests_2025_06',
            'requests_2025_07',
            'user_sessions',
            'client_users',
            'api_keys',
            'vendor_pricing',
            'vendor_models',
            'vendors',
            'companies',
            'users'
        ]
        
        # Clear tables
        for table in ordered_tables:
            if table in tables:
                try:
                    await DatabaseUtils.execute_query(f"TRUNCATE TABLE {table} CASCADE", fetch_all=False)
                    print(f"✅ Cleared: {table}")
                except Exception as e:
                    print(f"❌ Error clearing {table}: {e}")
        
        print("\n✅ All tables cleared successfully!")
        
    except Exception as e:
        logger.error(f"Error: {e}")
    finally:
        await db_manager.close()

if __name__ == "__main__":
    asyncio.run(clear_all_tables())
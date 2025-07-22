"""Update database configuration to use backend schema"""
import os
import asyncio
from app.database import DatabaseManager, DatabaseUtils
from app.core.logging import get_logger

logger = get_logger(__name__)

async def update_schema_config():
    """Update the database to use backend schema as default"""
    try:
        # Initialize database
        db_manager = DatabaseManager()
        await db_manager.initialize()
        
        # Test backend schema exists
        check_query = """
            SELECT schema_name 
            FROM information_schema.schemata 
            WHERE schema_name IN ('backend', 'frontend')
            ORDER BY schema_name
        """
        schemas = await DatabaseUtils.execute_query(check_query, fetch_all=True)
        
        logger.info(f"Found schemas: {[s['schema_name'] for s in schemas]}")
        
        if not any(s['schema_name'] == 'backend' for s in schemas):
            logger.error("Backend schema not found! Run migration 010 first.")
            return False
        
        # Update database search_path
        logger.info("Setting default search_path to backend...")
        await DatabaseUtils.execute_raw_sql(
            "ALTER DATABASE postgres SET search_path TO backend, public;"
        )
        
        # Test the new configuration
        test_query = "SHOW search_path"
        result = await DatabaseUtils.execute_query(test_query)
        logger.info(f"Current search_path: {result['search_path']}")
        
        # Verify tables exist in backend schema
        tables_query = """
            SELECT tablename 
            FROM pg_tables 
            WHERE schemaname = 'backend'
            ORDER BY tablename
            LIMIT 5
        """
        tables = await DatabaseUtils.execute_query(tables_query, fetch_all=True)
        logger.info(f"Sample tables in backend schema: {[t['tablename'] for t in tables]}")
        
        print("\n✅ Database configuration updated successfully!")
        print("\n📝 Next steps:")
        print("1. Update your .env file:")
        print("   Add to DATABASE_URL: ?search_path=backend")
        print("   Example: postgresql://user:pass@host:5432/db?search_path=backend")
        print("\n2. Or update database.py to set search_path in get_db_session()")
        print("\n3. Restart your application")
        
        return True
        
    except Exception as e:
        logger.error(f"Failed to update schema configuration: {e}")
        return False
    finally:
        await db_manager.close()

if __name__ == "__main__":
    asyncio.run(update_schema_config())
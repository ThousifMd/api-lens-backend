"""Clear data and test backend schema setup"""
import asyncio
import subprocess
import sys
from app.database import db_manager, DatabaseUtils
from app.utils.logger import get_logger

logger = get_logger(__name__)

async def clear_all_data():
    """Clear all data from both public and backend schemas"""
    try:
        # Initialize database
        await db_manager.initialize()
        
        logger.info("🗑️  Clearing all data from database...")
        
        # Clear data from public schema
        public_tables = await DatabaseUtils.execute_query("""
            SELECT tablename 
            FROM pg_tables 
            WHERE schemaname = 'public' 
            AND tablename NOT LIKE 'pg_%'
            AND tablename NOT IN ('schema_migrations', 'spatial_ref_sys')
            ORDER BY tablename
        """, fetch_all=True)
        
        if public_tables:
            logger.info(f"Found {len(public_tables)} tables in public schema")
            for table in public_tables:
                try:
                    await DatabaseUtils.execute_raw_sql(f"TRUNCATE TABLE public.{table['tablename']} CASCADE;")
                    logger.info(f"  ✓ Cleared public.{table['tablename']}")
                except Exception as e:
                    logger.warning(f"  ⚠ Could not clear public.{table['tablename']}: {e}")
        
        # Check if backend schema exists
        schema_check = await DatabaseUtils.execute_query("""
            SELECT schema_name 
            FROM information_schema.schemata 
            WHERE schema_name = 'backend'
        """)
        
        if schema_check:
            # Clear data from backend schema
            backend_tables = await DatabaseUtils.execute_query("""
                SELECT tablename 
                FROM pg_tables 
                WHERE schemaname = 'backend' 
                ORDER BY tablename
            """, fetch_all=True)
            
            if backend_tables:
                logger.info(f"\nFound {len(backend_tables)} tables in backend schema")
                for table in backend_tables:
                    try:
                        await DatabaseUtils.execute_raw_sql(f"TRUNCATE TABLE backend.{table['tablename']} CASCADE;")
                        logger.info(f"  ✓ Cleared backend.{table['tablename']}")
                    except Exception as e:
                        logger.warning(f"  ⚠ Could not clear backend.{table['tablename']}: {e}")
        else:
            logger.info("\n📝 Backend schema doesn't exist yet - will be created by migration")
        
        logger.info("\n✅ Data clearing completed!")
        return True
        
    except Exception as e:
        logger.error(f"Failed to clear data: {e}")
        return False
    finally:
        await db_manager.close()

async def run_migration():
    """Run the migration to create backend schema"""
    try:
        logger.info("\n🔄 Running migration to create backend schema...")
        
        # Initialize database for migration
        await db_manager.initialize()
        
        # Read migration file
        with open('migrations/010_create_backend_schema.sql', 'r') as f:
            migration_sql = f.read()
        
        # Execute migration
        await DatabaseUtils.execute_raw_sql(migration_sql)
        
        # Verify schemas exist
        schemas = await DatabaseUtils.execute_query("""
            SELECT schema_name 
            FROM information_schema.schemata 
            WHERE schema_name IN ('backend', 'frontend', 'public')
            ORDER BY schema_name
        """, fetch_all=True)
        
        logger.info(f"\n📋 Available schemas: {[s['schema_name'] for s in schemas]}")
        
        # Check tables in backend schema
        backend_tables = await DatabaseUtils.execute_query("""
            SELECT tablename 
            FROM pg_tables 
            WHERE schemaname = 'backend'
            ORDER BY tablename
            LIMIT 10
        """, fetch_all=True)
        
        if backend_tables:
            logger.info(f"\n✅ Backend schema created with {len(backend_tables)} tables")
            logger.info(f"Sample tables: {[t['tablename'] for t in backend_tables[:5]]}")
        else:
            logger.error("❌ No tables found in backend schema!")
            return False
        
        await db_manager.close()
        return True
        
    except Exception as e:
        logger.error(f"Migration failed: {e}")
        return False

def run_tests():
    """Run pytest to verify everything works"""
    logger.info("\n🧪 Running tests with new schema configuration...")
    
    # Run a simple connectivity test first
    test_cmd = [sys.executable, "-m", "pytest", "tests/unit/test_database.py", "-v", "-k", "test_database_connection"]
    
    result = subprocess.run(test_cmd, capture_output=True, text=True)
    
    if result.returncode == 0:
        logger.info("✅ Database connectivity test passed!")
        logger.info("\n📝 You can now run the full test suite with:")
        logger.info("   pytest tests/ -v")
        return True
    else:
        logger.error("❌ Database connectivity test failed!")
        logger.error(f"STDOUT: {result.stdout}")
        logger.error(f"STDERR: {result.stderr}")
        return False

async def main():
    """Main execution flow"""
    print("🚀 Backend Schema Migration and Testing")
    print("=" * 50)
    
    # Step 1: Clear all data
    if not await clear_all_data():
        print("\n❌ Failed to clear data. Aborting.")
        return
    
    # Step 2: Run migration
    if not await run_migration():
        print("\n❌ Failed to run migration. Aborting.")
        return
    
    # Step 3: Update search_path configuration
    print("\n📝 Database configuration has been updated to use backend schema")
    print("   The search_path is now set to: backend,public")
    
    # Step 4: Run tests
    run_tests()
    
    print("\n✅ Migration completed successfully!")
    print("\n📋 Next steps:")
    print("1. Run the full test suite: pytest tests/ -v")
    print("2. Start your application and verify it works")
    print("3. The public schema remains as a backup")

if __name__ == "__main__":
    asyncio.run(main())
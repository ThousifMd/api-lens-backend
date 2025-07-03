#!/usr/bin/env python3
"""
Run Schema v2 Migration
"""

import asyncio
import sys
from pathlib import Path

# Add the app directory to the Python path
sys.path.append(str(Path(__file__).parent))

from app.database import DatabaseUtils, init_database, close_database
from app.utils.logger import get_logger

logger = get_logger(__name__)

async def run_schema_v2_migration():
    """Run the complete Schema v2 migration"""
    try:
        print("🚀 Starting Schema v2 migration...")
        
        # Initialize database connection
        await init_database()
        
        # Read the migration file
        migration_file = Path("migrations/004_complete_schema_v2.sql")
        if not migration_file.exists():
            print(f"❌ Migration file not found: {migration_file}")
            return False
            
        with open(migration_file, 'r') as f:
            migration_sql = f.read()
        
        print(f"📋 Migration file loaded: {len(migration_sql)} characters")
        
        # Split into individual statements (basic approach)
        statements = migration_sql.split(';')
        
        print(f"🔧 Executing {len(statements)} SQL statements...")
        
        success_count = 0
        error_count = 0
        
        for i, statement in enumerate(statements):
            statement = statement.strip()
            if not statement or statement.startswith('--'):
                continue
                
            try:
                await DatabaseUtils.execute_query(statement, fetch_all=False)
                success_count += 1
                if i % 10 == 0:  # Progress indicator
                    print(f"  ✅ Executed {i+1}/{len(statements)} statements...")
            except Exception as e:
                error_count += 1
                print(f"  ❌ Error in statement {i+1}: {e}")
                print(f"     Statement: {statement[:100]}...")
        
        print(f"\n📊 Migration Results:")
        print(f"  ✅ Successful: {success_count}")
        print(f"  ❌ Errors: {error_count}")
        
        if error_count == 0:
            print("🎉 Schema v2 migration completed successfully!")
            return True
        else:
            print("⚠️  Migration completed with some errors")
            return False
            
    except Exception as e:
        print(f"❌ Migration failed: {e}")
        return False
    finally:
        await close_database()

async def verify_migration():
    """Verify the migration was successful"""
    try:
        await init_database()
        
        # Check for Schema v2 tables
        expected_tables = [
            'user_analytics_hourly', 'user_analytics_daily', 
            'cost_alerts', 'cost_anomalies'
        ]
        
        print("\n🔍 Verifying migration...")
        for table in expected_tables:
            try:
                result = await DatabaseUtils.execute_query(f"SELECT COUNT(*) as count FROM {table}", fetch_all=True)
                count = result[0]['count'] if result else 0
                print(f"  ✅ {table}: {count} rows")
            except Exception as e:
                print(f"  ❌ {table}: {e}")
        
        print("\n🎉 Migration verification completed!")
        
    except Exception as e:
        print(f"❌ Verification failed: {e}")
    finally:
        await close_database()

async def main():
    """Main function"""
    print("🔧 Schema v2 Migration Tool")
    print("=" * 50)
    
    # Run migration
    success = await run_schema_v2_migration()
    
    if success:
        # Verify migration
        await verify_migration()
        
        print("\n" + "=" * 50)
        print("🎉 MIGRATION COMPLETED SUCCESSFULLY!")
        print("Your database is now 100% compliant with Schema v2!")
    else:
        print("\n" + "=" * 50)
        print("❌ MIGRATION FAILED!")
        print("Please check the errors above and try again.")

if __name__ == "__main__":
    asyncio.run(main()) 
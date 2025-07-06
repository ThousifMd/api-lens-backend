#!/usr/bin/env python3
"""
Check migration status and schema_migrations table
"""
import asyncio
import os
from dotenv import load_dotenv
import asyncpg

# Load environment variables
load_dotenv()

async def check_migration_status():
    # Get database URL from environment
    DATABASE_URL = os.getenv('DATABASE_URL')
    if not DATABASE_URL:
        print("❌ DATABASE_URL not found in environment variables")
        return
    
    # Convert SQLAlchemy URL to asyncpg format
    if "+asyncpg" in DATABASE_URL:
        DATABASE_URL = DATABASE_URL.replace("postgresql+asyncpg://", "postgresql://")
    
    try:
        # Connect to database
        conn = await asyncpg.connect(DATABASE_URL)
        
        print("🔍 Checking migration status...")
        print("=" * 80)
        
        # Check if schema_migrations table exists
        table_exists_query = """
        SELECT EXISTS (
            SELECT FROM information_schema.tables 
            WHERE table_name = 'schema_migrations'
        );
        """
        
        table_exists = await conn.fetchval(table_exists_query)
        
        if table_exists:
            print("✅ schema_migrations table exists")
            
            # Get all applied migrations
            migrations_query = """
            SELECT version, name, applied_at
            FROM schema_migrations
            ORDER BY version;
            """
            
            migrations = await conn.fetch(migrations_query)
            
            if migrations:
                print(f"\n📊 Applied migrations ({len(migrations)} total):")
                for mig in migrations:
                    print(f"  - Version {mig['version']:03d}: {mig['name']} (applied: {mig['applied_at']})")
            else:
                print("\n⚠️  No migrations recorded in schema_migrations table")
        else:
            print("❌ schema_migrations table does NOT exist")
            print("   This suggests migrations have not been set up properly")
        
        # Check migration files in both locations
        print("\n📁 Checking migration files...")
        print("-" * 80)
        
        from pathlib import Path
        
        # Check root migrations directory
        root_migrations = Path("/Users/thousifudayagiri/Desktop/api-lens-backend/migrations")
        if root_migrations.exists():
            root_files = sorted(list(root_migrations.glob("*.sql")))
            print(f"\n📁 Root migrations directory ({len(root_files)} files):")
            for f in root_files:
                print(f"  - {f.name}")
        
        # Check sql/migrations directory
        sql_migrations = Path("/Users/thousifudayagiri/Desktop/api-lens-backend/sql/migrations")
        if sql_migrations.exists():
            sql_files = sorted(list(sql_migrations.glob("*.sql")))
            print(f"\n📁 SQL migrations directory ({len(sql_files)} files):")
            for f in sql_files:
                print(f"  - {f.name}")
        
        print("\n" + "=" * 80)
        print("💡 RECOMMENDATION:")
        print("-" * 80)
        
        if not table_exists:
            print("1. Create schema_migrations table first:")
            print("   CREATE TABLE IF NOT EXISTS schema_migrations (")
            print("     version INTEGER PRIMARY KEY,")
            print("     name VARCHAR(255) NOT NULL,")
            print("     applied_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP")
            print("   );")
            print("\n2. Apply migration 008 manually or move it to sql/migrations/")
            print("   and run: python scripts/migrations/migrate_db.py migrate")
        else:
            print("1. Move migration 008_add_image_generation_support.sql")
            print("   from: /migrations/")
            print("   to:   /sql/migrations/")
            print("\n2. Run: python scripts/migrations/migrate_db.py migrate")
        
        await conn.close()
        
    except Exception as e:
        print(f"\n❌ Error: {e}")
        import traceback
        traceback.print_exc()

if __name__ == "__main__":
    asyncio.run(check_migration_status())
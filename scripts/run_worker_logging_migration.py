#!/usr/bin/env python3
"""
Worker Logging Migration Runner
Applies the worker logging system schema migration
"""

import asyncio
import os
import sys
from pathlib import Path
import psycopg2
from psycopg2.extensions import ISOLATION_LEVEL_AUTOCOMMIT

# Add the app directory to the Python path
app_dir = Path(__file__).parent.parent
sys.path.insert(0, str(app_dir))

async def run_worker_logging_migration():
    """Run the worker logging system migration"""
    try:
        print("🚀 Starting Worker Logging Migration...")
        
        # Read the migration file
        migration_file = Path(__file__).parent.parent / "database" / "migrations" / "005_worker_logging_system.sql"
        
        if not migration_file.exists():
            print(f"❌ Migration file not found: {migration_file}")
            return False
        
        with open(migration_file, 'r') as f:
            migration_sql = f.read()
        
        print("📄 Migration SQL loaded successfully")
        
        # Get database connection details from environment or use defaults
        db_config = {
            'host': os.getenv('DB_HOST', 'localhost'),
            'port': os.getenv('DB_PORT', '5432'),
            'database': os.getenv('DB_NAME', 'api_lens'),
            'user': os.getenv('DB_USER', 'postgres'),
            'password': os.getenv('DB_PASSWORD', 'password')
        }
        
        print(f"🔌 Connecting to database: {db_config['user']}@{db_config['host']}:{db_config['port']}/{db_config['database']}")
        
        # Connect to database
        connection = psycopg2.connect(**db_config)
        connection.set_isolation_level(ISOLATION_LEVEL_AUTOCOMMIT)
        cursor = connection.cursor()
        
        print("⚡ Executing migration SQL...")
        
        # Execute the migration
        cursor.execute(migration_sql)
        
        print("✅ Migration SQL executed successfully!")
        
        # Verify key tables were created
        tables_to_check = [
            'worker_request_logs',
            'worker_performance_metrics',
            'worker_system_events',
            'worker_request_metadata'
        ]
        
        print("🔍 Verifying table creation...")
        for table in tables_to_check:
            cursor.execute("""
                SELECT EXISTS (
                    SELECT FROM information_schema.tables 
                    WHERE table_name = %s
                )
            """, (table,))
            
            result = cursor.fetchone()
            if result and result[0]:
                print(f"✅ Table '{table}' created successfully")
            else:
                print(f"❌ Table '{table}' was not created")
                return False
        
        # Check indexes
        print("🔍 Verifying indexes...")
        cursor.execute("""
            SELECT indexname FROM pg_indexes 
            WHERE tablename LIKE 'worker_%' 
            ORDER BY indexname
        """)
        
        indexes = cursor.fetchall()
        print(f"✅ Created {len(indexes)} indexes for worker logging tables")
        
        # Check triggers
        print("🔍 Verifying triggers...")
        cursor.execute("""
            SELECT trigger_name FROM information_schema.triggers 
            WHERE trigger_name LIKE '%worker%'
        """)
        
        triggers = cursor.fetchall()
        print(f"✅ Created {len(triggers)} triggers for worker logging tables")
        
        # Close connection
        cursor.close()
        connection.close()
        
        print("🎉 Worker Logging Migration completed successfully!")
        return True
        
    except Exception as e:
        print(f"❌ Migration failed: {e}")
        if 'cursor' in locals():
            cursor.close()
        if 'connection' in locals():
            connection.close()
        return False

def print_usage():
    """Print usage instructions"""
    print("""
🚀 Worker Logging Migration Script

This script creates the necessary database tables for the Worker Logging System:
- worker_request_logs: Stores request logs from Cloudflare Workers
- worker_performance_metrics: Stores performance metrics
- worker_system_events: Stores system events and errors  
- worker_request_metadata: Stores detailed request metadata

Environment Variables:
- DB_HOST: Database host (default: localhost)
- DB_PORT: Database port (default: 5432)
- DB_NAME: Database name (default: api_lens)
- DB_USER: Database user (default: postgres)
- DB_PASSWORD: Database password (default: password)

Usage:
    python3 scripts/run_worker_logging_migration.py
    """)

async def main():
    """Main function"""
    if len(sys.argv) > 1 and sys.argv[1] == "help":
        print_usage()
        return
    
    try:
        success = await run_worker_logging_migration()
        if success:
            print("✅ Worker Logging Migration completed successfully!")
            sys.exit(0)
        else:
            print("❌ Worker Logging Migration failed!")
            sys.exit(1)
            
    except KeyboardInterrupt:
        print("🛑 Migration interrupted by user")
        sys.exit(1)
    except Exception as e:
        print(f"💥 Unexpected error: {e}")
        sys.exit(1)

if __name__ == "__main__":
    asyncio.run(main())
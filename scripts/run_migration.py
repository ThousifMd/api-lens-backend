#!/usr/bin/env python3
"""
Database Migration Runner
Applies the cost calculation and rate limiting schema migration
"""

import asyncio
import os
import sys
from pathlib import Path

# Add the app directory to the Python path
app_dir = Path(__file__).parent.parent / "app"
sys.path.insert(0, str(app_dir))

from database import DatabaseUtils
from utils.logger import get_logger

logger = get_logger(__name__)

async def run_migration():
    """Run the cost calculation and rate limiting migration"""
    try:
        logger.info("Starting migration: Cost Calculation and Rate Limiting System")
        
        # Read the migration file
        migration_file = Path(__file__).parent.parent / "database" / "migrations" / "001_cost_and_rate_limiting_migration.sql"
        
        if not migration_file.exists():
            logger.error(f"Migration file not found: {migration_file}")
            return False
        
        with open(migration_file, 'r') as f:
            migration_sql = f.read()
        
        logger.info("Executing migration SQL...")
        
        # Execute the migration
        await DatabaseUtils.execute_raw_sql(migration_sql)
        
        logger.info("Migration completed successfully!")
        
        # Verify key tables were created
        tables_to_check = [
            'cost_calculations',
            'cost_alerts',
            'cost_accuracy_validations',
            'global_vendor_pricing',
            'rate_limit_configs',
            'company_quotas'
        ]
        
        logger.info("Verifying table creation...")
        for table in tables_to_check:
            query = """
                SELECT EXISTS (
                    SELECT FROM information_schema.tables 
                    WHERE table_name = $1
                )
            """
            result = await DatabaseUtils.execute_query(query, [table])
            if result and result['exists']:
                logger.info(f"✅ Table '{table}' created successfully")
            else:
                logger.error(f"❌ Table '{table}' was not created")
                return False
        
        # Check if default data was inserted
        logger.info("Verifying default data insertion...")
        
        # Check global vendor pricing
        pricing_count = await DatabaseUtils.execute_query(
            "SELECT COUNT(*) as count FROM global_vendor_pricing"
        )
        if pricing_count and pricing_count['count'] > 0:
            logger.info(f"✅ Default vendor pricing data inserted ({pricing_count['count']} records)")
        else:
            logger.warning("⚠️ No default vendor pricing data found")
        
        # Check rate limit configs
        rate_limit_count = await DatabaseUtils.execute_query(
            "SELECT COUNT(*) as count FROM rate_limit_configs"
        )
        if rate_limit_count and rate_limit_count['count'] > 0:
            logger.info(f"✅ Default rate limit configs created ({rate_limit_count['count']} records)")
        else:
            logger.warning("⚠️ No rate limit configs found")
        
        logger.info("🎉 Migration validation completed successfully!")
        return True
        
    except Exception as e:
        logger.error(f"Migration failed: {e}")
        return False

async def rollback_migration():
    """Rollback the migration if needed"""
    try:
        logger.info("Starting migration rollback...")
        
        # Get rollback SQL from migrations table
        query = """
            SELECT rollback_sql FROM schema_migrations 
            WHERE version = '001_cost_and_rate_limiting'
        """
        
        result = await DatabaseUtils.execute_query(query)
        if not result or not result.get('rollback_sql'):
            logger.error("No rollback SQL found for this migration")
            return False
        
        rollback_sql = result['rollback_sql']
        logger.info("Executing rollback SQL...")
        
        await DatabaseUtils.execute_raw_sql(rollback_sql)
        
        # Remove migration record
        await DatabaseUtils.execute_query(
            "DELETE FROM schema_migrations WHERE version = '001_cost_and_rate_limiting'"
        )
        
        logger.info("Migration rollback completed successfully!")
        return True
        
    except Exception as e:
        logger.error(f"Migration rollback failed: {e}")
        return False

async def check_migration_status():
    """Check if the migration has been applied"""
    try:
        # Check if migrations table exists
        query = """
            SELECT EXISTS (
                SELECT FROM information_schema.tables 
                WHERE table_name = 'schema_migrations'
            )
        """
        result = await DatabaseUtils.execute_query(query)
        
        if not result or not result['exists']:
            logger.info("Migrations tracking table does not exist - no migrations applied")
            return False
        
        # Check if this specific migration has been applied
        query = """
            SELECT applied_at FROM schema_migrations 
            WHERE version = '001_cost_and_rate_limiting'
        """
        result = await DatabaseUtils.execute_query(query)
        
        if result:
            logger.info(f"Migration 001_cost_and_rate_limiting was applied at: {result['applied_at']}")
            return True
        else:
            logger.info("Migration 001_cost_and_rate_limiting has not been applied")
            return False
            
    except Exception as e:
        logger.error(f"Failed to check migration status: {e}")
        return False

def print_usage():
    """Print usage instructions"""
    print("""
Usage: python run_migration.py [command]

Commands:
    run      - Apply the migration (default)
    rollback - Rollback the migration
    status   - Check migration status
    help     - Show this help message

Examples:
    python run_migration.py
    python run_migration.py run
    python run_migration.py rollback
    python run_migration.py status
    """)

async def main():
    """Main function"""
    command = sys.argv[1] if len(sys.argv) > 1 else "run"
    
    if command == "help":
        print_usage()
        return
    
    try:
        if command == "run":
            # Check if already applied first
            is_applied = await check_migration_status()
            if is_applied:
                logger.info("Migration has already been applied. Use 'rollback' to undo first.")
                return
            
            success = await run_migration()
            if success:
                logger.info("✅ Migration completed successfully!")
                sys.exit(0)
            else:
                logger.error("❌ Migration failed!")
                sys.exit(1)
                
        elif command == "rollback":
            success = await rollback_migration()
            if success:
                logger.info("✅ Migration rollback completed successfully!")
                sys.exit(0)
            else:
                logger.error("❌ Migration rollback failed!")
                sys.exit(1)
                
        elif command == "status":
            await check_migration_status()
            
        else:
            logger.error(f"Unknown command: {command}")
            print_usage()
            sys.exit(1)
            
    except KeyboardInterrupt:
        logger.info("Migration interrupted by user")
        sys.exit(1)
    except Exception as e:
        logger.error(f"Unexpected error: {e}")
        sys.exit(1)

if __name__ == "__main__":
    asyncio.run(main())
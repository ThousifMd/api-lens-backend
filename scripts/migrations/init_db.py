#!/usr/bin/env python3
"""
API Lens Database Initialization Script
=======================================

This script initializes the database with the enhanced schema for the B2B user analytics platform.
"""

import asyncio
import logging
import os
import sys
from pathlib import Path
import re

# Add the app directory to the Python path
sys.path.insert(0, str(Path(__file__).parent.parent))

from app.database import DatabaseUtils, db_manager
from app.utils.logger import setup_logging, get_logger

# Setup logging
setup_logging()
logger = get_logger(__name__)

async def init_database():
    """Initialize the database with the enhanced schema."""
    print("🔧 API Lens Database Initialization")
    print("=" * 50)
    
    logger.info("🚀 Starting database initialization...")
    
    # Path to the enhanced schema file
    schema_file = Path(__file__).parent.parent / "migrations" / "001_complete_schema_replacement.sql"
    
    if not schema_file.exists():
        logger.error(f"❌ Schema file not found: {schema_file}")
        return False
    
    logger.info(f"📖 Reading schema from: {schema_file}")
    
    try:
        # Read the schema file
        with open(schema_file, 'r') as f:
            schema_content = f.read()
        
        # Ensure DB pool is initialized
        if not db_manager.pool:
            await db_manager.initialize()
        
        # Drop and recreate the public schema for a full destructive migration
        logger.warning("⚠️  Dropping and recreating the public schema (all tables, views, functions, and data will be lost!)")
        await DatabaseUtils.execute_raw_sql('DROP SCHEMA public CASCADE; CREATE SCHEMA public;')
        logger.info("✅ Dropped and recreated public schema.")
        
        logger.info("🔧 Executing full schema as raw SQL...")
        await DatabaseUtils.execute_raw_sql(schema_content)
        logger.info("🎉 Database initialization completed successfully!")
        print("✅ Database initialized with enhanced schema!")
        print("📊 Features enabled:")
        print("   • Multi-tenant architecture")
        print("   • User analytics and tracking")
        print("   • Cost calculation and billing")
        print("   • Alerting and anomaly detection")
        print("   • Audit trails and compliance")
        print("   • Performance optimization")
        
        return True
        
    except Exception as e:
        logger.error(f"❌ Database initialization failed: {e}")
        return False
    finally:
        await db_manager.close()

async def main():
    """Main function."""
    try:
        success = await init_database()
        if not success:
            sys.exit(1)
    except KeyboardInterrupt:
        print("\n⚠️  Initialization interrupted by user")
        sys.exit(1)
    except Exception as e:
        logger.error(f"❌ Unexpected error: {e}")
        sys.exit(1)

if __name__ == "__main__":
    asyncio.run(main()) 
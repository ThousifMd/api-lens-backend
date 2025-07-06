#!/usr/bin/env python3
"""
Database Migration Script
Handles schema updates and data migrations
"""

import asyncio
import os
import sys
from pathlib import Path
from datetime import datetime
from typing import List, Dict, Optional
import sqlparse

# Add the app directory to the Python path
sys.path.append(str(Path(__file__).parent.parent))

from app.database import DatabaseUtils
from app.utils.logger import get_logger

logger = get_logger(__name__)

class DatabaseMigrator:
    """Handles database migrations"""
    
    def __init__(self):
        self.migrations_dir = Path(__file__).parent.parent / "sql" / "migrations"
        self.migrations = []
        self._load_migrations()
    
    def _load_migrations(self):
        """Load all migration files"""
        if not self.migrations_dir.exists():
            logger.info("No migrations directory found, creating...")
            self.migrations_dir.mkdir(parents=True, exist_ok=True)
            return
        
        migration_files = sorted([f for f in self.migrations_dir.glob("*.sql")])
        
        for migration_file in migration_files:
            migration_name = migration_file.stem
            migration_version = self._extract_version(migration_name)
            
            self.migrations.append({
                'version': migration_version,
                'name': migration_name,
                'file': migration_file
            })
    
    def _extract_version(self, migration_name: str) -> int:
        """Extract version number from migration filename"""
        try:
            # Expected format: 001_initial_schema.sql
            version_str = migration_name.split('_')[0]
            return int(version_str)
        except (IndexError, ValueError):
            return 0
    
    async def get_current_version(self) -> int:
        """Get the current database version"""
        try:
            result = await DatabaseUtils.execute_query(
                "SELECT COALESCE(MAX(version), 0) FROM schema_migrations"
            )
            return result[0][0] if result else 0
        except Exception as e:
            logger.warning(f"Could not get current version: {e}")
            return 0
    
    async def get_pending_migrations(self, target_version: Optional[int] = None) -> List[Dict]:
        """Get list of pending migrations"""
        current_version = await self.get_current_version()
        
        if target_version is None:
            # Get all migrations after current version
            target_version = float('inf')
        
        pending = []
        
        for migration_file in sorted(self.migrations_dir.glob("*.sql")):
            # Extract version from filename (e.g., "001_initial.sql" -> 1)
            version = int(migration_file.stem.split("_")[0])
            
            if current_version < version <= target_version:
                pending.append({
                    'version': version,
                    'name': migration_file.stem,
                    'file': migration_file
                })
        
        return pending
    
    async def apply_migration(self, migration: dict) -> bool:
        """Apply a single migration"""
        try:
            logger.info(f"🔧 Applying migration: {migration['name']}")
            
            # Read migration file
            with open(migration['file'], 'r') as f:
                migration_sql = f.read()
            
            # Use sqlparse to properly split SQL statements
            statements = sqlparse.split(migration_sql)
            
            # Filter out empty statements and comments
            valid_statements = []
            for stmt in statements:
                stmt = stmt.strip()
                if stmt and not stmt.startswith('--'):
                    valid_statements.append(stmt)
            
            logger.info(f"  Found {len(valid_statements)} statements to execute")
            
            # Execute each statement
            for i, statement in enumerate(valid_statements, 1):
                logger.info(f"  Executing statement {i}/{len(valid_statements)}")
                await DatabaseUtils.execute_query(statement, fetch_all=False)
            
            # Record the migration
            await DatabaseUtils.execute_query(
                "INSERT INTO schema_migrations (version, name) VALUES ($1, $2)",
                [migration['version'], migration['name']],
                fetch_all=False
            )
            
            logger.info(f"✅ Migration {migration['name']} applied successfully")
            return True
            
        except Exception as e:
            logger.error(f"❌ Migration {migration['name']} failed: {e}")
            return False
    
    async def migrate(self, target_version: Optional[int] = None):
        """Run migrations up to target version"""
        try:
            current_version = await self.get_current_version()
            logger.info(f"Current database version: {current_version}")
            
            if target_version is None:
                logger.info("Target version: latest")
            else:
                logger.info(f"Target version: {target_version}")
            
            pending_migrations = await self.get_pending_migrations(target_version)
            
            if not pending_migrations:
                logger.info("✅ Database is up to date")
                return
            
            logger.info(f"Found {len(pending_migrations)} pending migrations")
            
            for migration in pending_migrations:
                success = await self.apply_migration(migration)
                if not success:
                    logger.error("❌ Migration failed, stopping")
                    return
            
            logger.info("✅ All migrations completed successfully")
            
        except Exception as e:
            logger.error(f"❌ Migration failed: {e}")
            raise
    
    async def status(self):
        """Show migration status"""
        try:
            current_version = await self.get_current_version()
            logger.info(f"Current database version: {current_version}")
            
            if not self.migrations:
                logger.info("No migrations found")
                return
            
            logger.info("Migration status:")
            for migration in sorted(self.migrations, key=lambda x: x['version']):
                status = "✅ Applied" if migration['version'] <= current_version else "⏳ Pending"
                logger.info(f"  {migration['version']:03d}: {migration['name']} - {status}")
            
        except Exception as e:
            logger.error(f"❌ Error getting status: {e}")

async def main():
    """Main function"""
    import argparse
    
    parser = argparse.ArgumentParser(description="Database Migration Tool")
    parser.add_argument("action", choices=["migrate", "rollback", "status"], help="Action to perform")
    parser.add_argument("--version", type=int, help="Target version for migrate/rollback")
    parser.add_argument("--dry-run", action="store_true", help="Show what would be done without executing")
    
    args = parser.parse_args()
    
    migrator = DatabaseMigrator()
    
    if args.action == "status":
        await migrator.status()
    elif args.action == "migrate":
        if args.dry_run:
            logger.info("DRY RUN - Would migrate to version: {args.version or 'latest'}")
            await migrator.status()
        else:
            await migrator.migrate(args.version)
    elif args.action == "rollback":
        if args.version is None:
            logger.error("Rollback requires --version parameter")
            sys.exit(1)
        if args.dry_run:
            logger.info(f"DRY RUN - Would rollback to version: {args.version}")
        else:
            logger.error("❌ Rollback is not supported with the new migration tool")
            sys.exit(1)

if __name__ == "__main__":
    asyncio.run(main()) 
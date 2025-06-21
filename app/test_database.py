"""
Test Database Configuration
SQLite-based database setup for integration testing
"""

import sqlite3
import asyncio
import aiosqlite
import os
from pathlib import Path
from typing import Optional, Dict, Any
from contextlib import asynccontextmanager

from .utils.logger import get_logger

logger = get_logger(__name__)

class TestDatabaseManager:
    """Simplified database manager for testing with SQLite"""
    
    def __init__(self):
        self.db_path = None
        self.connection = None
        self._is_initialized = False
    
    async def initialize(self, db_path: Optional[str] = None):
        """Initialize test database"""
        if self._is_initialized:
            return
        
        if not db_path:
            # Use environment variable or default
            test_db_url = os.getenv('TEST_DATABASE_URL')
            if test_db_url and test_db_url.startswith('sqlite:///'):
                self.db_path = test_db_url.replace('sqlite:///', '')
            else:
                # Default test database path
                self.db_path = Path(__file__).parent.parent / "test_data" / "test_api_lens.db"
        else:
            self.db_path = db_path
        
        logger.info(f"Initializing test database at: {self.db_path}")
        
        # Ensure the database file exists
        if not Path(self.db_path).exists():
            raise FileNotFoundError(f"Test database not found: {self.db_path}")
        
        # Test connection
        async with aiosqlite.connect(self.db_path) as db:
            await db.execute("SELECT 1")
            
        self._is_initialized = True
        logger.info("Test database initialized successfully")
    
    @asynccontextmanager
    async def get_connection(self):
        """Get async database connection"""
        if not self._is_initialized:
            await self.initialize()
        
        async with aiosqlite.connect(self.db_path) as db:
            # Enable foreign keys and WAL mode for better performance
            await db.execute("PRAGMA foreign_keys = ON")
            await db.execute("PRAGMA journal_mode = WAL")
            yield db
    
    async def execute_query(self, query: str, params: tuple = None) -> Optional[Dict[str, Any]]:
        """Execute a query and return the first result"""
        async with self.get_connection() as db:
            # Enable row factory for dict-like access
            db.row_factory = aiosqlite.Row
            
            cursor = await db.execute(query, params or ())
            result = await cursor.fetchone()
            
            if result:
                return dict(result)
            return None
    
    async def execute_many(self, query: str, params_list: list) -> int:
        """Execute query with multiple parameter sets"""
        async with self.get_connection() as db:
            cursor = await db.executemany(query, params_list)
            await db.commit()
            return cursor.rowcount
    
    async def fetch_all(self, query: str, params: tuple = None) -> list:
        """Fetch all results from a query"""
        async with self.get_connection() as db:
            db.row_factory = aiosqlite.Row
            
            cursor = await db.execute(query, params or ())
            results = await cursor.fetchall()
            
            return [dict(row) for row in results]
    
    async def cleanup(self):
        """Clean up test data"""
        logger.info("Cleaning up test database...")
        
        async with self.get_connection() as db:
            # Clear all worker logging tables
            tables = [
                'worker_request_logs',
                'worker_performance_metrics', 
                'worker_system_events',
                'worker_request_metadata'
            ]
            
            for table in tables:
                await db.execute(f"DELETE FROM {table}")
            
            await db.commit()
            
        logger.info("Test database cleaned up")

# Global test database manager instance
test_db_manager = TestDatabaseManager()

async def get_test_db_connection():
    """Get test database connection for dependency injection"""
    async with test_db_manager.get_connection() as db:
        yield db

async def init_test_database():
    """Initialize test database"""
    await test_db_manager.initialize()

async def cleanup_test_database():
    """Clean up test database"""
    await test_db_manager.cleanup()

class TestDatabaseUtils:
    """Utility functions for test database operations"""
    
    @staticmethod
    async def execute_raw_sql(sql: str) -> bool:
        """Execute raw SQL (for migrations, etc.)"""
        try:
            async with test_db_manager.get_connection() as db:
                await db.executescript(sql)
                await db.commit()
            return True
        except Exception as e:
            logger.error(f"Error executing raw SQL: {e}")
            return False
    
    @staticmethod
    async def execute_query(query: str, params: tuple = None) -> Optional[Dict[str, Any]]:
        """Execute query and return first result"""
        return await test_db_manager.execute_query(query, params)
    
    @staticmethod
    async def fetch_all(query: str, params: tuple = None) -> list:
        """Fetch all results"""
        return await test_db_manager.fetch_all(query, params)
    
    @staticmethod
    async def insert_test_company(company_id: str, name: str, tier: str = "premium") -> bool:
        """Insert a test company"""
        try:
            async with test_db_manager.get_connection() as db:
                await db.execute("""
                    INSERT OR REPLACE INTO companies (id, name, schema_name, tier)
                    VALUES (?, ?, ?, ?)
                """, (company_id, name, f"company_{company_id}", tier))
                await db.commit()
            return True
        except Exception as e:
            logger.error(f"Error inserting test company: {e}")
            return False
    
    @staticmethod
    async def get_log_count(company_id: Optional[str] = None) -> int:
        """Get count of log entries"""
        query = "SELECT COUNT(*) as count FROM worker_request_logs"
        params = ()
        
        if company_id:
            query += " WHERE company_id = ?"
            params = (company_id,)
        
        result = await test_db_manager.execute_query(query, params)
        return result['count'] if result else 0
    
    @staticmethod
    async def get_performance_metrics_count(company_id: Optional[str] = None) -> int:
        """Get count of performance metrics"""
        query = "SELECT COUNT(*) as count FROM worker_performance_metrics"
        params = ()
        
        if company_id:
            query += " WHERE company_id = ?"
            params = (company_id,)
        
        result = await test_db_manager.execute_query(query, params)
        return result['count'] if result else 0
    
    @staticmethod
    async def get_system_events_count(event_type: Optional[str] = None) -> int:
        """Get count of system events"""
        query = "SELECT COUNT(*) as count FROM worker_system_events"
        params = ()
        
        if event_type:
            query += " WHERE event_type = ?"
            params = (event_type,)
        
        result = await test_db_manager.execute_query(query, params)
        return result['count'] if result else 0
    
    @staticmethod
    async def verify_company_isolation(company1_id: str, company2_id: str) -> Dict[str, Any]:
        """Verify that companies cannot access each other's data"""
        results = {}
        
        # Check logs isolation
        company1_logs = await TestDatabaseUtils.get_log_count(company1_id)
        company2_logs = await TestDatabaseUtils.get_log_count(company2_id)
        
        results['company1_logs'] = company1_logs
        results['company2_logs'] = company2_logs
        results['isolation_verified'] = company1_logs > 0 and company2_logs > 0
        
        # Check that each company only sees their own data
        company1_data = await test_db_manager.fetch_all(
            "SELECT company_id FROM worker_request_logs WHERE company_id = ?",
            (company1_id,)
        )
        
        company2_data = await test_db_manager.fetch_all(
            "SELECT company_id FROM worker_request_logs WHERE company_id = ?", 
            (company2_id,)
        )
        
        # Verify no cross-contamination
        company1_has_other_data = any(log['company_id'] != company1_id for log in company1_data)
        company2_has_other_data = any(log['company_id'] != company2_id for log in company2_data)
        
        results['company1_contaminated'] = company1_has_other_data
        results['company2_contaminated'] = company2_has_other_data
        results['no_contamination'] = not (company1_has_other_data or company2_has_other_data)
        
        return results
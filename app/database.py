import asyncio
import logging
import time
from contextlib import asynccontextmanager
from typing import AsyncGenerator, Optional, Dict, Any, List
from datetime import datetime, timedelta

import asyncpg
from sqlalchemy.ext.asyncio import create_async_engine, AsyncSession, AsyncConnection
from sqlalchemy.orm import sessionmaker, declarative_base
from sqlalchemy.pool import AsyncAdaptedQueuePool
from sqlalchemy.sql import text
from sqlalchemy.exc import SQLAlchemyError, DisconnectionError, OperationalError

from .config import get_settings
from .utils.logger import get_logger

settings = get_settings()
logger = get_logger(__name__)

class DatabaseConnectionManager:
    def __init__(self):
        self.engine = None
        self.async_session = None
        self.pool = None
        self._is_initialized = False
        self._connection_stats = {
            'total_connections': 0,
            'active_connections': 0,
            'failed_connections': 0,
            'last_connection_time': None,
            'connection_errors': []
        }
    
    async def initialize(self):
        """Initialize database connections with retry logic"""
        if self._is_initialized:
            return
        
        max_retries = 3
        retry_delay = 2
        
        for attempt in range(max_retries):
            try:
                await self._create_engine()
                await self._create_asyncpg_pool()
                await self._test_connection()
                self._is_initialized = True
                logger.info("Database connections initialized successfully")
                return
                
            except Exception as e:
                logger.error(f"Database initialization attempt {attempt + 1} failed: {e}")
                self._connection_stats['failed_connections'] += 1
                self._connection_stats['connection_errors'].append({
                    'timestamp': datetime.utcnow().isoformat(),
                    'error': str(e),
                    'attempt': attempt + 1
                })
                
                if attempt < max_retries - 1:
                    await asyncio.sleep(retry_delay * (2 ** attempt))
                else:
                    raise Exception(f"Failed to initialize database after {max_retries} attempts")
    
    async def _create_engine(self):
        """Create SQLAlchemy async engine with optimized connection pooling"""
        self.engine = create_async_engine(
            settings.DATABASE_URL,
            poolclass=AsyncAdaptedQueuePool,
            pool_size=settings.DB_POOL_SIZE,
            max_overflow=settings.DB_MAX_OVERFLOW,
            pool_timeout=settings.DB_POOL_TIMEOUT,
            pool_recycle=settings.DB_POOL_RECYCLE,
            pool_pre_ping=True,  # Enable connection health checks
            echo=settings.DB_ECHO,
            future=True,
            connect_args={
                "server_settings": {
                    "application_name": "api_lens_backend",
                    "jit": "off",  # Disable JIT for better performance with short queries
                }
            }
        )
        
        # Create async session factory
        self.async_session = sessionmaker(
            self.engine,
            class_=AsyncSession,
            expire_on_commit=False,
            autocommit=False,
            autoflush=False
        )
    
    async def _create_asyncpg_pool(self):
        """Create direct asyncpg connection pool for high-performance operations"""
        try:
            # Remove +asyncpg suffix for asyncpg and convert ssl parameter
            asyncpg_url = settings.DATABASE_URL.replace("postgresql+asyncpg://", "postgresql://").replace("ssl=require", "ssl=require")
            self.pool = await asyncpg.create_pool(
                asyncpg_url,
                min_size=2,
                max_size=settings.DB_POOL_SIZE,
                max_queries=50000,
                max_inactive_connection_lifetime=300,
                timeout=30,
                command_timeout=60,
                server_settings={
                    'application_name': 'api_lens_backend_pool',
                    'jit': 'off'
                }
            )
            logger.info("AsyncPG connection pool created successfully")
        except Exception as e:
            logger.error(f"Failed to create AsyncPG pool: {e}")
            raise
    
    async def _test_connection(self):
        """Test database connectivity"""
        try:
            async with self.engine.connect() as conn:
                result = await conn.execute(text("SELECT 1 as test, NOW() as timestamp"))
                row = result.fetchone()
                logger.info(f"Database connection test successful: {row}")
                self._connection_stats['last_connection_time'] = datetime.utcnow().isoformat()
                
        except Exception as e:
            logger.error(f"Database connection test failed: {e}")
            raise
    
    async def close(self):
        """Gracefully close all database connections"""
        try:
            if self.pool:
                await self.pool.close()
                logger.info("AsyncPG pool closed")
            
            if self.engine:
                await self.engine.dispose()
                logger.info("SQLAlchemy engine disposed")
                
            self._is_initialized = False
            logger.info("Database connections closed successfully")
            
        except Exception as e:
            logger.error(f"Error closing database connections: {e}")
    
    def get_connection_stats(self) -> Dict[str, Any]:
        """Get connection statistics"""
        stats = self._connection_stats.copy()
        if self.engine and hasattr(self.engine.pool, 'size'):
            stats['pool_size'] = self.engine.pool.size()
            stats['checked_in'] = self.engine.pool.checkedin()
            stats['checked_out'] = self.engine.pool.checkedout()
        return stats

# Global database manager instance
db_manager = DatabaseConnectionManager()

# Create async engine with enhanced connection pooling
async def get_engine():
    """Get the database engine, initializing if necessary"""
    if not db_manager._is_initialized:
        await db_manager.initialize()
    return db_manager.engine

# Backward compatibility
engine = None
async_session = None

# Create async session factory
async_session = sessionmaker(
    engine,
    class_=AsyncSession,
    expire_on_commit=False,
    autocommit=False,
    autoflush=False
)

# Create base class for models
Base = declarative_base()

# Database utility functions
class DatabaseUtils:
    """Utility class for common database operations"""
    
    @staticmethod
    async def execute_query(query: str, params: Optional[Dict] = None, fetch_all: bool = True):
        """Execute a raw SQL query using asyncpg pool"""
        if not db_manager.pool:
            await db_manager.initialize()
        
        start_time = time.time()
        try:
            async with db_manager.pool.acquire() as conn:
                if params:
                    result = await conn.fetch(query, *params.values()) if fetch_all else await conn.fetchrow(query, *params.values())
                else:
                    result = await conn.fetch(query) if fetch_all else await conn.fetchrow(query)
                
                execution_time = time.time() - start_time
                logger.debug(f"Query executed in {execution_time:.3f}s: {query[:100]}...")
                
                return result
        except Exception as e:
            execution_time = time.time() - start_time
            logger.error(f"Query failed after {execution_time:.3f}s: {query[:100]}... Error: {e}")
            raise
    
    @staticmethod
    async def execute_transaction(queries: List[Dict[str, Any]]):
        """Execute multiple queries in a transaction"""
        if not db_manager.pool:
            await db_manager.initialize()
        
        start_time = time.time()
        try:
            async with db_manager.pool.acquire() as conn:
                async with conn.transaction():
                    results = []
                    for query_info in queries:
                        query = query_info['query']
                        params = query_info.get('params', {})
                        
                        if params:
                            result = await conn.fetch(query, *params.values())
                        else:
                            result = await conn.fetch(query)
                        results.append(result)
                    
                    execution_time = time.time() - start_time
                    logger.debug(f"Transaction completed in {execution_time:.3f}s with {len(queries)} queries")
                    return results
                    
        except Exception as e:
            execution_time = time.time() - start_time
            logger.error(f"Transaction failed after {execution_time:.3f}s: {e}")
            raise
    
    @staticmethod
    async def bulk_insert(table_name: str, records: List[Dict], conflict_action: str = 'nothing'):
        """Perform bulk insert with conflict resolution"""
        if not records:
            return
        
        if not db_manager.pool:
            await db_manager.initialize()
        
        start_time = time.time()
        try:
            async with db_manager.pool.acquire() as conn:
                # Build INSERT query with conflict resolution
                columns = list(records[0].keys())
                placeholders = ', '.join([f'${i+1}' for i in range(len(columns))])
                column_names = ', '.join(columns)
                
                base_query = f"INSERT INTO {table_name} ({column_names}) VALUES ({placeholders})"
                
                if conflict_action == 'update':
                    # ON CONFLICT UPDATE
                    update_clause = ', '.join([f"{col} = EXCLUDED.{col}" for col in columns if col != 'id'])
                    query = f"{base_query} ON CONFLICT (id) DO UPDATE SET {update_clause}"
                else:
                    # ON CONFLICT DO NOTHING
                    query = f"{base_query} ON CONFLICT DO NOTHING"
                
                # Execute bulk insert
                data = [list(record.values()) for record in records]
                await conn.executemany(query, data)
                
                execution_time = time.time() - start_time
                logger.info(f"Bulk insert completed in {execution_time:.3f}s: {len(records)} records")
                
        except Exception as e:
            execution_time = time.time() - start_time
            logger.error(f"Bulk insert failed after {execution_time:.3f}s: {e}")
            raise
    
    @staticmethod
    async def execute_raw_sql(sql: str):
        """Execute raw SQL (for migrations and complex operations)"""
        if not db_manager.pool:
            await db_manager.initialize()
        
        start_time = time.time()
        try:
            async with db_manager.pool.acquire() as conn:
                # Split SQL into individual statements
                statements = [stmt.strip() for stmt in sql.split(';') if stmt.strip()]
                
                for statement in statements:
                    if statement:
                        await conn.execute(statement)
                
                execution_time = time.time() - start_time
                logger.info(f"Raw SQL executed successfully in {execution_time:.3f}s ({len(statements)} statements)")
                
        except Exception as e:
            execution_time = time.time() - start_time
            logger.error(f"Raw SQL execution failed after {execution_time:.3f}s: {e}")
            raise

# Enhanced session management with retry logic
@asynccontextmanager
async def get_db_session(retries: int = 3) -> AsyncGenerator[AsyncSession, None]:
    """Get database session with automatic retry logic"""
    if not db_manager._is_initialized:
        await db_manager.initialize()
    
    for attempt in range(retries):
        session = None
        try:
            async with db_manager.async_session() as session:
                yield session
                await session.commit()
                return
                
        except (DisconnectionError, OperationalError) as e:
            logger.warning(f"Database connection error (attempt {attempt + 1}/{retries}): {e}")
            if attempt < retries - 1:
                await asyncio.sleep(0.5 * (2 ** attempt))  # Exponential backoff
                continue
            raise
        except Exception as e:
            if session:
                await session.rollback()
            logger.error(f"Database session error: {e}")
            raise

# Dependency to get DB session (FastAPI compatible)
async def get_db():
    """FastAPI dependency for getting database session"""
    async with get_db_session() as session:
        yield session

# Function to get company-specific session
async def get_company_db(company_id: str):
    """Get database session with company-specific schema"""
    async with get_db_session() as session:
        try:
            await session.execute(text(f'SET search_path TO company_{company_id}, public'))
            yield session
        except Exception as e:
            logger.error(f"Failed to set company schema for {company_id}: {e}")
            raise

# Enhanced database health check
async def db_health_check() -> Dict[str, Any]:
    """Comprehensive database health check"""
    health_status = {
        'status': 'healthy',
        'timestamp': datetime.utcnow().isoformat(),
        'details': {}
    }
    
    try:
        if not db_manager._is_initialized:
            await db_manager.initialize()
        
        # Test SQLAlchemy connection
        start_time = time.time()
        async with db_manager.engine.connect() as conn:
            result = await conn.execute(text("SELECT 1 as test, NOW() as db_time, version() as version"))
            row = result.fetchone()
            
        sqlalchemy_time = time.time() - start_time
        health_status['details']['sqlalchemy'] = {
            'status': 'ok',
            'response_time_ms': round(sqlalchemy_time * 1000, 2),
            'db_time': str(row.db_time),
            'version': row.version[:50] + '...' if len(row.version) > 50 else row.version
        }
        
        # Test AsyncPG pool
        start_time = time.time()
        async with db_manager.pool.acquire() as conn:
            result = await conn.fetchrow("SELECT COUNT(*) as active_connections FROM pg_stat_activity WHERE datname = current_database()")
        
        asyncpg_time = time.time() - start_time
        health_status['details']['asyncpg'] = {
            'status': 'ok',
            'response_time_ms': round(asyncpg_time * 1000, 2),
            'active_connections': result['active_connections']
        }
        
        # Add connection pool stats
        health_status['details']['connection_stats'] = db_manager.get_connection_stats()
        
        # Overall response time
        total_time = sqlalchemy_time + asyncpg_time
        health_status['response_time_ms'] = round(total_time * 1000, 2)
        
        if total_time > 1.0:  # Flag slow responses
            health_status['status'] = 'degraded'
            health_status['details']['warning'] = 'Slow database response time'
        
    except Exception as e:
        health_status['status'] = 'unhealthy'
        health_status['error'] = str(e)
        health_status['details']['error_type'] = type(e).__name__
        logger.error(f"Database health check failed: {e}")
    
    return health_status

# Initialize database on startup
async def init_database():
    """Initialize database connections"""
    try:
        await db_manager.initialize()
        logger.info("Database initialization completed successfully")
    except Exception as e:
        logger.error(f"Database initialization failed: {e}")
        raise

# Graceful shutdown
async def close_database():
    """Close database connections gracefully"""
    try:
        await db_manager.close()
        logger.info("Database connections closed successfully")
    except Exception as e:
        logger.error(f"Error during database shutdown: {e}")
        raise 
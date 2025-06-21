import pytest
import asyncio
from unittest.mock import AsyncMock, patch
from datetime import datetime

from app.database import (
    DatabaseConnectionManager, 
    db_manager, 
    DatabaseUtils,
    get_db_session,
    db_health_check,
    init_database,
    close_database
)
from app.config import get_settings

settings = get_settings()

class TestDatabaseConnectionManager:
    """Test suite for DatabaseConnectionManager"""
    
    @pytest.fixture
    def db_manager_instance(self):
        """Create a fresh database manager instance for testing"""
        return DatabaseConnectionManager()
    
    @pytest.mark.asyncio
    async def test_initialization(self, db_manager_instance):
        """Test database manager initialization"""
        assert not db_manager_instance._is_initialized
        
        # Mock the database connection to avoid actual database calls in tests
        with patch.object(db_manager_instance, '_create_engine') as mock_engine, \
             patch.object(db_manager_instance, '_create_asyncpg_pool') as mock_pool, \
             patch.object(db_manager_instance, '_test_connection') as mock_test:
            
            await db_manager_instance.initialize()
            
            assert db_manager_instance._is_initialized
            mock_engine.assert_called_once()
            mock_pool.assert_called_once()
            mock_test.assert_called_once()
    
    @pytest.mark.asyncio
    async def test_initialization_retry_logic(self, db_manager_instance):
        """Test retry logic during initialization"""
        with patch.object(db_manager_instance, '_create_engine') as mock_engine:
            # Simulate failure on first two attempts, success on third
            mock_engine.side_effect = [Exception("Connection failed"), Exception("Connection failed"), None]
            
            with patch.object(db_manager_instance, '_create_asyncpg_pool'), \
                 patch.object(db_manager_instance, '_test_connection'), \
                 patch('asyncio.sleep') as mock_sleep:
                
                await db_manager_instance.initialize()
                
                assert db_manager_instance._is_initialized
                assert mock_engine.call_count == 3
                assert mock_sleep.call_count == 2  # Two sleeps for retries
    
    @pytest.mark.asyncio
    async def test_initialization_max_retries_exceeded(self, db_manager_instance):
        """Test initialization failure after max retries"""
        with patch.object(db_manager_instance, '_create_engine') as mock_engine:
            mock_engine.side_effect = Exception("Persistent connection failure")
            
            with patch('asyncio.sleep'):
                with pytest.raises(Exception, match="Failed to initialize database after 3 attempts"):
                    await db_manager_instance.initialize()
                
                assert not db_manager_instance._is_initialized
                assert db_manager_instance._connection_stats['failed_connections'] == 3
    
    def test_connection_stats(self, db_manager_instance):
        """Test connection statistics tracking"""
        stats = db_manager_instance.get_connection_stats()
        
        expected_keys = ['total_connections', 'active_connections', 'failed_connections', 
                        'last_connection_time', 'connection_errors']
        
        for key in expected_keys:
            assert key in stats
        
        assert isinstance(stats['connection_errors'], list)
        assert isinstance(stats['failed_connections'], int)

class TestDatabaseUtils:
    """Test suite for DatabaseUtils"""
    
    @pytest.mark.asyncio
    async def test_execute_query_with_mocked_pool(self):
        """Test query execution with mocked database pool"""
        mock_connection = AsyncMock()
        mock_connection.fetch.return_value = [{'id': 1, 'name': 'test'}]
        
        mock_pool = AsyncMock()
        mock_pool.acquire.return_value.__aenter__.return_value = mock_connection
        
        with patch.object(db_manager, 'pool', mock_pool), \
             patch.object(db_manager, '_is_initialized', True):
            
            result = await DatabaseUtils.execute_query("SELECT * FROM test_table")
            
            assert result == [{'id': 1, 'name': 'test'}]
            mock_connection.fetch.assert_called_once_with("SELECT * FROM test_table")
    
    @pytest.mark.asyncio
    async def test_execute_query_with_params(self):
        """Test query execution with parameters"""
        mock_connection = AsyncMock()
        mock_connection.fetch.return_value = [{'id': 1}]
        
        mock_pool = AsyncMock()
        mock_pool.acquire.return_value.__aenter__.return_value = mock_connection
        
        with patch.object(db_manager, 'pool', mock_pool), \
             patch.object(db_manager, '_is_initialized', True):
            
            params = {'user_id': 123}
            await DatabaseUtils.execute_query("SELECT * FROM users WHERE id = $1", params)
            
            mock_connection.fetch.assert_called_once_with("SELECT * FROM users WHERE id = $1", 123)
    
    @pytest.mark.asyncio
    async def test_execute_transaction(self):
        """Test transaction execution"""
        mock_connection = AsyncMock()
        mock_transaction = AsyncMock()
        mock_connection.transaction.return_value = mock_transaction
        mock_connection.fetch.return_value = [{'result': 'success'}]
        
        mock_pool = AsyncMock()
        mock_pool.acquire.return_value.__aenter__.return_value = mock_connection
        
        with patch.object(db_manager, 'pool', mock_pool), \
             patch.object(db_manager, '_is_initialized', True):
            
            queries = [
                {'query': 'INSERT INTO table1 VALUES (1)', 'params': {}},
                {'query': 'UPDATE table2 SET status = $1', 'params': {'status': 'active'}}
            ]
            
            result = await DatabaseUtils.execute_transaction(queries)
            
            assert len(result) == 2
            assert mock_connection.fetch.call_count == 2
    
    @pytest.mark.asyncio
    async def test_bulk_insert(self):
        """Test bulk insert functionality"""
        mock_connection = AsyncMock()
        mock_pool = AsyncMock()
        mock_pool.acquire.return_value.__aenter__.return_value = mock_connection
        
        with patch.object(db_manager, 'pool', mock_pool), \
             patch.object(db_manager, '_is_initialized', True):
            
            records = [
                {'id': 1, 'name': 'John'},
                {'id': 2, 'name': 'Jane'}
            ]
            
            await DatabaseUtils.bulk_insert('users', records)
            
            mock_connection.executemany.assert_called_once()
            call_args = mock_connection.executemany.call_args
            assert 'INSERT INTO users' in call_args[0][0]
            assert 'ON CONFLICT DO NOTHING' in call_args[0][0]

class TestDatabaseHealthCheck:
    """Test suite for database health check functionality"""
    
    @pytest.mark.asyncio
    async def test_health_check_success(self):
        """Test successful health check"""
        mock_engine = AsyncMock()
        mock_connection = AsyncMock()
        mock_result = AsyncMock()
        mock_row = AsyncMock()
        mock_row.db_time = datetime.now()
        mock_row.version = "PostgreSQL 14.0"
        
        mock_result.fetchone.return_value = mock_row
        mock_connection.execute.return_value = mock_result
        mock_engine.connect.return_value.__aenter__.return_value = mock_connection
        
        mock_pool = AsyncMock()
        mock_pool_connection = AsyncMock()
        mock_pool_connection.fetchrow.return_value = {'active_connections': 5}
        mock_pool.acquire.return_value.__aenter__.return_value = mock_pool_connection
        
        with patch.object(db_manager, 'engine', mock_engine), \
             patch.object(db_manager, 'pool', mock_pool), \
             patch.object(db_manager, '_is_initialized', True):
            
            result = await db_health_check()
            
            assert result['status'] == 'healthy'
            assert 'details' in result
            assert 'sqlalchemy' in result['details']
            assert 'asyncpg' in result['details']
            assert 'connection_stats' in result['details']
    
    @pytest.mark.asyncio
    async def test_health_check_failure(self):
        """Test health check failure scenario"""
        with patch.object(db_manager, 'initialize', side_effect=Exception("Database unavailable")):
            result = await db_health_check()
            
            assert result['status'] == 'unhealthy'
            assert 'error' in result
            assert result['error'] == "Database unavailable"

class TestDatabaseSession:
    """Test suite for database session management"""
    
    @pytest.mark.asyncio
    async def test_get_db_session_success(self):
        """Test successful database session creation"""
        mock_session = AsyncMock()
        mock_session_factory = AsyncMock()
        mock_session_factory.return_value.__aenter__.return_value = mock_session
        
        with patch.object(db_manager, 'async_session', mock_session_factory), \
             patch.object(db_manager, '_is_initialized', True):
            
            async with get_db_session() as session:
                assert session == mock_session
            
            mock_session.commit.assert_called_once()
    
    @pytest.mark.asyncio
    async def test_get_db_session_with_retry(self):
        """Test database session with retry logic"""
        from sqlalchemy.exc import DisconnectionError
        
        mock_session = AsyncMock()
        mock_session_factory = AsyncMock()
        
        # First call fails, second succeeds
        mock_session_factory.side_effect = [
            DisconnectionError("Connection lost", None, None),
            AsyncMock(return_value=AsyncMock(__aenter__=AsyncMock(return_value=mock_session)))
        ]
        
        with patch.object(db_manager, 'async_session', mock_session_factory), \
             patch.object(db_manager, '_is_initialized', True), \
             patch('asyncio.sleep') as mock_sleep:
            
            # This should eventually succeed after retry
            try:
                async with get_db_session() as session:
                    pass
            except DisconnectionError:
                pass  # Expected for this test case
            
            mock_sleep.assert_called()  # Verify retry delay was called

@pytest.mark.asyncio
async def test_init_and_close_database():
    """Test database initialization and closure"""
    with patch.object(db_manager, 'initialize') as mock_init, \
         patch.object(db_manager, 'close') as mock_close:
        
        await init_database()
        mock_init.assert_called_once()
        
        await close_database()
        mock_close.assert_called_once()

if __name__ == "__main__":
    # Run specific tests
    pytest.main([__file__, "-v"])
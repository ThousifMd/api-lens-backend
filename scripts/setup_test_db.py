#!/usr/bin/env python3
"""
Test Database Setup Script
Creates SQLite database for testing the logging system
"""

import sqlite3
import os
from pathlib import Path

def create_test_database():
    """Create SQLite test database with logging tables"""
    
    # Create test database directory
    test_db_dir = Path(__file__).parent.parent / "test_data"
    test_db_dir.mkdir(exist_ok=True)
    
    db_path = test_db_dir / "test_api_lens.db"
    
    print(f"🗄️  Creating test database at: {db_path}")
    
    # Connect to SQLite database (creates if doesn't exist)
    conn = sqlite3.connect(str(db_path))
    cursor = conn.cursor()
    
    try:
        # Read and execute the migration SQL (adapted for SQLite)
        migration_sql = """
        -- Companies table (simplified for testing)
        CREATE TABLE IF NOT EXISTS companies (
            id TEXT PRIMARY KEY,
            name TEXT NOT NULL,
            schema_name TEXT UNIQUE NOT NULL,
            tier TEXT DEFAULT 'free',
            is_active BOOLEAN DEFAULT true,
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
        );
        
        -- Worker request logs table
        CREATE TABLE IF NOT EXISTS worker_request_logs (
            id TEXT PRIMARY KEY,
            request_id TEXT UNIQUE NOT NULL,
            company_id TEXT NOT NULL,
            batch_id TEXT,
            
            -- Request metadata
            timestamp TIMESTAMP NOT NULL,
            method TEXT NOT NULL,
            url TEXT NOT NULL,
            vendor TEXT NOT NULL,
            model TEXT,
            endpoint TEXT,
            
            -- Response metadata
            status_code INTEGER NOT NULL,
            success BOOLEAN NOT NULL DEFAULT false,
            error_message TEXT,
            error_code TEXT,
            error_type TEXT,
            
            -- Performance metrics
            total_latency INTEGER NOT NULL DEFAULT 0,
            vendor_latency INTEGER,
            processing_latency INTEGER,
            queue_time INTEGER,
            
            -- Usage tracking
            input_tokens INTEGER DEFAULT 0,
            output_tokens INTEGER DEFAULT 0,
            total_tokens INTEGER DEFAULT 0,
            cost REAL DEFAULT 0,
            
            -- Client information
            ip_address TEXT,
            country TEXT,
            region TEXT,
            city TEXT,
            user_agent TEXT,
            
            -- Cache information
            cache_hit BOOLEAN DEFAULT false,
            cache_key TEXT,
            
            -- Timestamps
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
        );
        
        -- Performance metrics table
        CREATE TABLE IF NOT EXISTS worker_performance_metrics (
            id TEXT PRIMARY KEY,
            request_id TEXT NOT NULL,
            company_id TEXT NOT NULL,
            timestamp TIMESTAMP NOT NULL,
            
            -- Latency breakdown (in milliseconds)
            total_latency INTEGER NOT NULL DEFAULT 0,
            vendor_latency INTEGER DEFAULT 0,
            auth_latency INTEGER DEFAULT 0,
            ratelimit_latency INTEGER DEFAULT 0,
            cost_latency INTEGER DEFAULT 0,
            logging_latency INTEGER DEFAULT 0,
            
            -- Request outcome
            success BOOLEAN NOT NULL DEFAULT false,
            error_type TEXT,
            retry_count INTEGER DEFAULT 0,
            
            -- Resource usage
            memory_usage INTEGER,
            cpu_time INTEGER,
            bytes_in INTEGER DEFAULT 0,
            bytes_out INTEGER DEFAULT 0,
            connection_reused BOOLEAN,
            
            -- Cache metrics
            cache_hit_rate REAL,
            cache_latency INTEGER,
            
            -- Rate limiting
            rate_limit_remaining INTEGER,
            rate_limit_reset TIMESTAMP,
            
            -- Queue metrics
            queue_depth INTEGER,
            queue_wait_time INTEGER,
            
            -- Timestamps
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
        );
        
        -- System events table
        CREATE TABLE IF NOT EXISTS worker_system_events (
            id TEXT PRIMARY KEY,
            request_id TEXT NOT NULL,
            company_id TEXT,
            timestamp TIMESTAMP NOT NULL,
            
            -- Event classification
            event_type TEXT NOT NULL,
            success BOOLEAN,
            severity TEXT DEFAULT 'info',
            
            -- Event details
            details TEXT, -- JSON as TEXT in SQLite
            error_message TEXT,
            stack_trace TEXT,
            
            -- Request context
            method TEXT,
            url TEXT,
            ip_address TEXT,
            user_agent TEXT,
            path TEXT,
            
            -- Component information
            component TEXT,
            function_name TEXT,
            vendor TEXT,
            model TEXT,
            
            -- Recovery information
            recovered BOOLEAN DEFAULT false,
            recovery_action TEXT,
            retry_attempt INTEGER DEFAULT 0,
            
            -- Timestamps
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
        );
        
        -- Request metadata table
        CREATE TABLE IF NOT EXISTS worker_request_metadata (
            id TEXT PRIMARY KEY,
            request_id TEXT NOT NULL,
            
            -- Request details
            headers TEXT, -- JSON as TEXT
            request_body_hash TEXT,
            request_body_size INTEGER DEFAULT 0,
            content_type TEXT,
            
            -- Response details
            response_headers TEXT, -- JSON as TEXT
            response_body_hash TEXT,
            response_body_size INTEGER DEFAULT 0,
            response_content_type TEXT,
            
            -- Geographical data
            timezone TEXT,
            
            -- Additional metadata
            origin TEXT,
            referer TEXT,
            api_key_id TEXT,
            user_id TEXT,
            features TEXT, -- JSON as TEXT
            experiments TEXT, -- JSON as TEXT
            custom_metadata TEXT, -- JSON as TEXT
            
            -- Timestamps
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
        );
        
        -- Create indexes for performance
        CREATE INDEX IF NOT EXISTS idx_worker_request_logs_company_id ON worker_request_logs(company_id);
        CREATE INDEX IF NOT EXISTS idx_worker_request_logs_timestamp ON worker_request_logs(timestamp);
        CREATE INDEX IF NOT EXISTS idx_worker_request_logs_vendor ON worker_request_logs(vendor);
        CREATE INDEX IF NOT EXISTS idx_worker_request_logs_success ON worker_request_logs(success);
        CREATE INDEX IF NOT EXISTS idx_worker_request_logs_request_id ON worker_request_logs(request_id);
        
        CREATE INDEX IF NOT EXISTS idx_worker_performance_metrics_company_id ON worker_performance_metrics(company_id);
        CREATE INDEX IF NOT EXISTS idx_worker_performance_metrics_timestamp ON worker_performance_metrics(timestamp);
        CREATE INDEX IF NOT EXISTS idx_worker_performance_metrics_request_id ON worker_performance_metrics(request_id);
        
        CREATE INDEX IF NOT EXISTS idx_worker_system_events_company_id ON worker_system_events(company_id);
        CREATE INDEX IF NOT EXISTS idx_worker_system_events_timestamp ON worker_system_events(timestamp);
        CREATE INDEX IF NOT EXISTS idx_worker_system_events_event_type ON worker_system_events(event_type);
        
        CREATE INDEX IF NOT EXISTS idx_worker_request_metadata_request_id ON worker_request_metadata(request_id);
        """
        
        print("🔄 Executing migration SQL...")
        cursor.executescript(migration_sql)
        
        # Insert test company data
        print("📝 Inserting test data...")
        test_companies = [
            ('test-company-1', 'Test Company 1', 'company_test_1', 'premium'),
            ('test-company-2', 'Test Company 2', 'company_test_2', 'basic'),
            ('test-company-3', 'Test Company 3', 'company_test_3', 'free')
        ]
        
        cursor.executemany("""
            INSERT OR REPLACE INTO companies (id, name, schema_name, tier)
            VALUES (?, ?, ?, ?)
        """, test_companies)
        
        conn.commit()
        
        # Verify tables were created
        cursor.execute("SELECT name FROM sqlite_master WHERE type='table'")
        tables = cursor.fetchall()
        
        print("✅ Created tables:")
        for table in tables:
            print(f"   - {table[0]}")
        
        # Verify test data
        cursor.execute("SELECT COUNT(*) FROM companies")
        company_count = cursor.fetchone()[0]
        print(f"✅ Inserted {company_count} test companies")
        
        print(f"🎉 Test database created successfully at: {db_path}")
        
        # Set environment variable for testing
        os.environ['TEST_DATABASE_URL'] = f"sqlite:///{db_path}"
        print(f"📍 Set TEST_DATABASE_URL={os.environ['TEST_DATABASE_URL']}")
        
        return str(db_path)
        
    except Exception as e:
        print(f"❌ Error creating test database: {e}")
        raise
    finally:
        conn.close()

def verify_test_database(db_path):
    """Verify the test database is working correctly"""
    try:
        conn = sqlite3.connect(db_path)
        cursor = conn.cursor()
        
        print("🔍 Verifying test database...")
        
        # Test inserting a log entry
        test_log = {
            'id': 'test-log-1',
            'request_id': 'req-test-123',
            'company_id': 'test-company-1',
            'timestamp': '2024-01-01 12:00:00',
            'method': 'POST',
            'url': 'https://api.openai.com/v1/chat/completions',
            'vendor': 'openai',
            'model': 'gpt-4',
            'endpoint': 'chat/completions',
            'status_code': 200,
            'success': True,
            'total_latency': 1500,
            'vendor_latency': 1200,
            'input_tokens': 100,
            'output_tokens': 150,
            'cost': 0.003,
            'ip_address': '203.0.113.1'
        }
        
        cursor.execute("""
            INSERT INTO worker_request_logs (
                id, request_id, company_id, timestamp, method, url, vendor, model,
                endpoint, status_code, success, total_latency, vendor_latency,
                input_tokens, output_tokens, cost, ip_address
            ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
        """, tuple(test_log.values()))
        
        conn.commit()
        
        # Verify the log was inserted
        cursor.execute("SELECT COUNT(*) FROM worker_request_logs")
        log_count = cursor.fetchone()[0]
        
        if log_count > 0:
            print(f"✅ Test log insertion successful ({log_count} logs)")
        else:
            print("❌ Test log insertion failed")
            
        conn.close()
        return True
        
    except Exception as e:
        print(f"❌ Database verification failed: {e}")
        return False

if __name__ == "__main__":
    try:
        db_path = create_test_database()
        verify_test_database(db_path)
        print("\n🎉 Test database setup completed successfully!")
        print("\nNext steps:")
        print("1. Update app/config.py to use TEST_DATABASE_URL for testing")
        print("2. Run integration tests with the test database")
        print("3. Start backend server for end-to-end testing")
        
    except Exception as e:
        print(f"\n❌ Test database setup failed: {e}")
        exit(1)
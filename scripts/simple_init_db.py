#!/usr/bin/env python3
"""
Simple Database Initialization Script
Sets up the database schema step by step
"""

import asyncio
import sys
from pathlib import Path

# Add the app directory to the Python path
sys.path.append(str(Path(__file__).parent.parent))

from app.database import DatabaseUtils
from app.utils.logger import get_logger

logger = get_logger(__name__)

async def init_database_simple():
    """Initialize database with simple step-by-step approach"""
    try:
        print("🚀 Starting simple database initialization...")
        
        # Step 1: Enable UUID extension
        print("📋 Step 1: Enabling UUID extension...")
        await DatabaseUtils.execute_query('CREATE EXTENSION IF NOT EXISTS "uuid-ossp";', fetch_all=False)
        print("✅ UUID extension enabled")
        
        # Step 2: Create companies table
        print("📋 Step 2: Creating companies table...")
        await DatabaseUtils.execute_query("""
            CREATE TABLE IF NOT EXISTS companies (
                id UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
                name VARCHAR(255) NOT NULL,
                description TEXT,
                contact_email VARCHAR(255),
                billing_email VARCHAR(255),
                tier VARCHAR(50) DEFAULT 'standard',
                schema_name VARCHAR(100) UNIQUE,
                is_active BOOLEAN DEFAULT true,
                rate_limit_rps INTEGER DEFAULT 100,
                monthly_quota INTEGER DEFAULT 10000,
                created_at TIMESTAMP WITH TIME ZONE DEFAULT NOW(),
                updated_at TIMESTAMP WITH TIME ZONE DEFAULT NOW()
            );
        """, fetch_all=False)
        print("✅ Companies table created")
        
        # Step 3: Create vendors table
        print("📋 Step 3: Creating vendors table...")
        await DatabaseUtils.execute_query("""
            CREATE TABLE IF NOT EXISTS vendors (
                id SERIAL PRIMARY KEY,
                name VARCHAR(100) UNIQUE NOT NULL,
                display_name VARCHAR(255),
                description TEXT,
                is_active BOOLEAN DEFAULT true,
                created_at TIMESTAMP WITH TIME ZONE DEFAULT NOW()
            );
        """, fetch_all=False)
        print("✅ Vendors table created")
        
        # Step 4: Create vendor_models table
        print("📋 Step 4: Creating vendor_models table...")
        await DatabaseUtils.execute_query("""
            CREATE TABLE IF NOT EXISTS vendor_models (
                id SERIAL PRIMARY KEY,
                vendor_id INTEGER NOT NULL REFERENCES vendors(id) ON DELETE CASCADE,
                name VARCHAR(255) NOT NULL,
                display_name VARCHAR(255),
                description TEXT,
                is_active BOOLEAN DEFAULT true,
                created_at TIMESTAMP WITH TIME ZONE DEFAULT NOW(),
                UNIQUE(vendor_id, name)
            );
        """, fetch_all=False)
        print("✅ Vendor models table created")
        
        # Step 5: Create users table
        print("📋 Step 5: Creating users table...")
        await DatabaseUtils.execute_query("""
            CREATE TABLE IF NOT EXISTS users (
                id UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
                user_id VARCHAR(255) UNIQUE NOT NULL,
                display_name VARCHAR(255),
                email VARCHAR(255),
                created_at TIMESTAMP WITH TIME ZONE DEFAULT NOW()
            );
        """, fetch_all=False)
        print("✅ Users table created")
        
        # Step 6: Create user_sessions table
        print("📋 Step 6: Creating user_sessions table...")
        await DatabaseUtils.execute_query("""
            CREATE TABLE IF NOT EXISTS user_sessions (
                id UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
                company_id UUID NOT NULL REFERENCES companies(id) ON DELETE CASCADE,
                user_id UUID NOT NULL REFERENCES users(id) ON DELETE CASCADE,
                session_id VARCHAR(255) NOT NULL,
                tracking_method VARCHAR(50) DEFAULT 'api_request',
                created_at TIMESTAMP WITH TIME ZONE DEFAULT NOW(),
                UNIQUE(company_id, user_id, session_id)
            );
        """, fetch_all=False)
        print("✅ User sessions table created")
        
        # Step 7: Create api_keys table
        print("📋 Step 7: Creating api_keys table...")
        await DatabaseUtils.execute_query("""
            CREATE TABLE IF NOT EXISTS api_keys (
                id UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
                company_id UUID NOT NULL REFERENCES companies(id) ON DELETE CASCADE,
                key_hash VARCHAR(255) UNIQUE NOT NULL,
                name VARCHAR(255) NOT NULL,
                is_active BOOLEAN DEFAULT true,
                created_at TIMESTAMP WITH TIME ZONE DEFAULT NOW(),
                last_used_at TIMESTAMP WITH TIME ZONE
            );
        """, fetch_all=False)
        print("✅ API keys table created")
        
        # Step 8: Create requests table
        print("📋 Step 8: Creating requests table...")
        await DatabaseUtils.execute_query("""
            CREATE TABLE IF NOT EXISTS requests (
                id UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
                request_uuid VARCHAR(255) UNIQUE NOT NULL,
                company_id UUID NOT NULL REFERENCES companies(id) ON DELETE CASCADE,
                vendor_model_id INTEGER NOT NULL REFERENCES vendor_models(id) ON DELETE CASCADE,
                user_session_id UUID REFERENCES user_sessions(id) ON DELETE SET NULL,
                method VARCHAR(10) NOT NULL,
                endpoint VARCHAR(255) NOT NULL,
                url TEXT,
                timestamp_utc TIMESTAMP WITH TIME ZONE NOT NULL,
                timezone_name VARCHAR(100) NOT NULL,
                input_tokens INTEGER NOT NULL DEFAULT 0,
                output_tokens INTEGER NOT NULL DEFAULT 0,
                total_latency INTEGER NOT NULL DEFAULT 0,
                vendor_latency INTEGER NOT NULL DEFAULT 0,
                status_code INTEGER NOT NULL,
                success BOOLEAN NOT NULL DEFAULT false,
                ip_address INET,
                country VARCHAR(10),
                region VARCHAR(100),
                user_agent TEXT,
                calculated_timestamp TEXT,
                created_at TIMESTAMP WITH TIME ZONE DEFAULT NOW()
            );
        """, fetch_all=False)
        print("✅ Requests table created")
        
        # Step 9: Create cost_calculations table
        print("📋 Step 9: Creating cost_calculations table...")
        await DatabaseUtils.execute_query("""
            CREATE TABLE IF NOT EXISTS cost_calculations (
                id UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
                request_id UUID NOT NULL REFERENCES requests(id) ON DELETE CASCADE,
                input_cost NUMERIC(10, 6) NOT NULL,
                output_cost NUMERIC(10, 6) NOT NULL,
                calculation_method VARCHAR(50),
                calculated_timestamp TEXT,
                created_at TIMESTAMP WITH TIME ZONE DEFAULT NOW()
            );
        """, fetch_all=False)
        print("✅ Cost calculations table created")
        
        # Step 10: Create user_tracking table
        print("📋 Step 10: Creating user_tracking table...")
        await DatabaseUtils.execute_query("""
            CREATE TABLE IF NOT EXISTS user_tracking (
                id UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
                request_id UUID NOT NULL REFERENCES requests(id) ON DELETE CASCADE,
                company_id UUID NOT NULL REFERENCES companies(id) ON DELETE CASCADE,
                user_tracking_method VARCHAR(50) NOT NULL,
                user_id VARCHAR(255),
                client_user_id VARCHAR(255),
                client_user_metadata JSONB,
                tracking_timestamp TIMESTAMP WITH TIME ZONE NOT NULL,
                vendor VARCHAR(100),
                model VARCHAR(255),
                endpoint VARCHAR(255),
                success BOOLEAN NOT NULL DEFAULT false,
                calculated_timestamp TEXT,
                created_at TIMESTAMP WITH TIME ZONE DEFAULT NOW()
            );
        """, fetch_all=False)
        print("✅ User tracking table created")
        
        # Step 11: Create worker_request_logs table
        print("📋 Step 11: Creating worker_request_logs table...")
        await DatabaseUtils.execute_query("""
            CREATE TABLE IF NOT EXISTS worker_request_logs (
                id UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
                request_id UUID NOT NULL REFERENCES requests(id) ON DELETE CASCADE,
                company_id UUID NOT NULL REFERENCES companies(id) ON DELETE CASCADE,
                worker_id VARCHAR(255),
                vendor VARCHAR(100) NOT NULL,
                model VARCHAR(255) NOT NULL,
                endpoint VARCHAR(255) NOT NULL,
                method VARCHAR(10) NOT NULL,
                status_code INTEGER NOT NULL,
                success BOOLEAN NOT NULL DEFAULT false,
                timestamp TIMESTAMP WITH TIME ZONE NOT NULL,
                calculated_timestamp TEXT,
                created_at TIMESTAMP WITH TIME ZONE DEFAULT NOW()
            );
        """, fetch_all=False)
        print("✅ Worker request logs table created")
        
        # Step 12: Create request_errors table
        print("📋 Step 12: Creating request_errors table...")
        await DatabaseUtils.execute_query("""
            CREATE TABLE IF NOT EXISTS request_errors (
                request_id UUID PRIMARY KEY REFERENCES requests(id) ON DELETE CASCADE,
                error_message TEXT NOT NULL,
                error_code VARCHAR(100),
                error_type VARCHAR(50) DEFAULT 'api_error',
                calculated_timestamp TEXT,
                created_at TIMESTAMP WITH TIME ZONE DEFAULT NOW()
            );
        """, fetch_all=False)
        print("✅ Request errors table created")
        
        # Step 13: Create worker_performance table
        print("📋 Step 13: Creating worker_performance table...")
        await DatabaseUtils.execute_query("""
            CREATE TABLE IF NOT EXISTS worker_performance (
                id UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
                worker_id VARCHAR(255) NOT NULL,
                company_id UUID NOT NULL REFERENCES companies(id) ON DELETE CASCADE,
                vendor VARCHAR(100) NOT NULL,
                model VARCHAR(255) NOT NULL,
                total_requests INTEGER NOT NULL DEFAULT 0,
                successful_requests INTEGER NOT NULL DEFAULT 0,
                failed_requests INTEGER NOT NULL DEFAULT 0,
                total_latency BIGINT NOT NULL DEFAULT 0,
                avg_latency INTEGER NOT NULL DEFAULT 0,
                total_cost NUMERIC(10, 6) NOT NULL DEFAULT 0,
                timestamp TIMESTAMP WITH TIME ZONE NOT NULL,
                calculated_timestamp TEXT,
                created_at TIMESTAMP WITH TIME ZONE DEFAULT NOW()
            );
        """, fetch_all=False)
        print("✅ Worker performance table created")
        
        # Step 14: Create indexes
        print("📋 Step 14: Creating indexes...")
        indexes = [
            "CREATE INDEX IF NOT EXISTS idx_requests_company_id ON requests(company_id);",
            "CREATE INDEX IF NOT EXISTS idx_requests_timestamp_utc ON requests(timestamp_utc);",
            "CREATE INDEX IF NOT EXISTS idx_requests_vendor_model_id ON requests(vendor_model_id);",
            "CREATE INDEX IF NOT EXISTS idx_requests_success ON requests(success);",
            "CREATE INDEX IF NOT EXISTS idx_cost_calculations_request_id ON cost_calculations(request_id);",
            "CREATE INDEX IF NOT EXISTS idx_cost_calculations_created_at ON cost_calculations(created_at);",
            "CREATE INDEX IF NOT EXISTS idx_user_tracking_request_id ON user_tracking(request_id);",
            "CREATE INDEX IF NOT EXISTS idx_user_tracking_company_id ON user_tracking(company_id);",
            "CREATE INDEX IF NOT EXISTS idx_user_tracking_user_id ON user_tracking(user_id);",
            "CREATE INDEX IF NOT EXISTS idx_worker_logs_request_id ON worker_request_logs(request_id);",
            "CREATE INDEX IF NOT EXISTS idx_worker_logs_company_id ON worker_request_logs(company_id);",
            "CREATE INDEX IF NOT EXISTS idx_worker_logs_timestamp ON worker_request_logs(timestamp);",
            "CREATE INDEX IF NOT EXISTS idx_api_keys_company_id ON api_keys(company_id);",
            "CREATE INDEX IF NOT EXISTS idx_api_keys_key_hash ON api_keys(key_hash);"
        ]
        
        for i, index in enumerate(indexes, 1):
            await DatabaseUtils.execute_query(index, fetch_all=False)
            print(f"  ✅ Index {i}/{len(indexes)} created")
        
        # Step 15: Insert initial data
        print("📋 Step 15: Inserting initial data...")
        
        # Insert vendors
        await DatabaseUtils.execute_query("""
            INSERT INTO vendors (name, display_name, description) VALUES
            ('openai', 'OpenAI', 'OpenAI API services'),
            ('anthropic', 'Anthropic', 'Anthropic Claude services'),
            ('google', 'Google', 'Google Gemini services'),
            ('cohere', 'Cohere', 'Cohere AI services')
            ON CONFLICT (name) DO NOTHING;
        """, fetch_all=False)
        print("  ✅ Vendors inserted")
        
        # Insert vendor models
        await DatabaseUtils.execute_query("""
            INSERT INTO vendor_models (vendor_id, name, display_name) VALUES
            ((SELECT id FROM vendors WHERE name = 'openai'), 'gpt-3.5-turbo', 'GPT-3.5 Turbo'),
            ((SELECT id FROM vendors WHERE name = 'openai'), 'gpt-4', 'GPT-4'),
            ((SELECT id FROM vendors WHERE name = 'openai'), 'gpt-4-turbo', 'GPT-4 Turbo'),
            ((SELECT id FROM vendors WHERE name = 'anthropic'), 'claude-3-opus-20240229', 'Claude 3 Opus'),
            ((SELECT id FROM vendors WHERE name = 'anthropic'), 'claude-3-sonnet-20240229', 'Claude 3 Sonnet'),
            ((SELECT id FROM vendors WHERE name = 'anthropic'), 'claude-3-haiku-20240307', 'Claude 3 Haiku'),
            ((SELECT id FROM vendors WHERE name = 'google'), 'gemini-pro', 'Gemini Pro'),
            ((SELECT id FROM vendors WHERE name = 'google'), 'gemini-1.5-pro', 'Gemini 1.5 Pro'),
            ((SELECT id FROM vendors WHERE name = 'google'), 'gemini-1.5-flash', 'Gemini 1.5 Flash'),
            ((SELECT id FROM vendors WHERE name = 'cohere'), 'command', 'Command'),
            ((SELECT id FROM vendors WHERE name = 'cohere'), 'command-light', 'Command Light'),
            ((SELECT id FROM vendors WHERE name = 'cohere'), 'embed-english-v3.0', 'Embed English v3.0')
            ON CONFLICT (vendor_id, name) DO NOTHING;
        """, fetch_all=False)
        print("  ✅ Vendor models inserted")
        
        # Insert test companies
        await DatabaseUtils.execute_query("""
            INSERT INTO companies (id, name, description, schema_name, rate_limit_rps, monthly_quota) VALUES
            ('aaaaaaaa-bbbb-cccc-dddd-123456789012', 'Test Company A', 'Test company for development', 'company_test_a', 1000, 100000),
            ('6fa8a706-a938-4010-922c-05d22148bcad', 'Test Company B', 'Another test company', 'company_test_b', 500, 50000)
            ON CONFLICT (id) DO NOTHING;
        """, fetch_all=False)
        print("  ✅ Test companies inserted")
        
        print("🎉 Database initialization completed successfully!")
        return True
        
    except Exception as e:
        print(f"❌ Database initialization failed: {e}")
        return False

async def verify_schema():
    """Verify that the schema was created correctly"""
    try:
        print("🔍 Verifying database schema...")
        
        # Check if all tables exist
        tables = [
            'companies', 'vendors', 'vendor_models', 'users', 'user_sessions',
            'api_keys', 'requests', 'cost_calculations', 'user_tracking',
            'worker_request_logs', 'request_errors', 'worker_performance'
        ]
        
        for table in tables:
            try:
                result = await DatabaseUtils.execute_query(f"SELECT COUNT(*) as count FROM {table}", fetch_all=True)
                count = result[0]['count'] if result else 0
                print(f"✅ Table {table}: {count} rows")
            except Exception as e:
                print(f"❌ Table {table} not found or error: {e}")
                return False
        
        print("🎉 Schema verification completed successfully!")
        return True
        
    except Exception as e:
        print(f"❌ Schema verification failed: {e}")
        return False

async def main():
    """Main function"""
    print("🔧 API Lens Simple Database Initialization")
    print("=" * 50)
    
    try:
        # Initialize database
        if not await init_database_simple():
            print("❌ Database initialization failed")
            return 1
        
        # Verify schema
        if not await verify_schema():
            print("❌ Schema verification failed")
            return 1
        
        print("\n🎉 Database setup completed successfully!")
        print("📊 Your database is now ready for use.")
        print("🚀 You can start the API server with: uvicorn app.main:app --reload")
        
        return 0
        
    except Exception as e:
        print(f"❌ Unexpected error: {e}")
        return 1

if __name__ == "__main__":
    exit_code = asyncio.run(main())
    sys.exit(exit_code) 
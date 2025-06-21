import os
import psycopg2
from psycopg2.extensions import ISOLATION_LEVEL_AUTOCOMMIT
from dotenv import load_dotenv
from datetime import datetime

def init_database():
    # Load environment variables
    load_dotenv()
    
    # Get database connection details from environment variables
    db_url = os.getenv("DATABASE_URL")
    
    if not db_url:
        raise ValueError("DATABASE_URL environment variable is not set")
    
    # Track results
    results = {
        'success': [],
        'skipped': [],
        'failed': []
    }
    
    def log_with_timestamp(message):
        timestamp = datetime.now().strftime("[%Y-%m-%d %H:%M:%S]")
        print(f"{timestamp} {message}")
    
    try:
        # Connect to the database
        log_with_timestamp("🔌 Connecting to database...")
        conn = psycopg2.connect(db_url)
        conn.set_isolation_level(ISOLATION_LEVEL_AUTOCOMMIT)
        cursor = conn.cursor()
        log_with_timestamp("✅ Connected successfully!")
        
        # Get the directory of the current script
        current_dir = os.path.dirname(os.path.abspath(__file__))
        
        # Execute core system schema
        core_schema_path = os.path.join(current_dir, "schema", "01_core_system.sql")
        try:
            with open(core_schema_path, 'r') as file:
                core_schema_sql = file.read()
            cursor.execute(core_schema_sql)
            log_with_timestamp("✅ Core system schema initialized")
            results['success'].append("Core system schema initialized")
        except Exception as e:
            if "already exists" in str(e):
                log_with_timestamp("⚠️  Core system schema already exists, skipping...")
                results['skipped'].append("Core system schema (already exists)")
            else:
                log_with_timestamp(f"❌ Failed to execute core schema: {str(e)}")
                results['failed'].append(f"Core system schema: {str(e)}")
        
        # Execute company schema function
        company_schema_path = os.path.join(current_dir, "schema", "02_company_schema.sql")
        try:
            with open(company_schema_path, 'r') as file:
                company_schema_sql = file.read()
            cursor.execute(company_schema_sql)
            log_with_timestamp("✅ Company schema function created")
            results['success'].append("Company schema function created")
        except Exception as e:
            if "already exists" in str(e):
                log_with_timestamp("⚠️  Company schema function already exists, skipping...")
                results['skipped'].append("Company schema function (already exists)")
            else:
                log_with_timestamp(f"  ❌ Error executing statement: {str(e)}")
                results['failed'].append(f"Company schema function: {str(e)}")
        
        # Clean up existing test company schema before creating new one
        try:
            log_with_timestamp("\n🧹 Cleaning up existing test company...")
            cursor.execute("DROP SCHEMA IF EXISTS company_test_company CASCADE")
            # FIXED: Using slug column instead of schema_name
            cursor.execute("DELETE FROM companies WHERE slug = 'test-company'")
            log_with_timestamp("✅ Cleanup complete")
        except Exception as e:
            log_with_timestamp(f"⚠️  Cleanup warning: {str(e)}")
        
        # Test the company schema function with a sample company
        try:
            log_with_timestamp("\n🧪 Testing company schema creation...")
            
            # FIXED: Create test company using slug column instead of schema_name
            cursor.execute("""
                INSERT INTO companies (name, slug, status) 
                VALUES ('Test Company', 'test-company', 'active')
                RETURNING id
            """)
            company_id = cursor.fetchone()[0]
            
            # Create schema using the company ID
            cursor.execute(f"SELECT create_company_schema('{company_id}')")
            
            log_with_timestamp("✅ Test company schema created successfully!")
            results['success'].append("Test company schema created")
            
            # Verify the test company schema was created
            cursor.execute("""
                SELECT table_name 
                FROM information_schema.tables 
                WHERE table_schema = 'company_test_company'
                ORDER BY table_name
            """)
            test_tables = cursor.fetchall()
            if test_tables:
                log_with_timestamp("\n📋 Tables in test company schema:")
                for table in test_tables:
                    log_with_timestamp(f"  ✓ {table[0]}")
            
        except Exception as e:
            log_with_timestamp(f"⚠️  Test company creation failed: {str(e)}")
            results['failed'].append(f"Test company creation: {str(e)}")
        
        # Verify database setup
        log_with_timestamp("\n📊 Verifying database setup...")
        
        # Check tables
        cursor.execute("""
            SELECT table_name 
            FROM information_schema.tables 
            WHERE table_schema = 'public' 
            AND table_type = 'BASE TABLE'
            ORDER BY table_name
        """)
        tables = cursor.fetchall()
        log_with_timestamp("\n📋 Tables in public schema:")
        for table in tables:
            log_with_timestamp(f"  ✓ {table[0]}")
        
        # Check indexes
        cursor.execute("""
            SELECT indexname 
            FROM pg_indexes 
            WHERE schemaname = 'public'
            ORDER BY indexname
        """)
        indexes = cursor.fetchall()
        log_with_timestamp("\n🔍 Indexes created:")
        for index in indexes:
            log_with_timestamp(f"  ✓ {index[0]}")
        
        # Check functions
        cursor.execute("""
            SELECT routine_name 
            FROM information_schema.routines 
            WHERE routine_schema = 'public' 
            AND routine_type = 'FUNCTION'
            ORDER BY routine_name
        """)
        functions = cursor.fetchall()
        log_with_timestamp("\n🔧 Functions created:")
        for func in functions:
            log_with_timestamp(f"  ✓ {func[0]}")
        
        log_with_timestamp("\n🎉 Database initialization completed!")
        
    except Exception as e:
        log_with_timestamp(f"\n❌ Critical error: {str(e)}")
        raise
    finally:
        if 'cursor' in locals():
            cursor.close()
        if 'conn' in locals():
            conn.close()
        log_with_timestamp("\n🔌 Database connection closed")
        
        # Print summary
        log_with_timestamp("\n===== SUMMARY =====")
        log_with_timestamp(f"Success: {results['success']}")
        log_with_timestamp(f"Skipped: {results['skipped']}")
        log_with_timestamp(f"Failed: {results['failed']}")

if __name__ == "__main__":
    init_database()
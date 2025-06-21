import asyncio
import os
from pathlib import Path
from sqlalchemy.ext.asyncio import create_async_engine
from dotenv import load_dotenv

# Load environment variables
load_dotenv()

async def init_database():
    """Initialize database with core tables and functions"""
    # Get database URL from environment
    database_url = os.getenv("DATABASE_URL")
    if not database_url:
        raise ValueError("DATABASE_URL environment variable is not set")
    
    # Create engine
    engine = create_async_engine(database_url)
    
    try:
        # Read and execute core tables SQL
        core_tables_path = Path(__file__).parent.parent / "sql" / "core_tables.sql"
        with open(core_tables_path) as f:
            core_tables_sql = f.read()
        
        async with engine.begin() as conn:
            await conn.execute(core_tables_sql)
            print("Core tables created successfully")
        
        # Read and execute company schema SQL
        company_schema_path = Path(__file__).parent.parent / "sql" / "company_schema.sql"
        with open(company_schema_path) as f:
            company_schema_sql = f.read()
        
        async with engine.begin() as conn:
            await conn.execute(company_schema_sql)
            print("Company schema functions created successfully")
        
        # Test company schema creation
        async with engine.begin() as conn:
            await conn.execute("SELECT create_company_schema('test')")
            print("Test company schema created successfully")
            
            # Verify schema isolation
            await conn.execute("SET search_path TO company_test")
            await conn.execute("SELECT * FROM api_logs LIMIT 1")
            print("Schema isolation verified")
            
            # Clean up test schema
            await conn.execute("SELECT drop_company_schema('test')")
            print("Test company schema dropped successfully")
        
        print("Database initialization completed successfully")
    
    except Exception as e:
        print(f"Error initializing database: {e}")
        raise
    finally:
        await engine.dispose()

if __name__ == "__main__":
    asyncio.run(init_database()) 
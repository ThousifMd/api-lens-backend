import asyncio
from sqlalchemy.ext.asyncio import create_async_engine
from sqlalchemy import text
from dotenv import load_dotenv
import os

async def test_connection():
    """Test database connection and basic operations"""
    load_dotenv()
    database_url = os.getenv("DATABASE_URL")
    
    if not database_url:
        print("Error: DATABASE_URL not found in .env file")
        return
    
    engine = create_async_engine(database_url)
    
    try:
        async with engine.begin() as conn:
            # Test basic connection
            result = await conn.execute(text("SELECT version()"))
            version = result.scalar()
            print(f"\nConnected to PostgreSQL: {version}")
            
            # Test core tables
            tables = await conn.execute(text("""
                SELECT table_name 
                FROM information_schema.tables 
                WHERE table_schema = 'public'
            """))
            print("\nCore tables found:")
            for table in tables:
                print(f"- {table[0]}")
            
            # Test company schema creation
            print("\nTesting company schema creation...")
            await conn.execute(text("SELECT create_company_schema('test')"))
            
            # Verify schema isolation
            await conn.execute(text("SET search_path TO company_test"))
            result = await conn.execute(text("SELECT current_schema()"))
            schema = result.scalar()
            print(f"Current schema: {schema}")
            
            # Clean up
            await conn.execute(text("SELECT drop_company_schema('test')"))
            print("Test company schema dropped")
            
            print("\nAll tests passed successfully!")
    
    except Exception as e:
        print(f"\nError testing connection: {e}")
        raise
    finally:
        await engine.dispose()

if __name__ == "__main__":
    asyncio.run(test_connection()) 
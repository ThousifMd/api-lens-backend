#!/usr/bin/env python3
"""
Check vendors table schema
"""
import asyncio
import os
from dotenv import load_dotenv
import asyncpg

# Load environment variables
load_dotenv()

async def check_vendors_schema():
    # Get database URL from environment
    DATABASE_URL = os.getenv('DATABASE_URL')
    if not DATABASE_URL:
        print("❌ DATABASE_URL not found in environment variables")
        return
    
    # Convert SQLAlchemy URL to asyncpg format
    if "+asyncpg" in DATABASE_URL:
        DATABASE_URL = DATABASE_URL.replace("postgresql+asyncpg://", "postgresql://")
    
    try:
        # Connect to database
        conn = await asyncpg.connect(DATABASE_URL)
        
        print("📊 Checking vendors table schema...")
        print("=" * 80)
        
        # Get all columns in vendors table
        columns_query = """
        SELECT 
            column_name,
            data_type,
            is_nullable,
            column_default
        FROM information_schema.columns
        WHERE table_name = 'vendors'
        ORDER BY ordinal_position;
        """
        
        columns = await conn.fetch(columns_query)
        
        print(f"\n✅ Found {len(columns)} columns in vendors table:\n")
        
        for col in columns:
            nullable = "NULL" if col['is_nullable'] == 'YES' else "NOT NULL"
            default = f"DEFAULT {col['column_default']}" if col['column_default'] else ""
            print(f"  - {col['column_name']:<20} {col['data_type']:<20} {nullable:<10} {default}")
        
        # Check existing vendors
        print("\n📊 Existing vendors:")
        print("-" * 80)
        
        vendors_query = "SELECT id, name, is_active FROM vendors ORDER BY name;"
        vendors = await conn.fetch(vendors_query)
        
        for vendor in vendors:
            status = "✅ Active" if vendor['is_active'] else "❌ Inactive"
            print(f"  - {vendor['name']:<20} {status}")
        
        await conn.close()
        
    except Exception as e:
        print(f"\n❌ Error: {e}")
        import traceback
        traceback.print_exc()

if __name__ == "__main__":
    asyncio.run(check_vendors_schema())
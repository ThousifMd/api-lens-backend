#!/usr/bin/env python3
"""
Check vendor_pricing table schema
"""
import asyncio
import os
from dotenv import load_dotenv
import asyncpg

# Load environment variables
load_dotenv()

async def check_vendor_pricing_schema():
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
        
        print("📊 Checking vendor_pricing table schema...")
        print("=" * 80)
        
        # Get all columns in vendor_pricing table
        columns_query = """
        SELECT 
            column_name,
            data_type,
            is_nullable,
            column_default
        FROM information_schema.columns
        WHERE table_name = 'vendor_pricing'
        ORDER BY ordinal_position;
        """
        
        columns = await conn.fetch(columns_query)
        
        print(f"\n✅ Found {len(columns)} columns in vendor_pricing table:\n")
        
        for col in columns:
            nullable = "NULL" if col['is_nullable'] == 'YES' else "NOT NULL"
            default = f"DEFAULT {col['column_default']}" if col['column_default'] else ""
            print(f"  - {col['column_name']:<30} {col['data_type']:<20} {nullable:<10} {default}")
        
        # Check existing pricing
        print("\n📊 Sample existing pricing:")
        print("-" * 80)
        
        pricing_query = """
        SELECT 
            vp.*, 
            vm.name as model_name,
            v.name as vendor_name
        FROM vendor_pricing vp
        JOIN vendor_models vm ON vp.model_id = vm.id
        JOIN vendors v ON vm.vendor_id = v.id
        LIMIT 3;
        """
        pricing = await conn.fetch(pricing_query)
        
        if pricing:
            for p in pricing:
                print(f"\n  Model: {p['vendor_name']} - {p['model_name']}")
                print(f"  Pricing type: {p['pricing_type']}")
                if p.get('input_price_per_1k_tokens'):
                    print(f"  Input price: ${p['input_price_per_1k_tokens']}/1k tokens")
                if p.get('output_price_per_1k_tokens'):
                    print(f"  Output price: ${p['output_price_per_1k_tokens']}/1k tokens")
                if p.get('per_image_price'):
                    print(f"  Image price: ${p['per_image_price']}/image")
        
        await conn.close()
        
    except Exception as e:
        print(f"\n❌ Error: {e}")
        import traceback
        traceback.print_exc()

if __name__ == "__main__":
    asyncio.run(check_vendor_pricing_schema())
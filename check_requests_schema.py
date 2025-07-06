#!/usr/bin/env python3
"""
Check the current requests table schema and compare with migration 008
"""
import asyncio
import os
from dotenv import load_dotenv
import asyncpg

# Load environment variables
load_dotenv()

async def check_requests_schema():
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
        
        print("📊 Checking requests table schema...")
        print("=" * 80)
        
        # Get all columns in requests table
        columns_query = """
        SELECT 
            column_name,
            data_type,
            is_nullable,
            column_default,
            character_maximum_length
        FROM information_schema.columns
        WHERE table_name = 'requests'
        ORDER BY ordinal_position;
        """
        
        columns = await conn.fetch(columns_query)
        
        print(f"\n✅ Found {len(columns)} columns in requests table:\n")
        
        # Expected image generation columns from migration 008
        expected_image_columns = {
            'image_count': 'integer',
            'image_urls': 'ARRAY',
            'image_dimensions': 'character varying',
            'image_quality': 'character varying',
            'image_style': 'character varying',
            'prompt': 'text',
            'negative_prompt': 'text',
            'seed': 'integer',
            'generation_steps': 'integer',
            'guidance_scale': 'numeric'
        }
        
        # Check which columns exist
        existing_columns = {col['column_name']: col for col in columns}
        
        # Print all columns
        for col in columns:
            print(f"  - {col['column_name']:<25} {col['data_type']:<20} {'' if col['is_nullable'] == 'YES' else 'NOT NULL'}")
        
        print(f"\n🔍 Checking for image generation columns from migration 008:")
        print("-" * 80)
        
        missing_columns = []
        existing_image_columns = []
        
        for col_name, expected_type in expected_image_columns.items():
            if col_name in existing_columns:
                actual_type = existing_columns[col_name]['data_type']
                print(f"  ✅ {col_name:<25} EXISTS (type: {actual_type})")
                existing_image_columns.append(col_name)
            else:
                print(f"  ❌ {col_name:<25} MISSING (expected type: {expected_type})")
                missing_columns.append(col_name)
        
        # Check for indexes
        print(f"\n🔍 Checking for image generation indexes:")
        print("-" * 80)
        
        indexes_query = """
        SELECT 
            indexname,
            indexdef
        FROM pg_indexes
        WHERE tablename = 'requests'
        AND (indexname LIKE '%image%' OR indexdef LIKE '%image%');
        """
        
        indexes = await conn.fetch(indexes_query)
        
        if indexes:
            for idx in indexes:
                print(f"  ✅ {idx['indexname']}")
                print(f"     {idx['indexdef']}")
        else:
            print("  ❌ No image-related indexes found")
        
        # Check constraints
        print(f"\n🔍 Checking for image generation constraints:")
        print("-" * 80)
        
        constraints_query = """
        SELECT 
            conname,
            pg_get_constraintdef(oid) as definition
        FROM pg_constraint
        WHERE conrelid = 'requests'::regclass
        AND (conname LIKE '%image%' OR pg_get_constraintdef(oid) LIKE '%image%');
        """
        
        constraints = await conn.fetch(constraints_query)
        
        if constraints:
            for con in constraints:
                print(f"  ✅ {con['conname']}")
                print(f"     {con['definition']}")
        else:
            print("  ❌ No image-related constraints found")
        
        # Summary
        print("\n" + "=" * 80)
        print("📈 SUMMARY:")
        print("-" * 80)
        
        if missing_columns:
            print(f"❌ Migration 008 appears NOT fully applied")
            print(f"   - {len(missing_columns)} columns are missing: {', '.join(missing_columns)}")
            print(f"\n💡 To apply the migration, run:")
            print(f"   python scripts/migrations/migrate_db.py")
        else:
            print(f"✅ Migration 008 appears to be fully applied")
            print(f"   - All {len(expected_image_columns)} image generation columns exist")
        
        if existing_image_columns:
            print(f"\n✅ Existing image columns: {', '.join(existing_image_columns)}")
        
        # Check for any data in image columns
        if existing_image_columns:
            print(f"\n🔍 Checking for existing image generation data:")
            print("-" * 80)
            
            data_check_query = """
            SELECT 
                COUNT(*) as total_requests,
                COUNT(*) FILTER (WHERE image_count > 0) as image_requests,
                COUNT(*) FILTER (WHERE prompt IS NOT NULL) as requests_with_prompt
            FROM requests;
            """
            
            data_stats = await conn.fetchrow(data_check_query)
            
            print(f"  - Total requests: {data_stats['total_requests']}")
            print(f"  - Image generation requests: {data_stats['image_requests']}")
            print(f"  - Requests with prompts: {data_stats['requests_with_prompt']}")
        
        await conn.close()
        
    except Exception as e:
        print(f"\n❌ Error checking schema: {e}")
        import traceback
        traceback.print_exc()

if __name__ == "__main__":
    asyncio.run(check_requests_schema())
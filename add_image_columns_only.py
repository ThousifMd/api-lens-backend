#!/usr/bin/env python3
"""
Add only the image generation columns to requests table
"""
import asyncio
import os
from dotenv import load_dotenv
import asyncpg

# Load environment variables
load_dotenv()

async def add_image_columns_only():
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
        
        print("\n🚀 Adding image generation columns to requests table...")
        print("=" * 80)
        
        # Add columns one by one to better track errors
        columns_to_add = [
            ("image_count", "INTEGER DEFAULT 0"),
            ("image_urls", "TEXT[]"),
            ("image_dimensions", "VARCHAR(20)"),
            ("image_quality", "VARCHAR(20)"),
            ("image_style", "VARCHAR(50)"),
            ("prompt", "TEXT"),
            ("negative_prompt", "TEXT"),
            ("seed", "INTEGER"),
            ("generation_steps", "INTEGER"),
            ("guidance_scale", "DECIMAL(5,2)")
        ]
        
        added_count = 0
        
        for column_name, column_type in columns_to_add:
            try:
                sql = f"ALTER TABLE requests ADD COLUMN IF NOT EXISTS {column_name} {column_type};"
                await conn.execute(sql)
                print(f"✅ Added column: {column_name}")
                added_count += 1
            except Exception as e:
                print(f"❌ Failed to add column {column_name}: {e}")
        
        print(f"\n📊 Added {added_count} columns")
        
        # Verify columns were added
        print("\n🔍 Verifying columns...")
        
        columns = await conn.fetch("""
            SELECT column_name, data_type
            FROM information_schema.columns
            WHERE table_name = 'requests'
            AND column_name IN (
                'image_count', 'image_urls', 'image_dimensions', 
                'image_quality', 'image_style', 'prompt', 
                'negative_prompt', 'seed', 'generation_steps', 'guidance_scale'
            )
            ORDER BY column_name;
        """)
        
        print(f"\n✅ Image generation columns now in table ({len(columns)}/10):")
        for col in columns:
            print(f"  - {col['column_name']:<25} {col['data_type']}")
        
        await conn.close()
        
        if len(columns) == 10:
            print("\n✅ All image generation columns successfully added!")
            print("\n💡 Next steps:")
            print("   1. Run the full migration script to add indexes, constraints, and pricing")
            print("   2. Or manually update models and pricing as needed")
        else:
            print(f"\n⚠️  Only {len(columns)}/10 columns were added")
        
    except Exception as e:
        print(f"\n❌ Error: {e}")
        import traceback
        traceback.print_exc()

if __name__ == "__main__":
    asyncio.run(add_image_columns_only())
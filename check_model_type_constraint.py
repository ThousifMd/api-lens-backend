#!/usr/bin/env python3
"""
Check model_type constraint on vendor_models table
"""
import asyncio
import os
from dotenv import load_dotenv
import asyncpg

# Load environment variables
load_dotenv()

async def check_model_type_constraint():
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
        
        print("🔍 Checking model_type constraint on vendor_models table...")
        print("=" * 80)
        
        # Get constraint definition
        constraint_query = """
        SELECT 
            conname,
            pg_get_constraintdef(oid) as definition
        FROM pg_constraint
        WHERE conrelid = 'vendor_models'::regclass
        AND conname LIKE '%model_type%';
        """
        
        constraints = await conn.fetch(constraint_query)
        
        if constraints:
            print("\n📊 Model type constraint:")
            for con in constraints:
                print(f"  - {con['conname']}")
                print(f"    {con['definition']}")
        
        # Get distinct model types currently in use
        print("\n📊 Current model types in vendor_models:")
        model_types = await conn.fetch("""
            SELECT DISTINCT model_type, COUNT(*) as count
            FROM vendor_models
            GROUP BY model_type
            ORDER BY model_type;
        """)
        
        for mt in model_types:
            print(f"  - {mt['model_type']:<20} ({mt['count']} models)")
        
        # Check if we need to add image_generation to allowed types
        print("\n💡 Checking if 'image_generation' is allowed...")
        
        # Get the actual CHECK constraint definition
        check_def_query = """
        SELECT 
            conname,
            pg_get_constraintdef(oid) as definition
        FROM pg_constraint
        WHERE conrelid = 'vendor_models'::regclass
        AND contype = 'c'
        AND pg_get_constraintdef(oid) LIKE '%model_type%';
        """
        
        check_constraints = await conn.fetch(check_def_query)
        
        if check_constraints:
            print("\n📋 CHECK constraints on vendor_models:")
            for con in check_constraints:
                print(f"  - {con['conname']}")
                print(f"    {con['definition']}")
                
                # Check if image_generation is in the allowed list
                if 'image_generation' not in con['definition']:
                    print("\n❌ 'image_generation' is NOT in the allowed model types!")
                    print("\n💡 To fix this, we need to:")
                    print("   1. Drop the existing constraint")
                    print("   2. Add a new constraint that includes 'image_generation'")
                else:
                    print("\n✅ 'image_generation' is already allowed")
        
        await conn.close()
        
    except Exception as e:
        print(f"\n❌ Error: {e}")
        import traceback
        traceback.print_exc()

if __name__ == "__main__":
    asyncio.run(check_model_type_constraint())
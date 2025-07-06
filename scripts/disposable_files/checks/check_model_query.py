#!/usr/bin/env python3
"""Test the model query to see what's wrong"""
import asyncio
from app.database import DatabaseUtils, init_database, close_database

async def main():
    await init_database()
    
    print("🔍 TESTING MODEL QUERY ISSUE")
    print("=" * 50)
    
    # Show what columns exist in vendor_models
    print("\n📋 ACTUAL COLUMNS IN vendor_models TABLE:")
    columns = await DatabaseUtils.execute_query("""
        SELECT column_name, data_type
        FROM information_schema.columns
        WHERE table_name = 'vendor_models'
        ORDER BY ordinal_position
    """, fetch_all=True)
    
    for col in columns:
        print(f"  ✅ {col['column_name']}: {col['data_type']}")
    
    # Test the problematic query
    print("\n🚨 TESTING THE BROKEN QUERY:")
    try:
        model_query = """
        SELECT vm.id, vm.name, vm.display_name, vm.is_active
        FROM vendor_models vm
        JOIN vendors v ON vm.vendor_id = v.id
        WHERE v.name = $1 AND vm.name = $2 AND vm.is_active = true
        """
        
        result = await DatabaseUtils.execute_query(model_query, ["openai", "dall-e-3"], fetch_all=False)
        print("  ✅ Query succeeded!")
        print(f"  Result: {result}")
        
    except Exception as e:
        print(f"  ❌ Query failed: {e}")
    
    # Test the fixed query
    print("\n🔧 TESTING THE FIXED QUERY:")
    try:
        fixed_query = """
        SELECT vm.id, vm.name, vm.name as display_name, vm.is_active
        FROM vendor_models vm
        JOIN vendors v ON vm.vendor_id = v.id
        WHERE v.name = $1 AND vm.name = $2 AND vm.is_active = true
        """
        
        result = await DatabaseUtils.execute_query(fixed_query, ["openai", "dall-e-3"], fetch_all=False)
        print("  ✅ Fixed query succeeded!")
        print(f"  Result: {result}")
        
    except Exception as e:
        print(f"  ❌ Fixed query also failed: {e}")
    
    await close_database()

if __name__ == "__main__":
    asyncio.run(main()) 
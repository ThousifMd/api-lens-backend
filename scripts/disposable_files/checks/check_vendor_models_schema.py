#!/usr/bin/env python3
"""Check actual schema of vendor_models table"""
import asyncio
from app.database import DatabaseUtils, init_database, close_database

async def main():
    await init_database()
    
    print("🔍 VENDOR_MODELS TABLE SCHEMA:")
    print("=" * 50)
    
    # Show what columns exist in vendor_models table
    columns = await DatabaseUtils.execute_query("""
        SELECT column_name, data_type, is_nullable
        FROM information_schema.columns
        WHERE table_name = 'vendor_models'
        ORDER BY ordinal_position
    """, fetch_all=True)
    
    for col in columns:
        nullable = "NULL" if col['is_nullable'] == 'YES' else "NOT NULL"
        print(f"  ✅ {col['column_name']}: {col['data_type']} {nullable}")
    
    print(f"\n📊 Total columns: {len(columns)}")
    
    # Check for any missing columns that the code expects
    expected_columns = [
        'id', 'vendor_id', 'name', 'display_name', 'description', 'model_type',
        'context_window', 'max_output_tokens', 'supports_functions', 'supports_vision',
        'is_active', 'is_deprecated', 'deprecated_at', 'sunset_at', 'replacement_model_id',
        'created_at', 'updated_at'
    ]
    
    actual_columns = [col['column_name'] for col in columns]
    
    print(f"\n🔍 SCHEMA COMPLIANCE CHECK:")
    print("=" * 50)
    
    missing_columns = [col for col in expected_columns if col not in actual_columns]
    extra_columns = [col for col in actual_columns if col not in expected_columns]
    
    if missing_columns:
        print(f"❌ MISSING COLUMNS ({len(missing_columns)}):")
        for col in missing_columns:
            print(f"  - {col}")
    else:
        print("✅ All expected columns present")
    
    if extra_columns:
        print(f"\n⚠️  EXTRA COLUMNS ({len(extra_columns)}):")
        for col in extra_columns:
            print(f"  - {col}")
    
    compliance_percentage = ((len(expected_columns) - len(missing_columns)) / len(expected_columns)) * 100
    print(f"\n📊 SCHEMA COMPLIANCE: {compliance_percentage:.1f}%")
    
    await close_database()

if __name__ == "__main__":
    asyncio.run(main()) 
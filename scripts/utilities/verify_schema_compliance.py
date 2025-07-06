#!/usr/bin/env python3
"""Verify schema compliance after migration"""
import asyncio
from app.database import DatabaseUtils, init_database, close_database

async def verify_schema():
    await init_database()
    
    print("🔍 VERIFYING SCHEMA COMPLIANCE")
    print("=" * 60)
    
    # Check client_users columns
    print("\n📊 CLIENT_USERS TABLE:")
    print("-" * 40)
    
    client_users_result = await DatabaseUtils.execute_query("""
        SELECT column_name, data_type, is_nullable
        FROM information_schema.columns 
        WHERE table_name = 'client_users'
        ORDER BY ordinal_position
    """, fetch_all=True)
    
    required_columns = ['display_name', 'email', 'avatar_url', 'user_tier', 'signup_date', 'tags']
    found_columns = [col['column_name'] for col in client_users_result]
    
    print("Required columns for v2 compliance:")
    for col in required_columns:
        if col in found_columns:
            print(f"  ✅ {col}")
        else:
            print(f"  ❌ {col} (MISSING)")
    
    # Check if old columns were removed
    removed_columns = ['tier', 'timezone']
    print("\nColumns that should be removed:")
    for col in removed_columns:
        if col not in found_columns:
            print(f"  ✅ {col} (removed)")
        else:
            print(f"  ❌ {col} (still exists)")
    
    # Check vendor_models columns
    print("\n\n📊 VENDOR_MODELS TABLE:")
    print("-" * 40)
    
    vendor_models_result = await DatabaseUtils.execute_query("""
        SELECT column_name, data_type, is_nullable
        FROM information_schema.columns 
        WHERE table_name = 'vendor_models'
        ORDER BY ordinal_position
    """, fetch_all=True)
    
    required_vm_columns = ['display_name', 'description', 'context_window', 'max_output_tokens', 
                          'supports_functions', 'supports_vision', 'sunset_at', 'replacement_model_id']
    found_vm_columns = [col['column_name'] for col in vendor_models_result]
    
    print("Required columns for v2 compliance:")
    for col in required_vm_columns:
        if col in found_vm_columns:
            print(f"  ✅ {col}")
        else:
            print(f"  ❌ {col} (MISSING)")
    
    # Check if pricing columns were moved
    removed_vm_columns = ['input_price_per_1k', 'output_price_per_1k', 'pricing_model']
    print("\nColumns that should be removed (belong in vendor_pricing):")
    for col in removed_vm_columns:
        if col not in found_vm_columns:
            print(f"  ✅ {col} (removed)")
        else:
            print(f"  ❌ {col} (still exists)")
    
    # Show sample updated data
    print("\n\n📋 SAMPLE UPDATED CLIENT_USERS:")
    print("-" * 80)
    
    sample_users = await DatabaseUtils.execute_query("""
        SELECT client_user_id, display_name, email, user_tier, tags
        FROM client_users
        LIMIT 5
    """, fetch_all=True)
    
    for user in sample_users:
        print(f"{user['client_user_id']:20} | {user['display_name']:20} | {user['email']:25} | {user['user_tier']:8} | {user['tags']}")
    
    print("\n\n📋 SAMPLE UPDATED VENDOR_MODELS:")
    print("-" * 80)
    
    sample_models = await DatabaseUtils.execute_query("""
        SELECT name, display_name, context_window, supports_functions, supports_vision
        FROM vendor_models
        LIMIT 5
    """, fetch_all=True)
    
    for model in sample_models:
        print(f"{model['name']:30} | Context: {model['context_window']:6} | Functions: {model['supports_functions']} | Vision: {model['supports_vision']}")
    
    # Calculate compliance percentages
    client_users_compliance = (len([c for c in required_columns if c in found_columns]) / len(required_columns)) * 100
    vendor_models_compliance = (len([c for c in required_vm_columns if c in found_vm_columns]) / len(required_vm_columns)) * 100
    
    print("\n\n📊 COMPLIANCE SUMMARY:")
    print("-" * 40)
    print(f"client_users table: {client_users_compliance:.1f}% compliant")
    print(f"vendor_models table: {vendor_models_compliance:.1f}% compliant")
    
    if client_users_compliance == 100 and vendor_models_compliance == 100:
        print("\n✅ Both tables are now 100% compliant with schema v2!")
    else:
        print("\n⚠️  Some compliance issues remain. Check the details above.")
    
    await close_database()

if __name__ == "__main__":
    asyncio.run(verify_schema())
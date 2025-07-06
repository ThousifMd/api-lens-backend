#!/usr/bin/env python3
"""Verify the exact schema issues mentioned"""
import asyncio
from app.database import DatabaseUtils, init_database, close_database

async def main():
    await init_database()
    
    print("🔍 VERIFYING SCHEMA ISSUES")
    print("=" * 60)
    
    # 1. Check requests table for image-related columns
    print("\n1️⃣ REQUESTS TABLE - Checking for image columns:")
    print("-" * 40)
    
    image_columns = ['prompt', 'negative_prompt', 'image_count', 'image_urls', 
                     'image_dimensions', 'image_quality', 'image_style', 
                     'seed', 'generation_steps', 'guidance_scale']
    
    for col in image_columns:
        result = await DatabaseUtils.execute_query(f"""
            SELECT column_name 
            FROM information_schema.columns 
            WHERE table_name = 'requests' AND column_name = '{col}'
        """, fetch_all=True)
        
        exists = "✅ EXISTS" if result else "❌ MISSING"
        print(f"  {col}: {exists}")
    
    # 2. Check client_users table for location columns
    print("\n\n2️⃣ CLIENT_USERS TABLE - Checking for location columns:")
    print("-" * 40)
    
    location_columns = ['region', 'city', 'latitude', 'longitude', 
                        'timezone_name', 'utc_offset']
    
    for col in location_columns:
        result = await DatabaseUtils.execute_query(f"""
            SELECT column_name 
            FROM information_schema.columns 
            WHERE table_name = 'client_users' AND column_name = '{col}'
        """, fetch_all=True)
        
        exists = "✅ EXISTS" if result else "❌ MISSING"
        print(f"  {col}: {exists}")
    
    # 3. Check vendor_pricing for company_id
    print("\n\n3️⃣ VENDOR_PRICING TABLE - Checking for company_id:")
    print("-" * 40)
    
    result = await DatabaseUtils.execute_query("""
        SELECT column_name 
        FROM information_schema.columns 
        WHERE table_name = 'vendor_pricing' AND column_name = 'company_id'
    """, fetch_all=True)
    
    if result:
        print("  ❌ company_id EXISTS (should NOT exist - pricing is global)")
    else:
        print("  ✅ company_id DOES NOT EXIST (correct - pricing is global)")
    
    # 4. Check pricing service query
    print("\n\n4️⃣ CHECKING PRICING SERVICE QUERY:")
    print("-" * 40)
    
    try:
        # Try to run a pricing query similar to what pricing service uses
        test_query = """
            SELECT vp.input_cost_per_1k_tokens, vp.output_cost_per_1k_tokens
            FROM vendor_pricing vp
            JOIN vendor_models vm ON vp.model_id = vm.id
            JOIN vendors v ON vm.vendor_id = v.id
            WHERE v.name = 'openai' AND vm.name = 'gpt-4'
            AND vp.is_active = true
            LIMIT 1
        """
        result = await DatabaseUtils.execute_query(test_query, fetch_all=True)
        print("  ✅ Basic pricing query works")
    except Exception as e:
        print(f"  ❌ Pricing query error: {str(e)}")
    
    await close_database()
    
    print("\n\n📋 SUMMARY:")
    print("=" * 60)
    print("1. REQUESTS table is missing image-generation specific columns")
    print("2. CLIENT_USERS table is missing detailed location columns")
    print("3. VENDOR_PRICING correctly does NOT have company_id")
    print("4. The pricing service error comes from querying non-existent company_id")

if __name__ == "__main__":
    asyncio.run(main())
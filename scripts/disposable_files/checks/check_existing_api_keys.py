#!/usr/bin/env python3
"""Check existing API keys in the database"""
import asyncio
from app.database import DatabaseUtils, init_database, close_database

async def main():
    await init_database()
    
    print("🔍 EXISTING API KEYS IN DATABASE:")
    print("=" * 50)
    
    # Get all API keys with company info
    api_keys = await DatabaseUtils.execute_query("""
        SELECT 
            ak.id,
            ak.name,
            ak.key_prefix,
            ak.environment,
            ak.is_active,
            ak.created_at,
            ak.last_used_at,
            c.name as company_name,
            c.slug as company_slug
        FROM api_keys ak
        JOIN companies c ON ak.company_id = c.id
        ORDER BY ak.created_at DESC
    """, fetch_all=True)
    
    if not api_keys:
        print("❌ No API keys found in database")
        print("\n💡 To create an API key for frontend access:")
        print("   1. Use the /auth/generate endpoint")
        print("   2. Or run: python3 -c \"from app.services.auth import generate_api_key; import asyncio; print(asyncio.run(generate_api_key('your-company-id', 'Frontend API Key')))\"")
        return
    
    print(f"📊 Found {len(api_keys)} API keys:")
    print()
    
    for i, key in enumerate(api_keys, 1):
        status = "✅ ACTIVE" if key['is_active'] else "❌ INACTIVE"
        env = key['environment'].upper()
        last_used = key['last_used_at'].strftime("%Y-%m-%d %H:%M") if key['last_used_at'] else "Never"
        
        print(f"{i}. {key['name']} ({status})")
        print(f"   Company: {key['company_name']} ({key['company_slug']})")
        print(f"   Environment: {env}")
        print(f"   Prefix: {key['key_prefix']}")
        print(f"   Created: {key['created_at'].strftime('%Y-%m-%d %H:%M')}")
        print(f"   Last Used: {last_used}")
        print()
    
    # Show how to use the API key
    print("🔑 HOW TO USE THE API KEY:")
    print("-" * 30)
    print("1. Add to request headers:")
    print("   Authorization: Bearer als_xxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxx")
    print("   OR")
    print("   X-API-Key: als_xxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxx")
    print()
    print("2. Example curl request:")
    print("   curl -H 'Authorization: Bearer als_xxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxx' \\")
    print("        http://localhost:8000/proxy/logs/optimized")
    print()
    print("3. Frontend JavaScript:")
    print("   fetch('/api/data', {")
    print("     headers: {")
    print("       'Authorization': 'Bearer als_xxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxx'")
    print("     }")
    print("   })")
    
    await close_database()

if __name__ == "__main__":
    asyncio.run(main()) 
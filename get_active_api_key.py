#!/usr/bin/env python3
"""Get an existing API key that's been used recently"""
import asyncio
import hashlib
from app.database import DatabaseUtils, init_database, close_database
from app.config import get_settings

settings = get_settings()

async def main():
    await init_database()
    
    print("🔍 FINDING ACTIVE API KEY IN USE:")
    print("=" * 50)
    
    # Get API keys that have been used recently
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
            c.slug as company_slug,
            COUNT(r.id) as request_count
        FROM api_keys ak
        JOIN companies c ON ak.company_id = c.id
        LEFT JOIN requests r ON ak.id = r.api_key_id
        WHERE ak.is_active = true
        GROUP BY ak.id, ak.name, ak.key_prefix, ak.environment, ak.is_active, 
                 ak.created_at, ak.last_used_at, c.name, c.slug
        HAVING COUNT(r.id) > 0
        ORDER BY ak.last_used_at DESC NULLS LAST, COUNT(r.id) DESC
        LIMIT 5
    """, fetch_all=True)
    
    if not api_keys:
        print("❌ No API keys with usage found")
        print("\n🔍 Checking for any active API keys...")
        
        # Get any active API keys
        active_keys = await DatabaseUtils.execute_query("""
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
            WHERE ak.is_active = true
            ORDER BY ak.created_at DESC
            LIMIT 3
        """, fetch_all=True)
        
        if active_keys:
            print(f"📊 Found {len(active_keys)} active API keys (no usage yet):")
            print()
            
            for i, key in enumerate(active_keys, 1):
                print(f"{i}. {key['name']}")
                print(f"   Company: {key['company_name']} ({key['company_slug']})")
                print(f"   Environment: {key['environment'].upper()}")
                print(f"   Prefix: {key['key_prefix']}")
                print(f"   Created: {key['created_at'].strftime('%Y-%m-%d %H:%M')}")
                print()
            
            # Try to reconstruct the full API key for the first one
            if active_keys:
                key = active_keys[0]
                print("🔑 RECONSTRUCTING API KEY:")
                print("-" * 30)
                print(f"Company: {key['company_name']}")
                print(f"Key Prefix: {key['key_prefix']}")
                print()
                print("⚠️  Note: The full API key cannot be reconstructed from the database")
                print("   (it's stored as a hash for security). You'll need to:")
                print("   1. Generate a new API key, or")
                print("   2. Check your application logs/config files")
                print("   3. Use the API key generation endpoint")
        else:
            print("❌ No active API keys found")
        
        return
    
    print(f"📊 Found {len(api_keys)} API keys with usage:")
    print()
    
    for i, key in enumerate(api_keys, 1):
        last_used = key['last_used_at'].strftime("%Y-%m-%d %H:%M") if key['last_used_at'] else "Never"
        
        print(f"{i}. {key['name']}")
        print(f"   Company: {key['company_name']} ({key['company_slug']})")
        print(f"   Environment: {key['environment'].upper()}")
        print(f"   Prefix: {key['key_prefix']}")
        print(f"   Request Count: {key['request_count']}")
        print(f"   Last Used: {last_used}")
        print(f"   Created: {key['created_at'].strftime('%Y-%m-%d %H:%M')}")
        print()
    
    # Show the most used API key details
    most_used = api_keys[0]
    print("🏆 MOST ACTIVE API KEY:")
    print("-" * 30)
    print(f"Name: {most_used['name']}")
    print(f"Company: {most_used['company_name']}")
    print(f"Environment: {most_used['environment'].upper()}")
    print(f"Key Prefix: {most_used['key_prefix']}")
    print(f"Total Requests: {most_used['request_count']}")
    print(f"Last Used: {most_used['last_used_at'].strftime('%Y-%m-%d %H:%M') if most_used['last_used_at'] else 'Never'}")
    print()
    
    print("🔑 HOW TO GET THE FULL API KEY:")
    print("-" * 30)
    print("1. Check your application configuration files")
    print("2. Look in environment variables")
    print("3. Check your frontend code")
    print("4. Use the API key generation endpoint to create a new one")
    print()
    print("5. Example API key format:")
    print(f"   als_{'x' * 43}  (47 characters total)")
    print()
    print("6. Test with curl:")
    print("   curl -H 'Authorization: Bearer als_xxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxx' \\")
    print("        http://localhost:8000/proxy/stats/optimized")
    
    await close_database()

if __name__ == "__main__":
    asyncio.run(main()) 
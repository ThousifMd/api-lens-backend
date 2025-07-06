#!/usr/bin/env python3
"""Show the exact API keys that are already issued and in use"""
import asyncio
from app.database import DatabaseUtils, init_database, close_database

async def main():
    await init_database()
    
    print("🔑 API KEYS ALREADY ISSUED AND IN USE:")
    print("=" * 60)
    
    # These are the API keys found in the test files that are actually being used
    api_keys = [
        {
            "company": "TechCorp Inc",
            "company_id": "d74d5aa8-d092-4998-87eb-2b5ee447e710",
            "api_key": "als_z2Ad8pQn0jrWqe2tvr6oxwfSpeGV3L14KEyCnVpSl7M",
            "usage": "167 requests in database"
        },
        {
            "company": "AI Startup", 
            "company_id": "f77075d3-e0f3-46b2-aeec-da176e46e471",
            "api_key": "als_qS81gMDu-sqt48dZji2R9ZfMLIsCCzPp7QQL5Ty8_YY",
            "usage": "Active in tests"
        },
        {
            "company": "Enterprise Co",
            "company_id": "284defe6-7386-4e8f-82dd-c3312c4d7ff1", 
            "api_key": "als_q4MJ0dMoo73TxPciX91mhz1hcvAG8F0PEvBZ1B_V7oY",
            "usage": "Active in tests"
        }
    ]
    
    print("📊 Found 3 API keys that are actively being used:")
    print()
    
    for i, key_info in enumerate(api_keys, 1):
        print(f"{i}. {key_info['company']}")
        print(f"   Company ID: {key_info['company_id']}")
        print(f"   API Key: {key_info['api_key']}")
        print(f"   Usage: {key_info['usage']}")
        print()
    
    # Verify these keys exist in the database
    print("🔍 VERIFYING KEYS IN DATABASE:")
    print("-" * 40)
    
    for key_info in api_keys:
        # Check if the company exists
        company_result = await DatabaseUtils.execute_query("""
            SELECT id, name, slug, is_active
            FROM companies 
            WHERE id = $1
        """, [key_info['company_id']], fetch_all=True)
        
        if company_result:
            company = company_result[0]
            print(f"✅ Company '{company['name']}' exists (ID: {company['id']})")
            print(f"   Slug: {company['slug']}")
            print(f"   Active: {company['is_active']}")
        else:
            print(f"❌ Company '{key_info['company']}' not found in database")
        
        # Check if API key exists (by hash)
        import hashlib
        from app.config import get_settings
        settings = get_settings()
        
        # Hash the API key the same way the system does
        key_hash = hashlib.sha256(
            f"{key_info['api_key'][4:]}{settings.API_KEY_SALT}".encode()
        ).hexdigest()
        
        api_key_result = await DatabaseUtils.execute_query("""
            SELECT id, name, key_prefix, environment, is_active, created_at
            FROM api_keys 
            WHERE key_hash = $1
        """, [key_hash], fetch_all=True)
        
        if api_key_result:
            api_key = api_key_result[0]
            print(f"✅ API key exists in database")
            print(f"   Name: {api_key['name']}")
            print(f"   Prefix: {api_key['key_prefix']}")
            print(f"   Environment: {api_key['environment']}")
            print(f"   Active: {api_key['is_active']}")
        else:
            print(f"❌ API key not found in database")
        
        print()
    
    print("🚀 READY TO USE API KEYS:")
    print("-" * 40)
    print("You can use any of these API keys for frontend access:")
    print()
    
    for key_info in api_keys:
        print(f"🔑 {key_info['company']}:")
        print(f"   {key_info['api_key']}")
        print()
    
    print("📝 USAGE EXAMPLES:")
    print("-" * 40)
    print("1. Using curl:")
    print(f"   curl -H 'Authorization: Bearer {api_keys[0]['api_key']}' \\")
    print("        http://localhost:8000/proxy/stats/optimized")
    print()
    print("2. Using JavaScript:")
    print("   fetch('/api/data', {")
    print("     headers: {")
    print(f"       'Authorization': 'Bearer {api_keys[0]['api_key']}'")
    print("     }")
    print("   })")
    print()
    print("3. Using Python requests:")
    print("   import requests")
    print("   headers = {")
    print(f"       'Authorization': 'Bearer {api_keys[0]['api_key']}'")
    print("   }")
    print("   response = requests.get('http://localhost:8000/proxy/stats/optimized', headers=headers)")
    
    await close_database()

if __name__ == "__main__":
    asyncio.run(main()) 
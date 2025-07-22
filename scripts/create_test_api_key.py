"""Create a test API key for testing Cloudflare Workers flow"""
import asyncio
import uuid
import secrets
from app.database import db_manager, DatabaseUtils
from app.utils.logger import get_logger

logger = get_logger(__name__)

async def create_test_api_key():
    """Create a test company and API key"""
    try:
        await db_manager.initialize()
        
        # 1. Create a test company
        company_id = str(uuid.uuid4())
        company_name = "Test Company for Cloudflare"
        company_slug = "test-cloudflare"
        
        logger.info(f"Creating company: {company_name}")
        
        await DatabaseUtils.execute_query("""
            INSERT INTO companies (id, name, slug, rate_limit_rps, monthly_quota)
            VALUES ($1, $2, $3, $4, $5)
            ON CONFLICT (slug) DO UPDATE SET
                name = EXCLUDED.name,
                rate_limit_rps = EXCLUDED.rate_limit_rps,
                monthly_quota = EXCLUDED.monthly_quota
            RETURNING id
        """, params=[company_id, company_name, company_slug, 1000, 100000])
        
        # Get the company ID (in case it already existed)
        existing = await DatabaseUtils.execute_query(
            "SELECT id FROM companies WHERE slug = $1",
            params=[company_slug],
            fetch_all=False
        )
        
        if existing:
            company_id = str(existing['id'])
        
        logger.info(f"✅ Company ready: {company_id}")
        
        # 2. Generate a proper API key
        # Format: als_<environment>_<random_string>
        api_key = f"als_test_{secrets.token_urlsafe(32)}"
        api_key_id = str(uuid.uuid4())
        
        # The key_hash should match what your Cloudflare Worker expects
        # If your Worker validates against the raw key, use the key as hash
        # If it uses actual hashing, you'll need to match that algorithm
        
        logger.info(f"Creating API key...")
        
        await DatabaseUtils.execute_query("""
            INSERT INTO api_keys (
                id, 
                company_id, 
                key_hash, 
                key_prefix, 
                name, 
                is_active,
                environment,
                permissions
            )
            VALUES ($1, $2, $3, $4, $5, $6, $7, $8)
            ON CONFLICT (key_hash) DO NOTHING
            RETURNING id
        """, params=[
            api_key_id,
            company_id,
            api_key,  # Using raw key as hash for testing
            api_key[:12],  # First 12 chars as prefix
            "Test API Key for Cloudflare Workers",
            True,
            "test",
            ["read", "write"]
        ])
        
        logger.info(f"✅ API Key created successfully!")
        logger.info(f"\n📋 Test Credentials:")
        logger.info(f"   Company ID: {company_id}")
        logger.info(f"   API Key: {api_key}")
        
        # 3. Verify the key works locally
        key_check = await DatabaseUtils.execute_query("""
            SELECT 
                ak.id,
                ak.name,
                ak.is_active,
                c.name as company_name,
                c.rate_limit_rps,
                c.monthly_quota
            FROM api_keys ak
            JOIN companies c ON ak.company_id = c.id
            WHERE ak.key_hash = $1
        """, params=[api_key], fetch_all=False)
        
        if key_check:
            logger.info(f"\n✅ Key verified in database:")
            logger.info(f"   Company: {key_check['company_name']}")
            logger.info(f"   Rate Limit: {key_check['rate_limit_rps']} RPS")
            logger.info(f"   Monthly Quota: {key_check['monthly_quota']} requests")
        
        logger.info(f"\n📝 Next Steps:")
        logger.info(f"1. Add to your .env file:")
        logger.info(f"   TEST_API_KEY={api_key}")
        logger.info(f"\n2. Make sure your Cloudflare Worker accepts this key")
        logger.info(f"   - The Worker should validate against the key_hash column")
        logger.info(f"   - Or forward the key to your backend for validation")
        
        return api_key
        
    except Exception as e:
        logger.error(f"Failed to create API key: {e}")
        return None
    finally:
        await db_manager.close()

async def list_existing_keys():
    """List existing API keys you could use"""
    try:
        await db_manager.initialize()
        
        logger.info("\n📋 Existing API Keys:")
        
        keys = await DatabaseUtils.execute_query("""
            SELECT 
                ak.key_prefix,
                ak.name,
                ak.is_active,
                ak.created_at,
                c.name as company_name
            FROM api_keys ak
            JOIN companies c ON ak.company_id = c.id
            WHERE ak.is_active = true
            ORDER BY ak.created_at DESC
            LIMIT 10
        """, fetch_all=True)
        
        if keys:
            for key in keys:
                logger.info(f"\n   Prefix: {key['key_prefix']}...")
                logger.info(f"   Name: {key['name']}")
                logger.info(f"   Company: {key['company_name']}")
                logger.info(f"   Created: {key['created_at']}")
        else:
            logger.info("   No active API keys found")
            
    except Exception as e:
        logger.error(f"Failed to list keys: {e}")
    finally:
        await db_manager.close()

async def main():
    logger.info("🔑 API Key Setup for Cloudflare Workers Testing")
    logger.info("=" * 60)
    
    # List existing keys
    await list_existing_keys()
    
    # Create new key
    logger.info("\n🆕 Creating new test API key...")
    api_key = await create_test_api_key()
    
    if api_key:
        logger.info(f"\n✅ Success! Your test API key is:")
        logger.info(f"   {api_key}")
        logger.info(f"\n📝 Add this to your .env file:")
        logger.info(f"   TEST_API_KEY={api_key}")

if __name__ == "__main__":
    asyncio.run(main())
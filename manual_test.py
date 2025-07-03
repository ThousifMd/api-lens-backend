"""
Manual Database Record Test
Makes actual API calls and logs records for manual verification
"""
import asyncio
import httpx
import sys
import os
from uuid import uuid4
from datetime import datetime

# Add app directory to path
sys.path.append('app')
from app.database import DatabaseUtils

async def test_and_log_requests():
    """Make API calls and log records for manual verification"""
    
    print("🔥 Manual Database Record Test")
    print("=" * 50)
    
    # Test data
    company_id = "123e4567-e89b-12d3-a456-426614174000"
    user_id = "123e4567-e89b-12d3-a456-426614174001"
    api_key = "test-manual-key"
    
    try:
        # Setup test data first
        await setup_test_data(company_id, user_id, api_key)
        
        # Test 1: Log a text generation request manually
        print("\n📝 Logging Text Generation Request...")
        text_request_id = await log_text_request(company_id, user_id)
        
        # Test 2: Log an image generation request manually  
        print("\n🎨 Logging Image Generation Request...")
        image_request_id = await log_image_request(company_id, user_id)
        
        # Show what was logged
        print("\n💾 Records Created:")
        print(f"📝 Text Request ID: {text_request_id}")
        print(f"🎨 Image Request ID: {image_request_id}")
        
        # Manual verification query
        print("\n🔍 Manual Verification Queries:")
        print("=" * 50)
        print("-- Check text generation record:")
        print(f"SELECT * FROM requests WHERE request_id = '{text_request_id}';")
        print()
        print("-- Check image generation record:")
        print(f"SELECT * FROM requests WHERE request_id = '{image_request_id}';")
        print()
        print("-- Check all recent requests:")
        print(f"SELECT request_id, vendor_id, model_id, input_tokens, output_tokens, image_count, total_cost, timestamp_utc FROM requests WHERE company_id = '{company_id}' ORDER BY timestamp_utc DESC LIMIT 5;")
        
        return True
        
    except Exception as e:
        print(f"❌ Test failed: {e}")
        return False

async def setup_test_data(company_id: str, user_id: str, api_key: str):
    """Setup test company and API key"""
    try:
        # Create test company
        company_query = """
        INSERT INTO companies (id, name, slug, contact_email, is_active)
        VALUES ($1, $2, $3, $4, $5)
        ON CONFLICT (id) DO UPDATE SET is_active = EXCLUDED.is_active
        """
        await DatabaseUtils.execute_query(company_query, [
            company_id, "Manual Test Company", "manual-test", "manual@test.com", True
        ])
        
        # Create test client user
        client_user_query = """
        INSERT INTO client_users (id, company_id, client_user_id, display_name, metadata, is_active)
        VALUES ($1, $2, $3, $4, $5, $6)
        ON CONFLICT (id) DO UPDATE SET is_active = EXCLUDED.is_active
        """
        await DatabaseUtils.execute_query(client_user_query, [
            user_id, company_id, "manual-test-user", "Manual Test User", '{}', True
        ])
        
        # Create test API key
        api_key_query = """
        INSERT INTO api_keys (id, company_id, key_hash, key_prefix, name, is_active)
        VALUES ($1, $2, $3, $4, $5, $6)
        ON CONFLICT (key_hash) DO UPDATE SET is_active = EXCLUDED.is_active
        """
        await DatabaseUtils.execute_query(api_key_query, [
            str(uuid4()), company_id, api_key, "manual-", "Manual Test Key", True
        ])
        
        print("✅ Test data setup completed")
        
    except Exception as e:
        print(f"❌ Setup failed: {e}")
        raise

async def log_text_request(company_id: str, user_id: str) -> str:
    """Log a text generation request directly to database"""
    try:
        request_id = f"manual_text_{uuid4()}"
        
        # Note: Removing total_cost from INSERT since it's a generated column
        log_query = """
        INSERT INTO requests (
            id, request_id, company_id, client_user_id, vendor_id, model_id,
            method, endpoint, input_tokens, output_tokens, 
            timestamp_utc, status_code, total_latency_ms
        ) VALUES (
            $1, $2, $3, $4, 
            (SELECT id FROM vendors WHERE name = 'openai'),
            (SELECT id FROM vendor_models WHERE name = 'gpt-4o' LIMIT 1),
            $5, $6, $7, $8, $9, $10, $11
        ) RETURNING request_id
        """
        
        result = await DatabaseUtils.execute_query(
            log_query,
            [
                uuid4(), request_id, company_id, user_id,
                "POST", "/v1/openai/chat/completions",
                50, 150, datetime.utcnow(), 200, 1200
            ],
            fetch_all=False
        )
        
        print(f"   ✅ Text request logged: {result['request_id']}")
        return result['request_id']
        
    except Exception as e:
        print(f"   ❌ Text logging failed: {e}")
        raise

async def log_image_request(company_id: str, user_id: str) -> str:
    """Log an image generation request directly to database"""
    try:
        request_id = f"manual_image_{uuid4()}"
        
        # Note: Removing total_cost from INSERT since it's a generated column
        log_query = """
        INSERT INTO requests (
            id, request_id, company_id, client_user_id, vendor_id, model_id,
            method, endpoint, prompt, image_count, image_urls, image_dimensions,
            timestamp_utc, status_code, total_latency_ms
        ) VALUES (
            $1, $2, $3, $4, 
            (SELECT id FROM vendors WHERE name = 'openai'),
            (SELECT id FROM vendor_models WHERE name = 'dall-e-3' LIMIT 1),
            $5, $6, $7, $8, $9, $10, $11, $12, $13
        ) RETURNING request_id
        """
        
        mock_image_urls = ["https://example.com/generated_image_1.png"]
        
        result = await DatabaseUtils.execute_query(
            log_query,
            [
                uuid4(), request_id, company_id, user_id,
                "POST", "/v1/openai/images/generations",
                "A robot coding in a futuristic office", 1, mock_image_urls, "1024x1024",
                datetime.utcnow(), 200, 3500
            ],
            fetch_all=False
        )
        
        print(f"   ✅ Image request logged: {result['request_id']}")
        return result['request_id']
        
    except Exception as e:
        print(f"   ❌ Image logging failed: {e}")
        raise

if __name__ == "__main__":
    asyncio.run(test_and_log_requests())
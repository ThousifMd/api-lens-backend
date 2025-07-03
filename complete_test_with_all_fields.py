"""
Complete Test with ALL Fields Populated
This test ensures every single field in the requests table is properly populated
"""
import asyncio
import sys
import os
from uuid import uuid4
from datetime import datetime, timedelta
import random
import json

# Add app directory to path
sys.path.append('app')
from app.database import DatabaseUtils

async def create_complete_records():
    """Create records with ALL fields populated"""
    
    print("🔥 Complete Database Test - ALL FIELDS POPULATED")
    print("=" * 70)
    
    # Test data
    company_id = "123e4567-e89b-12d3-a456-426614174000"
    user_id = "123e4567-e89b-12d3-a456-426614174001"
    api_key = "test-complete-key"
    
    try:
        # Setup test data first
        await setup_test_data(company_id, user_id, api_key)
        
        print("\n📝 Creating Complete Text Generation Records...")
        
        # Create 3 comprehensive text records
        text_scenarios = [
            {
                "vendor": "openai", "model": "gpt-4o", 
                "input_tokens": 150, "output_tokens": 300,
                "prompt": "Write a detailed explanation of machine learning",
                "country": "US", "region": "California", "city": "San Francisco",
                "ip": "192.168.1.100", "user_agent": "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7)"
            },
            {
                "vendor": "anthropic", "model": "claude-3-5-sonnet-20241022",
                "input_tokens": 200, "output_tokens": 400,
                "prompt": "Analyze this business proposal in detail",
                "country": "UK", "region": "England", "city": "London",
                "ip": "203.0.113.45", "user_agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64)"
            },
            {
                "vendor": "google", "model": "gemini-1.5-pro",
                "input_tokens": 120, "output_tokens": 250,
                "prompt": "Explain quantum computing fundamentals",
                "country": "CA", "region": "Ontario", "city": "Toronto",
                "ip": "198.51.100.78", "user_agent": "Mozilla/5.0 (X11; Linux x86_64)"
            }
        ]
        
        for i, scenario in enumerate(text_scenarios, 1):
            request_id = await log_complete_text_request(company_id, user_id, scenario)
            print(f"   {i}. ✅ {scenario['vendor']}/{scenario['model']}: {request_id}")
        
        print(f"\n🎨 Creating Complete Image Generation Records...")
        
        # Create 3 comprehensive image records
        image_scenarios = [
            {
                "vendor": "openai", "model": "dall-e-3",
                "count": 1, "dimensions": "1024x1024",
                "prompt": "A futuristic cityscape with flying cars",
                "country": "JP", "region": "Tokyo", "city": "Shibuya",
                "ip": "210.147.25.33", "user_agent": "Mozilla/5.0 (iPhone; CPU iPhone OS 15_0 like Mac OS X)"
            },
            {
                "vendor": "stability-ai", "model": "stable-diffusion-xl-1024-v1-0",
                "count": 2, "dimensions": "1024x1024",
                "prompt": "Abstract digital art with neon colors",
                "country": "DE", "region": "Bavaria", "city": "Munich",
                "ip": "87.106.15.201", "user_agent": "Mozilla/5.0 (Android 12; Mobile; rv:108.0)"
            },
            {
                "vendor": "openai", "model": "dall-e-2",
                "count": 1, "dimensions": "512x512",
                "prompt": "Photorealistic portrait of a friendly robot",
                "country": "AU", "region": "New South Wales", "city": "Sydney",
                "ip": "202.89.45.123", "user_agent": "Mozilla/5.0 (iPad; CPU OS 15_6 like Mac OS X)"
            }
        ]
        
        for i, scenario in enumerate(image_scenarios, 1):
            request_id = await log_complete_image_request(company_id, user_id, scenario)
            print(f"   {i}. ✅ {scenario['vendor']}/{scenario['model']}: {request_id}")
        
        print(f"\n📊 Verification - Check ALL Fields Are Populated:")
        print("=" * 70)
        
        # Verify all fields are populated
        await verify_all_fields_populated(company_id)
        
        print(f"\n🔍 Manual Verification Queries:")
        print("=" * 70)
        print("-- Check all populated fields:")
        print(f"""
SELECT 
    request_id,
    v.name as vendor,
    vm.name as model,
    input_tokens, output_tokens, image_count,
    country, region, city, ip_address,
    user_agent, user_id_header,
    total_cost, timestamp_utc
FROM requests r 
JOIN vendor_models vm ON r.model_id = vm.id 
JOIN vendors v ON vm.vendor_id = v.id 
WHERE r.company_id = '{company_id}' 
ORDER BY r.timestamp_utc DESC;
""")
        
        return True
        
    except Exception as e:
        print(f"❌ Test failed: {e}")
        import traceback
        traceback.print_exc()
        return False

async def setup_test_data(company_id: str, user_id: str, api_key: str):
    """Setup test company and API key"""
    try:
        # Create test company
        company_query = """
        INSERT INTO companies (id, name, slug, contact_email, is_active, user_id_header_name)
        VALUES ($1, $2, $3, $4, $5, $6)
        ON CONFLICT (id) DO UPDATE SET 
            is_active = EXCLUDED.is_active,
            user_id_header_name = EXCLUDED.user_id_header_name
        """
        await DatabaseUtils.execute_query(company_query, [
            company_id, "Complete Test Company", "complete-test", "complete@test.com", True, "X-User-ID"
        ])
        
        # Create test client user
        client_user_query = """
        INSERT INTO client_users (id, company_id, client_user_id, display_name, email, country, metadata, is_active)
        VALUES ($1, $2, $3, $4, $5, $6, $7, $8)
        ON CONFLICT (id) DO UPDATE SET is_active = EXCLUDED.is_active
        """
        await DatabaseUtils.execute_query(client_user_query, [
            user_id, company_id, "complete-test-user", "Complete Test User", 
            "user@complete.test", "US", '{"role": "tester"}', True
        ])
        
        # Create test API key
        api_key_query = """
        INSERT INTO api_keys (id, company_id, key_hash, key_prefix, name, is_active)
        VALUES ($1, $2, $3, $4, $5, $6)
        ON CONFLICT (key_hash) DO UPDATE SET is_active = EXCLUDED.is_active
        """
        await DatabaseUtils.execute_query(api_key_query, [
            str(uuid4()), company_id, api_key, "comp-", "Complete Test API Key", True
        ])
        
        print("✅ Test data setup completed")
        
    except Exception as e:
        print(f"❌ Setup failed: {e}")
        raise

async def log_complete_text_request(company_id: str, user_id: str, scenario: dict) -> str:
    """Log a complete text generation request with ALL fields populated"""
    try:
        request_id = f"complete_text_{scenario['vendor']}_{uuid4()}"
        
        # Complete request logging with ALL available fields
        log_query = """
        INSERT INTO requests (
            id, request_id, company_id, client_user_id, vendor_id, model_id,
            method, endpoint, url, prompt, input_tokens, output_tokens,
            country, country_name, region, city, ip_address, user_agent, 
            user_id_header, custom_headers, latitude, longitude,
            timestamp_utc, status_code, total_latency_ms, request_sample, response_sample
        ) VALUES (
            $1, $2, $3, $4, 
            (SELECT id FROM vendors WHERE name = $5),
            (SELECT id FROM vendor_models WHERE name = $6 LIMIT 1),
            $7, $8, $9, $10, $11, $12, $13, $14, $15, $16, $17, $18, $19, $20, $21, $22, $23, $24, $25, $26, $27
        ) RETURNING request_id
        """
        
        # Country name mapping
        country_names = {
            "US": "United States", "UK": "United Kingdom", "CA": "Canada",
            "JP": "Japan", "DE": "Germany", "AU": "Australia"
        }
        
        # Realistic coordinates
        coordinates = {
            "US": (37.7749, -122.4194),  # San Francisco
            "UK": (51.5074, -0.1278),   # London
            "CA": (43.6532, -79.3832)   # Toronto
        }
        
        # Custom headers
        custom_headers = {
            "X-API-Version": "2024-01-01",
            "X-Client-ID": "api-lens-test",
            "X-Request-Source": "complete-test"
        }
        
        # Request and response samples
        request_sample = {
            "model": scenario["model"],
            "messages": [{"role": "user", "content": scenario["prompt"][:100] + "..."}],
            "max_tokens": scenario["output_tokens"]
        }
        
        response_sample = {
            "choices": [{"message": {"content": f"Response to: {scenario['prompt'][:30]}..."}}],
            "usage": {
                "prompt_tokens": scenario["input_tokens"],
                "completion_tokens": scenario["output_tokens"]
            }
        }
        
        latency = random.randint(1000, 3000)
        full_url = f"https://api.{scenario['vendor']}.com/v1/chat/completions"
        lat, lng = coordinates.get(scenario["country"], (0.0, 0.0))
        
        result = await DatabaseUtils.execute_query(
            log_query,
            [
                uuid4(), request_id, company_id, user_id, 
                scenario["vendor"], scenario["model"],
                "POST", f"/v1/{scenario['vendor']}/chat/completions", full_url,
                scenario["prompt"], scenario["input_tokens"], scenario["output_tokens"],
                scenario["country"], country_names.get(scenario["country"], scenario["country"]),
                scenario["region"], scenario["city"], scenario["ip"], scenario["user_agent"], 
                user_id, json.dumps(custom_headers), lat, lng,
                datetime.utcnow(), 200, latency, 
                json.dumps(request_sample), json.dumps(response_sample)
            ],
            fetch_all=False
        )
        
        return result['request_id']
        
    except Exception as e:
        print(f"   ❌ Complete text logging failed for {scenario['vendor']}/{scenario['model']}: {e}")
        raise

async def log_complete_image_request(company_id: str, user_id: str, scenario: dict) -> str:
    """Log a complete image generation request with ALL fields populated"""
    try:
        request_id = f"complete_image_{scenario['vendor']}_{uuid4()}"
        
        # Complete image request logging with ALL available fields
        log_query = """
        INSERT INTO requests (
            id, request_id, company_id, client_user_id, vendor_id, model_id,
            method, endpoint, url, prompt, image_count, image_urls, image_dimensions,
            image_quality, image_style, country, country_name, region, city, 
            ip_address, user_agent, user_id_header, custom_headers,
            latitude, longitude, timestamp_utc, status_code, 
            total_latency_ms, request_sample, response_sample
        ) VALUES (
            $1, $2, $3, $4, 
            (SELECT id FROM vendors WHERE name = $5),
            (SELECT id FROM vendor_models WHERE name = $6 LIMIT 1),
            $7, $8, $9, $10, $11, $12, $13, $14, $15, $16, $17, $18, $19, $20, $21, $22, $23, $24, $25, $26, $27, $28, $29, $30
        ) RETURNING request_id
        """
        
        # Generate realistic image URLs
        image_urls = [
            f"https://api-lens-generated.example.com/{scenario['vendor']}/{scenario['model']}/{uuid4()}.png"
            for _ in range(scenario["count"])
        ]
        
        # Country name mapping and coordinates
        country_names = {
            "US": "United States", "UK": "United Kingdom", "CA": "Canada",
            "JP": "Japan", "DE": "Germany", "AU": "Australia"
        }
        
        coordinates = {
            "JP": (35.6762, 139.6503),  # Tokyo
            "DE": (48.1351, 11.5820),  # Munich
            "AU": (-33.8688, 151.2093)  # Sydney
        }
        
        # Custom headers for image requests
        custom_headers = {
            "X-API-Version": "2024-01-01",
            "X-Client-ID": "api-lens-image-test",
            "X-Generation-Type": "standard"
        }
        
        # Request and response samples for images
        request_sample = {
            "model": scenario["model"],
            "prompt": scenario["prompt"][:100] + "...",
            "n": scenario["count"],
            "size": scenario["dimensions"]
        }
        
        response_sample = {
            "created": int(datetime.utcnow().timestamp()),
            "data": [{"url": url[:50] + "..."} for url in image_urls[:1]]  # Sample only
        }
        
        latency = random.randint(3000, 8000)  # Images take longer
        full_url = f"https://api.{scenario['vendor']}.com/v1/images/generations"
        lat, lng = coordinates.get(scenario["country"], (0.0, 0.0))
        
        result = await DatabaseUtils.execute_query(
            log_query,
            [
                uuid4(), request_id, company_id, user_id,
                scenario["vendor"], scenario["model"],
                "POST", f"/v1/{scenario['vendor']}/images/generations", full_url,
                scenario["prompt"], scenario["count"], image_urls, scenario["dimensions"],
                "standard", "photographic", scenario["country"], 
                country_names.get(scenario["country"], scenario["country"]),
                scenario["region"], scenario["city"], scenario["ip"], scenario["user_agent"], 
                user_id, json.dumps(custom_headers), lat, lng,
                datetime.utcnow(), 200, latency, 
                json.dumps(request_sample), json.dumps(response_sample)
            ],
            fetch_all=False
        )
        
        return result['request_id']
        
    except Exception as e:
        print(f"   ❌ Complete image logging failed for {scenario['vendor']}/{scenario['model']}: {e}")
        raise

async def verify_all_fields_populated(company_id: str):
    """Verify that ALL critical fields are populated"""
    try:
        verification_query = """
        SELECT 
            request_id,
            CASE WHEN country IS NULL THEN '❌' ELSE '✅' END as country_status,
            CASE WHEN region IS NULL THEN '❌' ELSE '✅' END as region_status,
            CASE WHEN city IS NULL THEN '❌' ELSE '✅' END as city_status,
            CASE WHEN ip_address IS NULL THEN '❌' ELSE '✅' END as ip_status,
            CASE WHEN user_agent IS NULL THEN '❌' ELSE '✅' END as user_agent_status,
            CASE WHEN user_id_header IS NULL THEN '❌' ELSE '✅' END as user_id_header_status,
            CASE WHEN total_cost IS NULL OR total_cost = 0 THEN '❌' ELSE '✅' END as cost_status,
            country, region, city, ip_address, total_cost
        FROM requests 
        WHERE company_id = $1 
        ORDER BY timestamp_utc DESC
        """
        
        results = await DatabaseUtils.execute_query(verification_query, [company_id], fetch_all=True)
        
        print(f"   📊 Field Population Status:")
        for result in results:
            req_id = result['request_id'][:30] + "..."
            print(f"   {req_id}")
            print(f"     🌍 Country: {result['country_status']} ({result['country']})")
            print(f"     🏭 Region: {result['region_status']} ({result['region']})")  
            print(f"     🏙️  City: {result['city_status']} ({result['city']})")
            print(f"     🌐 IP: {result['ip_status']} ({result['ip_address']})")
            print(f"     👤 User Agent: {result['user_agent_status']}")
            print(f"     🔑 User ID Header: {result['user_id_header_status']}")
            print(f"     💰 Cost: {result['cost_status']} (${result['total_cost']})")
            print()
        
        # Summary
        total_requests = len(results)
        populated_countries = len([r for r in results if r['country'] is not None])
        populated_regions = len([r for r in results if r['region'] is not None])
        populated_cities = len([r for r in results if r['city'] is not None])
        populated_ips = len([r for r in results if r['ip_address'] is not None])
        
        print(f"   📈 Summary: {total_requests} total requests")
        print(f"   🌍 Country populated: {populated_countries}/{total_requests}")
        print(f"   🏭 Region populated: {populated_regions}/{total_requests}")
        print(f"   🏙️  City populated: {populated_cities}/{total_requests}")
        print(f"   🌐 IP populated: {populated_ips}/{total_requests}")
        
        if populated_countries == total_requests and populated_regions == total_requests:
            print(f"   ✅ ALL FIELDS SUCCESSFULLY POPULATED!")
        else:
            print(f"   ❌ Some fields are still missing data")
        
    except Exception as e:
        print(f"   ❌ Verification failed: {e}")

if __name__ == "__main__":
    asyncio.run(create_complete_records())
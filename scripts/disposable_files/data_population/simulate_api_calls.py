#!/usr/bin/env python3
"""
Simulate API calls with automatic API key generation
"""
import asyncio
import httpx
import json
import time
import random
import uuid
from datetime import datetime, timedelta
import hashlib
import secrets

from app.database import DatabaseUtils, init_database, close_database
from app.config import get_settings
from app.utils.logger import get_logger

logger = get_logger(__name__)
settings = get_settings()

# Configuration
API_BASE_URL = "http://localhost:8000"

# Test scenarios
SCENARIOS = [
    {
        "name": "Customer Support Chat",
        "vendor": "openai",
        "model": "gpt-3.5-turbo",
        "endpoint": "/v1/chat/completions",
        "users": ["support_agent_1", "support_agent_2", "support_agent_3"],
        "latency_range": (800, 1500),
    },
    {
        "name": "Code Generation",
        "vendor": "openai",
        "model": "gpt-4",
        "endpoint": "/v1/chat/completions",
        "users": ["dev_1", "dev_2", "dev_3", "dev_4"],
        "latency_range": (1200, 2500),
    },
    {
        "name": "Content Writing",
        "vendor": "anthropic",
        "model": "claude-3-opus-20240229",
        "endpoint": "/v1/messages",
        "users": ["writer_1", "writer_2", "editor_1"],
        "latency_range": (1500, 3000),
    },
    {
        "name": "Marketing Images",
        "vendor": "openai",
        "model": "dall-e-3",
        "endpoint": "/v1/images/generations",
        "users": ["designer_1", "marketing_1", "marketing_2"],
        "latency_range": (3000, 6000),
    },
    {
        "name": "Research Assistant",
        "vendor": "openai",
        "model": "gpt-4-turbo",
        "endpoint": "/v1/chat/completions",
        "users": ["researcher_1", "researcher_2"],
        "latency_range": (1500, 3500),
    },
]

# Different user agents
USER_AGENTS = [
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36",
    "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36",
    "Python/3.9 aiohttp/3.8.1",
]

# IP addresses from different locations
IP_ADDRESSES = [
    "8.8.8.8",         # Google DNS (US)
    "185.60.216.35",   # UK
    "103.86.96.100",   # India
    "210.140.92.181",  # Japan
    "61.28.224.67",    # Australia
]

async def create_test_api_key():
    """Create a test API key for simulation"""
    # Get first company
    company_result = await DatabaseUtils.execute_query(
        "SELECT id, name FROM companies WHERE is_active = true LIMIT 1",
        fetch_all=True
    )
    
    if not company_result:
        raise Exception("No active companies found")
    
    company_id = company_result[0]['id']
    company_name = company_result[0]['name']
    
    # Generate API key components
    key_id = str(uuid.uuid4())
    raw_key = f"sk_test_{secrets.token_urlsafe(32)}"
    api_key = f"als_{raw_key}"
    
    # Hash the key
    key_hash = hashlib.sha256(
        f"{raw_key}{settings.API_KEY_SALT}".encode()
    ).hexdigest()
    
    # Insert API key
    await DatabaseUtils.execute_query("""
        INSERT INTO api_keys (
            id, company_id, key_hash, key_prefix, name, 
            environment, is_active, created_at
        ) VALUES (
            $1, $2, $3, $4, $5, $6, $7, NOW()
        )
    """, [
        key_id, company_id, key_hash, api_key[:15],
        "Test Simulation Key", "development", True
    ], fetch_all=False)
    
    print(f"✅ Created API key for company: {company_name}")
    print(f"   Key ID: {key_id}")
    print(f"   Key prefix: {api_key[:15]}...")
    
    return api_key, company_id

async def make_api_call(session: httpx.AsyncClient, api_key: str, company_id: str,
                       scenario: dict, user_id: str, hour_offset: int = 0):
    """Make a single API call"""
    
    # Generate request ID
    request_id = f"{scenario['vendor']}_{scenario['model'].split('-')[0]}_{uuid.uuid4().hex[:8]}"
    
    # Random latencies
    total_latency = random.randint(*scenario['latency_range'])
    vendor_latency = int(total_latency * random.uniform(0.7, 0.9))
    
    # Determine success (95% success rate)
    success = random.random() < 0.95
    status_code = 200 if success else random.choice([400, 429, 500, 503])
    
    # Calculate timestamp
    timestamp = int((datetime.now() - timedelta(hours=hour_offset)).timestamp() * 1000)
    
    # Build request payload
    payload = {
        "requestId": request_id,
        "companyId": company_id,
        "timestamp": timestamp,
        "method": "POST",
        "endpoint": scenario['endpoint'],
        "url": f"https://api.{scenario['vendor']}.com{scenario['endpoint']}",
        "vendor": scenario['vendor'],
        "model": scenario['model'],
        "userId": user_id,
        "userAgent": random.choice(USER_AGENTS),
        "ipAddress": random.choice(IP_ADDRESSES),
        "inputTokens": 0,  # Let the system calculate
        "outputTokens": 0,  # Let the system calculate
        "totalLatency": total_latency,
        "vendorLatency": vendor_latency,
        "statusCode": status_code,
        "success": success,
        "cost": 0  # Will be calculated
    }
    
    if not success:
        payload["errorMessage"] = random.choice([
            "Rate limit exceeded",
            "Invalid request format",
            "Model overloaded",
        ])
        payload["errorCode"] = f"ERR_{status_code}"
    
    try:
        response = await session.post(
            f"{API_BASE_URL}/proxy/logs/optimized",
            json=payload,
            headers={
                "Authorization": f"Bearer {api_key}",
                "Content-Type": "application/json",
                "X-Forwarded-For": payload["ipAddress"],
                "User-Agent": payload["userAgent"]
            }
        )
        
        if response.status_code == 200:
            result = response.json()
            return True, result
        else:
            return False, response.text
            
    except Exception as e:
        return False, str(e)

async def simulate_usage():
    """Simulate API usage with database setup"""
    print("🚀 SIMULATING API USAGE")
    print("=" * 60)
    
    # Initialize database
    await init_database()
    
    try:
        # Create test API key
        api_key, company_id = await create_test_api_key()
        
        print(f"\n📡 Making API calls...")
        print("-" * 40)
        
        async with httpx.AsyncClient(timeout=30.0) as session:
            success_count = 0
            fail_count = 0
            
            # Make 50 API calls with variety
            for i in range(50):
                # Pick random scenario and user
                scenario = random.choice(SCENARIOS)
                user_id = random.choice(scenario['users'])
                hour_offset = random.randint(0, 24)
                
                success, result = await make_api_call(
                    session, api_key, company_id,
                    scenario, user_id, hour_offset
                )
                
                if success:
                    success_count += 1
                    if (i + 1) % 10 == 0:
                        print(f"✅ {i + 1} calls completed...")
                else:
                    fail_count += 1
                
                # Small delay to avoid overwhelming
                if i % 5 == 0:
                    await asyncio.sleep(0.1)
        
        print(f"\n✅ Completed {success_count + fail_count} API calls!")
        print(f"   Successful: {success_count}")
        print(f"   Failed: {fail_count}")
        
        # Check results
        print("\n📊 CHECKING RESULTS...")
        print("-" * 40)
        
        results = await DatabaseUtils.execute_query("""
            SELECT 
                COUNT(*) as total,
                COUNT(DISTINCT client_user_id) as users,
                COUNT(DISTINCT city || ', ' || country) as locations,
                COUNT(DISTINCT vendor_id || '-' || model_id) as models,
                MIN(input_tokens) as min_input,
                MAX(input_tokens) as max_input,
                MIN(output_tokens) as min_output,
                MAX(output_tokens) as max_output,
                SUM(total_cost) as total_cost
            FROM requests
            WHERE company_id = $1
        """, [company_id], fetch_all=True)
        
        r = results[0]
        print(f"Total requests: {r['total']}")
        print(f"Unique users: {r['users']}")
        print(f"Unique locations: {r['locations']}")
        print(f"Unique models: {r['models']}")
        print(f"Token ranges: Input({r['min_input']}-{r['max_input']}), Output({r['min_output']}-{r['max_output']})")
        print(f"Total cost: ${r['total_cost']:.2f}")
        
        # Show sample records
        print("\n📋 SAMPLE RECORDS:")
        print("-" * 80)
        
        samples = await DatabaseUtils.execute_query("""
            SELECT 
                r.request_id,
                v.name || '/' || vm.name as model,
                r.input_tokens,
                r.output_tokens,
                r.city || ', ' || r.country as location,
                r.total_cost
            FROM requests r
            JOIN vendors v ON r.vendor_id = v.id
            JOIN vendor_models vm ON r.model_id = vm.id
            WHERE r.company_id = $1
            ORDER BY r.created_at DESC
            LIMIT 10
        """, [company_id], fetch_all=True)
        
        for s in samples:
            print(f"{s['request_id'][:30]:30} | {s['model'][:25]:25} | "
                  f"Tokens: {s['input_tokens']:4}/{s['output_tokens']:4} | "
                  f"{s['location']:15} | ${s['total_cost']:.4f}")
        
        # Clean up - delete the test API key
        await DatabaseUtils.execute_query(
            "DELETE FROM api_keys WHERE key_hash = $1",
            [hashlib.sha256(f"{api_key[4:]}{settings.API_KEY_SALT}".encode()).hexdigest()],
            fetch_all=False
        )
        print("\n✅ Test API key cleaned up")
        
    finally:
        await close_database()

if __name__ == "__main__":
    asyncio.run(simulate_usage())
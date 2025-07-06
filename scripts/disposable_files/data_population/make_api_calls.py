#!/usr/bin/env python3
"""
Make various API calls to populate the database with realistic data
"""
import asyncio
import httpx
import json
import time
import random
import uuid
from datetime import datetime, timedelta

# Configuration
API_BASE_URL = "http://localhost:8000"
API_KEY = "als_sk_test_12345"  # You'll need to use a valid API key

# Test scenarios
SCENARIOS = [
    # Chat completions
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
        "name": "Quick Responses",
        "vendor": "anthropic",
        "model": "claude-3-haiku-20240307",
        "endpoint": "/v1/messages",
        "users": ["api_user_1", "api_user_2"],
        "latency_range": (400, 800),
    },
    # Image generation
    {
        "name": "Marketing Images",
        "vendor": "openai",
        "model": "dall-e-3",
        "endpoint": "/v1/images/generations",
        "users": ["designer_1", "marketing_1", "marketing_2"],
        "latency_range": (3000, 6000),
    },
    {
        "name": "Product Images",
        "vendor": "openai",
        "model": "dall-e-2",
        "endpoint": "/v1/images/generations",
        "users": ["product_team_1", "product_team_2"],
        "latency_range": (2000, 4000),
    },
    # Advanced models
    {
        "name": "Research Assistant",
        "vendor": "openai",
        "model": "gpt-4-turbo",
        "endpoint": "/v1/chat/completions",
        "users": ["researcher_1", "researcher_2"],
        "latency_range": (1500, 3500),
    },
    {
        "name": "Creative Writing",
        "vendor": "anthropic",
        "model": "claude-3-5-sonnet-20241022",
        "endpoint": "/v1/messages",
        "users": ["author_1", "creative_team_1"],
        "latency_range": (1200, 2800),
    },
]

# Simulate different times of day and user patterns
def get_timestamp_for_pattern(hour_offset=0):
    """Generate timestamp for different times of day"""
    base_time = datetime.now() - timedelta(hours=hour_offset)
    return int(base_time.timestamp() * 1000)

# Different user agents
USER_AGENTS = [
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36",
    "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36",
    "Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.36",
    "Mozilla/5.0 (iPhone; CPU iPhone OS 14_7_1 like Mac OS X)",
    "Python/3.9 aiohttp/3.8.1",
    "MyApp/1.0.0 (Android 11)",
]

# IP addresses from different locations
IP_ADDRESSES = [
    "8.8.8.8",         # Google DNS (US)
    "1.1.1.1",         # Cloudflare (US)
    "208.67.222.222",  # OpenDNS (US)
    "185.60.216.35",   # UK
    "103.86.96.100",   # India
    "210.140.92.181",  # Japan
    "195.154.181.43",  # France
    "177.12.80.10",    # Brazil
    "41.203.16.101",   # South Africa
    "61.28.224.67",    # Australia
]

async def make_api_call(session: httpx.AsyncClient, scenario: dict, user_id: str, 
                       hour_offset: int = 0, call_number: int = 1):
    """Make a single API call"""
    
    # Generate request ID
    request_id = f"{scenario['vendor']}_{scenario['model'].split('-')[0]}_{uuid.uuid4().hex[:8]}"
    
    # Random latencies
    total_latency = random.randint(*scenario['latency_range'])
    vendor_latency = int(total_latency * random.uniform(0.7, 0.9))
    
    # Determine success (95% success rate)
    success = random.random() < 0.95
    status_code = 200 if success else random.choice([400, 429, 500, 503])
    
    # Build request payload
    payload = {
        "requestId": request_id,
        "companyId": "d74d5aa8-d092-4998-87eb-2b5ee447e710",  # TechCorp Inc
        "timestamp": get_timestamp_for_pattern(hour_offset),
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
            "Service temporarily unavailable"
        ])
        payload["errorCode"] = f"ERR_{status_code}"
    
    try:
        response = await session.post(
            f"{API_BASE_URL}/proxy/logs/optimized",
            json=payload,
            headers={
                "Authorization": f"Bearer {API_KEY}",
                "Content-Type": "application/json",
                "X-Forwarded-For": payload["ipAddress"],
                "User-Agent": payload["userAgent"]
            }
        )
        
        if response.status_code == 200:
            result = response.json()
            print(f"✅ Call {call_number}: {scenario['name']} - {user_id}")
            print(f"   Location: {result.get('location', 'Unknown')}")
            print(f"   Cost: ${result.get('cost', {}).get('total_cost', 0):.4f}")
        else:
            print(f"❌ Call {call_number}: Failed with status {response.status_code}")
            print(f"   Error: {response.text}")
            
    except Exception as e:
        print(f"❌ Call {call_number}: Exception: {str(e)}")

async def simulate_usage_pattern():
    """Simulate realistic usage patterns"""
    print("🚀 SIMULATING API USAGE PATTERNS")
    print("=" * 60)
    
    # Check if API is reachable
    try:
        async with httpx.AsyncClient() as client:
            health_response = await client.get(f"{API_BASE_URL}/health/")
            if health_response.status_code != 200:
                print("❌ API is not reachable. Make sure the server is running.")
                return
            print("✅ API is reachable\n")
    except Exception as e:
        print(f"❌ Cannot connect to API: {e}")
        print("Make sure the API server is running on http://localhost:8000")
        return
    
    async with httpx.AsyncClient(timeout=30.0) as session:
        call_number = 0
        
        # Simulate different time periods
        time_patterns = [
            ("Current time", 0, 10),
            ("1 hour ago", 1, 8),
            ("2 hours ago", 2, 12),
            ("3 hours ago", 3, 15),
            ("6 hours ago", 6, 20),
            ("12 hours ago", 12, 25),
            ("24 hours ago", 24, 30),
        ]
        
        for period_name, hour_offset, num_calls in time_patterns:
            print(f"\n📅 Simulating calls from {period_name}...")
            print("-" * 40)
            
            # Create tasks for concurrent calls
            tasks = []
            
            for _ in range(num_calls):
                # Pick random scenario
                scenario = random.choice(SCENARIOS)
                # Pick random user from scenario
                user_id = random.choice(scenario['users'])
                
                call_number += 1
                task = make_api_call(session, scenario, user_id, hour_offset, call_number)
                tasks.append(task)
                
                # Add small delay between calls to avoid overwhelming
                if len(tasks) >= 5:
                    await asyncio.gather(*tasks)
                    tasks = []
                    await asyncio.sleep(0.5)
            
            # Process remaining tasks
            if tasks:
                await asyncio.gather(*tasks)
    
    print(f"\n\n✅ Completed {call_number} API calls!")
    print("\n📊 CHECKING RESULTS...")
    print("-" * 40)
    
    # Check what was created
    from app.database import DatabaseUtils, init_database, close_database
    
    await init_database()
    
    # Get summary
    summary = await DatabaseUtils.execute_query("""
        SELECT 
            COUNT(*) as total_requests,
            COUNT(DISTINCT client_user_id) as unique_users,
            COUNT(DISTINCT CONCAT(vendor_id, '-', model_id)) as unique_models,
            COUNT(DISTINCT city || ', ' || country) as unique_locations,
            SUM(CASE WHEN success THEN 1 ELSE 0 END) as successful_requests,
            SUM(total_cost) as total_cost,
            MIN(timestamp_utc) as earliest_request,
            MAX(timestamp_utc) as latest_request
        FROM requests
    """, fetch_all=True)
    
    s = summary[0]
    print(f"Total requests: {s['total_requests']}")
    print(f"Unique users: {s['unique_users']}")
    print(f"Unique models: {s['unique_models']}")
    print(f"Unique locations: {s['unique_locations']}")
    print(f"Success rate: {(s['successful_requests'] / s['total_requests'] * 100):.1f}%")
    print(f"Total cost: ${s['total_cost']:.2f}")
    print(f"Time range: {s['earliest_request']} to {s['latest_request']}")
    
    # Show token variety
    print("\n📊 TOKEN VARIETY:")
    print("-" * 40)
    
    token_variety = await DatabaseUtils.execute_query("""
        SELECT 
            v.name || '/' || vm.name as model,
            MIN(r.input_tokens) as min_input,
            MAX(r.input_tokens) as max_input,
            MIN(r.output_tokens) as min_output,
            MAX(r.output_tokens) as max_output,
            COUNT(*) as count
        FROM requests r
        JOIN vendors v ON r.vendor_id = v.id
        JOIN vendor_models vm ON r.model_id = vm.id
        GROUP BY v.name, vm.name
        ORDER BY count DESC
        LIMIT 10
    """, fetch_all=True)
    
    for tv in token_variety:
        print(f"{tv['model'][:40]:40} | Input: {tv['min_input']}-{tv['max_input']} | Output: {tv['min_output']}-{tv['max_output']} | Count: {tv['count']}")
    
    await close_database()

if __name__ == "__main__":
    print("⚠️  Note: Make sure the API server is running on http://localhost:8000")
    print(f"⚠️  Note: Using API key prefix: {API_KEY[:15]}...")
    print("\nYou may need to update the API_KEY variable with a valid key.")
    print("You can get a valid key from the api_keys table.\n")
    
    response = input("Continue with the simulation? (yes/no): ")
    if response.lower() == 'yes':
        asyncio.run(simulate_usage_pattern())
    else:
        print("❌ Simulation cancelled.")
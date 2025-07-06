#!/usr/bin/env python3
"""
Directly populate the database with varied API call records
"""
import asyncio
import random
import uuid
from datetime import datetime, timedelta
from app.database import DatabaseUtils, init_database, close_database
from app.services.token_calculator import TokenCalculator
from app.services.pricing import FixedPricingService as PricingService
from app.utils.location import LocationService

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
        "name": "Quick Responses",
        "vendor": "anthropic",
        "model": "claude-3-haiku-20240307",
        "endpoint": "/v1/messages",
        "users": ["api_user_1", "api_user_2"],
        "latency_range": (400, 800),
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

# Location data
LOCATIONS = [
    {"ip": "8.8.8.8", "country": "US", "country_name": "United States", "region": "California", 
     "city": "Mountain View", "lat": 37.4056, "lon": -122.0775, "timezone": "America/Los_Angeles", "offset": -480},
    {"ip": "185.60.216.35", "country": "UK", "country_name": "United Kingdom", "region": "England", 
     "city": "London", "lat": 51.5074, "lon": -0.1278, "timezone": "Europe/London", "offset": 0},
    {"ip": "103.86.96.100", "country": "IN", "country_name": "India", "region": "Maharashtra", 
     "city": "Mumbai", "lat": 19.0760, "lon": 72.8777, "timezone": "Asia/Kolkata", "offset": 330},
    {"ip": "210.140.92.181", "country": "JP", "country_name": "Japan", "region": "Tokyo", 
     "city": "Tokyo", "lat": 35.6762, "lon": 139.6503, "timezone": "Asia/Tokyo", "offset": 540},
    {"ip": "61.28.224.67", "country": "AU", "country_name": "Australia", "region": "New South Wales", 
     "city": "Sydney", "lat": -33.8688, "lon": 151.2093, "timezone": "Australia/Sydney", "offset": 660},
]

async def get_or_create_vendor_model(vendor_name: str, model_name: str):
    """Get or create vendor and model"""
    # Get vendor
    vendor_result = await DatabaseUtils.execute_query(
        "SELECT id FROM vendors WHERE name = $1",
        [vendor_name],
        fetch_all=True
    )
    
    if not vendor_result:
        vendor_result = await DatabaseUtils.execute_query(
            "INSERT INTO vendors (name, slug) VALUES ($1, $2) RETURNING id",
            [vendor_name, vendor_name.lower()],
            fetch_all=True
        )
    
    vendor_id = vendor_result[0]['id']
    
    # Get model
    model_result = await DatabaseUtils.execute_query(
        "SELECT id FROM vendor_models WHERE vendor_id = $1 AND name = $2",
        [vendor_id, model_name],
        fetch_all=True
    )
    
    if not model_result:
        model_type = 'chat' if any(x in model_name for x in ['chat', 'claude', 'gpt', 'turbo']) else 'image'
        model_result = await DatabaseUtils.execute_query(
            """INSERT INTO vendor_models 
               (vendor_id, name, slug, model_type, input_price_per_1k, output_price_per_1k) 
               VALUES ($1, $2, $3, $4, $5, $6) RETURNING id""",
            [vendor_id, model_name, model_name.lower().replace('-', '_'), model_type, 0.001, 0.002],
            fetch_all=True
        )
    
    model_id = model_result[0]['id']
    
    # Ensure pricing exists
    pricing_result = await DatabaseUtils.execute_query(
        "SELECT id FROM vendor_pricing WHERE model_id = $1 AND is_active = true",
        [model_id],
        fetch_all=True
    )
    
    if not pricing_result:
        await DatabaseUtils.execute_query(
            "INSERT INTO vendor_pricing (vendor_id, model_id, input_cost_per_1k_tokens, output_cost_per_1k_tokens) VALUES ($1, $2, $3, $4)",
            [vendor_id, model_id, 0.001, 0.002],
            fetch_all=False
        )
    
    return vendor_id, model_id

async def populate_data():
    await init_database()
    
    print("🚀 POPULATING DATABASE WITH API CALLS")
    print("=" * 60)
    
    # Get company
    company_result = await DatabaseUtils.execute_query(
        "SELECT id, name FROM companies WHERE is_active = true LIMIT 1",
        fetch_all=True
    )
    
    if not company_result:
        print("❌ No active companies found!")
        await close_database()
        return
    
    company_id = company_result[0]['id']
    company_name = company_result[0]['name']
    
    print(f"Using company: {company_name}")
    print(f"Company ID: {company_id}\n")
    
    # Get an API key for this company
    api_key_result = await DatabaseUtils.execute_query(
        "SELECT id FROM api_keys WHERE company_id = $1 AND is_active = true LIMIT 1",
        [company_id],
        fetch_all=True
    )
    
    api_key_id = api_key_result[0]['id'] if api_key_result else None
    
    created_count = 0
    
    # Create records for different time periods
    time_periods = [
        (0, 15),   # Current time - 15 calls
        (1, 20),   # 1 hour ago - 20 calls
        (3, 25),   # 3 hours ago - 25 calls
        (6, 30),   # 6 hours ago - 30 calls
        (12, 35),  # 12 hours ago - 35 calls
        (24, 40),  # 24 hours ago - 40 calls
    ]
    
    for hours_ago, num_calls in time_periods:
        print(f"\n📅 Creating {num_calls} calls from {hours_ago} hours ago...")
        
        for i in range(num_calls):
            # Random scenario
            scenario = random.choice(SCENARIOS)
            user_id = random.choice(scenario['users'])
            location = random.choice(LOCATIONS)
            
            # Get vendor and model IDs
            vendor_id, model_id = await get_or_create_vendor_model(
                scenario['vendor'], 
                scenario['model']
            )
            
            # Calculate tokens
            input_tokens, output_tokens = TokenCalculator.calculate_tokens(
                vendor=scenario['vendor'],
                model=scenario['model'],
                endpoint=scenario['endpoint']
            )
            
            # Calculate costs
            cost_result = await PricingService.calculate_cost(
                vendor=scenario['vendor'],
                model=scenario['model'],
                input_tokens=input_tokens,
                output_tokens=output_tokens,
                company_id=company_id  # Already a UUID from database
            )
            
            # Timestamps
            timestamp_utc = datetime.now() - timedelta(hours=hours_ago, minutes=random.randint(0, 59))
            local_time, utc_offset = LocationService.calculate_local_time(timestamp_utc, location['timezone'])
            
            # Latencies
            total_latency = random.randint(*scenario['latency_range'])
            vendor_latency = int(total_latency * random.uniform(0.7, 0.9))
            
            # Success rate (95%)
            success = random.random() < 0.95
            status_code = 200 if success else random.choice([400, 429, 500, 503])
            
            # Create user if needed
            user_result = await DatabaseUtils.execute_query(
                """INSERT INTO client_users (company_id, client_user_id) 
                   VALUES ($1, $2) 
                   ON CONFLICT (company_id, client_user_id) DO UPDATE 
                   SET last_seen_at = NOW() 
                   RETURNING id""",
                [company_id, user_id],
                fetch_all=True
            )
            
            client_user_id = user_result[0]['id'] if user_result else None
            
            # Insert request
            request_id = f"{scenario['vendor']}_{scenario['model'].split('-')[0]}_{uuid.uuid4().hex[:8]}"
            
            await DatabaseUtils.execute_query(
                """INSERT INTO requests (
                    request_id, company_id, client_user_id, vendor_id, model_id, api_key_id,
                    method, endpoint, url,
                    timestamp_utc, timestamp_local, timezone_name, utc_offset,
                    response_time_ms,
                    ip_address, country, country_name, region, city, latitude, longitude,
                    user_agent, user_id_header,
                    input_tokens, output_tokens,
                    input_cost, output_cost,
                    total_latency_ms, vendor_latency_ms,
                    status_code,
                    error_message, error_code
                ) VALUES (
                    $1, $2, $3, $4, $5, $6, $7, $8, $9, $10, $11, $12, $13, $14, $15, $16,
                    $17, $18, $19, $20, $21, $22, $23, $24, $25, $26, $27, $28, $29, $30, $31, $32
                )""",
                [
                    request_id, company_id, client_user_id, vendor_id, model_id, api_key_id,
                    "POST", scenario['endpoint'], f"https://api.{scenario['vendor']}.com{scenario['endpoint']}",
                    timestamp_utc, local_time, location['timezone'], location['offset'],
                    total_latency,
                    location['ip'], location['country'], location['country_name'], 
                    location['region'], location['city'], location['lat'], location['lon'],
                    "Mozilla/5.0 Test Browser", user_id,
                    input_tokens, output_tokens,
                    cost_result.get('input_cost', 0), cost_result.get('output_cost', 0),
                    total_latency, vendor_latency,
                    status_code,
                    "Rate limit exceeded" if status_code == 429 else None,
                    f"ERR_{status_code}" if not success else None
                ],
                fetch_all=False
            )
            
            created_count += 1
            
            if created_count % 20 == 0:
                print(f"  ✅ Created {created_count} records...")
    
    print(f"\n✅ Created {created_count} total records!")
    
    # Show summary
    print("\n📊 SUMMARY:")
    print("-" * 60)
    
    summary = await DatabaseUtils.execute_query("""
        SELECT 
            COUNT(*) as total,
            COUNT(DISTINCT client_user_id) as users,
            COUNT(DISTINCT CONCAT(vendor_id, '-', model_id)) as models,
            COUNT(DISTINCT CONCAT(city, ', ', country)) as locations,
            SUM(CASE WHEN success THEN 1 ELSE 0 END) as successful,
            MIN(input_tokens) as min_input,
            MAX(input_tokens) as max_input,
            MIN(output_tokens) as min_output,
            MAX(output_tokens) as max_output,
            SUM(total_cost) as total_cost
        FROM requests
        WHERE company_id = $1
    """, [company_id], fetch_all=True)
    
    s = summary[0]
    print(f"Total requests: {s['total']}")
    print(f"Unique users: {s['users']}")
    print(f"Unique models: {s['models']}")
    print(f"Unique locations: {s['locations']}")
    print(f"Success rate: {(s['successful'] / s['total'] * 100):.1f}%")
    print(f"Token ranges: Input({s['min_input']}-{s['max_input']}), Output({s['min_output']}-{s['max_output']})")
    print(f"Total cost: ${s['total_cost']:.2f}")
    
    await close_database()

if __name__ == "__main__":
    asyncio.run(populate_data())
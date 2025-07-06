#!/usr/bin/env python3
"""Simplified populate requests script that works with current schema"""
import asyncio
import random
import uuid
from datetime import datetime, timedelta, timezone
from app.database import DatabaseUtils, init_database, close_database
import pytz

# Realistic location data
LOCATIONS = [
    {"city": "New York", "region": "New York", "country": "US", "ip": "72.229.28.185", "timezone": "America/New_York"},
    {"city": "Los Angeles", "region": "California", "country": "US", "ip": "173.252.74.22", "timezone": "America/Los_Angeles"},
    {"city": "Chicago", "region": "Illinois", "country": "US", "ip": "23.25.118.54", "timezone": "America/Chicago"},
    {"city": "Dallas", "region": "Texas", "country": "US", "ip": "162.215.248.119", "timezone": "America/Chicago"},
    {"city": "Miami", "region": "Florida", "country": "US", "ip": "66.102.8.105", "timezone": "America/New_York"},
    {"city": "London", "region": "England", "country": "GB", "ip": "81.2.69.142", "timezone": "Europe/London"},
    {"city": "Paris", "region": "Île-de-France", "country": "FR", "ip": "92.184.102.144", "timezone": "Europe/Paris"},
    {"city": "Berlin", "region": "Berlin", "country": "DE", "ip": "85.214.132.117", "timezone": "Europe/Berlin"},
    {"city": "Tokyo", "region": "Tokyo", "country": "JP", "ip": "210.188.201.44", "timezone": "Asia/Tokyo"},
    {"city": "Singapore", "region": "Singapore", "country": "SG", "ip": "103.253.147.9", "timezone": "Asia/Singapore"},
    {"city": "Sydney", "region": "New South Wales", "country": "AU", "ip": "103.43.6.66", "timezone": "Australia/Sydney"},
    {"city": "Mumbai", "region": "Maharashtra", "country": "IN", "ip": "103.21.124.77", "timezone": "Asia/Kolkata"},
    {"city": "Toronto", "region": "Ontario", "country": "CA", "ip": "70.52.4.111", "timezone": "America/Toronto"},
]

# Vendor/model combinations
VENDOR_MODELS = [
    ("openai", "gpt-4", 0.03, 0.06),
    ("openai", "gpt-3.5-turbo", 0.0005, 0.0015),
    ("anthropic", "claude-3-opus", 0.015, 0.075),
    ("anthropic", "claude-3-sonnet", 0.003, 0.015),
    ("google", "gemini-pro", 0.00025, 0.0005),
    ("cohere", "command", 0.0015, 0.002),
    ("openai", "dall-e-3", 0.04, 0),
    ("stability-ai", "stable-diffusion-xl", 0.02, 0)
]

USER_AGENTS = [
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36",
    "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36",
    "APIClient/2.0 (Enterprise)",
    "PythonRequests/2.28.0"
]

async def get_random_company_and_user():
    """Get a random existing company and create/get a user"""
    # Get random company
    companies = await DatabaseUtils.execute_query(
        "SELECT id, name FROM companies WHERE is_active = true",
        fetch_all=True
    )
    
    if not companies:
        # Create a test company
        company = await DatabaseUtils.execute_query(
            "INSERT INTO companies (name, slug) VALUES ($1, $2) RETURNING id, name",
            ["Test Company", "test-company"], fetch_all=True
        )
        company_id = company[0]['id']
        company_name = company[0]['name']
    else:
        company = random.choice(companies)
        company_id = company['id']
        company_name = company['name']
    
    # Create or get a user
    user_id_str = f"user_{random.randint(1, 10)}"
    user_result = await DatabaseUtils.execute_query(
        """INSERT INTO client_users (company_id, client_user_id)
           VALUES ($1, $2)
           ON CONFLICT (company_id, client_user_id) DO UPDATE SET last_seen_at = NOW()
           RETURNING id""",
        [company_id, user_id_str], fetch_all=True
    )
    
    return company_id, user_result[0]['id'] if user_result else None, user_id_str

async def get_vendor_model_ids(vendor_name, model_name):
    """Get vendor and model IDs"""
    result = await DatabaseUtils.execute_query(
        """SELECT v.id as vendor_id, vm.id as model_id
           FROM vendors v
           JOIN vendor_models vm ON v.id = vm.vendor_id
           WHERE v.name = $1 AND vm.name = $2""",
        [vendor_name, model_name], fetch_all=True
    )
    
    if result:
        return result[0]['vendor_id'], result[0]['model_id']
    
    # Create vendor and model if not exists
    vendor_result = await DatabaseUtils.execute_query(
        """INSERT INTO vendors (name, slug, is_active, is_supported)
           VALUES ($1, $2, true, true)
           ON CONFLICT (name) DO UPDATE SET is_active = true
           RETURNING id""",
        [vendor_name, vendor_name], fetch_all=True
    )
    vendor_id = vendor_result[0]['id']
    
    model_type = "image" if any(img in model_name for img in ["dall-e", "stable-diffusion"]) else "chat"
    model_result = await DatabaseUtils.execute_query(
        """INSERT INTO vendor_models (vendor_id, name, slug, model_type)
           VALUES ($1, $2, $3, $4)
           ON CONFLICT (vendor_id, name) DO NOTHING
           RETURNING id""",
        [vendor_id, model_name, model_name.lower().replace('.', '-'), model_type], fetch_all=True
    )
    
    if model_result:
        return vendor_id, model_result[0]['id']
    else:
        # Get existing model
        existing = await DatabaseUtils.execute_query(
            "SELECT id FROM vendor_models WHERE vendor_id = $1 AND name = $2",
            [vendor_id, model_name], fetch_all=True
        )
        return vendor_id, existing[0]['id'] if existing else None

async def populate_requests(num_requests=1000):
    """Populate requests with realistic data"""
    await init_database()
    
    print(f"📊 Generating {num_requests} requests with diverse locations...")
    
    # Ensure monthly partitions exist
    for i in range(3):
        date = datetime.now() - timedelta(days=30 * i)
        partition_name = f"requests_{date.year}_{date.month:02d}"
        try:
            await DatabaseUtils.execute_query(f"""
                CREATE TABLE IF NOT EXISTS {partition_name} PARTITION OF requests
                FOR VALUES FROM ('{date.year}-{date.month:02d}-01') 
                TO ('{date.year}-{(date.month % 12) + 1:02d}-01')
            """, fetch_all=False)
        except:
            pass
    
    success_count = 0
    error_count = 0
    
    for i in range(num_requests):
        try:
            # Random selections
            location = random.choice(LOCATIONS)
            vendor_name, model_name, input_price, output_price = random.choice(VENDOR_MODELS)
            company_id, client_user_id, user_id_str = await get_random_company_and_user()
            vendor_id, model_id = await get_vendor_model_ids(vendor_name, model_name)
            
            if not model_id:
                continue
            
            # Random timestamp in last 30 days
            days_ago = random.randint(0, 30)
            hours_ago = random.randint(0, 23)
            minutes_ago = random.randint(0, 59)
            timestamp = datetime.now(timezone.utc) - timedelta(days=days_ago, hours=hours_ago, minutes=minutes_ago)
            
            # Calculate local time
            tz = pytz.timezone(location["timezone"])
            local_time = timestamp.astimezone(tz)
            utc_offset = int(local_time.utcoffset().total_seconds() / 60)
            
            # Status (90% success rate)
            status_code = 200 if random.random() < 0.9 else random.choice([400, 429, 500])
            success = status_code == 200
            error_msg = None if success else "Simulated error"
            
            # Tokens (0 for image models)
            is_image = any(img in model_name for img in ["dall-e", "stable-diffusion"])
            input_tokens = 0 if is_image else random.randint(50, 2000)
            output_tokens = 0 if is_image else random.randint(100, 4000)
            
            # Costs
            input_cost = (input_tokens / 1000) * input_price
            output_cost = (output_tokens / 1000) * output_price
            
            # Latencies
            vendor_latency = random.randint(200, 5000)
            total_latency = vendor_latency + random.randint(10, 200)
            
            # Insert request
            await DatabaseUtils.execute_query(
                """INSERT INTO requests (
                    request_id, company_id, client_user_id,
                    vendor_id, model_id, 
                    method, endpoint, url,
                    user_id_header, 
                    timestamp_utc, timestamp_local, timezone_name, utc_offset,
                    response_time_ms,
                    ip_address, country, country_name, region, city,
                    user_agent,
                    input_tokens, output_tokens,
                    input_cost, output_cost,
                    total_latency_ms, vendor_latency_ms,
                    status_code, success, error_message,
                    created_at
                ) VALUES ($1,$2,$3,$4,$5,$6,$7,$8,$9,$10,$11,$12,$13,$14,$15,$16,$17,$18,$19,$20,$21,$22,$23,$24,$25,$26,$27,$28,$29,$30)""",
                [
                    str(uuid.uuid4()),  # request_id
                    company_id,
                    client_user_id,  # client_user_id
                    vendor_id,
                    model_id,
                    "POST",
                    f"/v1/{'images/generations' if is_image else 'chat/completions'}",
                    f"https://api.{vendor_name}.com",
                    user_id_str,  # user_id_header
                    timestamp,  # timestamp_utc
                    local_time,  # timestamp_local
                    location["timezone"],  # timezone_name
                    utc_offset,  # utc_offset
                    total_latency,  # response_time_ms
                    location["ip"],  # ip_address
                    location["country"],  # country
                    location["country"],  # country_name
                    location["region"],  # region
                    location["city"],  # city
                    random.choice(USER_AGENTS),  # user_agent
                    input_tokens,
                    output_tokens,
                    input_cost,
                    output_cost,
                    total_latency,  # total_latency_ms
                    vendor_latency,  # vendor_latency_ms
                    status_code,
                    success,
                    error_msg,  # error_message
                    timestamp  # created_at
                ], fetch_all=False
            )
            
            success_count += 1
            
            if (i + 1) % 100 == 0:
                print(f"  ✓ Generated {i + 1} requests... ({success_count} successful, {error_count} errors)")
                
        except Exception as e:
            error_count += 1
            if error_count <= 5:  # Only print first 5 errors
                print(f"  ✗ Error on request {i + 1}: {str(e)}")
    
    # Summary
    print(f"\n✅ Population complete!")
    print(f"   Total: {num_requests} attempted")
    print(f"   Success: {success_count}")
    print(f"   Errors: {error_count}")
    
    # Show location distribution
    location_stats = await DatabaseUtils.execute_query("""
        SELECT 
            city, region, country,
            COUNT(*) as request_count
        FROM requests
        WHERE created_at > NOW() - INTERVAL '1 hour'
        GROUP BY city, region, country
        ORDER BY request_count DESC
        LIMIT 10
    """, fetch_all=True)
    
    if location_stats:
        print(f"\n📍 Location Distribution (last hour):")
        for loc in location_stats:
            print(f"   • {loc['city']}, {loc['region']}, {loc['country']}: {loc['request_count']} requests")
    
    await close_database()

if __name__ == "__main__":
    asyncio.run(populate_requests(1000))
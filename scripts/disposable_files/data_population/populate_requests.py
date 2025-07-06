#!/usr/bin/env python3
"""Populate requests table with diverse, realistic data"""
import asyncio
import random
import uuid
from datetime import datetime, timedelta, timezone
from app.database import DatabaseUtils, init_database, close_database
from app.utils.location import LocationService
import pytz

# Realistic IP addresses from different locations
LOCATION_DATA = {
    "New York": {"ip": "72.229.28.185", "country": "US", "region": "New York", "city": "New York", "timezone": "America/New_York"},
    "Los Angeles": {"ip": "173.252.74.22", "country": "US", "region": "California", "city": "Los Angeles", "timezone": "America/Los_Angeles"},
    "Chicago": {"ip": "23.25.118.54", "country": "US", "region": "Illinois", "city": "Chicago", "timezone": "America/Chicago"},
    "Dallas": {"ip": "162.215.248.119", "country": "US", "region": "Texas", "city": "Dallas", "timezone": "America/Chicago"},
    "Miami": {"ip": "66.102.8.105", "country": "US", "region": "Florida", "city": "Miami", "timezone": "America/New_York"},
    "London": {"ip": "81.2.69.142", "country": "GB", "region": "England", "city": "London", "timezone": "Europe/London"},
    "Paris": {"ip": "92.184.102.144", "country": "FR", "region": "Île-de-France", "city": "Paris", "timezone": "Europe/Paris"},
    "Berlin": {"ip": "85.214.132.117", "country": "DE", "region": "Berlin", "city": "Berlin", "timezone": "Europe/Berlin"},
    "Tokyo": {"ip": "210.188.201.44", "country": "JP", "region": "Tokyo", "city": "Tokyo", "timezone": "Asia/Tokyo"},
    "Singapore": {"ip": "103.253.147.9", "country": "SG", "region": "Singapore", "city": "Singapore", "timezone": "Asia/Singapore"},
    "Sydney": {"ip": "103.43.6.66", "country": "AU", "region": "New South Wales", "city": "Sydney", "timezone": "Australia/Sydney"},
    "Mumbai": {"ip": "103.21.124.77", "country": "IN", "region": "Maharashtra", "city": "Mumbai", "timezone": "Asia/Kolkata"},
    "Toronto": {"ip": "70.52.4.111", "country": "CA", "region": "Ontario", "city": "Toronto", "timezone": "America/Toronto"},
    "São Paulo": {"ip": "200.155.38.42", "country": "BR", "region": "São Paulo", "city": "São Paulo", "timezone": "America/Sao_Paulo"},
    "Dubai": {"ip": "94.200.103.99", "country": "AE", "region": "Dubai", "city": "Dubai", "timezone": "Asia/Dubai"}
}

# Vendors and their models with realistic pricing
VENDOR_MODELS = {
    "openai": {
        "models": ["gpt-4", "gpt-4-turbo", "gpt-3.5-turbo", "dall-e-3", "dall-e-2"],
        "pricing": {
            "gpt-4": {"input": 0.03, "output": 0.06},
            "gpt-4-turbo": {"input": 0.01, "output": 0.03},
            "gpt-3.5-turbo": {"input": 0.0005, "output": 0.0015},
            "dall-e-3": {"input": 0.04, "output": 0},
            "dall-e-2": {"input": 0.02, "output": 0}
        }
    },
    "anthropic": {
        "models": ["claude-3-opus", "claude-3-sonnet", "claude-3-haiku"],
        "pricing": {
            "claude-3-opus": {"input": 0.015, "output": 0.075},
            "claude-3-sonnet": {"input": 0.003, "output": 0.015},
            "claude-3-haiku": {"input": 0.00025, "output": 0.00125}
        }
    },
    "google": {
        "models": ["gemini-pro", "gemini-pro-vision", "palm-2"],
        "pricing": {
            "gemini-pro": {"input": 0.00025, "output": 0.0005},
            "gemini-pro-vision": {"input": 0.00025, "output": 0.0005},
            "palm-2": {"input": 0.0005, "output": 0.001}
        }
    },
    "cohere": {
        "models": ["command", "command-light"],
        "pricing": {
            "command": {"input": 0.0015, "output": 0.002},
            "command-light": {"input": 0.00015, "output": 0.0006}
        }
    },
    "stability-ai": {
        "models": ["stable-diffusion-xl", "stable-diffusion-2", "stable-diffusion-1.5"],
        "pricing": {
            "stable-diffusion-xl": {"input": 0.02, "output": 0},
            "stable-diffusion-2": {"input": 0.01, "output": 0},
            "stable-diffusion-1.5": {"input": 0.008, "output": 0}
        }
    }
}

# User agents
USER_AGENTS = [
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36",
    "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36",
    "Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.36",
    "Mozilla/5.0 (iPhone; CPU iPhone OS 15_0 like Mac OS X) AppleWebKit/605.1.15",
    "Mozilla/5.0 (Android 12; Mobile; rv:97.0) Gecko/97.0 Firefox/97.0",
    "APIClient/2.0 (Enterprise)",
    "PythonRequests/2.28.0",
    "NodeFetch/3.0"
]

# Status codes with weights
STATUS_CODES = [
    (200, 0.85),  # 85% success
    (400, 0.05),  # 5% bad request
    (401, 0.02),  # 2% unauthorized
    (429, 0.03),  # 3% rate limited
    (500, 0.03),  # 3% server error
    (503, 0.02),  # 2% service unavailable
]

# Error messages
ERROR_MESSAGES = {
    400: ["Invalid request format", "Missing required parameter", "Invalid model specified"],
    401: ["Invalid API key", "Expired API key", "Unauthorized access"],
    429: ["Rate limit exceeded", "Too many requests", "Quota exceeded"],
    500: ["Internal server error", "Model processing failed", "Unexpected error"],
    503: ["Service temporarily unavailable", "Model is loading", "Capacity exceeded"]
}

async def create_companies_and_keys():
    """Create test companies and API keys"""
    companies = []
    
    company_data = [
        {"name": "TechCorp Global", "slug": "techcorp-global"},
        {"name": "AI Innovations Inc", "slug": "ai-innovations"},
        {"name": "DataFlow Systems", "slug": "dataflow-systems"},
        {"name": "CloudFirst Ltd", "slug": "cloudfirst-ltd"},
        {"name": "SmartApps GmbH", "slug": "smartapps-gmbh"},
    ]
    
    for comp in company_data:
        # Check if company exists
        existing = await DatabaseUtils.execute_query(
            "SELECT id FROM companies WHERE slug = $1",
            [comp["slug"]], fetch_all=True
        )
        
        if existing:
            companies.append(existing[0]['id'])
        else:
            # Create company
            result = await DatabaseUtils.execute_query(
                "INSERT INTO companies (name, slug, contact_email) VALUES ($1, $2, $3) RETURNING id",
                [comp["name"], comp["slug"], f"admin@{comp['slug']}.com"], fetch_all=True
            )
            companies.append(result[0]['id'])
            
            # Create API key with proper hash
            api_key = f"als_{uuid.uuid4().hex}_32"
            key_hash = f"hashed_{api_key}"  # In production, this would be properly hashed
            await DatabaseUtils.execute_query(
                "INSERT INTO api_keys (company_id, key_hash, key_prefix, name) VALUES ($1, $2, $3, $4)",
                [result[0]['id'], key_hash, "als", f"{comp['name']} API Key"], fetch_all=False
            )
    
    return companies

async def create_vendors_and_models():
    """Create or verify vendors and models exist"""
    for vendor_name, vendor_data in VENDOR_MODELS.items():
        # Check/create vendor
        vendor_result = await DatabaseUtils.execute_query(
            """INSERT INTO vendors (id, name, slug, is_active, is_supported)
               VALUES (gen_random_uuid(), $1, $2, true, true)
               ON CONFLICT (name) DO UPDATE SET is_active = true
               RETURNING id""",
            [vendor_name, vendor_name], fetch_all=True
        )
        vendor_id = vendor_result[0]['id']
        
        # Create models
        for model_name in vendor_data["models"]:
            pricing = vendor_data["pricing"].get(model_name, {"input": 0.001, "output": 0.002})
            model_type = "image" if any(img in model_name for img in ["dall-e", "stable-diffusion"]) else "chat"
            
            await DatabaseUtils.execute_query(
                """INSERT INTO vendor_models 
                   (id, vendor_id, name, slug, model_type, input_price_per_1k, output_price_per_1k)
                   VALUES (gen_random_uuid(), $1, $2, $3, $4, $5, $6)
                   ON CONFLICT (vendor_id, name) DO UPDATE SET is_active = true""",
                [vendor_id, model_name, model_name.lower().replace('.', '-'), 
                 model_type, pricing["input"], pricing["output"]], fetch_all=False
            )

async def create_users(company_id):
    """Create users for a company"""
    users = []
    user_names = ["john.doe", "jane.smith", "mike.jones", "sarah.wilson", "alex.brown"]
    
    for name in user_names:
        user_id = f"{name}_{company_id.hex[:8]}"
        result = await DatabaseUtils.execute_query(
            """INSERT INTO client_users (company_id, client_user_id)
               VALUES ($1, $2)
               ON CONFLICT (company_id, client_user_id) DO UPDATE SET last_seen_at = NOW()
               RETURNING id""",
            [company_id, user_id], fetch_all=True
        )
        users.append((result[0]['id'], user_id))
    
    return users

async def populate_requests(num_requests=1000):
    """Populate requests with diverse data"""
    await init_database()
    
    print("🏢 Creating companies and API keys...")
    companies = await create_companies_and_keys()
    print(f"  ✓ Created/verified {len(companies)} companies")
    
    print("\n🤖 Creating vendors and models...")
    await create_vendors_and_models()
    print(f"  ✓ Created/verified {len(VENDOR_MODELS)} vendors")
    
    print(f"\n📊 Generating {num_requests} requests...")
    
    # Create monthly partitions for last 3 months
    for i in range(3):
        date = datetime.now() - timedelta(days=30 * i)
        partition_name = f"requests_{date.year}_{date.month:02d}"
        try:
            await DatabaseUtils.execute_query(f"""
                CREATE TABLE IF NOT EXISTS {partition_name} PARTITION OF requests
                FOR VALUES FROM ('{date.year}-{date.month:02d}-01') 
                TO ('{date.year}-{date.month:02d + 1 if date.month < 12 else 1:02d}-01')
            """, fetch_all=False)
        except:
            pass  # Partition might already exist
    
    # Generate requests
    for i in range(num_requests):
        # Random selections
        company_id = random.choice(companies)
        location_name = random.choice(list(LOCATION_DATA.keys()))
        location = LOCATION_DATA[location_name]
        vendor = random.choice(list(VENDOR_MODELS.keys()))
        model = random.choice(VENDOR_MODELS[vendor]["models"])
        
        # Create user if needed
        users = await create_users(company_id)
        user_id, user_id_str = random.choice(users) if random.random() > 0.2 else (None, None)
        
        # Get vendor and model IDs
        vendor_model_result = await DatabaseUtils.execute_query(
            """SELECT vm.id as model_id, v.id as vendor_id 
               FROM vendor_models vm 
               JOIN vendors v ON vm.vendor_id = v.id 
               WHERE v.name = $1 AND vm.name = $2""",
            [vendor, model], fetch_all=True
        )
        
        if not vendor_model_result:
            continue
            
        model_id = vendor_model_result[0]['model_id']
        vendor_id = vendor_model_result[0]['vendor_id']
        
        # Random timestamp in last 30 days
        days_ago = random.randint(0, 30)
        hours_ago = random.randint(0, 23)
        timestamp = datetime.now(timezone.utc) - timedelta(days=days_ago, hours=hours_ago)
        
        # Calculate local time
        tz = pytz.timezone(location["timezone"])
        local_time = timestamp.astimezone(tz)
        utc_offset = int(local_time.utcoffset().total_seconds() / 60)
        
        # Status and error
        status_code = random.choices([s[0] for s in STATUS_CODES], 
                                   weights=[s[1] for s in STATUS_CODES])[0]
        success = status_code == 200
        error_msg = None if success else random.choice(ERROR_MESSAGES[status_code])
        
        # Tokens (0 for image models)
        is_image = any(img in model for img in ["dall-e", "stable-diffusion"])
        input_tokens = 0 if is_image else random.randint(50, 2000)
        output_tokens = 0 if is_image else random.randint(100, 4000)
        
        # Calculate cost
        pricing = VENDOR_MODELS[vendor]["pricing"].get(model, {"input": 0.001, "output": 0.002})
        input_cost = (input_tokens / 1000) * pricing["input"]
        output_cost = (output_tokens / 1000) * pricing["output"]
        total_cost = input_cost + output_cost
        
        # Latencies
        vendor_latency = random.randint(200, 5000)
        total_latency = vendor_latency + random.randint(10, 200)
        
        # Create session if user exists
        session_id = None
        if user_id:
            session_result = await DatabaseUtils.execute_query(
                """INSERT INTO user_sessions (client_user_id, session_id, ip_address, country, region, city, started_at, request_count)
                   VALUES ($1, $2, $3, $4, $5, $6, $7, 1)
                   ON CONFLICT (client_user_id, session_id) DO UPDATE SET request_count = user_sessions.request_count + 1
                   RETURNING id""",
                [user_id, f"session_{user_id_str}_{timestamp.date()}", location["ip"], 
                 location["country"], location["region"], location["city"], timestamp], fetch_all=True
            )
            session_id = session_result[0]['id'] if session_result else None
        
        # Insert request
        try:
            await DatabaseUtils.execute_query(
                """INSERT INTO requests (
                    request_id, company_id, client_user_id, user_session_id,
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
                ) VALUES ($1,$2,$3,$4,$5,$6,$7,$8,$9,$10,$11,$12,$13,$14,$15,$16,$17,$18,$19,$20,$21,$22,$23,$24,$25,$26,$27,$28,$29,$30,$31)""",
                [
                    str(uuid.uuid4()),  # request_id
                    company_id,
                    user_id,  # client_user_id
                    session_id,  # user_session_id
                    vendor_id,
                    model_id,
                    "POST",
                    f"/v1/{'images/generations' if is_image else 'chat/completions'}",
                    f"https://api.{vendor}.com/v1/{'images/generations' if is_image else 'chat/completions'}",
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
            
            if (i + 1) % 100 == 0:
                print(f"  ✓ Generated {i + 1} requests...")
                
        except Exception as e:
            print(f"  ✗ Error on request {i + 1}: {str(e)}")
    
    # Show summary
    print("\n📈 Summary of generated data:")
    
    summary = await DatabaseUtils.execute_query("""
        SELECT 
            COUNT(*) as total_requests,
            COUNT(DISTINCT company_id) as companies,
            COUNT(DISTINCT vendor_id) as vendors,
            COUNT(DISTINCT model_id) as models,
            COUNT(DISTINCT client_user_id) as users,
            COUNT(DISTINCT country) as countries,
            COUNT(DISTINCT city) as cities,
            SUM(CASE WHEN success THEN 1 ELSE 0 END) as successful,
            SUM(CASE WHEN NOT success THEN 1 ELSE 0 END) as failed,
            SUM(total_cost) as total_cost,
            AVG(total_latency_ms) as avg_latency
        FROM requests
        WHERE created_at > NOW() - INTERVAL '1 hour'
    """, fetch_all=True)
    
    if summary:
        s = summary[0]
        print(f"\n  Total Requests: {s['total_requests']:,}")
        print(f"  Companies: {s['companies']}")
        print(f"  Vendors: {s['vendors']}")
        print(f"  Models: {s['models']}")
        print(f"  Users: {s['users']}")
        print(f"  Countries: {s['countries']}")
        print(f"  Cities: {s['cities']}")
        print(f"  Success Rate: {(s['successful'] / s['total_requests'] * 100):.1f}%")
        print(f"  Total Cost: ${s['total_cost']:.2f}")
        print(f"  Avg Latency: {s['avg_latency']:.0f}ms")
    
    await close_database()
    print("\n✅ Population complete!")

if __name__ == "__main__":
    asyncio.run(populate_requests(1000))
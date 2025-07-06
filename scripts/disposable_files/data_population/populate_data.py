#!/usr/bin/env python3
"""Populate database with realistic test data"""
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
]

async def main():
    await init_database()
    print("🚀 Starting data population...")
    
    # 1. Create companies
    print("\n📁 Creating companies...")
    companies = []
    company_names = ["TechCorp", "AI Solutions", "DataFlow", "CloudFirst", "SmartApps"]
    
    for name in company_names:
        slug = name.lower().replace(" ", "-")
        try:
            result = await DatabaseUtils.execute_query(
                "INSERT INTO companies (name, slug) VALUES ($1, $2) ON CONFLICT (slug) DO NOTHING RETURNING id",
                [name, slug], fetch_all=True
            )
            if result:
                companies.append(result[0]['id'])
                print(f"  ✓ Created company: {name}")
        except Exception as e:
            # Get existing company
            existing = await DatabaseUtils.execute_query(
                "SELECT id FROM companies WHERE slug = $1",
                [slug], fetch_all=True
            )
            if existing:
                companies.append(existing[0]['id'])
    
    print(f"  Total companies: {len(companies)}")
    
    # 2. Create vendors and models
    print("\n🤖 Creating vendors and models...")
    vendor_models = [
        ("openai", ["gpt-4", "gpt-3.5-turbo", "dall-e-3"]),
        ("anthropic", ["claude-3-opus", "claude-3-sonnet"]),
        ("google", ["gemini-pro"]),
        ("stability-ai", ["stable-diffusion-xl"]),
    ]
    
    vendor_model_ids = {}
    
    for vendor_name, models in vendor_models:
        # Create vendor
        vendor_result = await DatabaseUtils.execute_query(
            """INSERT INTO vendors (name, slug, is_active, is_supported)
               VALUES ($1, $2, true, true)
               ON CONFLICT (name) DO UPDATE SET is_active = true
               RETURNING id""",
            [vendor_name, vendor_name], fetch_all=True
        )
        vendor_id = vendor_result[0]['id']
        
        # Create models
        for model_name in models:
            model_type = "image" if any(img in model_name for img in ["dall-e", "stable-diffusion"]) else "chat"
            try:
                model_result = await DatabaseUtils.execute_query(
                    """INSERT INTO vendor_models (vendor_id, name, slug, model_type)
                       VALUES ($1, $2, $3, $4)
                       ON CONFLICT (vendor_id, name) DO NOTHING
                       RETURNING id""",
                    [vendor_id, model_name, model_name.lower().replace('.', '-'), model_type], 
                    fetch_all=True
                )
                if model_result:
                    vendor_model_ids[f"{vendor_name}/{model_name}"] = (vendor_id, model_result[0]['id'])
                    print(f"  ✓ Created model: {vendor_name}/{model_name}")
            except:
                # Get existing
                existing = await DatabaseUtils.execute_query(
                    "SELECT id FROM vendor_models WHERE vendor_id = $1 AND name = $2",
                    [vendor_id, model_name], fetch_all=True
                )
                if existing:
                    vendor_model_ids[f"{vendor_name}/{model_name}"] = (vendor_id, existing[0]['id'])
    
    # 3. Create users for each company
    print("\n👥 Creating users...")
    company_users = {}
    
    for company_id in companies:
        users = []
        for i in range(5):
            user_id_str = f"user_{i+1}"
            try:
                user_result = await DatabaseUtils.execute_query(
                    """INSERT INTO client_users (company_id, client_user_id)
                       VALUES ($1, $2)
                       ON CONFLICT (company_id, client_user_id) DO UPDATE SET last_seen_at = NOW()
                       RETURNING id""",
                    [company_id, user_id_str], fetch_all=True
                )
                if user_result:
                    users.append((user_result[0]['id'], user_id_str))
            except:
                pass
        company_users[company_id] = users
    
    print(f"  ✓ Created users for {len(companies)} companies")
    
    # 4. Create requests with diverse data
    print("\n📊 Creating requests...")
    
    # Ensure partitions exist
    for i in range(2):
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
    total_requests = 500
    
    for i in range(total_requests):
        try:
            # Random selections
            location = random.choice(LOCATIONS)
            company_id = random.choice(companies)
            users = company_users.get(company_id, [])
            user_id, user_id_str = random.choice(users) if users else (None, None)
            vm_key = random.choice(list(vendor_model_ids.keys()))
            vendor_id, model_id = vendor_model_ids[vm_key]
            
            # Random timestamp in last 30 days
            days_ago = random.randint(0, 30)
            timestamp = datetime.now(timezone.utc) - timedelta(
                days=days_ago, 
                hours=random.randint(0, 23),
                minutes=random.randint(0, 59)
            )
            
            # Calculate local time
            tz = pytz.timezone(location["timezone"])
            local_time = timestamp.astimezone(tz)
            utc_offset = int(local_time.utcoffset().total_seconds() / 60)
            
            # Model type
            is_image = "dall-e" in vm_key or "stable-diffusion" in vm_key
            
            # Tokens and costs
            if is_image:
                input_tokens = 0
                output_tokens = 0
                input_cost = 0.02
                output_cost = 0
            else:
                input_tokens = random.randint(50, 1500)
                output_tokens = random.randint(100, 3000)
                input_cost = (input_tokens / 1000) * 0.001
                output_cost = (output_tokens / 1000) * 0.002
            
            # Status (90% success)
            status_code = 200 if random.random() < 0.9 else random.choice([400, 429, 500])
            error_msg = None if status_code == 200 else "Simulated error"
            
            # Latencies
            vendor_latency = random.randint(200, 3000)
            total_latency = vendor_latency + random.randint(10, 100)
            
            # Insert request (without generated columns)
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
                    status_code, error_message,
                    created_at
                ) VALUES ($1,$2,$3,$4,$5,$6,$7,$8,$9,$10,$11,$12,$13,$14,$15,$16,$17,$18,$19,$20,$21,$22,$23,$24,$25,$26,$27,$28,$29)""",
                [
                    str(uuid.uuid4()),
                    company_id,
                    user_id,
                    vendor_id,
                    model_id,
                    "POST",
                    f"/v1/{'images/generations' if is_image else 'chat/completions'}",
                    f"https://api.{vm_key.split('/')[0]}.com",
                    user_id_str,
                    timestamp,
                    local_time,
                    location["timezone"],
                    utc_offset,
                    total_latency,
                    location["ip"],
                    location["country"],
                    location["country"],
                    location["region"],
                    location["city"],
                    "APIClient/2.0",
                    input_tokens,
                    output_tokens,
                    input_cost,
                    output_cost,
                    total_latency,
                    vendor_latency,
                    status_code,
                    error_msg,
                    timestamp
                ], fetch_all=False
            )
            
            success_count += 1
            
            if (i + 1) % 100 == 0:
                print(f"  ✓ Created {i + 1} requests...")
                
        except Exception as e:
            if i < 5:  # Only show first few errors
                print(f"  ✗ Error: {str(e)}")
    
    print(f"\n✅ Population complete!")
    print(f"   Requests created: {success_count}/{total_requests}")
    
    # 5. Show summary
    print("\n📈 Data Summary:")
    
    # Check requests by location
    location_stats = await DatabaseUtils.execute_query("""
        SELECT city, region, country, COUNT(*) as count
        FROM requests
        WHERE created_at > NOW() - INTERVAL '1 hour'
        GROUP BY city, region, country
        ORDER BY count DESC
        LIMIT 10
    """, fetch_all=True)
    
    if location_stats:
        print("\n  Location Distribution:")
        for loc in location_stats:
            print(f"    • {loc['city']}, {loc['region']}, {loc['country']}: {loc['count']} requests")
    
    # Check by vendor/model
    model_stats = await DatabaseUtils.execute_query("""
        SELECT v.name as vendor, vm.name as model, COUNT(*) as count
        FROM requests r
        JOIN vendors v ON r.vendor_id = v.id
        JOIN vendor_models vm ON r.model_id = vm.id
        WHERE r.created_at > NOW() - INTERVAL '1 hour'
        GROUP BY v.name, vm.name
        ORDER BY count DESC
    """, fetch_all=True)
    
    if model_stats:
        print("\n  Model Usage:")
        for m in model_stats:
            print(f"    • {m['vendor']}/{m['model']}: {m['count']} requests")
    
    await close_database()

if __name__ == "__main__":
    asyncio.run(main())
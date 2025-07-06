#!/usr/bin/env python3
"""Test varied token calculation with different model types"""
import asyncio
import uuid
import random
from datetime import datetime, timezone
from app.database import DatabaseUtils, init_database, close_database
from app.services.token_calculator import TokenCalculator

async def add_varied_test_data():
    await init_database()
    
    print("🧪 ADDING VARIED TEST DATA")
    print("=" * 60)
    
    # Get a company ID
    company_result = await DatabaseUtils.execute_query(
        "SELECT id FROM companies LIMIT 1",
        fetch_all=True
    )
    
    if not company_result:
        print("❌ No companies found. Please run the setup script first.")
        await close_database()
        return
    
    company_id = company_result[0]['id']
    
    # Test models to add
    test_models = [
        ("openai", "gpt-3.5-turbo", "/v1/chat/completions"),
        ("openai", "gpt-4", "/v1/chat/completions"),
        ("openai", "gpt-4-turbo", "/v1/chat/completions"),
        ("anthropic", "claude-3-opus-20240229", "/v1/messages"),
        ("anthropic", "claude-3-haiku-20240307", "/v1/messages"),
        ("openai", "dall-e-3", "/v1/images/generations"),
        ("google", "gemini-pro", "/v1/chat/completions"),
    ]
    
    # Locations to use
    locations = [
        ("US", "California", "San Francisco", 37.7749, -122.4194, "America/Los_Angeles", -480),
        ("UK", "England", "London", 51.5074, -0.1278, "Europe/London", 0),
        ("JP", "Tokyo", "Tokyo", 35.6762, 139.6503, "Asia/Tokyo", 540),
        ("DE", "Berlin", "Berlin", 52.5200, 13.4050, "Europe/Berlin", 60),
        ("IN", "Maharashtra", "Mumbai", 19.0760, 72.8777, "Asia/Kolkata", 330),
    ]
    
    print(f"\nAdding test data for {len(test_models)} models...")
    
    for i, (vendor, model, endpoint) in enumerate(test_models):
        # Get or create vendor and model
        vendor_result = await DatabaseUtils.execute_query(
            "SELECT id FROM vendors WHERE name = $1",
            [vendor],
            fetch_all=True
        )
        
        if not vendor_result:
            # Create vendor
            vendor_result = await DatabaseUtils.execute_query(
                "INSERT INTO vendors (name, display_name) VALUES ($1, $2) RETURNING id",
                [vendor, vendor.title()],
                fetch_all=True
            )
        
        vendor_id = vendor_result[0]['id']
        
        # Get or create model
        model_result = await DatabaseUtils.execute_query(
            "SELECT id FROM vendor_models WHERE vendor_id = $1 AND name = $2",
            [vendor_id, model],
            fetch_all=True
        )
        
        if not model_result:
            # Create model
            model_result = await DatabaseUtils.execute_query(
                """INSERT INTO vendor_models 
                   (vendor_id, name, display_name, model_type) 
                   VALUES ($1, $2, $3, $4) RETURNING id""",
                [vendor_id, model, model, 'chat' if 'chat' in endpoint else 'image'],
                fetch_all=True
            )
        
        model_id = model_result[0]['id']
        
        # Add pricing if missing
        pricing_result = await DatabaseUtils.execute_query(
            "SELECT id FROM vendor_pricing WHERE model_id = $1",
            [model_id],
            fetch_all=True
        )
        
        if not pricing_result:
            # Add default pricing
            await DatabaseUtils.execute_query(
                """INSERT INTO vendor_pricing 
                   (vendor_id, model_id, input_cost_per_1k_tokens, output_cost_per_1k_tokens)
                   VALUES ($1, $2, $3, $4)""",
                [vendor_id, model_id, 0.001, 0.002],
                fetch_all=False
            )
        
        # Create 3 requests for each model
        for j in range(3):
            # Calculate tokens (this will generate varied values)
            input_tokens, output_tokens = TokenCalculator.calculate_tokens(
                vendor=vendor,
                model=model,
                endpoint=endpoint
            )
            
            # Choose random location
            location = random.choice(locations)
            country, region, city, lat, lon, timezone_name, utc_offset = location
            
            # Create request
            request_id = f"test_{vendor}_{model.split('-')[0]}_{uuid.uuid4().hex[:8]}"
            
            await DatabaseUtils.execute_query(
                """INSERT INTO requests (
                    request_id, company_id, vendor_id, model_id,
                    method, endpoint, url,
                    timestamp_utc, timestamp_local, timezone_name, utc_offset,
                    response_time_ms,
                    ip_address, country, country_name, region, city, latitude, longitude,
                    user_agent,
                    input_tokens, output_tokens,
                    input_cost, output_cost,
                    total_latency_ms, vendor_latency_ms,
                    status_code
                ) VALUES (
                    $1, $2, $3, $4, $5, $6, $7, $8, $9, $10, $11, $12, $13, $14, $15,
                    $16, $17, $18, $19, $20, $21, $22, $23, $24, $25, $26, $27
                )""",
                [
                    request_id, company_id, vendor_id, model_id,
                    "POST", endpoint, f"https://api.{vendor}.com{endpoint}",
                    datetime.now(timezone.utc), datetime.now(timezone.utc), timezone_name, utc_offset,
                    random.randint(500, 3000),  # response_time_ms
                    f"{random.randint(1,255)}.{random.randint(1,255)}.{random.randint(1,255)}.{random.randint(1,255)}",
                    country, f"{country} Name", region, city, lat, lon,
                    "Mozilla/5.0 Test Browser",
                    input_tokens, output_tokens,
                    (input_tokens / 1000) * 0.001,  # input_cost
                    (output_tokens / 1000) * 0.002,  # output_cost
                    random.randint(800, 4000),  # total_latency_ms
                    random.randint(600, 3500),  # vendor_latency_ms
                    200  # status_code
                ],
                fetch_all=False
            )
        
        print(f"  ✅ Added 3 requests for {vendor}/{model}")
    
    print("\n📊 CHECKING VARIETY IN ALL DATA:")
    print("-" * 40)
    
    # Check token variety
    token_stats = await DatabaseUtils.execute_query("""
        SELECT 
            v.name as vendor,
            vm.name as model,
            COUNT(*) as count,
            MIN(r.input_tokens) as min_input,
            MAX(r.input_tokens) as max_input,
            AVG(r.input_tokens)::int as avg_input,
            STDDEV(r.input_tokens)::int as stddev_input,
            MIN(r.output_tokens) as min_output,
            MAX(r.output_tokens) as max_output,
            AVG(r.output_tokens)::int as avg_output,
            STDDEV(r.output_tokens)::int as stddev_output
        FROM requests r
        JOIN vendors v ON r.vendor_id = v.id
        JOIN vendor_models vm ON r.model_id = vm.id
        GROUP BY v.name, vm.name
        ORDER BY v.name, vm.name
    """, fetch_all=True)
    
    print("\nToken Statistics by Model:")
    print(f"{'Model':40} {'Count':>5} {'Input (min/avg/max/std)':>30} {'Output (min/avg/max/std)':>30}")
    print("-" * 110)
    
    for stat in token_stats:
        model_name = f"{stat['vendor']}/{stat['model']}"[:40]
        input_stats = f"{stat['min_input']}/{stat['avg_input']}/{stat['max_input']}/{stat['stddev_input'] or 0}"
        output_stats = f"{stat['min_output']}/{stat['avg_output']}/{stat['max_output']}/{stat['stddev_output'] or 0}"
        print(f"{model_name:40} {stat['count']:>5} {input_stats:>30} {output_stats:>30}")
    
    # Check location distribution
    print("\n\nLocation Distribution:")
    location_stats = await DatabaseUtils.execute_query("""
        SELECT 
            city, country,
            COUNT(*) as count
        FROM requests
        GROUP BY city, country
        ORDER BY count DESC
    """, fetch_all=True)
    
    for loc in location_stats:
        print(f"  {loc['city']:15} {loc['country']:3} - {loc['count']:3} requests")
    
    await close_database()
    print("\n✅ Test data added successfully!")

if __name__ == "__main__":
    asyncio.run(add_varied_test_data())
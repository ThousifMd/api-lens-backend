#!/usr/bin/env python3
"""
Re-fix existing records with varied, realistic token values
"""
import asyncio
import random
from app.database import DatabaseUtils, init_database, close_database
from app.services.token_calculator import TokenCalculator
from app.utils.logger import get_logger

logger = get_logger(__name__)

# Location variety for more realistic data
LOCATION_OPTIONS = [
    {
        'country': 'US',
        'country_name': 'United States',
        'region': 'California',
        'city': 'San Francisco',
        'latitude': 37.7749,
        'longitude': -122.4194,
        'timezone_name': 'America/Los_Angeles',
        'utc_offset': -480
    },
    {
        'country': 'US',
        'country_name': 'United States',
        'region': 'New York',
        'city': 'New York',
        'latitude': 40.7128,
        'longitude': -74.0060,
        'timezone_name': 'America/New_York',
        'utc_offset': -300
    },
    {
        'country': 'UK',
        'country_name': 'United Kingdom',
        'region': 'England',
        'city': 'London',
        'latitude': 51.5074,
        'longitude': -0.1278,
        'timezone_name': 'Europe/London',
        'utc_offset': 0
    },
    {
        'country': 'JP',
        'country_name': 'Japan',
        'region': 'Tokyo',
        'city': 'Tokyo',
        'latitude': 35.6762,
        'longitude': 139.6503,
        'timezone_name': 'Asia/Tokyo',
        'utc_offset': 540
    },
    {
        'country': 'AU',
        'country_name': 'Australia',
        'region': 'New South Wales',
        'city': 'Sydney',
        'latitude': -33.8688,
        'longitude': 151.2093,
        'timezone_name': 'Australia/Sydney',
        'utc_offset': 660
    }
]

async def refix_with_variety():
    await init_database()
    
    print("🔧 RE-FIXING DATA WITH VARIED TOKEN VALUES")
    print("=" * 60)
    
    # Get all records to fix
    print("\n📊 Finding all records to re-fix...")
    records_to_fix = await DatabaseUtils.execute_query("""
        SELECT 
            r.id,
            r.request_id,
            r.vendor_id,
            r.model_id,
            r.endpoint,
            v.name as vendor_name,
            vm.name as model_name
        FROM requests r
        JOIN vendors v ON r.vendor_id = v.id
        JOIN vendor_models vm ON r.model_id = vm.id
        ORDER BY r.created_at DESC
    """, fetch_all=True)
    
    print(f"Found {len(records_to_fix)} records to re-fix with variety")
    
    # Fix each record with varied values
    fixed_count = 0
    for idx, record in enumerate(records_to_fix):
        try:
            # Generate varied tokens based on model
            input_tokens, output_tokens = TokenCalculator.calculate_tokens(
                vendor=record['vendor_name'],
                model=record['model_name'],
                input_tokens=None,  # Force recalculation
                output_tokens=None,  # Force recalculation
                endpoint=record['endpoint']
            )
            
            # Choose a random location
            location = random.choice(LOCATION_OPTIONS)
            
            # Update the record with varied data
            update_query = """
                UPDATE requests
                SET 
                    input_tokens = $2,
                    output_tokens = $3,
                    country = $4,
                    country_name = $5,
                    region = $6,
                    city = $7,
                    latitude = $8,
                    longitude = $9,
                    timezone_name = $10,
                    utc_offset = $11
                WHERE id = $1
            """
            
            await DatabaseUtils.execute_query(update_query, [
                record['id'],
                input_tokens,
                output_tokens,
                location['country'],
                location['country_name'],
                location['region'],
                location['city'],
                location['latitude'],
                location['longitude'],
                location['timezone_name'],
                location['utc_offset']
            ], fetch_all=False)
            
            fixed_count += 1
            
            if fixed_count % 10 == 0:
                print(f"  Fixed {fixed_count} records...")
                
        except Exception as e:
            logger.error(f"Error fixing record {record['request_id']}: {e}")
            continue
    
    print(f"\n✅ Re-fixed {fixed_count} records with varied data")
    
    # Recalculate costs
    print("\n💰 Recalculating costs...")
    
    cost_update_query = """
        UPDATE requests r
        SET 
            input_cost = (r.input_tokens::numeric / 1000) * COALESCE(vp.input_cost_per_1k_tokens, 0.001),
            output_cost = (r.output_tokens::numeric / 1000) * COALESCE(vp.output_cost_per_1k_tokens, 0.002)
        FROM vendor_pricing vp
        WHERE 
            r.model_id = vp.model_id AND
            vp.is_active = true
    """
    
    await DatabaseUtils.execute_query(cost_update_query, fetch_all=False)
    print("✅ Costs recalculated")
    
    # Show the variety in the data
    print("\n📊 DATA VARIETY CHECK:")
    print("-" * 40)
    
    # Check token variety
    token_variety = await DatabaseUtils.execute_query("""
        SELECT 
            v.name as vendor,
            vm.name as model,
            MIN(r.input_tokens) as min_input,
            MAX(r.input_tokens) as max_input,
            AVG(r.input_tokens)::int as avg_input,
            MIN(r.output_tokens) as min_output,
            MAX(r.output_tokens) as max_output,
            AVG(r.output_tokens)::int as avg_output,
            COUNT(*) as count
        FROM requests r
        JOIN vendors v ON r.vendor_id = v.id
        JOIN vendor_models vm ON r.model_id = vm.id
        GROUP BY v.name, vm.name
        ORDER BY count DESC
    """, fetch_all=True)
    
    print("\nToken Variety by Model:")
    for tv in token_variety:
        print(f"\n{tv['vendor']}/{tv['model']} ({tv['count']} requests):")
        print(f"  Input:  {tv['min_input']:4d} - {tv['max_input']:4d} (avg: {tv['avg_input']:4d})")
        print(f"  Output: {tv['min_output']:4d} - {tv['max_output']:4d} (avg: {tv['avg_output']:4d})")
    
    # Check location variety
    location_variety = await DatabaseUtils.execute_query("""
        SELECT 
            city,
            country,
            COUNT(*) as count
        FROM requests
        GROUP BY city, country
        ORDER BY count DESC
    """, fetch_all=True)
    
    print("\n\nLocation Distribution:")
    for loc in location_variety:
        print(f"  {loc['city']:15s} {loc['country']:3s} - {loc['count']:3d} requests")
    
    # Show sample records
    print("\n\n📋 SAMPLE VARIED RECORDS:")
    print("-" * 40)
    
    samples = await DatabaseUtils.execute_query("""
        SELECT 
            r.request_id,
            v.name as vendor,
            vm.name as model,
            r.input_tokens,
            r.output_tokens,
            r.total_cost,
            r.city,
            r.country
        FROM requests r
        JOIN vendors v ON r.vendor_id = v.id
        JOIN vendor_models vm ON r.model_id = vm.id
        ORDER BY RANDOM()
        LIMIT 10
    """, fetch_all=True)
    
    for record in samples:
        print(f"\n{record['request_id']}:")
        print(f"  Model: {record['vendor']}/{record['model']}")
        print(f"  Tokens: {record['input_tokens']} in / {record['output_tokens']} out")
        print(f"  Cost: ${record['total_cost']:.6f}")
        print(f"  Location: {record['city']}, {record['country']}")
    
    await close_database()
    print("\n✅ Data variety fix complete!")

if __name__ == "__main__":
    asyncio.run(refix_with_variety())
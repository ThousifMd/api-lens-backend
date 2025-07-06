#!/usr/bin/env python3
"""
Fix null tokens and location data in existing requests
"""
import asyncio
from app.database import DatabaseUtils, init_database, close_database
from app.services.token_calculator import TokenCalculator
from app.utils.logger import get_logger

logger = get_logger(__name__)

async def fix_null_data():
    await init_database()
    
    print("🔧 FIXING NULL DATA IN REQUESTS TABLE")
    print("=" * 60)
    
    # 1. Get records with missing data
    print("\n📊 Finding records with missing data...")
    records_to_fix = await DatabaseUtils.execute_query("""
        SELECT 
            r.id,
            r.request_id,
            r.vendor_id,
            r.model_id,
            r.endpoint,
            r.input_tokens,
            r.output_tokens,
            r.latitude,
            r.longitude,
            r.country,
            r.city,
            r.timezone_name,
            v.name as vendor_name,
            vm.name as model_name
        FROM requests r
        JOIN vendors v ON r.vendor_id = v.id
        JOIN vendor_models vm ON r.model_id = vm.id
        WHERE 
            r.input_tokens = 0 OR 
            r.output_tokens = 0 OR
            r.latitude IS NULL OR
            r.country IS NULL
    """, fetch_all=True)
    
    print(f"Found {len(records_to_fix)} records to fix")
    
    # 2. Fix each record
    fixed_count = 0
    for record in records_to_fix:
        try:
            # Calculate tokens if missing
            needs_token_fix = record['input_tokens'] == 0 or record['output_tokens'] == 0
            if needs_token_fix:
                input_tokens, output_tokens = TokenCalculator.calculate_tokens(
                    vendor=record['vendor_name'],
                    model=record['model_name'],
                    input_tokens=record['input_tokens'] if record['input_tokens'] > 0 else None,
                    output_tokens=record['output_tokens'] if record['output_tokens'] > 0 else None,
                    endpoint=record['endpoint']
                )
            else:
                input_tokens = record['input_tokens']
                output_tokens = record['output_tokens']
            
            # Fix location data if missing
            needs_location_fix = (
                record['latitude'] is None or 
                record['country'] is None or
                record['city'] is None or
                record['timezone_name'] is None
            )
            
            if needs_location_fix:
                # Use default San Francisco location
                country = 'US'
                country_name = 'United States'
                region = 'California'
                city = 'San Francisco'
                latitude = 37.7749
                longitude = -122.4194
                timezone_name = 'America/Los_Angeles'
                utc_offset = -480  # -8 hours in minutes
            else:
                # Keep existing values
                country = record['country']
                city = record['city']
                latitude = record['latitude']
                longitude = record['longitude']
                timezone_name = record['timezone_name']
                country_name = 'United States'  # Default
                region = 'California'  # Default
                utc_offset = -480  # Default
            
            # Update the record (excluding generated columns)
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
                country,
                country_name,
                region,
                city,
                latitude,
                longitude,
                timezone_name,
                utc_offset
            ], fetch_all=False)
            
            fixed_count += 1
            
            if fixed_count % 100 == 0:
                print(f"  Fixed {fixed_count} records...")
                
        except Exception as e:
            logger.error(f"Error fixing record {record['request_id']}: {e}")
            continue
    
    print(f"\n✅ Fixed {fixed_count} records")
    
    # 3. Recalculate costs for fixed records
    print("\n💰 Recalculating costs for fixed records...")
    
    cost_update_query = """
        UPDATE requests r
        SET 
            input_cost = (r.input_tokens::numeric / 1000) * COALESCE(vp.input_cost_per_1k_tokens, 0.001),
            output_cost = (r.output_tokens::numeric / 1000) * COALESCE(vp.output_cost_per_1k_tokens, 0.002)
        FROM vendor_pricing vp
        WHERE 
            r.model_id = vp.model_id AND
            vp.is_active = true AND
            (r.input_cost = 0 OR r.output_cost = 0)
    """
    
    await DatabaseUtils.execute_query(cost_update_query, fetch_all=False)
    print("✅ Costs recalculated")
    
    # 4. Verify the fix
    print("\n📊 VERIFICATION:")
    print("-" * 40)
    
    # Check remaining nulls
    null_checks = [
        ('input_tokens = 0', 'Zero Input Tokens'),
        ('output_tokens = 0', 'Zero Output Tokens'),
        ('latitude IS NULL', 'NULL Latitude'),
        ('country IS NULL', 'NULL Country'),
        ('timezone_name IS NULL', 'NULL Timezone')
    ]
    
    for condition, name in null_checks:
        result = await DatabaseUtils.execute_query(
            f"SELECT COUNT(*) as count FROM requests WHERE {condition}",
            fetch_all=True
        )
        print(f"{name}: {result[0]['count']} records")
    
    # Show sample fixed records
    print("\n📋 SAMPLE FIXED RECORDS:")
    print("-" * 40)
    
    fixed_samples = await DatabaseUtils.execute_query("""
        SELECT 
            request_id,
            input_tokens,
            output_tokens,
            total_cost,
            city,
            country,
            timezone_name
        FROM requests
        ORDER BY created_at DESC
        LIMIT 5
    """, fetch_all=True)
    
    for record in fixed_samples:
        print(f"\n{record['request_id']}:")
        print(f"  Tokens: {record['input_tokens']} in / {record['output_tokens']} out")
        print(f"  Cost: ${record['total_cost']:.6f}")
        print(f"  Location: {record['city']}, {record['country']} ({record['timezone_name']})")
    
    await close_database()
    print("\n✅ Data fix complete!")

if __name__ == "__main__":
    asyncio.run(fix_null_data())
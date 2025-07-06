#!/usr/bin/env python3
"""Check for null values in requests table"""
import asyncio
from app.database import DatabaseUtils, init_database, close_database

async def main():
    await init_database()
    
    print("🔍 CHECKING FOR NULL VALUES IN REQUESTS TABLE")
    print("=" * 60)
    
    # Check total records
    total_result = await DatabaseUtils.execute_query(
        "SELECT COUNT(*) as total FROM requests",
        fetch_all=True
    )
    total = total_result[0]['total']
    print(f"\nTotal requests: {total}")
    
    # Check for null values in key fields
    null_checks = [
        ('input_tokens', 'Input Tokens'),
        ('output_tokens', 'Output Tokens'),
        ('total_tokens', 'Total Tokens'),
        ('latitude', 'Latitude'),
        ('longitude', 'Longitude'),
        ('country', 'Country'),
        ('region', 'Region'),
        ('city', 'City'),
        ('timezone_name', 'Timezone'),
        ('input_cost', 'Input Cost'),
        ('output_cost', 'Output Cost'),
        ('total_cost', 'Total Cost')
    ]
    
    print("\n📊 NULL VALUE ANALYSIS:")
    print("-" * 40)
    
    for field, name in null_checks:
        result = await DatabaseUtils.execute_query(
            f"SELECT COUNT(*) as count FROM requests WHERE {field} IS NULL",
            fetch_all=True
        )
        null_count = result[0]['count']
        percentage = (null_count / total * 100) if total > 0 else 0
        print(f"{name:20} | NULL: {null_count:6} ({percentage:5.1f}%)")
    
    # Check for zero values in token fields
    print("\n📊 ZERO VALUE ANALYSIS (for numeric fields):")
    print("-" * 40)
    
    zero_checks = [
        ('input_tokens', 'Input Tokens'),
        ('output_tokens', 'Output Tokens'),
        ('input_cost', 'Input Cost'),
        ('output_cost', 'Output Cost')
    ]
    
    for field, name in zero_checks:
        result = await DatabaseUtils.execute_query(
            f"SELECT COUNT(*) as count FROM requests WHERE {field} = 0",
            fetch_all=True
        )
        zero_count = result[0]['count']
        percentage = (zero_count / total * 100) if total > 0 else 0
        print(f"{name:20} | ZERO: {zero_count:6} ({percentage:5.1f}%)")
    
    # Sample some records with null tokens
    print("\n📋 SAMPLE RECORDS WITH NULL TOKENS:")
    print("-" * 40)
    
    sample_nulls = await DatabaseUtils.execute_query("""
        SELECT 
            request_id,
            vendor_id,
            model_id,
            input_tokens,
            output_tokens,
            total_tokens,
            latitude,
            longitude,
            country,
            city
        FROM requests
        WHERE input_tokens IS NULL OR output_tokens IS NULL OR latitude IS NULL
        LIMIT 5
    """, fetch_all=True)
    
    for idx, record in enumerate(sample_nulls, 1):
        print(f"\nRecord {idx}:")
        print(f"  Request ID: {record['request_id']}")
        print(f"  Tokens: input={record['input_tokens']}, output={record['output_tokens']}, total={record['total_tokens']}")
        print(f"  Location: {record['city']}, {record['country']} ({record['latitude']}, {record['longitude']})")
    
    await close_database()
    print("\n✅ Analysis complete!")

if __name__ == "__main__":
    asyncio.run(main())
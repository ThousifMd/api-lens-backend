#!/usr/bin/env python3
"""Check actual schema of requests table"""
import asyncio
from app.database import DatabaseUtils, init_database, close_database

async def main():
    await init_database()
    
    print("🔍 REQUESTS TABLE SCHEMA:")
    print("=" * 50)
    
    # Show what columns exist in requests table
    columns = await DatabaseUtils.execute_query("""
        SELECT column_name, data_type, is_nullable
        FROM information_schema.columns
        WHERE table_name = 'requests'
        ORDER BY ordinal_position
    """, fetch_all=True)
    
    for col in columns:
        nullable = "NULL" if col['is_nullable'] == 'YES' else "NOT NULL"
        print(f"  ✅ {col['column_name']}: {col['data_type']} {nullable}")
    
    print(f"\n📊 Total columns: {len(columns)}")
    
    # Check for any missing columns that the code expects
    expected_columns = [
        'id', 'request_id', 'company_id', 'client_user_id', 'user_session_id',
        'vendor_id', 'model_id', 'api_key_id', 'method', 'endpoint', 'url',
        'user_id_header', 'custom_headers', 'timestamp_utc', 'timestamp_local',
        'timezone_name', 'utc_offset', 'response_time_ms', 'ip_address',
        'country', 'country_name', 'region', 'city', 'latitude', 'longitude',
        'user_agent', 'referer', 'input_tokens', 'output_tokens', 'total_tokens',
        'input_cost', 'output_cost', 'total_cost', 'total_latency_ms',
        'vendor_latency_ms', 'status_code', 'success', 'error_type',
        'error_message', 'error_code', 'request_sample', 'response_sample',
        'created_at'
    ]
    
    actual_columns = [col['column_name'] for col in columns]
    
    print(f"\n🔍 SCHEMA COMPLIANCE CHECK:")
    print("=" * 50)
    
    missing_columns = [col for col in expected_columns if col not in actual_columns]
    extra_columns = [col for col in actual_columns if col not in expected_columns]
    
    if missing_columns:
        print(f"❌ MISSING COLUMNS ({len(missing_columns)}):")
        for col in missing_columns:
            print(f"  - {col}")
    else:
        print("✅ All expected columns present")
    
    if extra_columns:
        print(f"\n⚠️  EXTRA COLUMNS ({len(extra_columns)}):")
        for col in extra_columns:
            print(f"  - {col}")
    
    compliance_percentage = ((len(expected_columns) - len(missing_columns)) / len(expected_columns)) * 100
    print(f"\n📊 SCHEMA COMPLIANCE: {compliance_percentage:.1f}%")
    
    await close_database()

if __name__ == "__main__":
    asyncio.run(main()) 
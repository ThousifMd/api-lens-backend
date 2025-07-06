#!/usr/bin/env python3
"""Comprehensive schema compliance check for all major tables"""
import asyncio
from app.database import DatabaseUtils, init_database, close_database

async def main():
    await init_database()
    
    print("🔍 COMPREHENSIVE SCHEMA COMPLIANCE REPORT")
    print("=" * 60)
    
    # Define expected schemas for each table
    table_schemas = {
        'requests': {
            'expected_columns': [
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
            ],
            'critical': True
        },
        'client_users': {
            'expected_columns': [
                'id', 'company_id', 'client_user_id', 'display_name', 'email', 'avatar_url',
                'user_tier', 'signup_date', 'country', 'language', 'first_seen_at',
                'last_seen_at', 'total_requests', 'total_cost_usd', 'metadata', 'tags',
                'is_active', 'is_blocked', 'blocked_reason', 'created_at', 'updated_at'
            ],
            'critical': True
        },
        'vendor_models': {
            'expected_columns': [
                'id', 'vendor_id', 'name', 'display_name', 'description', 'model_type',
                'context_window', 'max_output_tokens', 'supports_functions', 'supports_vision',
                'is_active', 'is_deprecated', 'deprecated_at', 'sunset_at', 'replacement_model_id',
                'created_at', 'updated_at'
            ],
            'critical': True
        },
        'companies': {
            'expected_columns': [
                'id', 'name', 'slug', 'contact_email', 'billing_email', 'tier',
                'rate_limit_rps', 'monthly_quota', 'monthly_budget_usd', 'webhook_url',
                'webhook_events', 'dashboard_settings', 'require_user_id', 'user_id_header_name',
                'additional_headers', 'is_active', 'is_trial', 'trial_ends_at',
                'created_at', 'updated_at'
            ],
            'critical': True
        },
        'api_keys': {
            'expected_columns': [
                'id', 'company_id', 'key_hash', 'key_prefix', 'name', 'environment',
                'scopes', 'allowed_ips', 'is_active', 'last_used_at', 'usage_count',
                'created_at', 'updated_at', 'expires_at'
            ],
            'critical': True
        },
        'user_sessions': {
            'expected_columns': [
                'id', 'client_user_id', 'session_id', 'ip_address', 'user_agent',
                'country', 'region', 'city', 'browser', 'os', 'device_type',
                'started_at', 'ended_at', 'duration_seconds', 'request_count',
                'total_cost_usd', 'created_at'
            ],
            'critical': False
        },
        'user_analytics_hourly': {
            'expected_columns': [
                'id', 'hour_bucket_utc', 'hour_bucket_local', 'timezone_name',
                'company_id', 'client_user_id', 'vendor_id', 'model_id',
                'request_count', 'success_count', 'error_count', 'total_tokens',
                'total_cost', 'avg_latency_ms', 'p95_latency_ms', 'p99_latency_ms',
                'unique_sessions', 'unique_ips', 'location_breakdown',
                'created_at', 'updated_at'
            ],
            'critical': False
        },
        'user_analytics_daily': {
            'expected_columns': [
                'id', 'date', 'company_id', 'client_user_id', 'total_requests',
                'total_tokens', 'total_cost', 'model_usage', 'avg_latency_ms',
                'error_rate', 'active_hours', 'unique_sessions', 'countries',
                'cost_rank_in_company', 'cost_percentile', 'created_at', 'updated_at'
            ],
            'critical': False
        }
    }
    
    total_compliance = 0
    critical_compliance = 0
    critical_tables = 0
    total_tables = len(table_schemas)
    
    for table_name, schema_info in table_schemas.items():
        print(f"\n📋 {table_name.upper()} TABLE:")
        print("-" * 40)
        
        # Get actual columns
        columns = await DatabaseUtils.execute_query(f"""
            SELECT column_name, data_type, is_nullable
            FROM information_schema.columns
            WHERE table_name = '{table_name}'
            ORDER BY ordinal_position
        """, fetch_all=True)
        
        actual_columns = [col['column_name'] for col in columns]
        expected_columns = schema_info['expected_columns']
        
        # Calculate compliance
        missing_columns = [col for col in expected_columns if col not in actual_columns]
        extra_columns = [col for col in actual_columns if col not in expected_columns]
        
        compliance_percentage = ((len(expected_columns) - len(missing_columns)) / len(expected_columns)) * 100
        total_compliance += compliance_percentage
        
        if schema_info['critical']:
            critical_compliance += compliance_percentage
            critical_tables += 1
        
        print(f"  📊 Total columns: {len(columns)}")
        print(f"  📊 Expected columns: {len(expected_columns)}")
        print(f"  📊 Compliance: {compliance_percentage:.1f}%")
        
        if missing_columns:
            print(f"  ❌ Missing ({len(missing_columns)}): {', '.join(missing_columns[:5])}{'...' if len(missing_columns) > 5 else ''}")
        
        if extra_columns:
            print(f"  ⚠️  Extra ({len(extra_columns)}): {', '.join(extra_columns[:5])}{'...' if len(extra_columns) > 5 else ''}")
        
        if compliance_percentage == 100:
            print("  ✅ Perfect compliance")
        elif compliance_percentage >= 80:
            print("  🟡 Good compliance")
        elif compliance_percentage >= 60:
            print("  🟠 Moderate compliance")
        else:
            print("  🔴 Poor compliance")
    
    # Overall summary
    print(f"\n" + "=" * 60)
    print("📊 OVERALL COMPLIANCE SUMMARY")
    print("=" * 60)
    
    avg_compliance = total_compliance / total_tables
    critical_avg = critical_compliance / critical_tables if critical_tables > 0 else 0
    
    print(f"  📈 Average Compliance: {avg_compliance:.1f}%")
    print(f"  🔴 Critical Tables Compliance: {critical_avg:.1f}%")
    print(f"  📋 Total Tables Checked: {total_tables}")
    print(f"  🔴 Critical Tables: {critical_tables}")
    
    # Compliance rating
    if avg_compliance >= 90:
        rating = "🟢 EXCELLENT"
    elif avg_compliance >= 80:
        rating = "🟡 GOOD"
    elif avg_compliance >= 70:
        rating = "🟠 MODERATE"
    elif avg_compliance >= 60:
        rating = "🔴 POOR"
    else:
        rating = "🔴 CRITICAL"
    
    print(f"  🏆 Overall Rating: {rating}")
    
    # Recommendations
    print(f"\n💡 RECOMMENDATIONS:")
    print("-" * 40)
    
    if critical_avg < 80:
        print("  🔴 CRITICAL: Fix schema mismatches in critical tables immediately")
        print("  🔴 CRITICAL: Update code to match actual database schema")
    
    if avg_compliance < 90:
        print("  🟡 MEDIUM: Consider aligning code expectations with actual schema")
        print("  🟡 MEDIUM: Add missing columns or update code to use existing ones")
    
    if avg_compliance >= 90:
        print("  🟢 GOOD: Schema compliance is excellent")
        print("  🟢 GOOD: Minor optimizations possible")
    
    await close_database()

if __name__ == "__main__":
    asyncio.run(main()) 
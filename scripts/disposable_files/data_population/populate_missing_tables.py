#!/usr/bin/env python3
"""Populate the empty tables with correct schema"""
import asyncio
import random
import uuid
from datetime import datetime, timedelta, timezone
from app.database import DatabaseUtils, init_database, close_database
import json

async def populate_vendor_pricing():
    """Populate vendor pricing with correct column names"""
    print("\n💰 Populating Vendor Pricing...")
    
    models = await DatabaseUtils.execute_query(
        """SELECT vm.id, vm.name, v.id as vendor_id, v.name as vendor_name, vm.model_type
           FROM vendor_models vm
           JOIN vendors v ON vm.vendor_id = v.id""",
        fetch_all=True
    )
    
    pricing_map = {
        "gpt-4": (0.03, 0.06),
        "gpt-3.5-turbo": (0.0005, 0.0015),
        "claude-3-opus": (0.015, 0.075),
        "claude-3-sonnet": (0.003, 0.015),
        "gemini-pro": (0.00025, 0.0005),
        "dall-e": (0.04, 0),
        "stable-diffusion": (0.02, 0)
    }
    
    count = 0
    for model in models:
        # Find matching pricing
        input_price = 0.001
        output_price = 0.002
        
        for key, (inp, out) in pricing_map.items():
            if key in model['name'].lower():
                input_price = inp
                output_price = out
                break
        
        # For image models
        if model['model_type'] == 'image':
            output_price = 0
            
        await DatabaseUtils.execute_query(
            """INSERT INTO vendor_pricing 
               (vendor_id, model_id, input_cost_per_1k_tokens, output_cost_per_1k_tokens,
                pricing_tier, effective_date, is_active)
               VALUES ($1, $2, $3, $4, $5, $6, $7)""",
            [model['vendor_id'], model['id'], input_price, output_price,
             'standard', datetime.now(timezone.utc), True],
            fetch_all=False
        )
        count += 1
    
    print(f"  ✓ Created {count} pricing records")

async def populate_user_sessions():
    """Populate user sessions with correct schema"""
    print("\n👥 Populating User Sessions...")
    
    # Get unique user/location combinations from requests
    sessions_data = await DatabaseUtils.execute_query(
        """SELECT 
               client_user_id,
               DATE(created_at) as date,
               ip_address,
               country,
               region,
               city,
               user_agent,
               COUNT(*) as request_count,
               SUM(total_cost) as total_cost
           FROM requests
           WHERE client_user_id IS NOT NULL
           GROUP BY client_user_id, DATE(created_at), ip_address, 
                    country, region, city, user_agent
           LIMIT 200""",
        fetch_all=True
    )
    
    count = 0
    for session in sessions_data:
        session_id = f"session_{count}_{session['date']}"
        
        await DatabaseUtils.execute_query(
            """INSERT INTO user_sessions 
               (client_user_id, session_id, ip_address, user_agent,
                country, region, city, started_at, request_count, total_cost_usd)
               VALUES ($1, $2, $3, $4, $5, $6, $7, $8, $9, $10)""",
            [session['client_user_id'], session_id, session['ip_address'],
             session['user_agent'], session['country'], session['region'],
             session['city'], session['date'], session['request_count'],
             session['total_cost']],
            fetch_all=False
        )
        count += 1
    
    print(f"  ✓ Created {count} user sessions")

async def populate_cost_alerts():
    """Populate cost alerts"""
    print("\n🚨 Populating Cost Alerts...")
    
    companies = await DatabaseUtils.execute_query(
        "SELECT id, name FROM companies WHERE is_active = true LIMIT 10",
        fetch_all=True
    )
    
    alert_configs = [
        ("daily_budget", 100.0),
        ("monthly_budget", 3000.0),
        ("hourly_spike", 10.0),
        ("user_limit", 50.0)
    ]
    
    count = 0
    for company in companies:
        for alert_type, threshold in alert_configs:
            await DatabaseUtils.execute_query(
                """INSERT INTO cost_alerts 
                   (company_id, alert_type, threshold_usd, is_active)
                   VALUES ($1, $2, $3, $4)""",
                [company['id'], alert_type, threshold, True],
                fetch_all=False
            )
            count += 1
    
    print(f"  ✓ Created {count} cost alerts")

async def populate_hourly_analytics():
    """Populate hourly analytics"""
    print("\n📊 Populating Hourly Analytics...")
    
    # Get hourly aggregated data
    hourly_data = await DatabaseUtils.execute_query(
        """SELECT 
               DATE_TRUNC('hour', created_at) as hour,
               company_id,
               client_user_id,
               vendor_id,
               model_id,
               COUNT(*) as request_count,
               SUM(CASE WHEN success THEN 1 ELSE 0 END) as success_count,
               SUM(total_tokens) as total_tokens,
               SUM(total_cost) as total_cost,
               AVG(total_latency_ms) as avg_latency
           FROM requests
           WHERE client_user_id IS NOT NULL
             AND created_at > NOW() - INTERVAL '7 days'
           GROUP BY DATE_TRUNC('hour', created_at), company_id, 
                    client_user_id, vendor_id, model_id
           LIMIT 500""",
        fetch_all=True
    )
    
    count = 0
    for hour in hourly_data:
        if hour['client_user_id']:
            await DatabaseUtils.execute_query(
                """INSERT INTO user_analytics_hourly 
                   (hour_bucket_utc, hour_bucket_local, company_id, client_user_id,
                    vendor_id, model_id, request_count, success_count, error_count,
                    total_tokens, total_cost, avg_latency_ms)
                   VALUES ($1, $2, $3, $4, $5, $6, $7, $8, $9, $10, $11, $12)""",
                [hour['hour'], hour['hour'], hour['company_id'], hour['client_user_id'],
                 hour['vendor_id'], hour['model_id'], hour['request_count'],
                 hour['success_count'], hour['request_count'] - hour['success_count'],
                 hour['total_tokens'] or 0, hour['total_cost'] or 0,
                 hour['avg_latency'] or 0],
                fetch_all=False
            )
            count += 1
    
    print(f"  ✓ Created {count} hourly analytics records")

async def populate_daily_analytics():
    """Populate daily analytics"""
    print("\n📊 Populating Daily Analytics...")
    
    # Get daily aggregated data
    daily_data = await DatabaseUtils.execute_query(
        """SELECT 
               DATE(created_at) as date,
               company_id,
               client_user_id,
               COUNT(*) as total_requests,
               SUM(total_tokens) as total_tokens,
               SUM(total_cost) as total_cost,
               AVG(total_latency_ms) as avg_latency,
               COUNT(DISTINCT model_id) as unique_models
           FROM requests
           WHERE client_user_id IS NOT NULL
             AND created_at > NOW() - INTERVAL '30 days'
           GROUP BY DATE(created_at), company_id, client_user_id
           LIMIT 500""",
        fetch_all=True
    )
    
    count = 0
    for day in daily_data:
        if day['client_user_id']:
            await DatabaseUtils.execute_query(
                """INSERT INTO user_analytics_daily 
                   (date, company_id, client_user_id, total_requests,
                    total_tokens, total_cost, avg_latency_ms, unique_sessions)
                   VALUES ($1, $2, $3, $4, $5, $6, $7, $8)""",
                [day['date'], day['company_id'], day['client_user_id'],
                 day['total_requests'], day['total_tokens'] or 0,
                 day['total_cost'] or 0, day['avg_latency'] or 0,
                 day['unique_models']],  # Using models as proxy for sessions
                fetch_all=False
            )
            count += 1
    
    print(f"  ✓ Created {count} daily analytics records")

async def main():
    await init_database()
    
    print("🚀 Populating empty tables...")
    
    try:
        await populate_vendor_pricing()
    except Exception as e:
        print(f"  ✗ Error in vendor pricing: {str(e)}")
    
    try:
        await populate_user_sessions()
    except Exception as e:
        print(f"  ✗ Error in user sessions: {str(e)}")
    
    try:
        await populate_cost_alerts()
    except Exception as e:
        print(f"  ✗ Error in cost alerts: {str(e)}")
    
    try:
        await populate_hourly_analytics()
    except Exception as e:
        print(f"  ✗ Error in hourly analytics: {str(e)}")
    
    try:
        await populate_daily_analytics()
    except Exception as e:
        print(f"  ✗ Error in daily analytics: {str(e)}")
    
    # Final check
    print("\n\n📊 FINAL STATUS:")
    print("=" * 40)
    
    tables = ["vendor_pricing", "user_sessions", "cost_alerts", 
              "user_analytics_hourly", "user_analytics_daily"]
    
    for table in tables:
        count = await DatabaseUtils.execute_query(
            f"SELECT COUNT(*) as count FROM {table}",
            fetch_all=True
        )
        print(f"{table}: {count[0]['count']} records")
    
    await close_database()
    print("\n✅ Done!")

if __name__ == "__main__":
    asyncio.run(main())
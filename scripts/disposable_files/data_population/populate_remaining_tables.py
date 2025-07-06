#!/usr/bin/env python3
"""Populate the remaining empty tables"""
import asyncio
import random
import uuid
from datetime import datetime, timedelta, timezone
from app.database import DatabaseUtils, init_database, close_database

async def populate_api_keys():
    """Ensure all companies have API keys"""
    print("\n🔑 Populating API Keys...")
    
    companies = await DatabaseUtils.execute_query(
        "SELECT id, name FROM companies WHERE is_active = true",
        fetch_all=True
    )
    
    for company in companies:
        # Check if company has API key
        existing = await DatabaseUtils.execute_query(
            "SELECT COUNT(*) as count FROM api_keys WHERE company_id = $1",
            [company['id']], fetch_all=True
        )
        
        if existing[0]['count'] == 0:
            # Create API key
            key_value = f"als_{uuid.uuid4().hex}_32"
            key_hash = f"sha256_{key_value}"  # In production, this would be properly hashed
            
            await DatabaseUtils.execute_query(
                """INSERT INTO api_keys (company_id, key_hash, key_prefix, name, environment)
                   VALUES ($1, $2, $3, $4, $5)""",
                [company['id'], key_hash, "als", f"{company['name']} Production Key", "production"],
                fetch_all=False
            )
            print(f"  ✓ Created API key for {company['name']}")

async def populate_vendor_pricing():
    """Populate vendor pricing table"""
    print("\n💰 Populating Vendor Pricing...")
    
    # Get all models
    models = await DatabaseUtils.execute_query(
        """SELECT vm.id, vm.name, v.name as vendor_name, vm.model_type
           FROM vendor_models vm
           JOIN vendors v ON vm.vendor_id = v.id""",
        fetch_all=True
    )
    
    pricing_data = {
        "gpt-4": {"input": 0.03, "output": 0.06},
        "gpt-4-turbo": {"input": 0.01, "output": 0.03},
        "gpt-3.5-turbo": {"input": 0.0005, "output": 0.0015},
        "claude-3-opus": {"input": 0.015, "output": 0.075},
        "claude-3-sonnet": {"input": 0.003, "output": 0.015},
        "gemini-pro": {"input": 0.00025, "output": 0.0005},
        "dall-e-3": {"input": 0.04, "output": 0},
        "stable-diffusion-xl": {"input": 0.02, "output": 0}
    }
    
    for model in models:
        # Get pricing or use defaults
        model_key = None
        for key in pricing_data.keys():
            if key in model['name']:
                model_key = key
                break
        
        if model_key:
            prices = pricing_data[model_key]
        else:
            # Default pricing
            if model['model_type'] == 'image':
                prices = {"input": 0.02, "output": 0}
            else:
                prices = {"input": 0.001, "output": 0.002}
        
        try:
            await DatabaseUtils.execute_query(
                """INSERT INTO vendor_pricing 
                   (model_id, pricing_tier, input_price_per_1k, output_price_per_1k, 
                    effective_date, is_active)
                   VALUES ($1, $2, $3, $4, $5, true)
                   ON CONFLICT (model_id, pricing_tier, effective_date) DO NOTHING""",
                [model['id'], 'standard', prices['input'], prices['output'], 
                 datetime.now(timezone.utc) - timedelta(days=30)],
                fetch_all=False
            )
            print(f"  ✓ Added pricing for {model['vendor_name']}/{model['name']}")
        except Exception as e:
            print(f"  ✗ Error adding pricing for {model['name']}: {str(e)}")

async def populate_user_sessions():
    """Populate user sessions based on requests"""
    print("\n👥 Populating User Sessions...")
    
    # Get unique user/date combinations from requests
    user_sessions = await DatabaseUtils.execute_query(
        """SELECT DISTINCT 
               client_user_id,
               DATE(created_at) as session_date,
               MIN(created_at) as first_request,
               MAX(created_at) as last_request,
               COUNT(*) as request_count,
               MIN(ip_address) as ip_address,
               MIN(country) as country,
               MIN(region) as region,
               MIN(city) as city,
               MIN(user_agent) as user_agent
           FROM requests
           WHERE client_user_id IS NOT NULL
           GROUP BY client_user_id, DATE(created_at)""",
        fetch_all=True
    )
    
    created = 0
    for session in user_sessions:
        session_id = f"session_{session['client_user_id']}_{session['session_date']}"
        
        try:
            await DatabaseUtils.execute_query(
                """INSERT INTO user_sessions 
                   (client_user_id, session_id, ip_address, user_agent,
                    country, region, city, started_at, request_count)
                   VALUES ($1, $2, $3, $4, $5, $6, $7, $8, $9)
                   ON CONFLICT (client_user_id, session_id) DO NOTHING""",
                [session['client_user_id'], session_id, session['ip_address'],
                 session['user_agent'], session['country'], session['region'],
                 session['city'], session['first_request'], session['request_count']],
                fetch_all=False
            )
            created += 1
        except Exception as e:
            if "no unique or exclusion constraint" not in str(e):
                print(f"  ✗ Error creating session: {str(e)}")
    
    print(f"  ✓ Created {created} user sessions")

async def populate_cost_alerts():
    """Populate cost alerts for companies"""
    print("\n🚨 Populating Cost Alerts...")
    
    companies = await DatabaseUtils.execute_query(
        "SELECT id, name FROM companies WHERE is_active = true",
        fetch_all=True
    )
    
    alert_types = [
        ("daily_budget_80", "Daily budget 80% reached", 80),
        ("daily_budget_100", "Daily budget exceeded", 100),
        ("anomaly_spike", "Unusual spike in usage", None),
        ("rate_limit", "Rate limit approaching", None)
    ]
    
    for company in companies[:5]:  # Add alerts for first 5 companies
        for alert_type, description, threshold in alert_types:
            try:
                await DatabaseUtils.execute_query(
                    """INSERT INTO cost_alerts 
                       (company_id, alert_type, threshold_value, is_active, description)
                       VALUES ($1, $2, $3, $4, $5)""",
                    [company['id'], alert_type, threshold, True, description],
                    fetch_all=False
                )
            except Exception as e:
                pass  # Ignore duplicates
    
    print(f"  ✓ Created cost alerts for {len(companies[:5])} companies")

async def populate_analytics():
    """Populate hourly and daily analytics"""
    print("\n📊 Populating Analytics Tables...")
    
    # Hourly analytics for last 7 days
    hourly_data = await DatabaseUtils.execute_query(
        """SELECT 
               DATE_TRUNC('hour', created_at) as hour,
               company_id,
               vendor_id,
               model_id,
               COUNT(*) as request_count,
               SUM(CASE WHEN success THEN 1 ELSE 0 END) as success_count,
               SUM(input_tokens) as total_input_tokens,
               SUM(output_tokens) as total_output_tokens,
               SUM(total_cost) as total_cost,
               AVG(total_latency_ms) as avg_latency,
               COUNT(DISTINCT client_user_id) as unique_users
           FROM requests
           WHERE created_at > NOW() - INTERVAL '7 days'
           GROUP BY DATE_TRUNC('hour', created_at), company_id, vendor_id, model_id""",
        fetch_all=True
    )
    
    hourly_created = 0
    for hour in hourly_data:
        try:
            await DatabaseUtils.execute_query(
                """INSERT INTO user_analytics_hourly 
                   (company_id, vendor_id, model_id, hour_utc, request_count,
                    success_count, error_count, unique_users, total_cost_usd,
                    avg_latency_ms, total_input_tokens, total_output_tokens)
                   VALUES ($1, $2, $3, $4, $5, $6, $7, $8, $9, $10, $11, $12)
                   ON CONFLICT (company_id, vendor_id, model_id, hour_utc) DO NOTHING""",
                [hour['company_id'], hour['vendor_id'], hour['model_id'], hour['hour'],
                 hour['request_count'], hour['success_count'], 
                 hour['request_count'] - hour['success_count'], hour['unique_users'],
                 hour['total_cost'] or 0, hour['avg_latency'] or 0,
                 hour['total_input_tokens'] or 0, hour['total_output_tokens'] or 0],
                fetch_all=False
            )
            hourly_created += 1
        except:
            pass
    
    print(f"  ✓ Created {hourly_created} hourly analytics records")
    
    # Daily analytics for last 30 days
    daily_data = await DatabaseUtils.execute_query(
        """SELECT 
               DATE(created_at) as date,
               company_id,
               vendor_id,
               model_id,
               COUNT(*) as request_count,
               SUM(CASE WHEN success THEN 1 ELSE 0 END) as success_count,
               SUM(input_tokens) as total_input_tokens,
               SUM(output_tokens) as total_output_tokens,
               SUM(total_cost) as total_cost,
               AVG(total_latency_ms) as avg_latency,
               COUNT(DISTINCT client_user_id) as unique_users,
               COUNT(DISTINCT country) as unique_countries
           FROM requests
           WHERE created_at > NOW() - INTERVAL '30 days'
           GROUP BY DATE(created_at), company_id, vendor_id, model_id""",
        fetch_all=True
    )
    
    daily_created = 0
    for day in daily_data:
        try:
            await DatabaseUtils.execute_query(
                """INSERT INTO user_analytics_daily 
                   (company_id, vendor_id, model_id, date, request_count,
                    success_count, error_count, unique_users, unique_sessions,
                    unique_countries, total_cost_usd, avg_latency_ms,
                    total_input_tokens, total_output_tokens)
                   VALUES ($1, $2, $3, $4, $5, $6, $7, $8, $9, $10, $11, $12, $13, $14)
                   ON CONFLICT (company_id, vendor_id, model_id, date) DO NOTHING""",
                [day['company_id'], day['vendor_id'], day['model_id'], day['date'],
                 day['request_count'], day['success_count'],
                 day['request_count'] - day['success_count'], day['unique_users'],
                 day['unique_users'], day['unique_countries'],  # Using users as sessions estimate
                 day['total_cost'] or 0, day['avg_latency'] or 0,
                 day['total_input_tokens'] or 0, day['total_output_tokens'] or 0],
                fetch_all=False
            )
            daily_created += 1
        except:
            pass
    
    print(f"  ✓ Created {daily_created} daily analytics records")

async def populate_cost_anomalies():
    """Populate some sample cost anomalies"""
    print("\n⚠️  Populating Cost Anomalies...")
    
    # Find companies with high usage
    high_usage = await DatabaseUtils.execute_query(
        """SELECT 
               company_id,
               DATE(created_at) as date,
               SUM(total_cost) as daily_cost,
               COUNT(*) as request_count
           FROM requests
           WHERE created_at > NOW() - INTERVAL '7 days'
           GROUP BY company_id, DATE(created_at)
           HAVING SUM(total_cost) > 5
           ORDER BY daily_cost DESC
           LIMIT 10""",
        fetch_all=True
    )
    
    for anomaly in high_usage[:5]:  # Create 5 anomalies
        await DatabaseUtils.execute_query(
            """INSERT INTO cost_anomalies 
               (company_id, detected_at, anomaly_type, severity,
                expected_value, actual_value, description)
               VALUES ($1, $2, $3, $4, $5, $6, $7)""",
            [anomaly['company_id'], anomaly['date'], 'cost_spike', 'medium',
             2.0, float(anomaly['daily_cost']), 
             f"Daily cost spike: ${anomaly['daily_cost']:.2f} vs expected $2.00"],
            fetch_all=False
        )
    
    print(f"  ✓ Created {len(high_usage[:5])} cost anomalies")

async def main():
    await init_database()
    
    print("🚀 Populating remaining tables...")
    
    await populate_api_keys()
    await populate_vendor_pricing()
    await populate_user_sessions()
    await populate_cost_alerts()
    await populate_analytics()
    await populate_cost_anomalies()
    
    # Final summary
    print("\n\n📊 FINAL TABLE STATUS:")
    print("=" * 40)
    
    tables_to_check = [
        "api_keys",
        "vendor_pricing",
        "user_sessions",
        "cost_alerts",
        "user_analytics_hourly",
        "user_analytics_daily",
        "cost_anomalies"
    ]
    
    for table in tables_to_check:
        count = await DatabaseUtils.execute_query(
            f"SELECT COUNT(*) as count FROM {table}",
            fetch_all=True
        )
        print(f"{table}: {count[0]['count']} records")
    
    await close_database()
    print("\n✅ All tables populated!")

if __name__ == "__main__":
    asyncio.run(main())
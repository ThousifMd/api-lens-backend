#!/usr/bin/env python3
"""Check what data was populated"""
import asyncio
from app.database import DatabaseUtils, init_database, close_database

async def main():
    await init_database()
    
    print("📊 DATABASE POPULATION SUMMARY")
    print("=" * 60)
    
    # 1. Companies
    companies = await DatabaseUtils.execute_query(
        "SELECT COUNT(*) as count FROM companies WHERE is_active = true",
        fetch_all=True
    )
    print(f"\n✓ Active Companies: {companies[0]['count']}")
    
    # 2. Vendors and Models
    vendors = await DatabaseUtils.execute_query(
        "SELECT COUNT(*) as count FROM vendors WHERE is_active = true",
        fetch_all=True
    )
    models = await DatabaseUtils.execute_query(
        "SELECT COUNT(*) as count FROM vendor_models WHERE is_active = true",
        fetch_all=True
    )
    print(f"✓ Active Vendors: {vendors[0]['count']}")
    print(f"✓ Active Models: {models[0]['count']}")
    
    # 3. Users
    users = await DatabaseUtils.execute_query(
        "SELECT COUNT(*) as count FROM client_users",
        fetch_all=True
    )
    print(f"✓ Client Users: {users[0]['count']}")
    
    # 4. Requests
    requests = await DatabaseUtils.execute_query(
        "SELECT COUNT(*) as count FROM requests",
        fetch_all=True
    )
    print(f"✓ Total Requests: {requests[0]['count']}")
    
    # 5. Location Distribution
    print("\n📍 LOCATION DISTRIBUTION:")
    print("-" * 40)
    locations = await DatabaseUtils.execute_query("""
        SELECT 
            city, region, country,
            COUNT(*) as count,
            COUNT(DISTINCT company_id) as companies,
            COUNT(DISTINCT client_user_id) as users
        FROM requests
        GROUP BY city, region, country
        ORDER BY count DESC
        LIMIT 15
    """, fetch_all=True)
    
    for loc in locations:
        print(f"  {loc['city']}, {loc['region']}, {loc['country']}: "
              f"{loc['count']} requests from {loc['companies']} companies, {loc['users']} users")
    
    # 6. Time Distribution
    print("\n📅 TIME DISTRIBUTION (last 30 days):")
    print("-" * 40)
    time_dist = await DatabaseUtils.execute_query("""
        SELECT 
            DATE(created_at) as date,
            COUNT(*) as requests,
            COUNT(DISTINCT company_id) as companies
        FROM requests
        WHERE created_at > NOW() - INTERVAL '30 days'
        GROUP BY DATE(created_at)
        ORDER BY date DESC
        LIMIT 10
    """, fetch_all=True)
    
    for t in time_dist:
        print(f"  {t['date']}: {t['requests']} requests from {t['companies']} companies")
    
    # 7. Model Usage
    print("\n🤖 MODEL USAGE:")
    print("-" * 40)
    model_usage = await DatabaseUtils.execute_query("""
        SELECT 
            v.name as vendor,
            vm.name as model,
            COUNT(*) as requests,
            SUM(r.input_tokens) as total_input_tokens,
            SUM(r.output_tokens) as total_output_tokens,
            SUM(r.total_cost) as total_cost
        FROM requests r
        JOIN vendors v ON r.vendor_id = v.id
        JOIN vendor_models vm ON r.model_id = vm.id
        GROUP BY v.name, vm.name
        ORDER BY requests DESC
        LIMIT 10
    """, fetch_all=True)
    
    for m in model_usage:
        cost = f"${m['total_cost']:.2f}" if m['total_cost'] else "$0.00"
        print(f"  {m['vendor']}/{m['model']}: {m['requests']} requests, {cost}")
    
    # 8. Success Rate
    print("\n📈 SUCCESS METRICS:")
    print("-" * 40)
    success_stats = await DatabaseUtils.execute_query("""
        SELECT 
            COUNT(*) as total,
            SUM(CASE WHEN success THEN 1 ELSE 0 END) as successful,
            AVG(total_latency_ms) as avg_latency,
            MIN(total_latency_ms) as min_latency,
            MAX(total_latency_ms) as max_latency
        FROM requests
    """, fetch_all=True)
    
    s = success_stats[0]
    success_rate = (s['successful'] / s['total'] * 100) if s['total'] > 0 else 0
    print(f"  Total Requests: {s['total']}")
    print(f"  Success Rate: {success_rate:.1f}%")
    print(f"  Avg Latency: {s['avg_latency']:.0f}ms")
    print(f"  Min/Max Latency: {s['min_latency']}ms / {s['max_latency']}ms")
    
    await close_database()
    print("\n✅ Data check complete!")

if __name__ == "__main__":
    asyncio.run(main())
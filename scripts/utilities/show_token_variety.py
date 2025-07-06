#!/usr/bin/env python3
"""Show the variety in token values after fixes"""
import asyncio
from app.database import DatabaseUtils, init_database, close_database

async def show_variety():
    await init_database()
    
    print("📊 TOKEN AND LOCATION VARIETY ANALYSIS")
    print("=" * 60)
    
    # Check token variety
    token_stats = await DatabaseUtils.execute_query("""
        SELECT 
            v.name as vendor,
            vm.name as model,
            COUNT(*) as count,
            MIN(r.input_tokens) as min_input,
            MAX(r.input_tokens) as max_input,
            AVG(r.input_tokens)::int as avg_input,
            MIN(r.output_tokens) as min_output,
            MAX(r.output_tokens) as max_output,
            AVG(r.output_tokens)::int as avg_output,
            SUM(r.total_cost) as total_cost
        FROM requests r
        JOIN vendors v ON r.vendor_id = v.id
        JOIN vendor_models vm ON r.model_id = vm.id
        GROUP BY v.name, vm.name
        ORDER BY count DESC
    """, fetch_all=True)
    
    print("\n📈 TOKEN STATISTICS BY MODEL:")
    print("-" * 90)
    print(f"{'Model':40} {'Count':>6} {'Input Tokens':>20} {'Output Tokens':>20}")
    print(f"{'':40} {'':>6} {'(min/avg/max)':>20} {'(min/avg/max)':>20}")
    print("-" * 90)
    
    for stat in token_stats:
        model_name = f"{stat['vendor']}/{stat['model']}"[:40]
        input_range = f"{stat['min_input']}/{stat['avg_input']}/{stat['max_input']}"
        output_range = f"{stat['min_output']}/{stat['avg_output']}/{stat['max_output']}"
        print(f"{model_name:40} {stat['count']:>6} {input_range:>20} {output_range:>20}")
    
    # Check specific examples
    print("\n\n📋 SAMPLE RECORDS SHOWING VARIETY:")
    print("-" * 90)
    
    samples = await DatabaseUtils.execute_query("""
        SELECT 
            r.request_id,
            v.name as vendor,
            vm.name as model,
            r.input_tokens,
            r.output_tokens,
            r.total_cost,
            r.city,
            r.country,
            r.created_at
        FROM requests r
        JOIN vendors v ON r.vendor_id = v.id
        JOIN vendor_models vm ON r.model_id = vm.id
        ORDER BY r.created_at DESC
        LIMIT 20
    """, fetch_all=True)
    
    print(f"{'Request ID':32} {'Model':25} {'Tokens (I/O)':>15} {'Cost':>10} {'Location':>15}")
    print("-" * 90)
    
    for sample in samples:
        req_id = sample['request_id'][:32]
        model = f"{sample['vendor']}/{sample['model'].split('-')[0]}"[:25]
        tokens = f"{sample['input_tokens']}/{sample['output_tokens']}"
        cost = f"${sample['total_cost']:.4f}"
        location = f"{sample['city'][:10]}, {sample['country']}"
        print(f"{req_id:32} {model:25} {tokens:>15} {cost:>10} {location:>15}")
    
    # Check location distribution
    print("\n\n🌍 LOCATION DISTRIBUTION:")
    print("-" * 40)
    
    locations = await DatabaseUtils.execute_query("""
        SELECT 
            city, country,
            COUNT(*) as count,
            COUNT(DISTINCT vendor_id || '-' || model_id) as models_used
        FROM requests
        GROUP BY city, country
        ORDER BY count DESC
    """, fetch_all=True)
    
    for loc in locations:
        print(f"{loc['city']:15} {loc['country']:3} - {loc['count']:3} requests using {loc['models_used']} different models")
    
    # Token distribution histogram
    print("\n\n📊 INPUT TOKEN DISTRIBUTION:")
    print("-" * 40)
    
    token_dist = await DatabaseUtils.execute_query("""
        SELECT 
            CASE 
                WHEN input_tokens = 0 THEN '0'
                WHEN input_tokens < 50 THEN '1-49'
                WHEN input_tokens < 100 THEN '50-99'
                WHEN input_tokens < 200 THEN '100-199'
                WHEN input_tokens < 500 THEN '200-499'
                WHEN input_tokens < 1000 THEN '500-999'
                ELSE '1000+'
            END as range,
            COUNT(*) as count
        FROM requests
        GROUP BY 1
        ORDER BY 
            CASE 
                WHEN input_tokens = 0 THEN 0
                WHEN input_tokens < 50 THEN 1
                WHEN input_tokens < 100 THEN 2
                WHEN input_tokens < 200 THEN 3
                WHEN input_tokens < 500 THEN 4
                WHEN input_tokens < 1000 THEN 5
                ELSE 6
            END
    """, fetch_all=True)
    
    for td in token_dist:
        bar = '█' * min(int(td['count'] / max(1, len(samples) / 20)), 40)
        print(f"{td['range']:10} | {bar} {td['count']}")
    
    await close_database()
    print("\n✅ Analysis complete!")

if __name__ == "__main__":
    asyncio.run(show_variety())
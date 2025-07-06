#!/usr/bin/env python3
"""Check partition setup for requests table"""
import asyncio
from app.database import DatabaseUtils, init_database, close_database

async def main():
    await init_database()
    
    print("🔍 PARTITIONING ANALYSIS FOR REQUESTS TABLE")
    print("=" * 60)
    
    # Check if requests is partitioned
    partition_info = await DatabaseUtils.execute_query("""
        SELECT 
            c.relname as table_name,
            p.partstrat as partition_strategy,
            pg_get_partkeydef(c.oid) as partition_key
        FROM pg_class c
        JOIN pg_partitioned_table p ON c.oid = p.partrelid
        WHERE c.relname = 'requests'
    """, fetch_all=True)
    
    if partition_info:
        print("\n✅ REQUESTS TABLE IS PARTITIONED:")
        print(f"  Strategy: {'RANGE' if partition_info[0]['partition_strategy'] == 'r' else 'OTHER'}")
        print(f"  Partition Key: {partition_info[0]['partition_key']}")
    
    # List all partitions
    print("\n📅 EXISTING PARTITIONS:")
    print("-" * 40)
    
    partitions = await DatabaseUtils.execute_query("""
        SELECT 
            inhrelid::regclass as partition_name,
            pg_get_expr(c.relpartbound, c.oid) as partition_range
        FROM pg_inherits
        JOIN pg_class c ON inhrelid = c.oid
        WHERE inhparent = 'requests'::regclass
        ORDER BY inhrelid::regclass::text
    """, fetch_all=True)
    
    for p in partitions:
        # Get row count for each partition
        count_result = await DatabaseUtils.execute_query(
            f"SELECT COUNT(*) as count FROM {p['partition_name']}",
            fetch_all=True
        )
        count = count_result[0]['count']
        print(f"  {p['partition_name']}: {count} rows")
        print(f"    Range: {p['partition_range']}")
    
    # Total rows
    total = await DatabaseUtils.execute_query(
        "SELECT COUNT(*) as count FROM requests",
        fetch_all=True
    )
    print(f"\n  TOTAL: {total[0]['count']} rows across all partitions")
    
    # Benefits explanation
    print("\n\n💡 WHY PARTITIONING?")
    print("-" * 40)
    print("1. **Performance**: Queries that filter by date only scan relevant partitions")
    print("2. **Maintenance**: Old data can be dropped by simply dropping old partitions")
    print("3. **Scalability**: Can handle billions of requests without slowing down")
    print("4. **Archival**: Easy to move old partitions to cold storage")
    print("5. **Parallel Processing**: Different partitions can be processed simultaneously")
    
    print("\n📊 EXAMPLE BENEFITS:")
    print("-" * 40)
    print("• Query for today's data: Scans only 1 partition instead of entire table")
    print("• Delete data older than 90 days: DROP PARTITION instead of DELETE (instant)")
    print("• Analytics for last month: Targets specific partition, 10-100x faster")
    print("• Backup strategy: Can backup partitions independently")
    
    await close_database()

if __name__ == "__main__":
    asyncio.run(main())
#!/usr/bin/env python3
"""
Clean up all existing request records to start fresh
"""
import asyncio
from app.database import DatabaseUtils, init_database, close_database
from app.utils.logger import get_logger

logger = get_logger(__name__)

async def clean_requests():
    await init_database()
    
    print("🧹 CLEANING UP REQUEST RECORDS")
    print("=" * 60)
    
    # First, check how many records exist
    count_result = await DatabaseUtils.execute_query(
        "SELECT COUNT(*) as count FROM requests",
        fetch_all=True
    )
    existing_count = count_result[0]['count']
    
    print(f"\n📊 Found {existing_count} existing request records")
    
    if existing_count == 0:
        print("✅ No records to delete. Table is already clean!")
        await close_database()
        return
    
    # Show a sample of what will be deleted
    print("\n📋 Sample records that will be deleted:")
    print("-" * 60)
    
    samples = await DatabaseUtils.execute_query("""
        SELECT 
            r.request_id,
            v.name as vendor,
            vm.name as model,
            r.created_at
        FROM requests r
        JOIN vendors v ON r.vendor_id = v.id
        JOIN vendor_models vm ON r.model_id = vm.id
        ORDER BY r.created_at DESC
        LIMIT 5
    """, fetch_all=True)
    
    for sample in samples:
        print(f"  {sample['request_id'][:40]:40} | {sample['vendor']}/{sample['model'][:20]:20} | {sample['created_at']}")
    
    # Also delete related data in dependent tables
    print("\n🗑️  Cleaning related tables...")
    
    # Delete user sessions (they reference requests indirectly)
    sessions_result = await DatabaseUtils.execute_query(
        "DELETE FROM user_sessions WHERE request_count > 0",
        fetch_all=False
    )
    print("  ✓ Cleaned user sessions")
    
    # Delete analytics data if any
    try:
        await DatabaseUtils.execute_query(
            "DELETE FROM user_analytics_hourly",
            fetch_all=False
        )
        print("  ✓ Cleaned hourly analytics")
    except:
        pass
    
    try:
        await DatabaseUtils.execute_query(
            "DELETE FROM user_analytics_daily",
            fetch_all=False
        )
        print("  ✓ Cleaned daily analytics")
    except:
        pass
    
    # Now delete all requests
    print("\n🗑️  Deleting all request records...")
    
    delete_result = await DatabaseUtils.execute_query(
        "DELETE FROM requests",
        fetch_all=False
    )
    
    print("✅ All request records deleted successfully!")
    
    # Verify deletion
    verify_result = await DatabaseUtils.execute_query(
        "SELECT COUNT(*) as count FROM requests",
        fetch_all=True
    )
    remaining_count = verify_result[0]['count']
    
    if remaining_count == 0:
        print(f"\n✅ Verification successful: {remaining_count} records remaining")
    else:
        print(f"\n⚠️  Warning: {remaining_count} records still remain")
    
    # Check table health
    print("\n🏥 Checking table health...")
    
    # Check if sequences need resetting (optional)
    # This is useful if you want IDs to start fresh
    
    # Show partition information
    partition_info = await DatabaseUtils.execute_query("""
        SELECT 
            schemaname,
            tablename,
            pg_size_pretty(pg_total_relation_size(schemaname||'.'||tablename)) as size
        FROM pg_tables
        WHERE tablename LIKE 'requests_%'
        ORDER BY tablename
    """, fetch_all=True)
    
    if partition_info:
        print("\n📊 Request table partitions:")
        for part in partition_info:
            print(f"  {part['tablename']:25} | Size: {part['size']}")
    
    # Show other relevant tables
    print("\n📊 Related table record counts:")
    
    tables_to_check = [
        ('companies', 'Companies'),
        ('api_keys', 'API Keys'),
        ('client_users', 'Client Users'),
        ('vendors', 'Vendors'),
        ('vendor_models', 'Vendor Models'),
        ('vendor_pricing', 'Vendor Pricing')
    ]
    
    for table_name, display_name in tables_to_check:
        try:
            count_result = await DatabaseUtils.execute_query(
                f"SELECT COUNT(*) as count FROM {table_name}",
                fetch_all=True
            )
            count = count_result[0]['count']
            print(f"  {display_name:20} | {count:6} records")
        except Exception as e:
            print(f"  {display_name:20} | Error: {str(e)}")
    
    await close_database()
    
    print("\n" + "=" * 60)
    print("✅ CLEANUP COMPLETE!")
    print("=" * 60)
    print("\nYour requests table is now clean and ready for fresh API calls.")
    print("The API endpoint will automatically populate all fields including:")
    print("  • Varied token counts based on model type")
    print("  • Location data (with fallback if IP detection fails)")
    print("  • Accurate cost calculations")
    print("  • Proper timezone information")
    print("\nYou can now start making API calls through the proxy endpoint!")

if __name__ == "__main__":
    print("⚠️  WARNING: This will delete ALL request records!")
    print("This action cannot be undone.")
    response = input("\nAre you sure you want to proceed? (yes/no): ")
    
    if response.lower() == 'yes':
        asyncio.run(clean_requests())
    else:
        print("❌ Cleanup cancelled.")
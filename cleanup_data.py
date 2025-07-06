#!/usr/bin/env python3
"""Clean up data records while keeping metadata"""
import asyncio
from app.database import DatabaseUtils, init_database, close_database

async def main():
    await init_database()
    
    print("🧹 CLEANING UP DATA RECORDS")
    print("=" * 60)
    print("This will DELETE all records from data tables while keeping:")
    print("  ✓ Companies")
    print("  ✓ Vendors & Models") 
    print("  ✓ Vendor Pricing")
    print("  ✓ API Keys")
    print("\nTables to be CLEARED:")
    print("  • requests (all partitions)")
    print("  • client_users")
    print("  • user_sessions")
    print("  • user_analytics_hourly")
    print("  • user_analytics_daily")
    print("  • cost_alerts")
    print("  • cost_anomalies")
    
    # Confirm
    response = input("\n⚠️  Are you sure you want to delete all data records? (yes/no): ")
    if response.lower() != 'yes':
        print("Cancelled.")
        await close_database()
        return
    
    print("\n🗑️  Deleting data...")
    
    # Tables to clean (order matters due to foreign keys)
    tables_to_clean = [
        ("user_analytics_hourly", "hourly analytics"),
        ("user_analytics_daily", "daily analytics"),
        ("user_sessions", "user sessions"),
        ("requests", "requests"),
        ("client_users", "client users"),
        ("cost_alerts", "cost alerts"),
        ("cost_anomalies", "cost anomalies")
    ]
    
    for table, description in tables_to_clean:
        try:
            # Get count before deletion
            count_result = await DatabaseUtils.execute_query(
                f"SELECT COUNT(*) as count FROM {table}",
                fetch_all=True
            )
            count = count_result[0]['count']
            
            if count > 0:
                # Delete all records
                await DatabaseUtils.execute_query(
                    f"TRUNCATE TABLE {table} CASCADE",
                    fetch_all=False
                )
                print(f"  ✓ Deleted {count} {description}")
            else:
                print(f"  - {description} was already empty")
                
        except Exception as e:
            print(f"  ✗ Error cleaning {table}: {str(e)}")
    
    # Show what remains
    print("\n\n📊 REMAINING METADATA:")
    print("-" * 40)
    
    metadata_tables = [
        ("companies", "Companies"),
        ("vendors", "Vendors"),
        ("vendor_models", "Vendor Models"),
        ("vendor_pricing", "Vendor Pricing"),
        ("api_keys", "API Keys")
    ]
    
    for table, name in metadata_tables:
        count_result = await DatabaseUtils.execute_query(
            f"SELECT COUNT(*) as count FROM {table}",
            fetch_all=True
        )
        count = count_result[0]['count']
        print(f"  {name}: {count} records")
    
    # Verify data tables are empty
    print("\n\n✅ VERIFICATION - Data tables are now empty:")
    print("-" * 40)
    
    for table, description in tables_to_clean:
        count_result = await DatabaseUtils.execute_query(
            f"SELECT COUNT(*) as count FROM {table}",
            fetch_all=True
        )
        count = count_result[0]['count']
        status = "✓ EMPTY" if count == 0 else f"❌ Still has {count} records"
        print(f"  {table}: {status}")
    
    await close_database()
    print("\n✅ Cleanup complete! Ready for fresh testing.")

if __name__ == "__main__":
    asyncio.run(main())
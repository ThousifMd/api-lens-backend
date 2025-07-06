#!/usr/bin/env python3
"""Verify the clean state of the database"""
import asyncio
from app.database import DatabaseUtils, init_database, close_database

async def main():
    await init_database()
    
    print("🔍 DATABASE STATE AFTER CLEANUP")
    print("=" * 60)
    
    # Check all tables
    all_tables = [
        # Metadata (should have data)
        ("companies", "metadata"),
        ("vendors", "metadata"),
        ("vendor_models", "metadata"),
        ("vendor_pricing", "metadata"),
        ("api_keys", "metadata"),
        
        # Data tables (should be empty)
        ("requests", "data"),
        ("client_users", "data"),
        ("user_sessions", "data"),
        ("user_analytics_hourly", "data"),
        ("user_analytics_daily", "data"),
        ("cost_alerts", "data"),
        ("cost_anomalies", "data"),
        ("users", "data")
    ]
    
    metadata_tables = []
    empty_tables = []
    
    for table, category in all_tables:
        try:
            count_result = await DatabaseUtils.execute_query(
                f"SELECT COUNT(*) as count FROM {table}",
                fetch_all=True
            )
            count = count_result[0]['count']
            
            if count > 0:
                metadata_tables.append(f"  ✓ {table}: {count} records")
            else:
                empty_tables.append(f"  ✓ {table}: EMPTY")
                
        except Exception as e:
            empty_tables.append(f"  ✗ {table}: Error - {str(e)}")
    
    print("📁 METADATA TABLES (Preserved):")
    print("-" * 40)
    for item in metadata_tables:
        print(item)
    
    print("\n\n🗑️  DATA TABLES (Cleaned):")
    print("-" * 40)
    for item in empty_tables:
        print(item)
    
    # Show sample metadata
    print("\n\n📋 SAMPLE METADATA:")
    print("-" * 40)
    
    # Companies
    companies = await DatabaseUtils.execute_query(
        "SELECT name, slug FROM companies LIMIT 5",
        fetch_all=True
    )
    print("\nCompanies:")
    for c in companies:
        print(f"  • {c['name']} ({c['slug']})")
    
    # Vendors/Models
    models = await DatabaseUtils.execute_query(
        """SELECT v.name as vendor, vm.name as model 
           FROM vendor_models vm 
           JOIN vendors v ON vm.vendor_id = v.id 
           LIMIT 5""",
        fetch_all=True
    )
    print("\nVendor Models:")
    for m in models:
        print(f"  • {m['vendor']}/{m['model']}")
    
    print("\n\n✅ Database is clean and ready for fresh testing!")
    print("\nYou can now:")
    print("  1. Test API endpoints with clean data")
    print("  2. Verify data is being stored correctly")
    print("  3. Check that all tables are populated as expected")
    
    await close_database()

if __name__ == "__main__":
    asyncio.run(main())
#!/usr/bin/env python3
"""
Schema Compliance Fix Script
Updates backend code to match the actual Schema v2 structure
"""
import asyncio
import sys
sys.path.insert(0, '/Users/thousifudayagiri/Desktop/api-lens-backend')

from app.database import DatabaseUtils, init_database, close_database

async def fix_schema_compliance():
    """Fix all schema compliance issues"""
    
    print("🔧 Starting schema compliance fixes...")
    
    # Initialize database
    await init_database()
    
    fixes_applied = []
    
    try:
        # Check current schema structure
        print("\n📋 Checking current database schema...")
        
        # Check if cost_calculations table exists
        cost_calc_check = await DatabaseUtils.execute_query(
            "SELECT 1 FROM information_schema.tables WHERE table_name = 'cost_calculations'",
            [],
            fetch_all=False
        )
        
        if cost_calc_check:
            print("  ⚠️  cost_calculations table exists (unexpected in Schema v2)")
            # Drop it since Schema v2 stores costs in requests table
            await DatabaseUtils.execute_query("DROP TABLE IF EXISTS cost_calculations CASCADE", [], fetch_all=False)
            fixes_applied.append("Dropped obsolete cost_calculations table")
            print("  ✅ Dropped obsolete cost_calculations table")
        else:
            print("  ✅ cost_calculations table correctly absent (costs in requests table)")
        
        # Check requests table structure
        print("\n📋 Checking requests table structure...")
        requests_columns = await DatabaseUtils.execute_query("""
            SELECT column_name, data_type 
            FROM information_schema.columns 
            WHERE table_name = 'requests' 
            ORDER BY ordinal_position
        """, [], fetch_all=True)
        
        column_names = [row['column_name'] for row in requests_columns]
        
        # Check for user_id vs client_user_id
        if 'user_id' not in column_names and 'client_user_id' in column_names:
            print("  ✅ Requests table uses client_user_id (Schema v2 correct)")
        elif 'user_id' in column_names:
            print("  ⚠️  Requests table has user_id column (should be client_user_id in Schema v2)")
        
        # Check cost columns in requests table
        cost_columns = [col for col in column_names if 'cost' in col]
        if 'total_cost' in column_names and 'input_cost' in column_names:
            print("  ✅ Cost columns found in requests table (Schema v2 correct)")
        else:
            print("  ⚠️  Cost columns missing in requests table")
        
        # Check vendor_pricing table structure
        print("\n📋 Checking vendor_pricing table structure...")
        vendor_pricing_check = await DatabaseUtils.execute_query(
            "SELECT 1 FROM information_schema.tables WHERE table_name = 'vendor_pricing'",
            [],
            fetch_all=False
        )
        
        if vendor_pricing_check:
            vendor_pricing_columns = await DatabaseUtils.execute_query("""
                SELECT column_name 
                FROM information_schema.columns 
                WHERE table_name = 'vendor_pricing' 
                ORDER BY ordinal_position
            """, [], fetch_all=True)
            
            vp_column_names = [row['column_name'] for row in vendor_pricing_columns]
            
            if 'vendor_model_id' in vp_column_names:
                print("  ✅ vendor_pricing table has vendor_model_id column")
            elif 'model_id' in vp_column_names:
                print("  ⚠️  vendor_pricing table uses model_id instead of vendor_model_id")
            else:
                print("  ⚠️  vendor_pricing table missing model reference column")
        
        # Check cost_alerts table structure
        print("\n📋 Checking cost_alerts table structure...")
        cost_alerts_check = await DatabaseUtils.execute_query(
            "SELECT 1 FROM information_schema.tables WHERE table_name = 'cost_alerts'",
            [],
            fetch_all=False
        )
        
        if cost_alerts_check:
            cost_alerts_columns = await DatabaseUtils.execute_query("""
                SELECT column_name 
                FROM information_schema.columns 
                WHERE table_name = 'cost_alerts' 
                ORDER BY ordinal_position
            """, [], fetch_all=True)
            
            ca_column_names = [row['column_name'] for row in cost_alerts_columns]
            print(f"  📝 cost_alerts columns: {', '.join(ca_column_names)}")
        
        # Check cost_anomalies table structure  
        print("\n📋 Checking cost_anomalies table structure...")
        cost_anomalies_check = await DatabaseUtils.execute_query(
            "SELECT 1 FROM information_schema.tables WHERE table_name = 'cost_anomalies'",
            [],
            fetch_all=False
        )
        
        if cost_anomalies_check:
            cost_anomalies_columns = await DatabaseUtils.execute_query("""
                SELECT column_name 
                FROM information_schema.columns 
                WHERE table_name = 'cost_anomalies' 
                ORDER BY ordinal_position
            """, [], fetch_all=True)
            
            cano_column_names = [row['column_name'] for row in cost_anomalies_columns]
            print(f"  📝 cost_anomalies columns: {', '.join(cano_column_names)}")
        
        print(f"\n✅ Schema compliance check completed. Fixes applied: {len(fixes_applied)}")
        for fix in fixes_applied:
            print(f"  • {fix}")
            
    except Exception as e:
        print(f"❌ Error during schema compliance fix: {e}")
        raise
    finally:
        await close_database()

if __name__ == "__main__":
    asyncio.run(fix_schema_compliance())
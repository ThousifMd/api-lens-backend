#!/usr/bin/env python3
"""
Populate Location Data Script
Safely populates the new location-based timezone columns with data
"""
import asyncio
import sys
sys.path.append('.')

from app.services.location_timezone import populate_all_location_data, get_location_data_summary

async def main():
    """Populate location data for existing records"""
    
    print("🌍 POPULATING LOCATION-BASED TIMEZONE DATA")
    print("=" * 50)
    print("This will populate the new location columns with timezone data")
    print("based on existing IP addresses and country codes")
    print()
    
    try:
        # First, get summary of current state
        print("📊 CURRENT LOCATION DATA COVERAGE:")
        print("-" * 40)
        
        summary_before = await get_location_data_summary()
        for table, stats in summary_before.items():
            print(f"📋 {table}:")
            print(f"   Total records: {stats['total_records']}")
            print(f"   With location data: {stats['with_location_data']}")
            print(f"   Coverage: {stats['coverage_percentage']}%")
        
        print()
        print("🚀 Starting location data population...")
        print()
        
        # Populate all location data
        results = await populate_all_location_data()
        
        # Show results
        print("📈 POPULATION RESULTS:")
        print("-" * 30)
        
        for table, result in results.items():
            if table != 'summary':
                updated = result.get('updated', 0)
                errors = result.get('errors', 0)
                processed = result.get('processed', 0)
                
                if processed > 0:
                    success_rate = (updated / processed) * 100
                    print(f"📋 {table}:")
                    print(f"   Processed: {processed}")
                    print(f"   Updated: {updated}")
                    print(f"   Errors: {errors}")
                    print(f"   Success rate: {success_rate:.1f}%")
                else:
                    print(f"📋 {table}: Updated {updated} records")
        
        # Overall summary
        summary = results.get('summary', {})
        total_updated = summary.get('total_updated', 0)
        total_errors = summary.get('total_errors', 0)
        
        print()
        print("🎯 OVERALL SUMMARY:")
        print(f"   Total records updated: {total_updated}")
        print(f"   Total errors: {total_errors}")
        
        if total_updated > 0:
            print("   ✅ Location data population completed successfully!")
        else:
            print("   ℹ️  No records needed location data population")
        
        # Get final coverage
        print()
        print("📊 FINAL LOCATION DATA COVERAGE:")
        print("-" * 40)
        
        summary_after = await get_location_data_summary()
        for table, stats in summary_after.items():
            before_coverage = summary_before.get(table, {}).get('coverage_percentage', 0)
            after_coverage = stats['coverage_percentage']
            improvement = after_coverage - before_coverage
            
            print(f"📋 {table}:")
            print(f"   Total records: {stats['total_records']}")
            print(f"   With location data: {stats['with_location_data']}")
            print(f"   Coverage: {after_coverage}% (+{improvement:.1f}%)")
        
        print()
        print("🎉 LOCATION DATA POPULATION COMPLETED!")
        print()
        print("🔍 WHAT WAS ADDED:")
        print("   📍 detected_timezone - User's timezone (e.g., 'America/New_York')")
        print("   📍 detected_country_code - Country code from IP (e.g., 'US')")
        print("   📍 *_local_detected - All timestamps converted to user's local time")
        print()
        print("💡 USAGE EXAMPLES:")
        print("   • Show user activity in their local time")
        print("   • Generate reports by geographic region")
        print("   • Analyze usage patterns by timezone")
        print("   • Provide localized analytics dashboards")
        
        return 0
        
    except Exception as e:
        print(f"❌ Error populating location data: {e}")
        import traceback
        traceback.print_exc()
        return 1

if __name__ == "__main__":
    exit_code = asyncio.run(main())
    sys.exit(exit_code)
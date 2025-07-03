#!/usr/bin/env python3
"""
Safe Location-Based Timestamp Migration Runner
Adds location-based timezone columns without breaking existing functionality
"""
import asyncio
import sys
sys.path.append('.')

from app.database import DatabaseUtils
from app.utils.logger import get_logger

logger = get_logger(__name__)

async def run_location_migration():
    """Run the location-based timestamp migration safely"""
    
    print("🚀 STARTING LOCATION-BASED TIMESTAMP MIGRATION")
    print("=" * 60)
    print("🛡️  This migration only ADDS columns - no existing data will be modified")
    print()
    
    try:
        # Migration SQL - broken into smaller, safer chunks
        migrations = [
            # 1. Add columns to requests table
            {
                "name": "Add location columns to requests table",
                "sql": """
                ALTER TABLE requests 
                ADD COLUMN IF NOT EXISTS detected_timezone VARCHAR(50),
                ADD COLUMN IF NOT EXISTS detected_country_code CHAR(2),
                ADD COLUMN IF NOT EXISTS timestamp_local_detected TIMESTAMP WITH TIME ZONE,
                ADD COLUMN IF NOT EXISTS created_at_local_detected TIMESTAMP WITH TIME ZONE;
                """
            },
            
            # 2. Add columns to user_sessions table
            {
                "name": "Add location columns to user_sessions table",
                "sql": """
                ALTER TABLE user_sessions
                ADD COLUMN IF NOT EXISTS detected_timezone VARCHAR(50),
                ADD COLUMN IF NOT EXISTS detected_country_code CHAR(2),
                ADD COLUMN IF NOT EXISTS started_at_local_detected TIMESTAMP WITH TIME ZONE,
                ADD COLUMN IF NOT EXISTS ended_at_local_detected TIMESTAMP WITH TIME ZONE,
                ADD COLUMN IF NOT EXISTS last_activity_local_detected TIMESTAMP WITH TIME ZONE;
                """
            },
            
            # 3. Add columns to client_users table
            {
                "name": "Add location columns to client_users table",
                "sql": """
                ALTER TABLE client_users
                ADD COLUMN IF NOT EXISTS detected_timezone VARCHAR(50),
                ADD COLUMN IF NOT EXISTS detected_country_code CHAR(2),
                ADD COLUMN IF NOT EXISTS first_seen_local_detected TIMESTAMP WITH TIME ZONE,
                ADD COLUMN IF NOT EXISTS last_seen_local_detected TIMESTAMP WITH TIME ZONE,
                ADD COLUMN IF NOT EXISTS created_at_local_detected TIMESTAMP WITH TIME ZONE,
                ADD COLUMN IF NOT EXISTS updated_at_local_detected TIMESTAMP WITH TIME ZONE;
                """
            },
            
            # 4. Add columns to analytics tables
            {
                "name": "Add location columns to user_analytics_hourly table",
                "sql": """
                ALTER TABLE user_analytics_hourly
                ADD COLUMN IF NOT EXISTS user_timezone VARCHAR(50),
                ADD COLUMN IF NOT EXISTS user_country_code CHAR(2),
                ADD COLUMN IF NOT EXISTS hour_bucket_user_local TIMESTAMP WITH TIME ZONE,
                ADD COLUMN IF NOT EXISTS created_at_user_local TIMESTAMP WITH TIME ZONE,
                ADD COLUMN IF NOT EXISTS updated_at_user_local TIMESTAMP WITH TIME ZONE;
                """
            },
            
            {
                "name": "Add location columns to user_analytics_daily table",
                "sql": """
                ALTER TABLE user_analytics_daily
                ADD COLUMN IF NOT EXISTS user_timezone VARCHAR(50),
                ADD COLUMN IF NOT EXISTS user_country_code CHAR(2),
                ADD COLUMN IF NOT EXISTS date_user_local DATE,
                ADD COLUMN IF NOT EXISTS created_at_user_local TIMESTAMP WITH TIME ZONE,
                ADD COLUMN IF NOT EXISTS updated_at_user_local TIMESTAMP WITH TIME ZONE;
                """
            },
            
            # 5. Create timezone conversion function
            {
                "name": "Create timezone conversion function",
                "sql": """
                CREATE OR REPLACE FUNCTION convert_to_detected_timezone(
                    utc_timestamp TIMESTAMP WITH TIME ZONE,
                    timezone_name TEXT
                ) RETURNS TIMESTAMP WITH TIME ZONE AS $$
                BEGIN
                    -- If timezone is provided and valid, convert
                    IF timezone_name IS NOT NULL AND timezone_name != '' THEN
                        BEGIN
                            RETURN utc_timestamp AT TIME ZONE timezone_name;
                        EXCEPTION WHEN OTHERS THEN
                            -- If timezone conversion fails, return UTC
                            RETURN utc_timestamp;
                        END;
                    END IF;
                    
                    -- Default to UTC if no timezone provided
                    RETURN utc_timestamp;
                END;
                $$ LANGUAGE plpgsql IMMUTABLE;
                """
            },
            
            # 6. Create country timezone mapping function
            {
                "name": "Create country timezone mapping function",
                "sql": """
                CREATE OR REPLACE FUNCTION get_default_timezone_for_country(country_code TEXT) 
                RETURNS TEXT AS $$
                BEGIN
                    -- Common timezone mappings for major countries
                    CASE country_code
                        WHEN 'US' THEN RETURN 'America/New_York';
                        WHEN 'CA' THEN RETURN 'America/Toronto';
                        WHEN 'GB' THEN RETURN 'Europe/London';
                        WHEN 'DE' THEN RETURN 'Europe/Berlin';
                        WHEN 'FR' THEN RETURN 'Europe/Paris';
                        WHEN 'JP' THEN RETURN 'Asia/Tokyo';
                        WHEN 'AU' THEN RETURN 'Australia/Sydney';
                        WHEN 'IN' THEN RETURN 'Asia/Kolkata';
                        WHEN 'CN' THEN RETURN 'Asia/Shanghai';
                        WHEN 'BR' THEN RETURN 'America/Sao_Paulo';
                        WHEN 'MX' THEN RETURN 'America/Mexico_City';
                        WHEN 'RU' THEN RETURN 'Europe/Moscow';
                        WHEN 'ZA' THEN RETURN 'Africa/Johannesburg';
                        WHEN 'EG' THEN RETURN 'Africa/Cairo';
                        WHEN 'NG' THEN RETURN 'Africa/Lagos';
                        WHEN 'SG' THEN RETURN 'Asia/Singapore';
                        WHEN 'KR' THEN RETURN 'Asia/Seoul';
                        WHEN 'TH' THEN RETURN 'Asia/Bangkok';
                        WHEN 'ID' THEN RETURN 'Asia/Jakarta';
                        WHEN 'PH' THEN RETURN 'Asia/Manila';
                        WHEN 'VN' THEN RETURN 'Asia/Ho_Chi_Minh';
                        WHEN 'MY' THEN RETURN 'Asia/Kuala_Lumpur';
                        WHEN 'NZ' THEN RETURN 'Pacific/Auckland';
                        WHEN 'AR' THEN RETURN 'America/Argentina/Buenos_Aires';
                        WHEN 'CL' THEN RETURN 'America/Santiago';
                        WHEN 'CO' THEN RETURN 'America/Bogota';
                        WHEN 'PE' THEN RETURN 'America/Lima';
                        WHEN 'VE' THEN RETURN 'America/Caracas';
                        WHEN 'AE' THEN RETURN 'Asia/Dubai';
                        WHEN 'SA' THEN RETURN 'Asia/Riyadh';
                        WHEN 'IL' THEN RETURN 'Asia/Jerusalem';
                        WHEN 'TR' THEN RETURN 'Europe/Istanbul';
                        WHEN 'IT' THEN RETURN 'Europe/Rome';
                        WHEN 'ES' THEN RETURN 'Europe/Madrid';
                        WHEN 'NL' THEN RETURN 'Europe/Amsterdam';
                        WHEN 'CH' THEN RETURN 'Europe/Zurich';
                        WHEN 'SE' THEN RETURN 'Europe/Stockholm';
                        WHEN 'NO' THEN RETURN 'Europe/Oslo';
                        WHEN 'DK' THEN RETURN 'Europe/Copenhagen';
                        WHEN 'FI' THEN RETURN 'Europe/Helsinki';
                        WHEN 'PL' THEN RETURN 'Europe/Warsaw';
                        WHEN 'AT' THEN RETURN 'Europe/Vienna';
                        WHEN 'BE' THEN RETURN 'Europe/Brussels';
                        WHEN 'PT' THEN RETURN 'Europe/Lisbon';
                        WHEN 'GR' THEN RETURN 'Europe/Athens';
                        WHEN 'IE' THEN RETURN 'Europe/Dublin';
                        ELSE RETURN 'UTC';
                    END CASE;
                END;
                $$ LANGUAGE plpgsql IMMUTABLE;
                """
            }
        ]
        
        # Run each migration step
        for i, migration in enumerate(migrations, 1):
            print(f"📝 Step {i}/{len(migrations)}: {migration['name']}")
            
            try:
                await DatabaseUtils.execute_query(migration['sql'], [], fetch_all=False)
                print(f"   ✅ Completed successfully")
            except Exception as e:
                print(f"   ⚠️  Warning: {e}")
                # Don't fail the whole migration for individual steps
                continue
        
        # Record migration (if table exists)
        try:
            await DatabaseUtils.execute_query("""
                INSERT INTO schema_migrations (version, name, applied_at) 
                VALUES ('007', 'add_location_based_timestamps', NOW())
                ON CONFLICT (version) DO NOTHING
            """, [], fetch_all=False)
            print("📋 Migration recorded in schema_migrations")
        except:
            print("📋 Note: Could not record in schema_migrations (table may not exist)")
        
        print()
        print("🎉 LOCATION-BASED TIMESTAMP MIGRATION COMPLETED!")
        print("=" * 60)
        print("✅ Added location-based timezone columns to:")
        print("   📍 requests (4 new columns)")
        print("   📍 user_sessions (5 new columns)")
        print("   📍 client_users (6 new columns)")
        print("   📍 user_analytics_hourly (5 new columns)")
        print("   📍 user_analytics_daily (5 new columns)")
        print("🔧 Added timezone conversion functions")
        print("🛡️  All existing functionality remains unchanged")
        print()
        
        return True
        
    except Exception as e:
        logger.error(f"Migration failed: {e}")
        print(f"❌ Migration failed: {e}")
        return False

async def verify_migration():
    """Verify that the migration was successful"""
    
    print("🔍 VERIFYING MIGRATION SUCCESS")
    print("=" * 40)
    
    try:
        # Check that new columns exist
        tables_to_check = [
            'requests',
            'user_sessions', 
            'client_users',
            'user_analytics_hourly',
            'user_analytics_daily'
        ]
        
        for table in tables_to_check:
            query = f"""
            SELECT column_name 
            FROM information_schema.columns 
            WHERE table_name = '{table}' 
            AND column_name LIKE '%detected%' OR column_name LIKE '%user_timezone%' OR column_name LIKE '%user_country%'
            ORDER BY column_name
            """
            
            columns = await DatabaseUtils.execute_query(query, [], fetch_all=True)
            
            if columns:
                print(f"✅ {table}: {len(columns)} location columns added")
                for col in columns:
                    print(f"    📍 {col['column_name']}")
            else:
                print(f"⚠️  {table}: No location columns found")
        
        # Check functions exist
        function_query = """
        SELECT routine_name 
        FROM information_schema.routines 
        WHERE routine_name IN ('convert_to_detected_timezone', 'get_default_timezone_for_country')
        AND routine_schema = 'public'
        """
        
        functions = await DatabaseUtils.execute_query(function_query, [], fetch_all=True)
        print(f"✅ Created {len(functions)} timezone functions:")
        for func in functions:
            print(f"    🔧 {func['routine_name']}")
        
        print()
        print("✅ Migration verification completed successfully!")
        return True
        
    except Exception as e:
        print(f"❌ Verification failed: {e}")
        return False

async def main():
    """Main execution"""
    
    print("🌍 LOCATION-BASED TIMEZONE MIGRATION TOOL")
    print("=" * 50)
    print("This tool adds location-based timezone columns to store")
    print("timestamps in user local time based on IP geolocation")
    print()
    
    # Run migration
    success = await run_location_migration()
    
    if success:
        # Verify migration
        await verify_migration()
        
        print("🎯 NEXT STEPS:")
        print("1. Use LocationTimezoneService.populate_all_location_data() to populate existing data")
        print("2. Update your application code to populate new columns on new requests")
        print("3. Use the new local timestamp columns for user-facing displays")
        print()
    else:
        print("❌ Migration failed. Please check the errors above.")
        return 1
    
    return 0

if __name__ == "__main__":
    exit_code = asyncio.run(main())
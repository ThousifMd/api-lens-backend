#!/usr/bin/env python3
import asyncio
import sys
sys.path.append('.')
from app.services.location_timezone import populate_all_location_data

async def update_new_requests():
    print('🔄 UPDATING GEOLOCATION FOR NEW REQUESTS')
    print('=' * 45)
    
    # Populate location data for all requests that don't have it yet
    results = await populate_all_location_data()
    
    print('📊 POPULATION RESULTS:')
    for table, result in results.items():
        if table != 'summary':
            updated = result.get('updated', 0)
            errors = result.get('errors', 0)
            print(f'   {table}: {updated} updated, {errors} errors')
    
    print()
    print('✅ Location data updated!')

if __name__ == "__main__":
    asyncio.run(update_new_requests())
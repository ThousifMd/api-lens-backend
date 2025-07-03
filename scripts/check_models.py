#!/usr/bin/env python3
"""
Check current vendor models in database
"""
import asyncio
import sys
sys.path.insert(0, '/Users/thousifudayagiri/Desktop/api-lens-backend')

async def check_current_models():
    from app.database import init_database, close_database, DatabaseUtils
    
    try:
        await init_database()
        
        # Check current vendors
        vendors_query = '''
            SELECT id, name, display_name, description
            FROM vendors
            ORDER BY name
        '''
        vendors = await DatabaseUtils.execute_query(vendors_query, [], fetch_all=True)
        
        print('📋 Current Vendors:')
        for vendor in vendors:
            print(f'  - {vendor["name"]}: {vendor["display_name"]} ({vendor["id"]})')
        
        # Check current models
        models_query = '''
            SELECT v.name as vendor_name, vm.name as model_name, vm.display_name, vm.model_type, vm.is_active
            FROM vendor_models vm
            JOIN vendors v ON vm.vendor_id = v.id
            ORDER BY v.name, vm.name
        '''
        models = await DatabaseUtils.execute_query(models_query, [], fetch_all=True)
        
        print(f'\n📋 Current Models ({len(models)} total):')
        current_vendor = None
        for model in models:
            if model['vendor_name'] != current_vendor:
                current_vendor = model['vendor_name']
                print(f'\n  {current_vendor.upper()}:')
            status = '✅' if model['is_active'] else '❌'
            print(f'    {status} {model["model_name"]} ({model["model_type"]})')
        
    except Exception as e:
        print(f'❌ Error: {str(e)}')
    finally:
        await close_database()

if __name__ == "__main__":
    asyncio.run(check_current_models())
#!/usr/bin/env python3
"""Fix missing gpt-4o model in vendor_models table"""
import asyncio
from app.database import DatabaseUtils, init_database, close_database

async def main():
    await init_database()
    
    print("🔧 Fixing missing gpt-4o model...")
    print("=" * 50)
    
    # Check if gpt-4o model exists
    existing_model = await DatabaseUtils.execute_query("""
        SELECT vm.id, vm.name, v.name as vendor_name
        FROM vendor_models vm
        JOIN vendors v ON vm.vendor_id = v.id
        WHERE v.name = 'openai' AND vm.name = 'gpt-4o'
    """, fetch_all=True)
    
    if existing_model:
        print(f"✅ gpt-4o model already exists: {existing_model[0]['name']}")
        model_id = existing_model[0]['id']
    else:
        print("❌ gpt-4o model not found, creating it...")
        
        # Get OpenAI vendor ID
        vendor_result = await DatabaseUtils.execute_query("""
            SELECT id FROM vendors WHERE name = 'openai'
        """, fetch_all=True)
        
        if not vendor_result:
            print("❌ OpenAI vendor not found, creating it...")
            vendor_result = await DatabaseUtils.execute_query("""
                INSERT INTO vendors (name, display_name, description, website_url)
                VALUES ('openai', 'OpenAI', 'OpenAI API services', 'https://openai.com')
                RETURNING id
            """, fetch_all=True)
        
        vendor_id = vendor_result[0]['id']
        
        # Create gpt-4o model
        model_result = await DatabaseUtils.execute_query("""
            INSERT INTO vendor_models (
                vendor_id, name, display_name, description, model_type,
                context_window, max_output_tokens, supports_functions, supports_vision, is_active
            ) VALUES (
                $1, 'gpt-4o', 'GPT-4o', 'Most capable GPT-4 model', 'chat',
                128000, 4096, true, true, true
            ) RETURNING id
        """, [vendor_id], fetch_all=True)
        
        model_id = model_result[0]['id']
        print(f"✅ Created gpt-4o model with ID: {model_id}")
    
    # Check if pricing exists for gpt-4o
    pricing_result = await DatabaseUtils.execute_query("""
        SELECT id FROM vendor_pricing 
        WHERE model_id = $1 AND is_active = true
    """, [model_id], fetch_all=True)
    
    if not pricing_result:
        print("❌ No pricing found for gpt-4o, creating it...")
        
        # Create pricing for gpt-4o
        await DatabaseUtils.execute_query("""
            INSERT INTO vendor_pricing (
                vendor_id, model_id, input_cost_per_1k_tokens, output_cost_per_1k_tokens,
                currency, pricing_tier, effective_date, is_active
            ) VALUES (
                (SELECT vendor_id FROM vendor_models WHERE id = $1),
                $1, 0.0025, 0.01, 'USD', 'standard', NOW(), true
            )
        """, [model_id], fetch_all=False)
        
        print("✅ Created pricing for gpt-4o: $0.0025/1K input, $0.01/1K output")
    else:
        print("✅ Pricing already exists for gpt-4o")
    
    # Verify the fix
    verification = await DatabaseUtils.execute_query("""
        SELECT 
            vm.name as model_name,
            v.name as vendor_name,
            vm.model_type,
            vm.context_window,
            vm.max_output_tokens,
            vp.input_cost_per_1k_tokens,
            vp.output_cost_per_1k_tokens
        FROM vendor_models vm
        JOIN vendors v ON vm.vendor_id = v.id
        LEFT JOIN vendor_pricing vp ON vm.id = vp.model_id AND vp.is_active = true
        WHERE vm.name = 'gpt-4o'
    """, fetch_all=True)
    
    if verification:
        model_info = verification[0]
        print(f"\n✅ VERIFICATION SUCCESSFUL:")
        print(f"   Model: {model_info['model_name']}")
        print(f"   Vendor: {model_info['vendor_name']}")
        print(f"   Type: {model_info['model_type']}")
        print(f"   Context: {model_info['context_window']:,}")
        print(f"   Max Output: {model_info['max_output_tokens']:,}")
        print(f"   Input Cost: ${model_info['input_cost_per_1k_tokens']:.4f}/1K")
        print(f"   Output Cost: ${model_info['output_cost_per_1k_tokens']:.4f}/1K")
    else:
        print("❌ Verification failed - model not found")
    
    await close_database()

if __name__ == "__main__":
    asyncio.run(main()) 
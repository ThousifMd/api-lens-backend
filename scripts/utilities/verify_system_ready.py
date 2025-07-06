#!/usr/bin/env python3
"""
Verify the system is ready for fresh API calls
"""
import asyncio
from app.database import DatabaseUtils, init_database, close_database
from app.services.token_calculator import TokenCalculator

async def verify_ready():
    await init_database()
    
    print("🔍 SYSTEM READINESS CHECK")
    print("=" * 60)
    
    all_good = True
    
    # 1. Check requests table is empty
    print("\n1️⃣ Checking requests table...")
    count_result = await DatabaseUtils.execute_query(
        "SELECT COUNT(*) as count FROM requests",
        fetch_all=True
    )
    request_count = count_result[0]['count']
    
    if request_count == 0:
        print("   ✅ Requests table is empty and ready")
    else:
        print(f"   ❌ Requests table has {request_count} records")
        all_good = False
    
    # 2. Check required tables exist and have data
    print("\n2️⃣ Checking required tables...")
    required_tables = [
        ('companies', 'Companies', True),
        ('api_keys', 'API Keys', True),
        ('vendors', 'Vendors', True),
        ('vendor_models', 'Vendor Models', True),
        ('vendor_pricing', 'Vendor Pricing', True)
    ]
    
    for table, name, need_data in required_tables:
        try:
            result = await DatabaseUtils.execute_query(
                f"SELECT COUNT(*) as count FROM {table}",
                fetch_all=True
            )
            count = result[0]['count']
            
            if need_data and count == 0:
                print(f"   ❌ {name} table is empty (needs data)")
                all_good = False
            else:
                print(f"   ✅ {name} table ready ({count} records)")
        except Exception as e:
            print(f"   ❌ {name} table error: {str(e)}")
            all_good = False
    
    # 3. Test token calculator
    print("\n3️⃣ Testing token calculator...")
    try:
        # Test different models
        test_cases = [
            ("openai", "gpt-4", "/v1/chat/completions"),
            ("anthropic", "claude-3-opus-20240229", "/v1/messages"),
            ("openai", "dall-e-3", "/v1/images/generations")
        ]
        
        for vendor, model, endpoint in test_cases:
            input_tokens, output_tokens = TokenCalculator.calculate_tokens(
                vendor=vendor,
                model=model,
                endpoint=endpoint
            )
            print(f"   ✅ {vendor}/{model}: {input_tokens} input, {output_tokens} output tokens")
    except Exception as e:
        print(f"   ❌ Token calculator error: {str(e)}")
        all_good = False
    
    # 4. Check API endpoint
    print("\n4️⃣ API endpoint information:")
    print("   📍 Endpoint: POST /proxy/logs/optimized")
    print("   🔑 Requires: Authorization header with API key")
    print("   📊 Will populate: tokens, location, costs automatically")
    
    # 5. Sample API call format
    print("\n5️⃣ Sample API call:")
    print("-" * 60)
    print("""
curl -X POST http://localhost:8000/proxy/logs/optimized \\
  -H "Authorization: Bearer YOUR_API_KEY" \\
  -H "Content-Type: application/json" \\
  -d '{
    "requestId": "unique-request-id",
    "companyId": "company-uuid",
    "timestamp": 1704067200000,
    "method": "POST",
    "endpoint": "/v1/chat/completions",
    "vendor": "openai",
    "model": "gpt-4",
    "userId": "user-123",
    "userAgent": "Mozilla/5.0...",
    "inputTokens": 0,
    "outputTokens": 0,
    "totalLatency": 1500,
    "vendorLatency": 1200,
    "statusCode": 200,
    "success": true,
    "cost": 0.01
  }'
""")
    
    await close_database()
    
    print("\n" + "=" * 60)
    if all_good:
        print("✅ SYSTEM IS READY FOR FRESH API CALLS!")
        print("\nThe proxy endpoint will automatically:")
        print("  • Calculate varied tokens if not provided (or if 0)")
        print("  • Detect location from IP address")
        print("  • Use fallback location if detection fails")
        print("  • Calculate accurate costs based on token counts")
        print("  • Store timezone information")
    else:
        print("❌ SYSTEM NEEDS ATTENTION")
        print("\nPlease fix the issues above before making API calls.")
    print("=" * 60)

if __name__ == "__main__":
    asyncio.run(verify_ready())
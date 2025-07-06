#!/usr/bin/env python3
"""Test image generation service after fixing display_name issue"""
import asyncio
from app.database import init_database, close_database
from app.services.image_generation import ImageGenerationService
import uuid

async def main():
    await init_database()
    
    print("🎨 Testing Image Generation Service")
    print("=" * 60)
    
    # 1. Test getting supported models
    print("\n1️⃣ Getting supported image models...")
    supported = await ImageGenerationService.get_supported_models()
    
    if supported["status"] == "success":
        print(f"✅ Found {supported['data']['total_models']} image models")
        for provider, info in supported["data"]["providers"].items():
            print(f"\n  {provider}:")
            for model in info["models"]:
                print(f"    • {model['name']} (${model['cost_per_image']:.2f} per image)")
    else:
        print(f"❌ Error: {supported['error']}")
        
    # 2. Test image generation
    print("\n\n2️⃣ Testing image generation...")
    
    # Use a test company and user ID
    test_company_id = uuid.uuid4()
    test_user_id = uuid.uuid4()
    
    test_cases = [
        ("openai", "dall-e-3", "A futuristic city with flying cars"),
        ("stability-ai", "stable-diffusion-xl", "A serene mountain landscape"),
        ("openai", "dall-e-2", "A cute robot playing guitar")
    ]
    
    for vendor, model, prompt in test_cases:
        print(f"\n  Testing {vendor}/{model}...")
        result = await ImageGenerationService.generate_image(
            vendor=vendor,
            model=model,
            prompt=prompt,
            company_id=test_company_id,
            user_id=test_user_id,
            image_count=2,
            dimensions="1024x1024",
            quality="standard"
        )
        
        if result["status"] == "success":
            print(f"    ✅ Generated {result['image_count']} images")
            print(f"    💰 Cost: ${result['cost']['total_cost']:.4f}")
            print(f"    ⏱️  Time: {result['generation_time_ms']}ms")
        else:
            print(f"    ❌ Error: {result['error']}")
    
    await close_database()
    print("\n✅ Image generation service test complete!")

if __name__ == "__main__":
    asyncio.run(main())
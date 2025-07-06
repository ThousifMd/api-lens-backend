#!/usr/bin/env python3
"""
Comprehensive API Test Script
Tests multiple vendors, models, users, and companies
"""
import httpx
import json
import uuid
import random
from datetime import datetime
import asyncio
from typing import Dict, List

# API Configuration
API_URL = "http://127.0.0.1:8000"
API_ENDPOINT = "/proxy/logs/optimized"

# Test Data Configuration
COMPANIES = [
    {"id": "d74d5aa8-d092-4998-87eb-2b5ee447e710", "name": "TechCorp Inc", "api_key": "als_z2Ad8pQn0jrWqe2tvr6oxwfSpeGV3L14KEyCnVpSl7M"},
    {"id": "f77075d3-e0f3-46b2-aeec-da176e46e471", "name": "AI Startup", "api_key": "als_qS81gMDu-sqt48dZji2R9ZfMLIsCCzPp7QQL5Ty8_YY"},
    {"id": "284defe6-7386-4e8f-82dd-c3312c4d7ff1", "name": "Enterprise Co", "api_key": "als_q4MJ0dMoo73TxPciX91mhz1hcvAG8F0PEvBZ1B_V7oY"},
]

USERS = [
    {"id": str(uuid.uuid4()), "name": "John Developer"},
    {"id": str(uuid.uuid4()), "name": "Sarah Engineer"},
    {"id": str(uuid.uuid4()), "name": "Mike Designer"},
    {"id": str(uuid.uuid4()), "name": "Lisa Analyst"},
    {"id": str(uuid.uuid4()), "name": "Tom Manager"},
]

# Text Generation Scenarios
TEXT_SCENARIOS = [
    # OpenAI Models
    {"vendor": "openai", "model": "gpt-4", "endpoint": "/v1/chat/completions", "type": "chat"},
    {"vendor": "openai", "model": "gpt-4-turbo", "endpoint": "/v1/chat/completions", "type": "chat"},
    {"vendor": "openai", "model": "gpt-3.5-turbo", "endpoint": "/v1/chat/completions", "type": "chat"},
    {"vendor": "openai", "model": "gpt-3.5-turbo-16k", "endpoint": "/v1/chat/completions", "type": "chat"},
    
    # Anthropic Models
    {"vendor": "anthropic", "model": "claude-3-opus-20240229", "endpoint": "/v1/messages", "type": "messages"},
    {"vendor": "anthropic", "model": "claude-3-sonnet-20240229", "endpoint": "/v1/messages", "type": "messages"},
    {"vendor": "anthropic", "model": "claude-3-haiku-20240307", "endpoint": "/v1/messages", "type": "messages"},
    {"vendor": "anthropic", "model": "claude-2.1", "endpoint": "/v1/complete", "type": "completion"},
    
    # Google Models
    {"vendor": "google", "model": "gemini-pro", "endpoint": "/v1/models/gemini-pro:generateContent", "type": "generate"},
    {"vendor": "google", "model": "gemini-pro-vision", "endpoint": "/v1/models/gemini-pro-vision:generateContent", "type": "generate"},
    {"vendor": "google", "model": "palm-2", "endpoint": "/v1/models/text-bison-001:generateText", "type": "generate"},
]

# Image Generation Scenarios
IMAGE_SCENARIOS = [
    # OpenAI DALL-E
    {"vendor": "openai", "model": "dall-e-3", "endpoint": "/v1/images/generations", "type": "image"},
    {"vendor": "openai", "model": "dall-e-2", "endpoint": "/v1/images/generations", "type": "image"},
    
    # Stability AI
    {"vendor": "stability-ai", "model": "stable-diffusion-xl-1024-v1-0", "endpoint": "/v1/generation/stable-diffusion-xl-1024-v1-0/text-to-image", "type": "image"},
    {"vendor": "stability-ai", "model": "stable-diffusion-v1-6", "endpoint": "/v1/generation/stable-diffusion-v1-6/text-to-image", "type": "image"},
    
    # Adobe Firefly
    {"vendor": "adobe", "model": "firefly-v2", "endpoint": "/v1/images/generate", "type": "image"},
]

LOCATIONS = [
    {"country": "US", "region": "California", "city": "San Francisco", "ip": "192.168.1.100"},
    {"country": "US", "region": "New York", "city": "New York", "ip": "192.168.1.101"},
    {"country": "UK", "region": "England", "city": "London", "ip": "192.168.1.102"},
    {"country": "DE", "region": "Berlin", "city": "Berlin", "ip": "192.168.1.103"},
    {"country": "JP", "region": "Tokyo", "city": "Tokyo", "ip": "192.168.1.104"},
    {"country": "AU", "region": "NSW", "city": "Sydney", "ip": "192.168.1.105"},
    {"country": "CA", "region": "Ontario", "city": "Toronto", "ip": "192.168.1.106"},
    {"country": "FR", "region": "Île-de-France", "city": "Paris", "ip": "192.168.1.107"},
]

def generate_text_request(scenario: Dict, company: Dict, user: Dict, location: Dict) -> Dict:
    """Generate a text generation request"""
    input_tokens = random.randint(50, 500)
    output_tokens = random.randint(100, 1000)
    
    # Calculate cost based on rough estimates (per 1K tokens)
    cost_per_1k_input = {"gpt-4": 0.03, "gpt-3.5-turbo": 0.0015, "claude-3-opus": 0.015, "gemini-pro": 0.001}
    cost_per_1k_output = {"gpt-4": 0.06, "gpt-3.5-turbo": 0.002, "claude-3-sonnet": 0.03, "gemini-pro": 0.002}
    
    base_model = scenario['model'].split('-')[0] + '-' + scenario['model'].split('-')[1] if '-' in scenario['model'] else scenario['model']
    input_cost = (input_tokens / 1000) * cost_per_1k_input.get(base_model, 0.001)
    output_cost = (output_tokens / 1000) * cost_per_1k_output.get(base_model, 0.002)
    
    return {
        "requestId": str(uuid.uuid4()),
        "companyId": company["id"],
        "timestamp": int(datetime.now().timestamp() * 1000),
        "method": "POST",
        "endpoint": scenario["endpoint"],
        "url": f"https://api.{scenario['vendor']}.com{scenario['endpoint']}",
        "vendor": scenario["vendor"],
        "model": scenario["model"],
        "userId": user["id"],
        "userAgent": "API-Lens-Test/1.0",
        "country": location["country"],
        "region": location["region"],
        "ipAddress": location["ip"],
        "inputTokens": input_tokens,
        "outputTokens": output_tokens,
        "totalLatency": random.randint(500, 3000),
        "vendorLatency": random.randint(400, 2800),
        "statusCode": 200 if random.random() > 0.1 else random.choice([400, 429, 500]),
        "success": random.random() > 0.1,
        "errorMessage": None if random.random() > 0.1 else "Rate limit exceeded",
        "errorCode": None if random.random() > 0.1 else "rate_limit_error",
        "cost": round(input_cost + output_cost, 6)
    }

def generate_image_request(scenario: Dict, company: Dict, user: Dict, location: Dict) -> Dict:
    """Generate an image generation request"""
    image_count = random.choice([1, 2, 4])
    dimensions = random.choice(["1024x1024", "512x512", "768x768", "1024x768"])
    
    # Calculate cost based on image size and count
    cost_per_image = {
        "dall-e-3": {"1024x1024": 0.04, "1024x768": 0.04},
        "dall-e-2": {"1024x1024": 0.02, "512x512": 0.018},
        "stable-diffusion": {"1024x1024": 0.01, "512x512": 0.005},
        "firefly": {"1024x1024": 0.03, "512x512": 0.02}
    }
    
    model_family = "stable-diffusion" if "stable-diffusion" in scenario['model'] else scenario['model'].split('-')[0]
    base_cost = cost_per_image.get(model_family, {}).get(dimensions, 0.02)
    total_cost = base_cost * image_count
    
    return {
        "requestId": str(uuid.uuid4()),
        "companyId": company["id"],
        "timestamp": int(datetime.now().timestamp() * 1000),
        "method": "POST",
        "endpoint": scenario["endpoint"],
        "url": f"https://api.{scenario['vendor']}.com{scenario['endpoint']}",
        "vendor": scenario["vendor"],
        "model": scenario["model"],
        "userId": user["id"],
        "userAgent": "API-Lens-Test/1.0",
        "country": location["country"],
        "region": location["region"],
        "ipAddress": location["ip"],
        "inputTokens": 0,  # Images don't use tokens
        "outputTokens": 0,
        "totalLatency": random.randint(2000, 10000),  # Image generation is slower
        "vendorLatency": random.randint(1800, 9500),
        "statusCode": 200 if random.random() > 0.05 else random.choice([400, 429, 500]),
        "success": random.random() > 0.05,
        "errorMessage": None if random.random() > 0.05 else "Invalid image parameters",
        "errorCode": None if random.random() > 0.05 else "invalid_request",
        "cost": round(total_cost, 6),
        # Image-specific fields (these would be added in a real implementation)
        "imageCount": image_count,
        "imageDimensions": dimensions,
        "imageQuality": random.choice(["standard", "hd"]),
        "imageStyle": random.choice(["vivid", "natural"]) if scenario["vendor"] == "openai" else None
    }

async def send_request(client: httpx.AsyncClient, request_data: Dict, api_key: str) -> Dict:
    """Send a single request to the API"""
    headers = {
        "Authorization": f"Bearer {api_key}",
        "Content-Type": "application/json"
    }
    
    try:
        response = await client.post(
            f"{API_URL}{API_ENDPOINT}",
            json=request_data,
            headers=headers,
            timeout=10.0
        )
        
        return {
            "status": response.status_code,
            "success": response.status_code in [200, 201],
            "data": response.json() if response.status_code in [200, 201] else None,
            "error": response.text if response.status_code not in [200, 201] else None
        }
    except Exception as e:
        return {
            "status": 0,
            "success": False,
            "data": None,
            "error": str(e)
        }

async def run_comprehensive_test():
    """Run comprehensive tests"""
    print("=" * 80)
    print("🚀 COMPREHENSIVE API LENS TEST")
    print("=" * 80)
    
    total_requests = 0
    successful_requests = 0
    failed_requests = 0
    
    async with httpx.AsyncClient() as client:
        # Test 1: Text Generation Requests
        print("\n📝 Testing Text Generation APIs...")
        print("-" * 50)
        
        for _ in range(20):  # Generate 20 text requests
            company = random.choice(COMPANIES)
            user = random.choice(USERS)
            location = random.choice(LOCATIONS)
            scenario = random.choice(TEXT_SCENARIOS)
            
            request_data = generate_text_request(scenario, company, user, location)
            
            print(f"\n→ {company['name']} | {user['name']} | {scenario['vendor']}/{scenario['model']}")
            print(f"  Location: {location['city']}, {location['country']}")
            print(f"  Tokens: {request_data['inputTokens']} in, {request_data['outputTokens']} out")
            print(f"  Cost: ${request_data['cost']:.4f}")
            
            result = await send_request(client, request_data, company['api_key'])
            total_requests += 1
            
            if result['success']:
                successful_requests += 1
                print(f"  ✅ Success: {result['data'].get('message', 'Logged successfully')}")
            else:
                failed_requests += 1
                print(f"  ❌ Failed: {result['error']}")
        
        # Test 2: Image Generation Requests
        print("\n\n🖼️  Testing Image Generation APIs...")
        print("-" * 50)
        
        for _ in range(15):  # Generate 15 image requests
            company = random.choice(COMPANIES)
            user = random.choice(USERS)
            location = random.choice(LOCATIONS)
            scenario = random.choice(IMAGE_SCENARIOS)
            
            request_data = generate_image_request(scenario, company, user, location)
            
            print(f"\n→ {company['name']} | {user['name']} | {scenario['vendor']}/{scenario['model']}")
            print(f"  Location: {location['city']}, {location['country']}")
            print(f"  Images: {request_data.get('imageCount', 1)} @ {request_data.get('imageDimensions', 'unknown')}")
            print(f"  Cost: ${request_data['cost']:.4f}")
            
            result = await send_request(client, request_data, company['api_key'])
            total_requests += 1
            
            if result['success']:
                successful_requests += 1
                print(f"  ✅ Success: {result['data'].get('message', 'Logged successfully')}")
            else:
                failed_requests += 1
                print(f"  ❌ Failed: {result['error']}")
        
        # Test 3: Error Scenarios
        print("\n\n⚠️  Testing Error Scenarios...")
        print("-" * 50)
        
        # Invalid API key
        print("\n→ Testing invalid API key...")
        request_data = generate_text_request(TEXT_SCENARIOS[0], COMPANIES[0], USERS[0], LOCATIONS[0])
        result = await send_request(client, request_data, "invalid_key_12345")
        total_requests += 1
        if not result['success']:
            print(f"  ✅ Correctly rejected: {result['error']}")
            successful_requests += 1
        else:
            print(f"  ❌ Should have failed but didn't")
            failed_requests += 1
    
    # Summary
    print("\n" + "=" * 80)
    print("📊 TEST SUMMARY")
    print("=" * 80)
    print(f"Total Requests: {total_requests}")
    print(f"Successful: {successful_requests} ({successful_requests/total_requests*100:.1f}%)")
    print(f"Failed: {failed_requests} ({failed_requests/total_requests*100:.1f}%)")
    print("\n✅ Test completed! Check your database for logged requests.")

if __name__ == "__main__":
    print("Starting comprehensive API test...")
    print(f"API URL: {API_URL}")
    print("\nMake sure your FastAPI server is running!")
    print("Press Ctrl+C to cancel, or wait 3 seconds to continue...")
    
    try:
        import time
        time.sleep(3)
    except KeyboardInterrupt:
        print("\nTest cancelled.")
        exit(0)
    
    asyncio.run(run_comprehensive_test())
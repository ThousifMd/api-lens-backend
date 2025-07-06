#!/usr/bin/env python3
"""Test a single API call"""
import requests
import json
import time
import uuid

# First, let's use the admin API key from env
API_URL = "http://localhost:8000/proxy/logs/optimized"

# Create test payload
payload = {
    "requestId": f"test_{uuid.uuid4().hex[:8]}",
    "companyId": "d74d5aa8-d092-4998-87eb-2b5ee447e710",  # TechCorp Inc
    "timestamp": int(time.time() * 1000),
    "method": "POST",
    "endpoint": "/v1/chat/completions",
    "url": "https://api.openai.com/v1/chat/completions",
    "vendor": "openai",
    "model": "gpt-4",
    "userId": "test_user_123",
    "userAgent": "Mozilla/5.0 Test",
    "ipAddress": "8.8.8.8",
    "inputTokens": 0,
    "outputTokens": 0,
    "totalLatency": 1500,
    "vendorLatency": 1200,
    "statusCode": 200,
    "success": True,
    "cost": 0
}

# Try without auth first (for testing)
print("Testing API call...")
print(f"Payload: {json.dumps(payload, indent=2)}")
print("\n" + "-" * 60 + "\n")

# Make request without auth header
response = requests.post(
    API_URL,
    json=payload,
    headers={
        "Content-Type": "application/json",
        "X-Forwarded-For": "8.8.8.8",
        "User-Agent": "Test Script"
    }
)

print(f"Status Code: {response.status_code}")
print(f"Response: {response.text}")

if response.status_code == 401:
    print("\n⚠️  API requires authentication. Let's try with admin key...")
    
    # Try with admin key from env
    import os
    admin_key = os.getenv("ADMIN_API_KEY", "supersecretadmin123")
    
    response2 = requests.post(
        API_URL,
        json=payload,
        headers={
            "Content-Type": "application/json",
            "X-Forwarded-For": "8.8.8.8",
            "User-Agent": "Test Script",
            "Authorization": f"Bearer {admin_key}"
        }
    )
    
    print(f"\nWith admin key - Status Code: {response2.status_code}")
    print(f"Response: {response2.text}")
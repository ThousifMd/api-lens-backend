# Getting Started with API Lens

This guide will help you get up and running with API Lens in just a few minutes.

## Prerequisites

- An API Lens account and API key
- Basic knowledge of REST APIs
- Access to AI services (OpenAI, Anthropic, etc.) - optional for BYOK

## Step 1: Get Your API Key

Contact your API Lens administrator to obtain your API key. Your key will look like:
```
als_abc123def456ghi789jkl012mno345pqr678stu901vwx234yz
```

⚠️ **Keep your API key secure!** Never expose it in client-side code or public repositories.

## Step 2: Verify Your API Key

Test your API key with a simple authentication check:

```bash
curl -X GET \
  -H "Authorization: Bearer als_your_api_key_here" \
  https://api.apilens.dev/auth/verify
```

Expected response:
```json
{
  "valid": true,
  "company_id": "123e4567-e89b-12d3-a456-426614174000",
  "company_name": "Your Company",
  "tier": "premium",
  "expires_at": null
}
```

## Step 3: Get Your Company Information

Retrieve your company profile and current usage:

```bash
curl -X GET \
  -H "Authorization: Bearer als_your_api_key_here" \
  https://api.apilens.dev/companies/me
```

This will show your company details, current usage, and available quotas.

## Step 4: Make Your First Proxied Request

### Option A: Using System Keys (Recommended for Getting Started)

Make an OpenAI chat completion request through API Lens:

```bash
curl -X POST \
  -H "Authorization: Bearer als_your_api_key_here" \
  -H "Content-Type: application/json" \
  https://api.apilens.dev/proxy/openai/chat/completions \
  -d '{
    "model": "gpt-3.5-turbo",
    "messages": [
      {"role": "user", "content": "Hello, API Lens!"}
    ],
    "max_tokens": 50
  }'
```

### Option B: Using Your Own Keys (BYOK)

First, store your OpenAI API key:

```bash
curl -X POST \
  -H "Authorization: Bearer als_your_api_key_here" \
  -H "Content-Type: application/json" \
  https://api.apilens.dev/companies/me/vendor-keys \
  -d '{
    "vendor": "openai",
    "api_key": "sk-your-openai-key-here",
    "description": "Primary OpenAI key"
  }'
```

Then make the same request as above - API Lens will automatically use your stored key.

## Step 5: Monitor Your Usage

Check your usage and costs:

```bash
curl -X GET \
  -H "Authorization: Bearer als_your_api_key_here" \
  https://api.apilens.dev/companies/me/analytics/usage?period=7d
```

## Environment Setup

### Environment Variables

Create a `.env` file for your application:

```bash
API_LENS_BASE_URL=https://api.apilens.dev
API_LENS_API_KEY=als_your_api_key_here
```

### Python Example

```python
import os
import requests

# Configuration
API_BASE = os.getenv('API_LENS_BASE_URL', 'https://api.apilens.dev')
API_KEY = os.getenv('API_LENS_API_KEY')

headers = {
    'Authorization': f'Bearer {API_KEY}',
    'Content-Type': 'application/json'
}

# Make a request
response = requests.post(
    f'{API_BASE}/proxy/openai/chat/completions',
    headers=headers,
    json={
        'model': 'gpt-3.5-turbo',
        'messages': [{'role': 'user', 'content': 'Hello!'}],
        'max_tokens': 50
    }
)

print(response.json())
```

### Node.js Example

```javascript
const axios = require('axios');

const apiBase = process.env.API_LENS_BASE_URL || 'https://api.apilens.dev';
const apiKey = process.env.API_LENS_API_KEY;

const headers = {
    'Authorization': `Bearer ${apiKey}`,
    'Content-Type': 'application/json'
};

async function makeRequest() {
    try {
        const response = await axios.post(
            `${apiBase}/proxy/openai/chat/completions`,
            {
                model: 'gpt-3.5-turbo',
                messages: [{ role: 'user', content: 'Hello!' }],
                max_tokens: 50
            },
            { headers }
        );
        
        console.log(response.data);
    } catch (error) {
        console.error('Error:', error.response?.data || error.message);
    }
}

makeRequest();
```

## Common Use Cases

### 1. Cost Tracking for OpenAI
Replace your OpenAI base URL with API Lens:

**Before:**
```
https://api.openai.com/v1/chat/completions
```

**After:**
```
https://api.apilens.dev/proxy/openai/chat/completions
```

### 2. Multi-Vendor AI
Use different vendors with the same interface:

```python
# OpenAI request
response = requests.post(f'{API_BASE}/proxy/openai/chat/completions', ...)

# Anthropic request  
response = requests.post(f'{API_BASE}/proxy/anthropic/messages', ...)

# Google request
response = requests.post(f'{API_BASE}/proxy/google/generateContent', ...)
```

### 3. Usage Analytics
Track your AI spending:

```python
# Get cost breakdown by vendor
response = requests.get(f'{API_BASE}/companies/me/analytics/costs?period=30d')
cost_data = response.json()

print(f"Total cost: ${cost_data['total_cost']}")
for vendor in cost_data['vendor_costs']:
    print(f"{vendor['vendor']}: ${vendor['total_cost']}")
```

## Next Steps

1. **Read the [Authentication Guide](authentication.md)** - Learn about API key security
2. **Explore [Integration Guides](integrations/)** - Vendor-specific setup instructions  
3. **Set up [Analytics](analytics/)** - Monitor costs and optimize usage
4. **Try the [Python SDK](sdks/python/)** - Use our official client library

## Troubleshooting

### Common Issues

**401 Unauthorized**
- Check that your API key is correct and properly formatted
- Ensure you're including the `Bearer ` prefix in the Authorization header

**429 Rate Limited**
- You've exceeded your rate limit - check your tier limits
- Implement exponential backoff in your retry logic

**400 Bad Request**
- Check the request format matches the vendor's API specification
- Ensure all required fields are included

**500 Internal Server Error**
- This indicates a server-side issue - contact support if persistent

### Getting Help

- Check the [API Reference](api-reference.md) for detailed endpoint documentation
- Review [common examples](examples/) for your use case
- Contact your administrator for account-specific issues
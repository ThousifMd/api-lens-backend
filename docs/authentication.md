# Authentication Guide

API Lens uses API key authentication to secure access to your company's data and AI resources.

## API Key Format

API Lens API keys follow this format:
```
als_[43 random characters]
```

Example: `als_abc123def456ghi789jkl012mno345pqr678stu901vwx234yz`

## Authentication Methods

### Bearer Token (Recommended)

Include your API key in the `Authorization` header:

```bash
curl -H "Authorization: Bearer als_your_api_key_here" \
     https://api.apilens.dev/companies/me
```

### Header Authentication (Alternative)

You can also use a custom header:

```bash
curl -H "X-API-Key: als_your_api_key_here" \
     https://api.apilens.dev/companies/me
```

## Security Best Practices

### 1. Keep Keys Secure

✅ **DO:**
- Store API keys in environment variables
- Use secure key management systems in production
- Rotate keys regularly
- Limit key permissions to necessary scopes

❌ **DON'T:**
- Hardcode keys in source code
- Commit keys to version control
- Share keys via email or chat
- Use the same key across multiple environments

### 2. Environment Variables

Set up your API key as an environment variable:

```bash
# Linux/macOS
export API_LENS_API_KEY="als_your_api_key_here"

# Windows
set API_LENS_API_KEY=als_your_api_key_here

# .env file
API_LENS_API_KEY=als_your_api_key_here
```

### 3. Application Configuration

#### Python
```python
import os
from dotenv import load_dotenv

load_dotenv()  # Load .env file

API_KEY = os.getenv('API_LENS_API_KEY')
if not API_KEY:
    raise ValueError("API_LENS_API_KEY environment variable not set")

headers = {'Authorization': f'Bearer {API_KEY}'}
```

#### Node.js
```javascript
require('dotenv').config();

const apiKey = process.env.API_LENS_API_KEY;
if (!apiKey) {
    throw new Error('API_LENS_API_KEY environment variable not set');
}

const headers = { 'Authorization': `Bearer ${apiKey}` };
```

#### Go
```go
package main

import (
    "os"
    "fmt"
)

func main() {
    apiKey := os.Getenv("API_LENS_API_KEY")
    if apiKey == "" {
        panic("API_LENS_API_KEY environment variable not set")
    }
    
    headers := map[string]string{
        "Authorization": fmt.Sprintf("Bearer %s", apiKey),
    }
}
```

## API Key Management

### Creating API Keys

API keys are created by administrators through the admin interface:

```bash
curl -X POST \
  -H "Authorization: Bearer admin_token_here" \
  -H "Content-Type: application/json" \
  https://api.apilens.dev/admin/companies/123/api-keys \
  -d '{
    "name": "Production API Key",
    "description": "Main production key for web application"
  }'
```

### Listing Your API Keys

View all API keys for your company:

```bash
curl -H "Authorization: Bearer als_your_api_key_here" \
     https://api.apilens.dev/companies/me/api-keys
```

Response:
```json
[
  {
    "id": "key_123456",
    "name": "Production Key",
    "is_active": true,
    "created_at": "2024-01-01T00:00:00Z",
    "last_used_at": "2024-01-15T14:30:00Z"
  },
  {
    "id": "key_789012",
    "name": "Development Key", 
    "is_active": true,
    "created_at": "2024-01-10T09:15:00Z",
    "last_used_at": "2024-01-15T16:45:00Z"
  }
]
```

### Revoking API Keys

Revoke a compromised or unused API key:

```bash
curl -X DELETE \
  -H "Authorization: Bearer als_your_api_key_here" \
  https://api.apilens.dev/companies/me/api-keys/key_123456
```

⚠️ **Warning:** Revoked keys cannot be restored. Update all applications using the revoked key.

## Authentication Verification

### Verify API Key

Test if your API key is valid:

```bash
curl -X GET \
  -H "Authorization: Bearer als_your_api_key_here" \
  https://api.apilens.dev/auth/verify
```

Success response:
```json
{
  "valid": true,
  "company_id": "123e4567-e89b-12d3-a456-426614174000",
  "company_name": "Acme Corporation",
  "tier": "premium",
  "rate_limits": {
    "requests_per_minute": 2000,
    "requests_per_hour": 50000,
    "requests_per_day": 500000
  },
  "expires_at": null
}
```

Error response:
```json
{
  "valid": false,
  "error": "Invalid API key",
  "error_code": "INVALID_KEY"
}
```

### Check Permissions

Verify what endpoints you can access:

```bash
curl -X GET \
  -H "Authorization: Bearer als_your_api_key_here" \
  https://api.apilens.dev/auth/permissions
```

## Error Handling

### Common Authentication Errors

#### 401 Unauthorized

**Missing Authorization Header:**
```json
{
  "detail": "Missing or invalid authorization header"
}
```

**Invalid API Key:**
```json
{
  "detail": "Invalid or revoked API key"
}
```

**Expired API Key:**
```json
{
  "detail": "API key has expired"
}
```

#### 403 Forbidden

**Insufficient Permissions:**
```json
{
  "detail": "Insufficient permissions for this operation"
}
```

**Suspended Account:**
```json
{
  "detail": "Company account is suspended"
}
```

### Retry Logic

Implement retry logic for authentication failures:

```python
import time
import requests
from requests.adapters import HTTPAdapter
from urllib3.util.retry import Retry

def create_session_with_retries():
    session = requests.Session()
    
    retry_strategy = Retry(
        total=3,
        status_forcelist=[429, 500, 502, 503, 504],
        method_whitelist=["HEAD", "GET", "POST", "PUT", "DELETE"],
        backoff_factor=1
    )
    
    adapter = HTTPAdapter(max_retries=retry_strategy)
    session.mount("http://", adapter)
    session.mount("https://", adapter)
    
    return session

def make_authenticated_request(url, api_key, **kwargs):
    session = create_session_with_retries()
    headers = kwargs.get('headers', {})
    headers['Authorization'] = f'Bearer {api_key}'
    kwargs['headers'] = headers
    
    try:
        response = session.request(**kwargs)
        response.raise_for_status()
        return response
    except requests.exceptions.HTTPError as e:
        if e.response.status_code == 401:
            print("Authentication failed - check your API key")
        elif e.response.status_code == 403:
            print("Access denied - insufficient permissions")
        raise
```

## Admin Authentication

Administrative endpoints require special admin tokens. These are separate from regular API keys and have elevated privileges.

### Admin Token Usage

```bash
curl -X GET \
  -H "Authorization: Bearer admin_your_admin_token_here" \
  https://api.apilens.dev/admin/companies
```

### Admin Permissions

Admin tokens can:
- Create and manage companies
- View system-wide analytics
- Manage vendor pricing
- Configure system settings
- Access admin health endpoints

Regular API keys cannot access admin endpoints.

## Rate Limiting

Authentication is subject to rate limiting:

- **Auth endpoint**: 100 requests per minute per IP
- **Key creation**: 10 requests per hour per company
- **Key revocation**: 50 requests per hour per company

Rate limit headers are included in responses:
```
X-RateLimit-Limit: 100
X-RateLimit-Remaining: 95
X-RateLimit-Reset: 1640995200
```

## Security Considerations

### Network Security

- Always use HTTPS in production
- Consider IP whitelisting for sensitive operations
- Use API gateways or proxies for additional security layers

### Key Rotation

Implement regular key rotation:

1. Generate a new API key
2. Update all applications to use the new key
3. Test thoroughly in staging
4. Deploy to production
5. Revoke the old key after verification

### Monitoring

Monitor API key usage:

```bash
# Check recent activity
curl -H "Authorization: Bearer als_your_api_key_here" \
     https://api.apilens.dev/companies/me/analytics/usage?period=1d

# Set up alerts for unusual patterns
curl -H "Authorization: Bearer als_your_api_key_here" \
     https://api.apilens.dev/companies/me/alerts
```

## Next Steps

- Learn about [Rate Limits & Quotas](rate-limits.md)
- Explore [Integration Guides](integrations/) for your AI provider
- Set up [Monitoring & Analytics](analytics/) for your usage
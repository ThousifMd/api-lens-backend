# API Lens - API Documentation

## Quick Start

**Base URL**: `https://your-api-gateway-url.com`  
**Authentication**: Bearer token (API Key)

## Making API Calls

### Endpoint
```
POST /v1/chat/completions
```

### Headers
```
Authorization: Bearer YOUR_API_KEY
Content-Type: application/json
```

### Request Format
```json
{
  "model": "gpt-4",
  "messages": [
    {
      "role": "user", 
      "content": "Your prompt here"
    }
  ],
  "max_tokens": 100
}
```

## Supported Models

### OpenAI
- `gpt-4` - Most capable model
- `gpt-4o` - Optimized for chat
- `gpt-3.5-turbo` - Fast and cost-effective

### Anthropic
- `claude-3-opus` - Most capable Claude model
- `claude-3-sonnet` - Balanced performance
- `claude-3-haiku` - Fast responses

### Google
- `gemini-1.5-pro` - Advanced reasoning
- `gemini-1.5-flash` - Fast responses
- `gemini-1.0-pro` - Stable version

## Examples

### Basic Chat Completion
```bash
curl -X POST https://your-api-gateway-url.com/v1/chat/completions \
  -H "Authorization: Bearer YOUR_API_KEY" \
  -H "Content-Type: application/json" \
  -d '{
    "model": "gpt-4",
    "messages": [
      {
        "role": "user",
        "content": "Explain quantum computing in simple terms"
      }
    ],
    "max_tokens": 150
  }'
```

### Using Different Models
```bash
# Using Claude
curl -X POST https://your-api-gateway-url.com/v1/chat/completions \
  -H "Authorization: Bearer YOUR_API_KEY" \
  -H "Content-Type: application/json" \
  -d '{
    "model": "claude-3-sonnet",
    "messages": [
      {
        "role": "user",
        "content": "Write a haiku about programming"
      }
    ]
  }'

# Using Gemini
curl -X POST https://your-api-gateway-url.com/v1/chat/completions \
  -H "Authorization: Bearer YOUR_API_KEY" \
  -H "Content-Type: application/json" \
  -d '{
    "model": "gemini-1.5-flash",
    "messages": [
      {
        "role": "user",
        "content": "What is 2+2?"
      }
    ]
  }'
```

### Conversation with Context
```bash
curl -X POST https://your-api-gateway-url.com/v1/chat/completions \
  -H "Authorization: Bearer YOUR_API_KEY" \
  -H "Content-Type: application/json" \
  -d '{
    "model": "gpt-4",
    "messages": [
      {
        "role": "system",
        "content": "You are a helpful assistant that speaks like a pirate"
      },
      {
        "role": "user",
        "content": "How do I bake a cake?"
      }
    ],
    "max_tokens": 200
  }'
```

## Response Format

### Success Response
```json
{
  "id": "chatcmpl-abc123",
  "object": "chat.completion",
  "created": 1234567890,
  "model": "gpt-4",
  "choices": [
    {
      "index": 0,
      "message": {
        "role": "assistant",
        "content": "The response from the AI model"
      },
      "finish_reason": "stop"
    }
  ],
  "usage": {
    "prompt_tokens": 10,
    "completion_tokens": 20,
    "total_tokens": 30
  }
}
```

### Error Response
```json
{
  "error": {
    "message": "Invalid API key",
    "type": "authentication_error",
    "code": 401
  }
}
```

## Error Codes

| Code | Description |
|------|-------------|
| 401  | Invalid or missing API key |
| 429  | Rate limit exceeded |
| 500  | Internal server error |
| 503  | Model temporarily unavailable |

## Rate Limits

- **Requests**: 100 per minute
- **Tokens**: 100,000 per hour

## Code Examples

### Python
```python
import requests

url = "https://your-api-gateway-url.com/v1/chat/completions"
headers = {
    "Authorization": "Bearer YOUR_API_KEY",
    "Content-Type": "application/json"
}
data = {
    "model": "gpt-4",
    "messages": [{"role": "user", "content": "Hello!"}],
    "max_tokens": 50
}

response = requests.post(url, json=data, headers=headers)
print(response.json())
```

### JavaScript
```javascript
const response = await fetch('https://your-api-gateway-url.com/v1/chat/completions', {
  method: 'POST',
  headers: {
    'Authorization': 'Bearer YOUR_API_KEY',
    'Content-Type': 'application/json'
  },
  body: JSON.stringify({
    model: 'gpt-4',
    messages: [{role: 'user', content: 'Hello!'}],
    max_tokens: 50
  })
});

const data = await response.json();
console.log(data);
```

### Node.js
```javascript
const axios = require('axios');

const response = await axios.post(
  'https://your-api-gateway-url.com/v1/chat/completions',
  {
    model: 'gpt-4',
    messages: [{role: 'user', content: 'Hello!'}],
    max_tokens: 50
  },
  {
    headers: {
      'Authorization': 'Bearer YOUR_API_KEY',
      'Content-Type': 'application/json'
    }
  }
);

console.log(response.data);
```

## Best Practices

1. **Always include max_tokens** to control response length and costs
2. **Use appropriate models** - Don't use GPT-4 for simple tasks
3. **Handle errors gracefully** - Implement retry logic for 503 errors
4. **Cache responses** when appropriate to reduce costs
5. **Monitor your usage** to avoid unexpected charges

## Support

For issues or questions:
- Email: support@apilens.com
- Response time: Within 24 hours

## Getting Started Checklist

- [ ] Receive your API key
- [ ] Test with a simple curl command
- [ ] Implement error handling
- [ ] Monitor your usage
- [ ] Scale as needed
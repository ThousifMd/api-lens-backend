# API Lens Workers Proxy

A high-performance Cloudflare Workers proxy for AI API requests with built-in cost tracking, rate limiting, and analytics.

## Features

- 🚀 **Edge Performance**: Deploy globally on Cloudflare's edge network
- 🔒 **Authentication**: Secure API key validation and company isolation
- ⚡ **Rate Limiting**: Distributed rate limiting with KV and Durable Objects
- 💰 **Cost Tracking**: Real-time cost calculation for AI API usage
- 📊 **Analytics**: Built-in logging to Analytics Engine and backend API
- 🔄 **Multi-Vendor**: Support for OpenAI, Anthropic, Google AI, and more
- 🛡️ **Security**: Request validation, CORS protection, and error handling

## Architecture

```
┌─────────────┐    ┌──────────────────┐    ┌─────────────────┐
│   Client    │───▶│  Workers Proxy   │───▶│   AI Vendor     │
│             │    │                  │    │  (OpenAI, etc)  │
└─────────────┘    └──────────────────┘    └─────────────────┘
                            │
                            ▼
                   ┌──────────────────┐
                   │  API Lens        │
                   │  Backend         │
                   └──────────────────┘
```

## Project Structure

```
workers-proxy/
├── src/
│   ├── index.ts          # Main Worker entry point
│   ├── auth.ts           # Authentication logic
│   ├── ratelimit.ts      # Rate limiting with KV/DO
│   ├── vendor.ts         # Vendor routing integration
│   ├── cost.ts           # Cost calculation engine
│   ├── logger.ts         # Async logging to backend
│   ├── validation.ts     # Request validation
│   └── error-handler.ts  # Centralized error handling
├── wrangler.toml         # Workers configuration
├── package.json          # Dependencies and scripts
├── tsconfig.json         # TypeScript configuration
└── README.md            # This file
```

## Quick Start

### Prerequisites

- Node.js 18+ 
- Cloudflare account
- Wrangler CLI installed: `npm install -g wrangler`

### Installation

1. **Clone and install dependencies:**
   ```bash
   git clone <repository-url>
   cd workers-proxy
   npm install
   ```

2. **Login to Cloudflare:**
   ```bash
   wrangler login
   ```

3. **Configure environment variables:**
   ```bash
   # Set required secrets
   wrangler secret put API_LENS_BACKEND_URL
   wrangler secret put API_LENS_BACKEND_TOKEN
   wrangler secret put ENCRYPTION_KEY
   
   # Set vendor API URLs (optional)
   wrangler secret put OPENAI_API_URL
   wrangler secret put ANTHROPIC_API_URL
   wrangler secret put GOOGLE_AI_API_URL
   ```

4. **Create KV namespaces:**
   ```bash
   wrangler kv:namespace create "RATE_LIMIT_KV"
   wrangler kv:namespace create "CACHE_KV"
   ```

5. **Update wrangler.toml with your KV namespace IDs**

### Development

```bash
# Start local development server
npm run dev

# Type checking
npm run typecheck

# Linting and formatting
npm run lint
npm run format

# Testing
npm test
npm run test:coverage
```

### Deployment

```bash
# Deploy to staging
npm run deploy:staging

# Deploy to production
npm run deploy:production
```

## Configuration

### Environment Variables

Configure these in `wrangler.toml` under the `[vars]` section:

| Variable | Description | Default |
|----------|-------------|---------|
| `ENVIRONMENT` | Deployment environment | `development` |
| `CORS_ORIGINS` | Allowed CORS origins | `*` |
| `DEFAULT_RATE_LIMIT` | Default rate limit | `1000` |
| `MAX_REQUEST_SIZE` | Max request size in bytes | `10485760` |
| `REQUEST_TIMEOUT` | Request timeout in ms | `30000` |

### Secrets

Set these using `wrangler secret put`:

| Secret | Description | Required |
|--------|-------------|----------|
| `API_LENS_BACKEND_URL` | Backend API URL | ✅ |
| `API_LENS_BACKEND_TOKEN` | Backend auth token | ✅ |
| `ENCRYPTION_KEY` | Encryption key for sensitive data | ✅ |
| `WEBHOOK_SECRET` | Webhook validation secret | ❌ |
| `OPENAI_API_URL` | OpenAI API base URL | ❌ |
| `ANTHROPIC_API_URL` | Anthropic API base URL | ❌ |
| `GOOGLE_AI_API_URL` | Google AI API base URL | ❌ |

## API Endpoints

### Health & Status

- `GET /health` - Basic health check
- `GET /status` - Detailed system status
- `GET /` - API information

### Proxy Endpoints

- `POST /proxy/openai/*` - OpenAI API proxy
- `POST /proxy/anthropic/*` - Anthropic API proxy  
- `POST /proxy/google/*` - Google AI API proxy

### Authentication

All proxy requests require authentication via:
- `Authorization: Bearer als_your_api_key_here`
- `X-API-Key: als_your_api_key_here`

## Usage Examples

### OpenAI Chat Completion

```bash
curl -X POST https://your-worker.dev/proxy/openai/chat/completions \
  -H "Authorization: Bearer als_your_api_key_here" \
  -H "Content-Type: application/json" \
  -d '{
    "model": "gpt-3.5-turbo",
    "messages": [
      {"role": "user", "content": "Hello!"}
    ],
    "max_tokens": 100
  }'
```

### Anthropic Message

```bash
curl -X POST https://your-worker.dev/proxy/anthropic/messages \
  -H "Authorization: Bearer als_your_api_key_here" \
  -H "Content-Type: application/json" \
  -d '{
    "model": "claude-3-haiku-20240307",
    "max_tokens": 100,
    "messages": [
      {"role": "user", "content": "Hello Claude!"}
    ]
  }'
```

### Google AI Generate Content

```bash
curl -X POST https://your-worker.dev/proxy/google/v1/models/gemini-pro:generateContent \
  -H "Authorization: Bearer als_your_api_key_here" \
  -H "Content-Type: application/json" \
  -d '{
    "contents": [{
      "parts": [{"text": "Hello Gemini!"}]
    }]
  }'
```

## Rate Limiting

The proxy implements multi-tiered rate limiting:

- **Per-minute limits**: Short-term burst protection
- **Per-hour limits**: Medium-term usage control  
- **Per-day limits**: Long-term quota enforcement

Rate limit headers are included in responses:

```
X-RateLimit-Limit-Minute: 60
X-RateLimit-Remaining-Minute: 59
X-RateLimit-Reset-Minute: 1640995200

X-RateLimit-Limit-Hour: 1000
X-RateLimit-Remaining-Hour: 999
X-RateLimit-Reset-Hour: 1640998800
```

## Cost Tracking

Each request includes cost information:

```
X-Cost-Estimate: 0.000015
X-Tokens-Used: 25
X-Response-Time: 245ms
```

## Error Handling

Standardized error responses:

```json
{
  "error": "Authentication Failed",
  "message": "Invalid API key format",
  "code": "AUTH_ERROR",
  "requestId": "uuid-here",
  "timestamp": "2024-01-15T10:30:00Z"
}
```

Common error codes:

- `AUTH_ERROR` - Authentication failed
- `RATE_LIMIT_ERROR` - Rate limit exceeded
- `VENDOR_ERROR` - Vendor API error
- `VALIDATION_ERROR` - Request validation failed
- `INTERNAL_ERROR` - Internal server error

## Monitoring

### Logs

View logs in real-time:

```bash
wrangler tail
```

### Analytics

Access analytics through:
- Cloudflare Dashboard
- Analytics Engine queries
- Backend API endpoints

### Metrics

Key metrics tracked:
- Request count and latency
- Error rates by vendor
- Token usage and costs
- Rate limit hits

## Development

### Project Structure

- `src/index.ts` - Main application entry point with Hono routing
- `src/auth.ts` - API key validation and company authentication  
- `src/ratelimit.ts` - Distributed rate limiting using KV and Durable Objects
- `src/vendor.ts` - Vendor-specific request handling and routing
- `src/cost.ts` - Real-time cost calculation based on token usage
- `src/logger.ts` - Async logging to backend API and Analytics Engine
- `src/validation.ts` - Request validation and security checks
- `src/error-handler.ts` - Centralized error handling and formatting

### Testing

```bash
# Run all tests
npm test

# Run tests in watch mode
npm run test:watch

# Generate coverage report
npm run test:coverage
```

### Local Development

The development server runs at `http://localhost:8787` with:
- Hot reloading for code changes
- Local KV and Durable Object simulation
- Environment variable injection
- Request/response logging

## Deployment

### Staging Deployment

```bash
npm run deploy:staging
```

Deploys to staging environment with:
- Separate KV namespaces
- Staging backend API
- Debug logging enabled

### Production Deployment

```bash
npm run deploy:production
```

Deploys to production with:
- Production KV namespaces
- Production backend API
- Optimized logging
- Error reporting

### CI/CD Pipeline

The project supports automated deployment via GitHub Actions:

1. **On Pull Request**: Run tests and linting
2. **On Merge to Main**: Deploy to staging
3. **On Release Tag**: Deploy to production

## Security Considerations

- API keys are validated against the backend API
- Request size and depth limits prevent abuse
- CORS policies restrict cross-origin access
- Rate limiting prevents excessive usage
- Input validation sanitizes potentially dangerous content
- Error responses don't leak sensitive information

## Performance

- **Cold Start**: < 10ms globally
- **Response Time**: < 50ms + vendor API latency
- **Throughput**: Handles thousands of concurrent requests
- **Edge Caching**: Authentication results cached for 5 minutes

## Troubleshooting

### Common Issues

1. **"Invalid API key format"**
   - Ensure API key starts with `als_` and is 47 characters
   - Check for extra spaces or characters

2. **"Rate limit exceeded"**
   - Check rate limit headers in response
   - Wait for reset time or upgrade tier

3. **"Vendor API Error"**
   - Verify vendor API key is configured (BYOK)
   - Check vendor service status

4. **"Request validation failed"**
   - Verify request format matches vendor requirements
   - Check content-type headers

### Debug Mode

Enable debug logging by setting `debug: true` in environment:

```bash
wrangler dev --var DEBUG=true
```

### Health Checks

Monitor service health:

```bash
curl https://your-worker.dev/health
curl https://your-worker.dev/status
```

## Contributing

1. Fork the repository
2. Create a feature branch
3. Make your changes
4. Add tests
5. Run linting and tests
6. Submit a pull request

## License

This project is licensed under the MIT License - see the LICENSE file for details.
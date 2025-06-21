# API Lens Documentation

Welcome to the API Lens documentation! This directory contains comprehensive guides, examples, and SDKs for integrating with the API Lens platform.

## Quick Start

1. **Get Your API Key**: Contact your administrator to obtain an API key
2. **Test Authentication**: Make a test request to verify your setup
3. **Start Proxying**: Route your AI API calls through API Lens
4. **Monitor Usage**: Use analytics to track costs and optimize usage

## Documentation Structure

### 📚 Core Documentation
- [**Getting Started Guide**](getting-started.md) - Complete setup and first request
- [**Authentication Guide**](authentication.md) - API key setup and security
- [**API Reference**](api-reference.md) - Complete endpoint documentation
- [**Rate Limits & Quotas**](rate-limits.md) - Understanding limits and tiers

### 🔌 Integration Guides
- [**OpenAI Integration**](integrations/openai.md) - Proxy OpenAI API calls
- [**Anthropic Integration**](integrations/anthropic.md) - Proxy Claude API calls
- [**Google AI Integration**](integrations/google.md) - Proxy Gemini API calls
- [**Multi-Vendor Setup**](integrations/multi-vendor.md) - Using multiple AI providers

### 📊 Analytics & Monitoring
- [**Usage Analytics**](analytics/usage-analytics.md) - Track API usage patterns
- [**Cost Analytics**](analytics/cost-analytics.md) - Monitor and optimize costs
- [**Performance Monitoring**](analytics/performance.md) - Latency and success rates
- [**Cost Optimization**](analytics/optimization.md) - Reduce AI API costs

### 🛠 Client Libraries & SDKs
- [**Python SDK**](sdks/python/) - Official Python client library
- [**JavaScript SDK**](sdks/javascript/) - Node.js and browser support
- [**cURL Examples**](examples/curl/) - Command-line examples
- [**Postman Collection**](examples/postman/) - Ready-to-use Postman collection

### 🏢 Enterprise Features
- [**Admin Management**](admin/admin-guide.md) - Company and user management
- [**BYOK (Bring Your Own Keys)**](enterprise/byok.md) - Vendor key management
- [**Webhooks**](enterprise/webhooks.md) - Real-time notifications
- [**SSO Integration**](enterprise/sso.md) - Single sign-on setup

### 🚀 Deployment & Operations
- [**Self-Hosting Guide**](deployment/self-hosting.md) - Deploy API Lens yourself
- [**Production Setup**](deployment/production.md) - Production best practices
- [**Monitoring & Alerts**](deployment/monitoring.md) - Operational monitoring
- [**Backup & Recovery**](deployment/backup.md) - Data backup strategies

## Quick Reference

### Base URLs
- **Production**: `https://api.apilens.dev`
- **Staging**: `https://staging-api.apilens.dev`
- **Documentation**: Visit `/docs` for interactive API docs

### Authentication
```bash
curl -H "Authorization: Bearer als_your_api_key_here" \
     https://api.apilens.dev/companies/me
```

### Rate Limits
| Tier | Requests/Min | Requests/Hour | Requests/Day |
|------|--------------|---------------|--------------|
| Free | 100 | 1,000 | 10,000 |
| Basic | 500 | 10,000 | 100,000 |
| Premium | 2,000 | 50,000 | 500,000 |
| Enterprise | Custom | Custom | Custom |

### Common Status Codes
- `200` - Success
- `401` - Invalid or missing API key
- `403` - Insufficient permissions
- `429` - Rate limit exceeded
- `500` - Server error

## Support

- **Documentation Issues**: Create an issue in the repository
- **API Support**: Contact your administrator
- **Enterprise Support**: Contact support@apilens.dev

## Contributing

We welcome contributions to our documentation! Please see [CONTRIBUTING.md](../CONTRIBUTING.md) for guidelines.
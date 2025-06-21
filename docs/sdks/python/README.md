# API Lens Python SDK

The official Python client library for API Lens, making it easy to integrate AI API cost tracking and analytics into your Python applications.

## Installation

```bash
pip install apilens-python
```

Or install from source:

```bash
git clone https://github.com/apilens/python-sdk.git
cd python-sdk
pip install -e .
```

## Quick Start

```python
import apilens

# Initialize the client
client = apilens.Client(api_key="als_your_api_key_here")

# Get company information
company = client.get_company()
print(f"Company: {company.name} (Tier: {company.tier})")

# Make an OpenAI request through API Lens
response = client.openai.chat.completions.create(
    model="gpt-3.5-turbo",
    messages=[
        {"role": "user", "content": "Hello, API Lens!"}
    ],
    max_tokens=50
)

print(response.choices[0].message.content)

# Get usage analytics
analytics = client.analytics.get_usage(period="7d")
print(f"Total requests: {analytics.total_requests}")
print(f"Total cost: ${analytics.total_cost}")
```

## Features

- ✅ **Drop-in Replacement**: Compatible with existing OpenAI/Anthropic client code
- ✅ **Automatic Cost Tracking**: All requests are automatically tracked and analyzed
- ✅ **Multi-Vendor Support**: OpenAI, Anthropic, Google AI, and more
- ✅ **Analytics Built-in**: Built-in analytics and cost optimization
- ✅ **Type Safety**: Full type hints for better IDE support
- ✅ **Async Support**: Both sync and async interfaces
- ✅ **Retry Logic**: Automatic retries with exponential backoff
- ✅ **Error Handling**: Comprehensive error handling and logging

## Client Configuration

### Basic Configuration

```python
import apilens

# Using API key directly
client = apilens.Client(api_key="als_your_api_key_here")

# Using environment variable
import os
client = apilens.Client(api_key=os.getenv("API_LENS_API_KEY"))

# Custom base URL (for self-hosted instances)
client = apilens.Client(
    api_key="als_your_api_key_here",
    base_url="https://your-api-lens-instance.com"
)
```

### Advanced Configuration

```python
import apilens

client = apilens.Client(
    api_key="als_your_api_key_here",
    base_url="https://api.apilens.dev",
    timeout=30.0,
    max_retries=3,
    retry_delay=1.0,
    user_agent="MyApp/1.0.0",
    debug=False
)
```

## AI Provider Integration

### OpenAI

```python
# Direct usage (recommended)
response = client.openai.chat.completions.create(
    model="gpt-4",
    messages=[{"role": "user", "content": "Explain quantum computing"}],
    max_tokens=200
)

# Drop-in replacement for openai library
import apilens.openai as openai
openai.api_key = client.api_key
openai.api_base = f"{client.base_url}/proxy/openai"

response = openai.ChatCompletion.create(
    model="gpt-4",
    messages=[{"role": "user", "content": "Hello!"}]
)
```

### Anthropic

```python
# Using API Lens client
response = client.anthropic.messages.create(
    model="claude-3-opus-20240229",
    max_tokens=200,
    messages=[{"role": "user", "content": "Hello, Claude!"}]
)

# Drop-in replacement for anthropic library
import apilens.anthropic as anthropic
anthropic_client = anthropic.Anthropic(
    api_key=client.api_key,
    base_url=f"{client.base_url}/proxy/anthropic"
)
```

### Google AI

```python
# Using API Lens client  
response = client.google.generateContent(
    model="gemini-pro",
    contents=[{"parts": [{"text": "Hello, Gemini!"}]}]
)
```

## Company Management

### Get Company Information

```python
company = client.get_company()
print(f"""
Company: {company.name}
Tier: {company.tier}
Active: {company.is_active}
Current Month Requests: {company.current_month_requests}
Current Month Cost: ${company.current_month_cost}
""")
```

### Update Company Profile

```python
client.update_company(
    name="Updated Company Name",
    description="AI-powered solutions company",
    contact_email="admin@company.com",
    webhook_url="https://company.com/api/webhooks/apilens"
)
```

## API Key Management

### List API Keys

```python
api_keys = client.api_keys.list()
for key in api_keys:
    print(f"Key: {key.name} (Active: {key.is_active})")
    print(f"Created: {key.created_at}")
    print(f"Last Used: {key.last_used_at}")
```

### Create New API Key

```python
new_key = client.api_keys.create(name="Production Key v2")
print(f"New API Key: {new_key.secret_key}")
# ⚠️ Save this key securely - it won't be shown again!
```

### Revoke API Key

```python
client.api_keys.revoke("key_id_here")
```

## Vendor Key Management (BYOK)

### Store Vendor Keys

```python
# Store OpenAI key
client.vendor_keys.store(
    vendor="openai",
    api_key="sk-your-openai-key-here",
    description="Primary OpenAI key"
)

# Store Anthropic key
client.vendor_keys.store(
    vendor="anthropic", 
    api_key="sk-ant-api03-your-anthropic-key-here",
    description="Primary Anthropic key"
)
```

### List Vendor Keys

```python
vendor_keys = client.vendor_keys.list()
for key in vendor_keys:
    print(f"Vendor: {key.vendor}")
    print(f"Preview: {key.key_preview}")
    print(f"Active: {key.is_active}")
```

### Update/Remove Vendor Keys

```python
# Update a vendor key
client.vendor_keys.update("openai", new_api_key="sk-new-openai-key")

# Remove a vendor key
client.vendor_keys.remove("anthropic")
```

## Analytics

### Usage Analytics

```python
# Get usage for last 30 days
usage = client.analytics.get_usage(period="30d")
print(f"Total Requests: {usage.total_requests}")
print(f"Total Tokens: {usage.total_tokens}")
print(f"Peak Requests/Hour: {usage.peak_requests_per_hour}")

# Vendor breakdown
for vendor in usage.vendor_breakdown:
    print(f"{vendor.vendor}: {vendor.requests} requests, ${vendor.cost}")

# Custom date range
from datetime import datetime, timedelta
end_date = datetime.now()
start_date = end_date - timedelta(days=7)

usage = client.analytics.get_usage(
    start_date=start_date,
    end_date=end_date,
    vendors=["openai", "anthropic"],
    group_by="day"
)
```

### Cost Analytics

```python
# Get cost analytics
costs = client.analytics.get_costs(period="30d")
print(f"Total Cost: ${costs.total_cost}")
print(f"Average Cost/Request: ${costs.average_cost_per_request}")
print(f"Cost Trend: {costs.cost_trend_percentage:+.1f}%")

# Model cost breakdown
for model in costs.ai_model_costs:
    print(f"{model.vendor}/{model.model}: ${model.total_cost}")
    print(f"  Cost per token: ${model.cost_per_token:.6f}")
```

### Performance Analytics

```python
# Get performance metrics
performance = client.analytics.get_performance(period="7d")
print(f"Average Latency: {performance.average_latency_ms}ms")
print(f"P95 Latency: {performance.p95_latency_ms}ms")
print(f"Success Rate: {performance.success_rate_percentage}%")

# Vendor performance comparison
for vendor in performance.vendor_performance:
    print(f"{vendor.vendor}: {vendor.avg_latency_ms}ms avg latency")
```

### Cost Optimization

```python
# Get cost optimization recommendations
recommendations = client.analytics.get_recommendations(min_savings=10.0)
print(f"Total Potential Savings: ${recommendations.total_potential_savings}")

for rec in recommendations.recommendations:
    print(f"\n{rec.title}")
    print(f"Potential Savings: ${rec.potential_savings} ({rec.savings_percentage:.1f}%)")
    print(f"Confidence: {rec.confidence_score:.1f}")
    print(f"Effort: {rec.implementation_effort}")
    for step in rec.actionable_steps:
        print(f"  • {step}")
```

### Export Analytics

```python
# Export usage data as CSV
export_data = client.analytics.export(
    export_type="usage",
    format="csv",
    period="30d"
)

# Save to file
with open("usage_analytics.csv", "w") as f:
    f.write(export_data)

# Export with custom filters
export_data = client.analytics.export(
    export_type="costs",
    format="json", 
    start_date=start_date,
    end_date=end_date,
    vendors=["openai"],
    include_raw_data=True
)
```

## Async Support

All methods have async equivalents:

```python
import asyncio
import apilens

async def main():
    # Initialize async client
    client = apilens.AsyncClient(api_key="als_your_api_key_here")
    
    # Async operations
    company = await client.get_company()
    
    # Async AI requests
    response = await client.openai.chat.completions.create(
        model="gpt-3.5-turbo",
        messages=[{"role": "user", "content": "Hello!"}]
    )
    
    # Async analytics
    usage = await client.analytics.get_usage(period="7d")
    
    await client.close()

# Run async code
asyncio.run(main())
```

## Error Handling

```python
import apilens
from apilens.exceptions import (
    APILensError,
    AuthenticationError,
    RateLimitError,
    ServerError
)

client = apilens.Client(api_key="als_your_api_key_here")

try:
    response = client.openai.chat.completions.create(
        model="gpt-4",
        messages=[{"role": "user", "content": "Hello!"}]
    )
except AuthenticationError as e:
    print(f"Authentication failed: {e}")
except RateLimitError as e:
    print(f"Rate limit exceeded: {e}")
    print(f"Retry after: {e.retry_after} seconds")
except ServerError as e:
    print(f"Server error: {e}")
except APILensError as e:
    print(f"API Lens error: {e}")
```

## Logging and Debugging

```python
import logging
import apilens

# Enable debug logging
logging.basicConfig(level=logging.DEBUG)

client = apilens.Client(
    api_key="als_your_api_key_here",
    debug=True  # Enable debug mode
)

# Custom logger
logger = logging.getLogger("my_app")
client.set_logger(logger)
```

## Configuration Management

### Using Configuration Files

Create `apilens.yaml`:

```yaml
api_key: ${API_LENS_API_KEY}
base_url: https://api.apilens.dev
timeout: 30.0
max_retries: 3
debug: false

vendors:
  openai:
    default_model: gpt-3.5-turbo
  anthropic:
    default_model: claude-3-haiku-20240307
```

Load configuration:

```python
import apilens

client = apilens.Client.from_config("apilens.yaml")
```

### Environment Variables

The SDK supports these environment variables:

```bash
API_LENS_API_KEY=als_your_api_key_here
API_LENS_BASE_URL=https://api.apilens.dev
API_LENS_TIMEOUT=30.0
API_LENS_MAX_RETRIES=3
API_LENS_DEBUG=false
```

## Advanced Usage

### Custom Request Headers

```python
client = apilens.Client(
    api_key="als_your_api_key_here",
    default_headers={
        "X-App-Name": "MyApplication",
        "X-App-Version": "1.0.0"
    }
)
```

### Request Middleware

```python
def request_middleware(request):
    # Add custom headers, logging, etc.
    request.headers["X-Request-ID"] = generate_request_id()
    return request

def response_middleware(response):
    # Log response times, handle errors, etc.
    logger.info(f"Request took {response.elapsed.total_seconds()}s")
    return response

client = apilens.Client(
    api_key="als_your_api_key_here",
    request_middleware=request_middleware,
    response_middleware=response_middleware
)
```

### Connection Pooling

```python
import apilens

# Configure connection pooling
client = apilens.Client(
    api_key="als_your_api_key_here",
    connection_pool_maxsize=20,
    connection_pool_maxsize_per_host=5
)
```

## Migration Guide

### From OpenAI Python Library

Replace your OpenAI imports:

```python
# Before
import openai
openai.api_key = "sk-your-openai-key"

response = openai.ChatCompletion.create(
    model="gpt-3.5-turbo",
    messages=[{"role": "user", "content": "Hello!"}]
)

# After
import apilens
client = apilens.Client(api_key="als_your_api_lens_key")

# Store your OpenAI key in API Lens
client.vendor_keys.store("openai", "sk-your-openai-key")

# Same interface, now with cost tracking
response = client.openai.chat.completions.create(
    model="gpt-3.5-turbo", 
    messages=[{"role": "user", "content": "Hello!"}]
)

# Plus get analytics
usage = client.analytics.get_usage(period="1d")
print(f"Today's cost: ${usage.total_cost}")
```

### From Anthropic Python Library

```python
# Before
import anthropic
client = anthropic.Anthropic(api_key="sk-ant-api03-your-key")

message = client.messages.create(
    model="claude-3-opus-20240229",
    max_tokens=1000,
    messages=[{"role": "user", "content": "Hello!"}]
)

# After
import apilens
client = apilens.Client(api_key="als_your_api_lens_key")

# Store your Anthropic key
client.vendor_keys.store("anthropic", "sk-ant-api03-your-key")

# Same interface with tracking
message = client.anthropic.messages.create(
    model="claude-3-opus-20240229",
    max_tokens=1000,
    messages=[{"role": "user", "content": "Hello!"}]
)
```

## Examples

See the [examples directory](examples/) for complete working examples:

- [Basic Usage](examples/basic_usage.py)
- [Async Operations](examples/async_example.py)
- [Cost Optimization](examples/cost_optimization.py)
- [Multi-Vendor Setup](examples/multi_vendor.py)
- [Analytics Dashboard](examples/analytics_dashboard.py)
- [Flask Integration](examples/flask_app.py)
- [Django Integration](examples/django_app.py)

## API Reference

For complete API documentation, visit [docs.apilens.dev/python](https://docs.apilens.dev/python).

## Contributing

Contributions are welcome! Please see [CONTRIBUTING.md](CONTRIBUTING.md) for guidelines.

## License

This project is licensed under the MIT License - see the [LICENSE](LICENSE) file for details.
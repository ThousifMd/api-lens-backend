# API Lens JavaScript SDK

The official JavaScript/Node.js client library for API Lens, making it easy to integrate AI API cost tracking and analytics into your JavaScript applications.

## Installation

```bash
npm install @apilens/javascript
```

Or with yarn:

```bash
yarn add @apilens/javascript
```

## Quick Start

```javascript
import APILens from '@apilens/javascript';

// Initialize the client
const client = new APILens.APILensClient({
  apiKey: 'als_your_api_key_here'
});

// Get company information
const company = await client.getCompany();
console.log(`Company: ${company.name} (Tier: ${company.tier})`);

// Make an OpenAI request through API Lens
const response = await client.openai.chat.completions.create({
  model: 'gpt-3.5-turbo',
  messages: [
    { role: 'user', content: 'Hello, API Lens!' }
  ],
  maxTokens: 50
});

console.log(response.choices[0].message.content);

// Get usage analytics
const analytics = await client.analytics.getUsage({ period: '7d' });
console.log(`Total requests: ${analytics.totalRequests}`);
console.log(`Total cost: $${analytics.totalCost}`);
```

## Features

- ✅ **Drop-in Replacement**: Compatible with existing OpenAI/Anthropic client code
- ✅ **Automatic Cost Tracking**: All requests are automatically tracked and analyzed
- ✅ **Multi-Vendor Support**: OpenAI, Anthropic, Google AI, and more
- ✅ **Analytics Built-in**: Built-in analytics and cost optimization
- ✅ **Type Safety**: Full TypeScript support with comprehensive type definitions
- ✅ **Promise-based**: Modern async/await support
- ✅ **Retry Logic**: Automatic retries with exponential backoff
- ✅ **Error Handling**: Comprehensive error handling with custom exception types

## Client Configuration

### Basic Configuration

```javascript
import { APILensClient } from '@apilens/javascript';

// Using API key directly
const client = new APILensClient({
  apiKey: 'als_your_api_key_here'
});

// Using environment variable
const client = new APILensClient({
  apiKey: process.env.API_LENS_API_KEY
});

// Custom base URL (for self-hosted instances)
const client = new APILensClient({
  apiKey: 'als_your_api_key_here',
  baseURL: 'https://your-api-lens-instance.com'
});
```

### Advanced Configuration

```javascript
const client = new APILensClient({
  apiKey: 'als_your_api_key_here',
  baseURL: 'https://api.apilens.dev',
  timeout: 30000,
  maxRetries: 3,
  retryDelay: 1000,
  userAgent: 'MyApp/1.0.0',
  debug: false,
  defaultHeaders: {
    'X-Custom-Header': 'value'
  }
});
```

## AI Provider Integration

### OpenAI

```javascript
// Direct usage (recommended)
const response = await client.openai.chat.completions.create({
  model: 'gpt-4',
  messages: [{ role: 'user', content: 'Explain quantum computing' }],
  maxTokens: 200
});

// Streaming
const stream = await client.openai.chat.completions.createStream({
  model: 'gpt-4',
  messages: [{ role: 'user', content: 'Tell me a story' }],
  stream: true
});

for await (const chunk of stream) {
  console.log(chunk.choices[0]?.delta?.content || '');
}
```

### Anthropic

```javascript
// Using API Lens client
const response = await client.anthropic.messages.create({
  model: 'claude-3-opus-20240229',
  maxTokens: 200,
  messages: [{ role: 'user', content: 'Hello, Claude!' }]
});

console.log(response.content[0].text);
```

### Google AI

```javascript
// Using API Lens client  
const response = await client.google.generateContent('gemini-pro', {
  contents: [{
    parts: [{ text: 'Hello, Gemini!' }]
  }]
});

console.log(response.candidates[0].content.parts[0].text);
```

## Company Management

### Get Company Information

```javascript
const company = await client.getCompany();
console.log(`
Company: ${company.name}
Tier: ${company.tier}
Active: ${company.isActive}
Current Month Requests: ${company.currentMonthRequests}
Current Month Cost: $${company.currentMonthCost}
`);
```

### Update Company Profile

```javascript
await client.updateCompany({
  name: 'Updated Company Name',
  description: 'AI-powered solutions company',
  contactEmail: 'admin@company.com',
  webhookUrl: 'https://company.com/api/webhooks/apilens'
});
```

## API Key Management

### List API Keys

```javascript
const apiKeys = await client.apiKeys.list();
for (const key of apiKeys) {
  console.log(`Key: ${key.name} (Active: ${key.isActive})`);
  console.log(`Created: ${key.createdAt}`);
  console.log(`Last Used: ${key.lastUsedAt || 'Never'}`);
}
```

### Create New API Key

```javascript
const newKey = await client.apiKeys.create('Production Key v2');
console.log(`New API Key: ${newKey.secretKey}`);
// ⚠️ Save this key securely - it won't be shown again!
```

### Revoke API Key

```javascript
await client.apiKeys.revoke('key_id_here');
```

## Vendor Key Management (BYOK)

### Store Vendor Keys

```javascript
// Store OpenAI key
await client.vendorKeys.store(
  'openai',
  'sk-your-openai-key-here',
  'Primary OpenAI key'
);

// Store Anthropic key
await client.vendorKeys.store(
  'anthropic', 
  'sk-ant-api03-your-anthropic-key-here',
  'Primary Anthropic key'
);
```

### List Vendor Keys

```javascript
const vendorKeys = await client.vendorKeys.list();
for (const key of vendorKeys) {
  console.log(`Vendor: ${key.vendor}`);
  console.log(`Preview: ${key.keyPreview}`);
  console.log(`Active: ${key.isActive}`);
}
```

### Update/Remove Vendor Keys

```javascript
// Update a vendor key
await client.vendorKeys.update('openai', 'sk-new-openai-key');

// Remove a vendor key
await client.vendorKeys.remove('anthropic');
```

## Analytics

### Usage Analytics

```javascript
// Get usage for last 30 days
const usage = await client.analytics.getUsage({ period: '30d' });
console.log(`Total Requests: ${usage.totalRequests}`);
console.log(`Total Tokens: ${usage.totalTokens}`);
console.log(`Peak Requests/Hour: ${usage.peakRequestsPerHour}`);

// Vendor breakdown
for (const vendor of usage.vendorBreakdown) {
  console.log(`${vendor.vendor.toUpperCase()}: ${vendor.requests} requests, $${vendor.cost}`);
}

// Custom date range
const endDate = new Date();
const startDate = new Date(endDate.getTime() - 7 * 24 * 60 * 60 * 1000);

const customUsage = await client.analytics.getUsage({
  startDate: startDate.toISOString(),
  endDate: endDate.toISOString(),
  vendors: ['openai', 'anthropic'],
  groupBy: 'day'
});
```

### Cost Analytics

```javascript
// Get cost analytics
const costs = await client.analytics.getCosts({ period: '30d' });
console.log(`Total Cost: $${costs.totalCost}`);
console.log(`Average Cost/Request: $${costs.averageCostPerRequest}`);
console.log(`Cost Trend: ${costs.costTrendPercentage > 0 ? '+' : ''}${costs.costTrendPercentage}%`);

// Model cost breakdown
for (const model of costs.modelCosts) {
  console.log(`${model.vendor}/${model.model}: $${model.totalCost}`);
  console.log(`  Cost per token: $${model.costPerToken.toFixed(6)}`);
}
```

### Performance Analytics

```javascript
// Get performance metrics
const performance = await client.analytics.getPerformance({ period: '7d' });
console.log(`Average Latency: ${performance.averageLatencyMs}ms`);
console.log(`P95 Latency: ${performance.p95LatencyMs}ms`);
console.log(`Success Rate: ${performance.successRatePercentage}%`);

// Vendor performance comparison
for (const vendor of performance.vendorPerformance) {
  console.log(`${vendor.vendor}: ${vendor.avgLatencyMs}ms avg latency`);
}
```

### Cost Optimization

```javascript
// Get cost optimization recommendations
const recommendations = await client.analytics.getRecommendations(10.0);
console.log(`Total Potential Savings: $${recommendations.totalPotentialSavings}`);

for (const rec of recommendations.recommendations) {
  console.log(`\n${rec.title}`);
  console.log(`Potential Savings: $${rec.potentialSavings} (${rec.savingsPercentage}%)`);
  console.log(`Confidence: ${rec.confidenceScore}`);
  console.log(`Effort: ${rec.implementationEffort}`);
  for (const step of rec.actionableSteps) {
    console.log(`  • ${step}`);
  }
}
```

### Export Analytics

```javascript
// Export usage data as CSV
const exportData = await client.analytics.export({
  exportType: 'usage',
  format: 'csv',
  dateRange: { period: '30d' }
});

// Save to file (Node.js)
import fs from 'fs';
fs.writeFileSync('usage_analytics.csv', exportData);

// Export with custom filters
const customExport = await client.analytics.export({
  exportType: 'costs',
  format: 'json',
  dateRange: {
    startDate: startDate.toISOString(),
    endDate: endDate.toISOString()
  },
  filters: {
    vendors: ['openai'],
    includeRawData: true
  }
});
```

## Error Handling

```javascript
import { 
  APILensError,
  AuthenticationError,
  RateLimitError,
  ServerError 
} from '@apilens/javascript';

try {
  const response = await client.openai.chat.completions.create({
    model: 'gpt-4',
    messages: [{ role: 'user', content: 'Hello!' }]
  });
} catch (error) {
  if (error instanceof AuthenticationError) {
    console.error(`Authentication failed: ${error.message}`);
  } else if (error instanceof RateLimitError) {
    console.error(`Rate limit exceeded: ${error.message}`);
    console.error(`Retry after: ${error.retryAfter} seconds`);
  } else if (error instanceof ServerError) {
    console.error(`Server error: ${error.message}`);
  } else if (error instanceof APILensError) {
    console.error(`API Lens error: ${error.message}`);
  } else {
    console.error(`Unknown error: ${error.message}`);
  }
}
```

## TypeScript Support

The SDK is written in TypeScript and provides full type definitions:

```typescript
import { APILensClient, Company, UsageAnalytics, ChatCompletionRequest } from '@apilens/javascript';

const client = new APILensClient({
  apiKey: process.env.API_LENS_API_KEY!
});

// All methods are fully typed
const company: Company = await client.getCompany();
const usage: UsageAnalytics = await client.analytics.getUsage({ period: '7d' });

const request: ChatCompletionRequest = {
  model: 'gpt-3.5-turbo',
  messages: [{ role: 'user', content: 'Hello!' }],
  maxTokens: 100
};
```

## Browser Support

The SDK works in both Node.js and modern browsers. For browser usage:

```html
<script type="module">
  import { APILensClient } from 'https://cdn.skypack.dev/@apilens/javascript';
  
  const client = new APILensClient({
    apiKey: 'als_your_api_key_here'
  });
  
  // Use the client...
</script>
```

**Note**: Never expose your API key in client-side code. Use a proxy server for browser applications.

## Migration Guide

### From OpenAI JavaScript Library

```javascript
// Before
import OpenAI from 'openai';
const openai = new OpenAI({ apiKey: 'sk-your-openai-key' });

const response = await openai.chat.completions.create({
  model: 'gpt-3.5-turbo',
  messages: [{ role: 'user', content: 'Hello!' }]
});

// After
import { APILensClient } from '@apilens/javascript';
const client = new APILensClient({ apiKey: 'als_your_api_lens_key' });

// Store your OpenAI key in API Lens
await client.vendorKeys.store('openai', 'sk-your-openai-key');

// Same interface, now with cost tracking
const response = await client.openai.chat.completions.create({
  model: 'gpt-3.5-turbo',
  messages: [{ role: 'user', content: 'Hello!' }]
});

// Plus get analytics
const usage = await client.analytics.getUsage({ period: '1d' });
console.log(`Today's cost: $${usage.totalCost}`);
```

## API Reference

For complete API documentation, visit [docs.apilens.dev/javascript](https://docs.apilens.dev/javascript).

## Contributing

Contributions are welcome! Please see [CONTRIBUTING.md](CONTRIBUTING.md) for guidelines.

## License

This project is licensed under the MIT License - see the [LICENSE](LICENSE) file for details.
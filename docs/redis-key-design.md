# Redis Key Design & TTL Strategy

## Key Naming Conventions

### Pattern Structure
All Redis keys follow the pattern: `{namespace}:{identifier}:{additional_info}`

### Key Patterns

#### 1. API Key Mapping
- **Pattern**: `api_key:{hash}`
- **Purpose**: Cache API key to company mapping
- **TTL**: 1 hour (3600 seconds)
- **Example**: `api_key:sha256_abc123def456`
- **Data**: JSON object with company info

#### 2. Vendor API Keys
- **Pattern**: `vendor_key:{company_id}:{vendor}`
- **Purpose**: Cache encrypted vendor API keys
- **TTL**: 30 minutes (1800 seconds)
- **Example**: `vendor_key:550e8400-e29b-41d4-a716-446655440000:openai`
- **Data**: Encrypted API key string

#### 3. Rate Limiting
- **Pattern**: `rate_limit:{company_id}:{limit_type}`
- **Purpose**: Track rate limit counters
- **TTL**: 1 minute (60 seconds)
- **Example**: `rate_limit:550e8400-e29b-41d4-a716-446655440000:requests`
- **Data**: Integer counter

#### 4. Cost Tracking
- **Pattern**: `cost:{company_id}:{period}`
- **Purpose**: Track usage costs per time period
- **TTL**: 1 day (86400 seconds)
- **Example**: `cost:550e8400-e29b-41d4-a716-446655440000:2024-01-15`
- **Data**: Float cost value

#### 5. Analytics Cache
- **Pattern**: `analytics:{company_id}:{metric}:{timeframe}`
- **Purpose**: Cache computed analytics data
- **TTL**: 15 minutes (900 seconds)
- **Example**: `analytics:550e8400-e29b-41d4-a716-446655440000:requests:hourly`
- **Data**: JSON analytics object

#### 6. Session Cache
- **Pattern**: `session:{session_id}`
- **Purpose**: Cache user session data
- **TTL**: 24 hours (86400 seconds)
- **Example**: `session:sess_abc123def456`
- **Data**: JSON session object

## TTL Strategy

### Primary TTL Values
- **API Keys**: 1 hour (3600s) - Balance between performance and security
- **Vendor Keys**: 30 minutes (1800s) - More frequent refresh for security
- **Rate Limits**: 1 minute (60s) - Quick reset for rate limiting
- **Cost Data**: 1 day (86400s) - Daily cost aggregation
- **Analytics**: 15 minutes (900s) - Fresh analytics data
- **Sessions**: 24 hours (86400s) - Standard session duration

### TTL Guidelines
1. **Security-sensitive data**: Shorter TTL (≤30 min)
2. **Performance-critical data**: Longer TTL (≤1 hour)
3. **Real-time data**: Very short TTL (≤1 min)
4. **Aggregated data**: Longer TTL (≤1 day)

## Namespace Organization

### Environment Prefixes
- **Production**: `prod:`
- **Staging**: `stage:`
- **Development**: `dev:`

### Full Key Examples
```
# Production API key cache
prod:api_key:sha256_abc123def456

# Staging rate limit
stage:rate_limit:550e8400-e29b-41d4-a716-446655440000:requests

# Development vendor key
dev:vendor_key:550e8400-e29b-41d4-a716-446655440000:anthropic
```

## Redis Operations Best Practices

### Connection Pooling
- **Pool Size**: 10-20 connections
- **Max Connections**: 50
- **Connection Timeout**: 5 seconds
- **Socket Timeout**: 5 seconds

### Error Handling
- Always implement fallback for cache misses
- Log Redis connection failures
- Graceful degradation when Redis is unavailable

### Memory Management
- Set maxmemory policy: `allkeys-lru`
- Monitor memory usage
- Use appropriate data types (strings vs hashes)
/**
 * API Lens Workers Proxy - Main Entry Point
 * 
 * Edge proxy for AI API requests with cost tracking, rate limiting,
 * and analytics built on Cloudflare Workers.
 */

import { Hono } from 'hono';
import { cors } from 'hono/cors';
import { logger } from 'hono/logger';
import { prettyJSON } from 'hono/pretty-json';
import { authenticate, getAuthStats } from './auth';
import { checkRateLimit, incrementRateLimitCounters } from './ratelimit';
import { handleVendorRequest } from './vendor';
import { createVendorHealthCheck, getAvailableModels } from './vendor/index';
import { calculateCost } from './cost';
import { logRequest } from './logger';
import { validateRequest } from './validation';
import { handleError } from './error-handler';

import { Env, HonoVariables } from './types';

// Create Hono app
const app = new Hono<{ Bindings: Env; Variables: HonoVariables }>();

// Global middleware
app.use('*', logger());
app.use('*', prettyJSON());

// CORS configuration
app.use('*', async (c, next) => {
  const corsOrigins = c.env.CORS_ORIGINS?.split(',') || ['*'];
  
  return cors({
    origin: corsOrigins,
    allowHeaders: [
      'Content-Type',
      'Authorization',
      'X-API-Key',
      'X-Request-ID',
      'X-Company-ID',
      'User-Agent'
    ],
    allowMethods: ['GET', 'POST', 'PUT', 'DELETE', 'OPTIONS'],
    exposeHeaders: [
      'X-Request-ID',
      'X-Rate-Limit-Remaining',
      'X-Rate-Limit-Reset',
      'X-Cost-Estimate'
    ],
    credentials: true,
    maxAge: 86400, // 24 hours
  })(c, next);
});

// Request validation middleware
app.use('*', async (c, next) => {
  try {
    await validateRequest(c);
    await next();
  } catch (error) {
    return handleError(c, error);
  }
});

// Health check endpoint
app.get('/health', (c) => {
  return c.json({
    status: 'healthy',
    timestamp: new Date().toISOString(),
    version: '1.0.0',
    environment: c.env.ENVIRONMENT || 'unknown',
    region: 'unknown',
  });
});

// Root endpoint with API information
app.get('/', (c) => {
  return c.json({
    name: 'API Lens Workers Proxy',
    version: '1.0.0',
    description: 'Edge proxy for AI API requests with cost tracking and analytics',
    environment: c.env.ENVIRONMENT || 'unknown',
    endpoints: {
      health: '/health',
      status: '/status',
      models: '/models',
      vendorHealth: '/health/vendors',
      openai: '/proxy/openai/*',
      anthropic: '/proxy/anthropic/*',
      google: '/proxy/google/*',
    },
    documentation: 'https://docs.apilens.dev/workers-proxy'
  });
});

// Status endpoint with detailed system information
app.get('/status', async (c) => {
  const startTime = Date.now();
  
  // Test KV access
  let kvStatus = 'unknown';
  try {
    await c.env.RATE_LIMIT_KV.get('health-check');
    kvStatus = 'healthy';
  } catch (error) {
    kvStatus = 'error';
  }
  
  const responseTime = Date.now() - startTime;
  
  return c.json({
    status: 'operational',
    timestamp: new Date().toISOString(),
    environment: c.env.ENVIRONMENT || 'unknown',
    region: 'unknown',
    performance: {
      responseTimeMs: responseTime,
      kvStatus,
    },
    limits: {
      maxRequestSize: c.env.MAX_REQUEST_SIZE || '10MB',
      requestTimeout: c.env.REQUEST_TIMEOUT || '30s',
      defaultRateLimit: c.env.DEFAULT_RATE_LIMIT || '1000/hour',
    }
  });
});

// Vendor health check endpoint
app.get('/health/vendors', createVendorHealthCheck());

// Available models endpoint
app.get('/models', (c) => {
  const models = getAvailableModels();
  return c.json({
    models: models.map(model => ({
      id: model.model,
      object: 'model',
      vendor: model.vendor,
      category: model.category,
      context_length: model.contextLength,
      features: model.features,
      pricing: {
        input_cost_per_1k_tokens: model.pricing.input,
        output_cost_per_1k_tokens: model.pricing.output,
      },
    })),
    total: models.length,
  });
});

// Main proxy routes with authentication and rate limiting
app.use('/proxy/*', async (c, next) => {
  const startTime = Date.now();
  
  try {
    // 1. Authenticate request
    const authResult = await authenticate(c);
    c.set('auth', authResult);
    
    // 2. Check rate limits (with estimated cost if available)
    const estimatedCost = (c.get('estimatedCost') as number) || 0;
    await checkRateLimit(c, estimatedCost);
    
    // 3. Continue to vendor handler
    await next();
    
    // 4. Increment rate limit counters after successful request
    const actualCost = (c.get('actualCost') as number) || (c.get('requestCost') as number) || 0;
    if (c.res && c.res.status < 400) {
      incrementRateLimitCounters(c, actualCost).catch(err => {
        console.error('Failed to increment rate limit counters:', err);
      });
    }
    
  } catch (error) {
    // Log failed request
    await logRequest(c, {
      startTime,
      endTime: Date.now(),
      success: false,
      error: error instanceof Error ? error.message : 'Unknown error',
    });
    
    return handleError(c, error);
  }
});

// OpenAI proxy routes
app.all('/proxy/openai/*', async (c) => {
  return handleVendorRequest(c, 'openai');
});

// Anthropic proxy routes  
app.all('/proxy/anthropic/*', async (c) => {
  return handleVendorRequest(c, 'anthropic');
});

// Google AI proxy routes
app.all('/proxy/google/*', async (c) => {
  return handleVendorRequest(c, 'google');
});

// Catch-all for unknown routes
app.all('*', (c) => {
  return c.json({
    error: 'Not Found',
    message: 'The requested endpoint does not exist',
    availableEndpoints: [
      '/health',
      '/status', 
      '/proxy/openai/*',
      '/proxy/anthropic/*',
      '/proxy/google/*'
    ]
  }, 404);
});

// Global error handler
app.onError((error, c) => {
  console.error('Unhandled error:', error);
  
  return c.json({
    error: 'Internal Server Error',
    message: 'An unexpected error occurred',
    requestId: c.get('requestId') || 'unknown',
    timestamp: new Date().toISOString()
  }, 500);
});

// Scheduled event handler for cron jobs
export async function scheduled(
  controller: any,
  env: Env,
  ctx: any
): Promise<void> {
  console.log('Scheduled event triggered:', controller.cron);
  
  switch (controller.cron) {
    case '0 */6 * * *': // Every 6 hours - cleanup expired cache
      await cleanupExpiredCache(env);
      break;
      
    case '0 0 * * *': // Daily - sync rate limits
      await syncRateLimits(env);
      break;
      
    default:
      console.log('Unknown cron schedule:', controller.cron);
  }
}

// Cleanup expired cache entries
async function cleanupExpiredCache(env: Env): Promise<void> {
  try {
    // This would implement cache cleanup logic
    console.log('Cleaning up expired cache entries...');
    
    // Example: List and delete expired keys
    const keys = await env.CACHE_KV.list({ prefix: 'temp_' });
    let deletedCount = 0;
    
    for (const key of keys.keys) {
      const value = await env.CACHE_KV.get(key.name);
      if (!value) {
        await env.CACHE_KV.delete(key.name);
        deletedCount++;
      }
    }
    
    console.log(`Cleaned up ${deletedCount} expired cache entries`);
  } catch (error) {
    console.error('Error cleaning up cache:', error);
  }
}

// Sync rate limits with backend
async function syncRateLimits(env: Env): Promise<void> {
  try {
    console.log('Syncing rate limits with backend...');
    
    // This would implement rate limit synchronization
    // For example, fetch updated rate limits from the backend API
    const response = await fetch(`${env.API_LENS_BACKEND_URL}/admin/rate-limits`, {
      headers: {
        'Authorization': `Bearer ${env.API_LENS_BACKEND_TOKEN}`,
        'Content-Type': 'application/json',
      },
    });
    
    if (response.ok) {
      const rateLimits = await response.json();
      console.log('Successfully synced rate limits:', rateLimits.length);
    } else {
      console.error('Failed to sync rate limits:', response.status);
    }
  } catch (error) {
    console.error('Error syncing rate limits:', error);
  }
}

export default app;

// Export Durable Object classes for wrangler
export { RateLimiter } from './ratelimit';
/**
 * Basic functionality tests for API Lens Workers Proxy
 */

import { describe, it, expect, beforeAll } from 'vitest';
import app from '../src/index';

// Mock environment for testing
const mockEnv = {
  ENVIRONMENT: 'test',
  CORS_ORIGINS: 'https://test.apilens.dev',
  DEFAULT_RATE_LIMIT: '1000',
  MAX_REQUEST_SIZE: '10485760',
  REQUEST_TIMEOUT: '30000',
  API_LENS_BACKEND_URL: 'https://api.test.apilens.dev',
  API_LENS_BACKEND_TOKEN: 'test-token',
  ENCRYPTION_KEY: 'test-encryption-key',
  WEBHOOK_SECRET: 'test-webhook-secret',
  OPENAI_API_URL: 'https://api.openai.com/v1',
  ANTHROPIC_API_URL: 'https://api.anthropic.com',
  GOOGLE_AI_API_URL: 'https://generativelanguage.googleapis.com',
  
  // Mock KV and Durable Object bindings
  RATE_LIMIT_KV: {
    get: vi.fn(),
    put: vi.fn(),
    delete: vi.fn(),
    list: vi.fn(),
  },
  CACHE_KV: {
    get: vi.fn(),
    put: vi.fn(),
    delete: vi.fn(),
    list: vi.fn(),
  },
  RATE_LIMITER: {
    idFromName: vi.fn(),
    get: vi.fn(),
  },
  API_ANALYTICS: {
    writeDataPoint: vi.fn(),
  },
} as any;

describe('API Lens Workers Proxy', () => {
  describe('Health Endpoints', () => {
    it('should return health status', async () => {
      const request = new Request('https://test.workers.dev/health');
      const response = await app.fetch(request, mockEnv);
      
      expect(response.status).toBe(200);
      
      const data = await response.json();
      expect(data).toMatchObject({
        status: 'healthy',
        version: '1.0.0',
        environment: 'test',
      });
      expect(data.timestamp).toBeTruthy();
    });

    it('should return detailed status', async () => {
      const request = new Request('https://test.workers.dev/status');
      const response = await app.fetch(request, mockEnv);
      
      expect(response.status).toBe(200);
      
      const data = await response.json();
      expect(data).toMatchObject({
        status: 'operational',
        environment: 'test',
        performance: expect.objectContaining({
          responseTimeMs: expect.any(Number),
          kvStatus: expect.any(String),
        }),
        limits: expect.objectContaining({
          maxRequestSize: '10485760',
          requestTimeout: '30000',
          defaultRateLimit: '1000',
        }),
      });
    });

    it('should return API information at root', async () => {
      const request = new Request('https://test.workers.dev/');
      const response = await app.fetch(request, mockEnv);
      
      expect(response.status).toBe(200);
      
      const data = await response.json();
      expect(data).toMatchObject({
        name: 'API Lens Workers Proxy',
        version: '1.0.0',
        description: expect.any(String),
        environment: 'test',
        endpoints: expect.objectContaining({
          health: '/health',
          openai: '/proxy/openai/*',
          anthropic: '/proxy/anthropic/*',
          google: '/proxy/google/*',
        }),
      });
    });
  });

  describe('CORS Handling', () => {
    it('should handle OPTIONS preflight request', async () => {
      const request = new Request('https://test.workers.dev/proxy/openai/chat/completions', {
        method: 'OPTIONS',
        headers: {
          'Origin': 'https://test.apilens.dev',
          'Access-Control-Request-Method': 'POST',
          'Access-Control-Request-Headers': 'Content-Type, Authorization',
        },
      });
      
      const response = await app.fetch(request, mockEnv);
      
      expect(response.status).toBe(200);
      expect(response.headers.get('Access-Control-Allow-Origin')).toBeTruthy();
      expect(response.headers.get('Access-Control-Allow-Methods')).toContain('POST');
      expect(response.headers.get('Access-Control-Allow-Headers')).toContain('Authorization');
    });

    it('should include CORS headers in response', async () => {
      const request = new Request('https://test.workers.dev/health', {
        headers: {
          'Origin': 'https://test.apilens.dev',
        },
      });
      
      const response = await app.fetch(request, mockEnv);
      
      expect(response.status).toBe(200);
      expect(response.headers.get('Access-Control-Allow-Origin')).toBeTruthy();
    });
  });

  describe('Request Validation', () => {
    it('should reject requests with missing authentication', async () => {
      const request = new Request('https://test.workers.dev/proxy/openai/chat/completions', {
        method: 'POST',
        headers: {
          'Content-Type': 'application/json',
        },
        body: JSON.stringify({
          model: 'gpt-3.5-turbo',
          messages: [{ role: 'user', content: 'Hello' }],
        }),
      });
      
      const response = await app.fetch(request, mockEnv);
      
      expect(response.status).toBe(401);
      
      const data = await response.json();
      expect(data).toMatchObject({
        error: 'Authentication Failed',
        code: 'AUTH_ERROR',
      });
    });

    it('should reject requests with invalid API key format', async () => {
      const request = new Request('https://test.workers.dev/proxy/openai/chat/completions', {
        method: 'POST',
        headers: {
          'Authorization': 'Bearer invalid-key-format',
          'Content-Type': 'application/json',
        },
        body: JSON.stringify({
          model: 'gpt-3.5-turbo',
          messages: [{ role: 'user', content: 'Hello' }],
        }),
      });
      
      const response = await app.fetch(request, mockEnv);
      
      expect(response.status).toBe(401);
      
      const data = await response.json();
      expect(data.message).toContain('Invalid API key format');
    });

    it('should reject oversized requests', async () => {
      const largeBody = 'x'.repeat(11 * 1024 * 1024); // 11MB
      
      const request = new Request('https://test.workers.dev/proxy/openai/chat/completions', {
        method: 'POST',
        headers: {
          'Authorization': 'Bearer als_test_key_12345678901234567890123456789012345',
          'Content-Type': 'application/json',
          'Content-Length': largeBody.length.toString(),
        },
        body: largeBody,
      });
      
      const response = await app.fetch(request, mockEnv);
      
      expect(response.status).toBe(413);
      
      const data = await response.json();
      expect(data.message).toContain('Request body too large');
    });
  });

  describe('Error Handling', () => {
    it('should return 404 for unknown routes', async () => {
      const request = new Request('https://test.workers.dev/unknown-endpoint');
      const response = await app.fetch(request, mockEnv);
      
      expect(response.status).toBe(404);
      
      const data = await response.json();
      expect(data).toMatchObject({
        error: 'Not Found',
        message: 'The requested endpoint does not exist',
      });
    });

    it('should include request ID in error responses', async () => {
      const request = new Request('https://test.workers.dev/unknown-endpoint');
      const response = await app.fetch(request, mockEnv);
      
      const data = await response.json();
      expect(data.requestId).toBeTruthy();
      expect(typeof data.requestId).toBe('string');
    });

    it('should include timestamp in error responses', async () => {
      const request = new Request('https://test.workers.dev/unknown-endpoint');
      const response = await app.fetch(request, mockEnv);
      
      const data = await response.json();
      expect(data.timestamp).toBeTruthy();
      expect(new Date(data.timestamp).getTime()).toBeGreaterThan(0);
    });
  });

  describe('Vendor Routing', () => {
    it('should recognize OpenAI proxy path', async () => {
      const request = new Request('https://test.workers.dev/proxy/openai/models', {
        headers: {
          'Authorization': 'Bearer als_test_key_12345678901234567890123456789012345',
        },
      });
      
      // This will fail authentication, but should reach the vendor handler
      const response = await app.fetch(request, mockEnv);
      
      // Should get auth error, not 404
      expect(response.status).toBe(401);
    });

    it('should recognize Anthropic proxy path', async () => {
      const request = new Request('https://test.workers.dev/proxy/anthropic/messages', {
        method: 'POST',
        headers: {
          'Authorization': 'Bearer als_test_key_12345678901234567890123456789012345',
          'Content-Type': 'application/json',
        },
        body: JSON.stringify({
          model: 'claude-3-haiku-20240307',
          max_tokens: 100,
          messages: [{ role: 'user', content: 'Hello' }],
        }),
      });
      
      const response = await app.fetch(request, mockEnv);
      
      // Should get auth error, not 404
      expect(response.status).toBe(401);
    });

    it('should reject unsupported vendor', async () => {
      const request = new Request('https://test.workers.dev/proxy/unsupported-vendor/test');
      const response = await app.fetch(request, mockEnv);
      
      expect(response.status).toBe(400);
      
      const data = await response.json();
      expect(data.message).toContain('Unsupported vendor');
    });
  });
});

describe('Utility Functions', () => {
  describe('API Key Validation', () => {
    it('should validate correct API key format', () => {
      const { validateApiKeyFormat } = require('../src/validation');
      
      expect(validateApiKeyFormat('als_1234567890123456789012345678901234567890123')).toBe(true);
    });

    it('should reject incorrect API key format', () => {
      const { validateApiKeyFormat } = require('../src/validation');
      
      expect(validateApiKeyFormat('invalid-key')).toBe(false);
      expect(validateApiKeyFormat('als_short')).toBe(false);
      expect(validateApiKeyFormat('sk_openai_key')).toBe(false);
    });
  });
});
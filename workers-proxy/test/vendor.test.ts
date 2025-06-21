/**
 * Vendor Integration System Tests for API Lens Workers Proxy
 */

import { describe, it, expect, beforeAll, vi, beforeEach } from 'vitest';
import {
  routeToVendor,
  getVendorKey,
  transformRequest,
  callVendorAPI,
  parseVendorResponse,
  estimateRequestCost,
  calculateRequestCost,
  VendorType,
  VendorHandler,
  getModelMapping,
  getAllSupportedModels,
  testVendorKey,
} from '../src/vendor';

// Mock environment for testing
const mockEnv = {
  ENVIRONMENT: 'test',
  API_LENS_BACKEND_URL: 'https://api.test.apilens.dev',
  API_LENS_BACKEND_TOKEN: 'test-backend-token',
  OPENAI_API_KEY: 'sk-test-openai-key',
  ANTHROPIC_API_KEY: 'sk-ant-test-key',
  GOOGLE_AI_API_KEY: 'test-google-key',
  ENCRYPTION_KEY: 'test-encryption-key',
} as any;

// Mock context
const mockContext = {
  requestId: 'req_123',
  companyId: 'comp_123',
  apiKeyId: 'key_123',
  vendor: 'openai',
  model: 'gpt-3.5-turbo',
  endpoint: 'chat',
  startTime: Date.now(),
  metadata: {},
};

describe('Vendor Routing', () => {
  describe('routeToVendor', () => {
    it('should route OpenAI models correctly', () => {
      const config = routeToVendor('gpt-4o');
      expect(config.name).toBe(VendorType.OPENAI);
      expect(config.supportedModels).toContain('gpt-4o');
    });

    it('should route Anthropic models correctly', () => {
      const config = routeToVendor('claude-3-5-sonnet');
      expect(config.name).toBe(VendorType.ANTHROPIC);
      expect(config.supportedModels).toContain('claude-3-5-sonnet-20241022');
    });

    it('should route Google models correctly', () => {
      const config = routeToVendor('gemini-1.5-pro');
      expect(config.name).toBe(VendorType.GOOGLE);
      expect(config.supportedModels).toContain('gemini-1.5-pro');
    });

    it('should handle unknown models by defaulting to OpenAI', () => {
      const config = routeToVendor('unknown-model');
      expect(config.name).toBe(VendorType.OPENAI);
    });

    it('should infer vendor from model name patterns', () => {
      expect(routeToVendor('gpt-custom').name).toBe(VendorType.OPENAI);
      expect(routeToVendor('claude-custom').name).toBe(VendorType.ANTHROPIC);
      expect(routeToVendor('gemini-custom').name).toBe(VendorType.GOOGLE);
    });
  });

  describe('getModelMapping', () => {
    it('should return correct mapping for known models', () => {
      const mapping = getModelMapping('gpt-4o');
      expect(mapping).toBeTruthy();
      expect(mapping?.vendor).toBe(VendorType.OPENAI);
      expect(mapping?.inputCostPer1kTokens).toBe(0.015);
    });

    it('should return null for unknown models', () => {
      const mapping = getModelMapping('unknown-model');
      expect(mapping).toBeNull();
    });
  });

  describe('getAllSupportedModels', () => {
    it('should return all supported models', () => {
      const models = getAllSupportedModels();
      expect(models.length).toBeGreaterThan(0);
      expect(models.some(m => m === 'gpt-4o')).toBe(true);
      expect(models.some(m => m === 'claude-3-5-sonnet')).toBe(true);
    });
  });
});

describe('BYOK Key Management', () => {
  describe('getVendorKey', () => {
    beforeEach(() => {
      vi.clearAllMocks();
    });

    it('should return BYOK key when available', async () => {
      // Mock successful BYOK response
      vi.spyOn(global, 'fetch').mockImplementation(async (url) => {
        if (url.toString().includes('/vendor-keys/')) {
          return new Response(JSON.stringify({
            id: 'vkey_123',
            companyId: 'comp_123',
            vendor: 'openai',
            encryptedKey: btoa('sk-test-byok-key'),
            isActive: true,
          }), { status: 200 });
        }
        return new Response('Not Found', { status: 404 });
      });

      const key = await getVendorKey('comp_123', 'openai', mockEnv);
      expect(key).toBe('sk-test-byok-key');
    });

    it('should fallback to default key when no BYOK', async () => {
      // Mock 404 for BYOK
      vi.spyOn(global, 'fetch').mockImplementation(async () => 
        new Response('Not Found', { status: 404 })
      );

      const key = await getVendorKey('comp_123', 'openai', mockEnv);
      expect(key).toBe('sk-test-openai-key');
    });

    it('should handle inactive BYOK keys', async () => {
      vi.spyOn(global, 'fetch').mockImplementation(async (url) => {
        if (url.toString().includes('/vendor-keys/')) {
          return new Response(JSON.stringify({
            id: 'vkey_123',
            encryptedKey: btoa('sk-test-key'),
            isActive: false,
          }), { status: 200 });
        }
        return new Response('Not Found', { status: 404 });
      });

      await expect(getVendorKey('comp_123', 'openai', mockEnv))
        .rejects.toThrow('Vendor key is not active');
    });

    it('should throw error when no keys available', async () => {
      vi.spyOn(global, 'fetch').mockImplementation(async () => 
        new Response('Not Found', { status: 404 })
      );

      // Remove default key
      const envWithoutKey = { ...mockEnv, OPENAI_API_KEY: undefined };

      await expect(getVendorKey('comp_123', 'openai', envWithoutKey))
        .rejects.toThrow('No API key found');
    });
  });

  describe('testVendorKey', () => {
    it('should validate working API key', async () => {
      vi.spyOn(global, 'fetch').mockImplementation(async () => 
        new Response(JSON.stringify({
          data: [{ id: 'model-1' }, { id: 'model-2' }],
          organization: 'org-123',
        }), { status: 200 })
      );

      const result = await testVendorKey('openai', 'sk-valid-key', mockEnv);
      expect(result.valid).toBe(true);
      expect(result.details?.models).toBe(2);
    });

    it('should detect invalid API key', async () => {
      vi.spyOn(global, 'fetch').mockImplementation(async () => 
        new Response(JSON.stringify({
          error: { message: 'Invalid API key' }
        }), { status: 401 })
      );

      const result = await testVendorKey('openai', 'sk-invalid-key', mockEnv);
      expect(result.valid).toBe(false);
      expect(result.error).toContain('Invalid API key');
    });
  });
});

describe('Request Transformation', () => {
  describe('transformRequest for OpenAI', () => {
    it('should pass OpenAI requests through unchanged', () => {
      const request = {
        model: 'gpt-3.5-turbo',
        messages: [{ role: 'user', content: 'Hello' }],
        temperature: 0.7,
        max_tokens: 150,
      };

      const transformed = transformRequest('openai', request);
      expect(transformed).toEqual(request);
    });
  });

  describe('transformRequest for Anthropic', () => {
    it('should transform messages and extract system message', () => {
      const request = {
        model: 'claude-3-5-sonnet',
        messages: [
          { role: 'system', content: 'You are a helpful assistant' },
          { role: 'user', content: 'Hello' },
        ],
        temperature: 0.7,
      };

      const transformed = transformRequest('anthropic', request);
      
      expect(transformed.system).toBe('You are a helpful assistant');
      expect(transformed.messages).toHaveLength(1);
      expect(transformed.messages[0].role).toBe('user');
      expect(transformed.max_tokens).toBe(4096); // Default added
    });

    it('should handle requests without system message', () => {
      const request = {
        model: 'claude-3-5-sonnet',
        messages: [{ role: 'user', content: 'Hello' }],
      };

      const transformed = transformRequest('anthropic', request);
      
      expect(transformed.system).toBeUndefined();
      expect(transformed.messages).toHaveLength(1);
    });
  });

  describe('transformRequest for Google', () => {
    it('should transform to Google format', () => {
      const request = {
        model: 'gemini-1.5-pro',
        messages: [
          { role: 'user', content: 'Hello' },
          { role: 'assistant', content: 'Hi there!' },
        ],
        temperature: 0.8,
        max_tokens: 100,
      };

      const transformed = transformRequest('google', request);
      
      expect(transformed.contents).toHaveLength(2);
      expect(transformed.contents[0].role).toBe('user');
      expect(transformed.contents[1].role).toBe('model');
      expect(transformed.contents[0].parts[0].text).toBe('Hello');
      expect(transformed.generationConfig?.temperature).toBe(0.8);
    });
  });
});

describe('Vendor API Calls', () => {
  describe('callVendorAPI', () => {
    it('should make successful API call', async () => {
      const mockResponse = {
        id: 'chatcmpl-123',
        object: 'chat.completion',
        model: 'gpt-3.5-turbo',
        choices: [{
          message: { content: 'Hello there!' },
          finish_reason: 'stop',
        }],
        usage: {
          prompt_tokens: 10,
          completion_tokens: 5,
          total_tokens: 15,
        },
      };

      vi.spyOn(global, 'fetch').mockImplementation(async () => 
        new Response(JSON.stringify(mockResponse), { status: 200 })
      );

      const request = {
        model: 'gpt-3.5-turbo',
        messages: [{ role: 'user', content: 'Hello' }],
      };

      const result = await callVendorAPI(
        'openai',
        'sk-test-key',
        request,
        mockContext,
        mockEnv
      );

      expect(result.success).toBe(true);
      expect(result.response).toEqual(mockResponse);
      expect(result.usage?.totalTokens).toBe(15);
      expect(result.retryCount).toBe(0);
    });

    it('should handle API errors with retries', async () => {
      let callCount = 0;
      vi.spyOn(global, 'fetch').mockImplementation(async () => {
        callCount++;
        if (callCount <= 2) {
          return new Response(JSON.stringify({
            error: { message: 'Rate limit exceeded' }
          }), { status: 429 });
        }
        return new Response(JSON.stringify({
          choices: [{ message: { content: 'Success!' } }],
          usage: { total_tokens: 10 },
        }), { status: 200 });
      });

      const result = await callVendorAPI(
        'openai',
        'sk-test-key',
        { model: 'gpt-3.5-turbo' },
        mockContext,
        mockEnv
      );

      expect(result.success).toBe(true);
      expect(result.retryCount).toBe(2);
      expect(callCount).toBe(3);
    });

    it('should fail after max retries', async () => {
      vi.spyOn(global, 'fetch').mockImplementation(async () => 
        new Response(JSON.stringify({
          error: { message: 'Server error' }
        }), { status: 500 })
      );

      const result = await callVendorAPI(
        'openai',
        'sk-test-key',
        { model: 'gpt-3.5-turbo' },
        mockContext,
        mockEnv
      );

      expect(result.success).toBe(false);
      expect(result.error?.code).toBe('server_error');
      expect(result.retryCount).toBe(3); // Max retries
    });

    it('should handle network errors', async () => {
      vi.spyOn(global, 'fetch').mockRejectedValue(new Error('Network error'));

      const result = await callVendorAPI(
        'openai',
        'sk-test-key',
        { model: 'gpt-3.5-turbo' },
        mockContext,
        mockEnv
      );

      expect(result.success).toBe(false);
      expect(result.error?.type).toBe('network_error');
    });
  });
});

describe('Response Parsing', () => {
  describe('parseVendorResponse', () => {
    it('should parse OpenAI response correctly', () => {
      const response = {
        id: 'chatcmpl-123',
        model: 'gpt-3.5-turbo',
        choices: [{ finish_reason: 'stop' }],
        usage: {
          prompt_tokens: 10,
          completion_tokens: 5,
          total_tokens: 15,
        },
      };

      const usage = parseVendorResponse('openai', response);

      expect(usage.inputTokens).toBe(10);
      expect(usage.outputTokens).toBe(5);
      expect(usage.totalTokens).toBe(15);
      expect(usage.model).toBe('gpt-3.5-turbo');
      expect(usage.finishReason).toBe('stop');
      expect(usage.requestId).toBe('chatcmpl-123');
    });

    it('should parse Anthropic response correctly', () => {
      const response = {
        id: 'msg_123',
        model: 'claude-3-5-sonnet-20241022',
        stop_reason: 'end_turn',
        usage: {
          input_tokens: 12,
          output_tokens: 8,
        },
      };

      const usage = parseVendorResponse('anthropic', response);

      expect(usage.inputTokens).toBe(12);
      expect(usage.outputTokens).toBe(8);
      expect(usage.totalTokens).toBe(20);
    });

    it('should parse Google response correctly', () => {
      const response = {
        candidates: [{ finishReason: 'STOP' }],
        usageMetadata: {
          promptTokenCount: 15,
          candidatesTokenCount: 10,
          totalTokenCount: 25,
        },
      };

      const usage = parseVendorResponse('google', response);

      expect(usage.inputTokens).toBe(15);
      expect(usage.outputTokens).toBe(10);
      expect(usage.totalTokens).toBe(25);
    });

    it('should handle missing usage data gracefully', () => {
      const response = {
        id: 'test',
        model: 'gpt-3.5-turbo',
      };

      const usage = parseVendorResponse('openai', response);

      expect(usage.inputTokens).toBe(0);
      expect(usage.outputTokens).toBe(0);
      expect(usage.totalTokens).toBe(0);
      expect(usage.model).toBe('gpt-3.5-turbo');
    });
  });
});

describe('Cost Calculation', () => {
  describe('estimateRequestCost', () => {
    it('should estimate cost for known models', () => {
      const cost = estimateRequestCost('gpt-4o', 1000);
      expect(cost).toBe(0.015); // $0.015 per 1k input tokens
    });

    it('should return 0 for unknown models', () => {
      const cost = estimateRequestCost('unknown-model', 1000);
      expect(cost).toBe(0);
    });
  });

  describe('calculateRequestCost', () => {
    it('should calculate actual cost with input and output tokens', () => {
      const usage = {
        inputTokens: 1000,
        outputTokens: 500,
        totalTokens: 1500,
        model: 'gpt-4o',
      };

      const cost = calculateRequestCost('gpt-4o', usage);
      expect(cost).toBe(0.045); // $0.015 + $0.030
    });

    it('should handle models without pricing data', () => {
      const usage = {
        inputTokens: 1000,
        outputTokens: 500,
        totalTokens: 1500,
        model: 'unknown-model',
      };

      const cost = calculateRequestCost('unknown-model', usage);
      expect(cost).toBe(0);
    });
  });
});

describe('VendorHandler', () => {
  let handler: VendorHandler;

  beforeEach(() => {
    handler = new VendorHandler(mockEnv);
    vi.clearAllMocks();
  });

  describe('handleRequest', () => {
    const mockHonoContext = {
      req: {
        header: vi.fn(() => 'test-agent'),
        json: vi.fn(async () => ({
          model: 'gpt-3.5-turbo',
          messages: [{ role: 'user', content: 'Hello' }],
        })),
      },
      get: vi.fn((key: string) => {
        if (key === 'requestId') return 'req_123';
        return null;
      }),
      set: vi.fn(),
      json: vi.fn((data: any, status: number, headers?: any) => 
        new Response(JSON.stringify(data), { status, headers })
      ),
      env: mockEnv,
    };

    it('should handle successful request end-to-end', async () => {
      // Mock authentication
      vi.doMock('../src/auth', () => ({
        getAuthResult: vi.fn(() => ({
          company: { id: 'comp_123' },
          apiKey: { id: 'key_123' },
        })),
      }));

      // Mock successful vendor response
      vi.spyOn(global, 'fetch').mockImplementation(async (url) => {
        if (url.toString().includes('/vendor-keys/')) {
          return new Response('Not Found', { status: 404 });
        }
        return new Response(JSON.stringify({
          choices: [{ message: { content: 'Hello there!' } }],
          usage: { prompt_tokens: 5, completion_tokens: 3, total_tokens: 8 },
        }), { status: 200 });
      });

      const response = await handler.handleRequest(
        mockHonoContext as any,
        'openai',
        { model: 'gpt-3.5-turbo', messages: [{ role: 'user', content: 'Hello' }] }
      );

      expect(response.status).toBe(200);
    });

    it('should handle authentication failure', async () => {
      // Mock no authentication
      vi.doMock('../src/auth', () => ({
        getAuthResult: vi.fn(() => null),
      }));

      await expect(handler.handleRequest(
        mockHonoContext as any,
        'openai',
        { model: 'gpt-3.5-turbo' }
      )).rejects.toThrow('Request not authenticated');
    });
  });

  describe('healthCheck', () => {
    it('should return healthy status for working vendor', async () => {
      vi.spyOn(global, 'fetch').mockImplementation(async () => 
        new Response(JSON.stringify({ data: [] }), { status: 200 })
      );

      const result = await handler.healthCheck('openai');

      expect(result.vendor).toBe('openai');
      expect(result.status).toBe('healthy');
      expect(result.latency).toBeGreaterThan(0);
    });

    it('should return down status for failing vendor', async () => {
      vi.spyOn(global, 'fetch').mockImplementation(async () => 
        new Response('Server Error', { status: 500 })
      );

      const result = await handler.healthCheck('openai');

      expect(result.vendor).toBe('openai');
      expect(result.status).toBe('down');
      expect(result.details?.statusCode).toBe(500);
    });

    it('should return degraded status for slow vendor', async () => {
      vi.spyOn(global, 'fetch').mockImplementation(async () => {
        await new Promise(resolve => setTimeout(resolve, 6000)); // 6 second delay
        return new Response(JSON.stringify({ data: [] }), { status: 200 });
      });

      const result = await handler.healthCheck('openai');

      expect(result.vendor).toBe('openai');
      expect(result.status).toBe('degraded');
      expect(result.latency).toBeGreaterThan(5000);
    });
  });
});

describe('Integration Tests', () => {
  describe('End-to-End Vendor Workflow', () => {
    it('should complete full request workflow', async () => {
      // Setup mocks for full workflow
      vi.spyOn(global, 'fetch').mockImplementation(async (url) => {
        const urlStr = url.toString();
        
        // BYOK key fetch (not found)
        if (urlStr.includes('/vendor-keys/')) {
          return new Response('Not Found', { status: 404 });
        }
        
        // Vendor API call
        if (urlStr.includes('api.openai.com')) {
          return new Response(JSON.stringify({
            id: 'chatcmpl-test',
            choices: [{ message: { content: 'Test response' }, finish_reason: 'stop' }],
            usage: { prompt_tokens: 10, completion_tokens: 5, total_tokens: 15 },
          }), { status: 200 });
        }
        
        return new Response('Not Found', { status: 404 });
      });

      // 1. Route to vendor
      const vendor = routeToVendor('gpt-3.5-turbo');
      expect(vendor.name).toBe('openai');

      // 2. Get API key
      const apiKey = await getVendorKey('comp_123', 'openai', mockEnv);
      expect(apiKey).toBe('sk-test-openai-key');

      // 3. Transform request
      const request = { model: 'gpt-3.5-turbo', messages: [{ role: 'user', content: 'Hello' }] };
      const transformed = transformRequest('openai', request);
      expect(transformed).toEqual(request);

      // 4. Call vendor API
      const result = await callVendorAPI('openai', apiKey, transformed, mockContext, mockEnv);
      expect(result.success).toBe(true);

      // 5. Parse response
      const usage = parseVendorResponse('openai', result.response!);
      expect(usage.totalTokens).toBe(15);

      // 6. Calculate cost
      const cost = calculateRequestCost('gpt-3.5-turbo', usage);
      expect(cost).toBeGreaterThan(0);
    });
  });

  describe('Error Handling Scenarios', () => {
    it('should handle vendor downtime gracefully', async () => {
      vi.spyOn(global, 'fetch').mockRejectedValue(new Error('Connection refused'));

      const result = await callVendorAPI(
        'openai',
        'sk-test-key',
        { model: 'gpt-3.5-turbo' },
        mockContext,
        mockEnv
      );

      expect(result.success).toBe(false);
      expect(result.error?.type).toBe('network_error');
      expect(result.retryCount).toBeGreaterThan(0);
    });

    it('should handle invalid model gracefully', async () => {
      expect(() => routeToVendor('completely-unknown-model-xyz')).not.toThrow();
      
      const config = routeToVendor('completely-unknown-model-xyz');
      expect(config.name).toBe('openai'); // Default fallback
    });
  });
});

describe('Performance Tests', () => {
  it('should handle concurrent vendor requests', async () => {
    vi.spyOn(global, 'fetch').mockImplementation(async () => {
      await new Promise(resolve => setTimeout(resolve, 10)); // 10ms delay
      return new Response(JSON.stringify({
        choices: [{ message: { content: 'Response' } }],
        usage: { total_tokens: 10 },
      }), { status: 200 });
    });

    const promises = Array(50).fill(0).map((_, i) =>
      callVendorAPI(
        'openai',
        'sk-test-key',
        { model: 'gpt-3.5-turbo', messages: [{ role: 'user', content: `Request ${i}` }] },
        { ...mockContext, requestId: `req_${i}` },
        mockEnv
      )
    );

    const results = await Promise.all(promises);
    
    expect(results).toHaveLength(50);
    expect(results.every(r => r.success)).toBe(true);
  });
});
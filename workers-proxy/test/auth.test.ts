/**
 * Authentication System Tests for API Lens Workers Proxy
 */

import { describe, it, expect, beforeAll, vi } from 'vitest';
import {
  extractAPIKey,
  validateAPIKeyFormat,
  hashAPIKey,
  createKeyPreview,
  validateIPWhitelist,
  Authenticator,
  AuthErrorHandler,
  AuthErrorCode,
  CompanyTier,
} from '../src/auth/index';

// Mock environment for testing
const mockEnv = {
  ENVIRONMENT: 'test',
  API_LENS_BACKEND_URL: 'https://api.test.apilens.dev',
  API_LENS_BACKEND_TOKEN: 'test-backend-token',
  REDIS_URL: 'https://redis.test.apilens.dev',
  REDIS_TOKEN: 'test-redis-token',
  
  // Mock KV bindings
  CACHE_KV: {
    get: vi.fn(),
    put: vi.fn(),
    delete: vi.fn(),
    list: vi.fn(),
  },
} as any;

describe('API Key Extraction', () => {
  describe('extractAPIKey', () => {
    it('should extract API key from Authorization header (Bearer)', async () => {
      const request = new Request('https://test.workers.dev/proxy/openai/models', {
        headers: {
          'Authorization': 'Bearer als_1234567890123456789012345678901234567890123',
        },
      });
      
      const result = await extractAPIKey(request);
      
      expect(result.key).toBe('als_1234567890123456789012345678901234567890123');
      expect(result.source).toBe('authorization');
      expect(result.preview).toBe('als_1234...0123');
      expect(result.hash).toBeTruthy();
    });

    it('should extract API key from X-API-Key header', async () => {
      const request = new Request('https://test.workers.dev/proxy/openai/models', {
        headers: {
          'X-API-Key': 'als_1234567890123456789012345678901234567890123',
        },
      });
      
      const result = await extractAPIKey(request);
      
      expect(result.key).toBe('als_1234567890123456789012345678901234567890123');
      expect(result.source).toBe('x-api-key');
    });

    it('should extract API key from query parameter', async () => {
      const request = new Request('https://test.workers.dev/webhook?api_key=als_1234567890123456789012345678901234567890123');
      
      const result = await extractAPIKey(request);
      
      expect(result.key).toBe('als_1234567890123456789012345678901234567890123');
      expect(result.source).toBe('query');
    });

    it('should extract API key from request body', async () => {
      const request = new Request('https://test.workers.dev/webhook', {
        method: 'POST',
        headers: {
          'Content-Type': 'application/json',
        },
        body: JSON.stringify({
          api_key: 'als_1234567890123456789012345678901234567890123',
          data: 'test',
        }),
      });
      
      const result = await extractAPIKey(request);
      
      expect(result.key).toBe('als_1234567890123456789012345678901234567890123');
      expect(result.source).toBe('body');
    });

    it('should throw error when no API key is found', async () => {
      const request = new Request('https://test.workers.dev/proxy/openai/models');
      
      await expect(extractAPIKey(request)).rejects.toThrow('API key is required');
    });

    it('should handle Basic auth with API key as username', async () => {
      const apiKey = 'als_1234567890123456789012345678901234567890123';
      const credentials = btoa(`${apiKey}:password`);
      
      const request = new Request('https://test.workers.dev/proxy/openai/models', {
        headers: {
          'Authorization': `Basic ${credentials}`,
        },
      });
      
      const result = await extractAPIKey(request);
      
      expect(result.key).toBe(apiKey);
      expect(result.source).toBe('authorization');
    });
  });

  describe('validateAPIKeyFormat', () => {
    it('should validate correct API Lens key format', () => {
      expect(validateAPIKeyFormat('als_1234567890123456789012345678901234567890123')).toBe(true);
    });

    it('should validate test key format', () => {
      expect(validateAPIKeyFormat('test_123456789012345678901234567890123456789')).toBe(true);
    });

    it('should reject invalid formats', () => {
      expect(validateAPIKeyFormat('invalid-key')).toBe(false);
      expect(validateAPIKeyFormat('als_short')).toBe(false);
      expect(validateAPIKeyFormat('sk_openai_key')).toBe(false);
      expect(validateAPIKeyFormat('')).toBe(false);
      expect(validateAPIKeyFormat(null as any)).toBe(false);
    });
  });

  describe('hashAPIKey', () => {
    it('should create consistent hash for same API key', async () => {
      const apiKey = 'als_1234567890123456789012345678901234567890123';
      
      const hash1 = await hashAPIKey(apiKey);
      const hash2 = await hashAPIKey(apiKey);
      
      expect(hash1).toBe(hash2);
      expect(hash1).toHaveLength(64); // SHA-256 hex string
    });

    it('should create different hashes for different API keys', async () => {
      const hash1 = await hashAPIKey('als_1234567890123456789012345678901234567890123');
      const hash2 = await hashAPIKey('als_9876543210987654321098765432109876543210987');
      
      expect(hash1).not.toBe(hash2);
    });
  });

  describe('createKeyPreview', () => {
    it('should create correct preview for normal API key', () => {
      const preview = createKeyPreview('als_1234567890123456789012345678901234567890123');
      expect(preview).toBe('als_1234...0123');
    });

    it('should return full key for short keys', () => {
      const shortKey = 'short';
      const preview = createKeyPreview(shortKey);
      expect(preview).toBe(shortKey);
    });
  });

  describe('validateIPWhitelist', () => {
    it('should allow any IP when no whitelist', () => {
      expect(validateIPWhitelist('192.168.1.1', [])).toBe(true);
    });

    it('should allow exact IP match', () => {
      expect(validateIPWhitelist('192.168.1.1', ['192.168.1.1', '10.0.0.1'])).toBe(true);
    });

    it('should reject non-matching IP', () => {
      expect(validateIPWhitelist('192.168.1.2', ['192.168.1.1', '10.0.0.1'])).toBe(false);
    });

    it('should handle CIDR notation (basic)', () => {
      expect(validateIPWhitelist('192.168.1.100', ['192.168.1.0/24'])).toBe(true);
      expect(validateIPWhitelist('192.168.2.100', ['192.168.1.0/24'])).toBe(false);
    });

    it('should handle wildcard patterns', () => {
      expect(validateIPWhitelist('192.168.1.100', ['192.168.1.*'])).toBe(true);
      expect(validateIPWhitelist('192.168.2.100', ['192.168.1.*'])).toBe(false);
    });
  });
});

describe('Authentication Flow', () => {
  let authenticator: Authenticator;
  let errorHandler: AuthErrorHandler;

  beforeAll(() => {
    authenticator = new Authenticator(mockEnv);
    errorHandler = new AuthErrorHandler(mockEnv);
  });

  describe('Authenticator', () => {
    it('should handle missing API key', async () => {
      const request = new Request('https://test.workers.dev/proxy/openai/models');
      
      const result = await authenticator.authenticateRequest(request);
      
      expect(result.success).toBe(false);
      expect(result.error?.code).toBe(AuthErrorCode.MISSING_API_KEY);
    });

    it('should handle invalid API key format', async () => {
      const request = new Request('https://test.workers.dev/proxy/openai/models', {
        headers: {
          'Authorization': 'Bearer invalid-key-format',
        },
      });
      
      const result = await authenticator.authenticateRequest(request);
      
      expect(result.success).toBe(false);
      expect(result.error?.code).toBe(AuthErrorCode.INVALID_API_KEY_FORMAT);
    });

    it('should handle backend not found', async () => {
      // Mock backend response for not found
      vi.spyOn(global, 'fetch').mockImplementation(async (url) => {
        if (url.toString().includes('/auth/verify-key')) {
          return new Response(null, { status: 404 });
        }
        return new Response('OK');
      });

      const request = new Request('https://test.workers.dev/proxy/openai/models', {
        headers: {
          'Authorization': 'Bearer als_1234567890123456789012345678901234567890123',
        },
      });
      
      const result = await authenticator.authenticateRequest(request);
      
      expect(result.success).toBe(false);
      expect(result.error?.code).toBe(AuthErrorCode.API_KEY_NOT_FOUND);
    });

    it('should handle successful authentication with backend', async () => {
      const mockCompany = {
        id: 'comp_123',
        name: 'Test Company',
        tier: CompanyTier.PROFESSIONAL,
        isActive: true,
        currentMonthRequests: 100,
        currentMonthCost: 5.50,
        createdAt: '2024-01-01T00:00:00Z',
        updatedAt: '2024-01-15T00:00:00Z',
        settings: {
          allowedVendors: ['openai', 'anthropic'],
          enableCostAlerts: true,
          enableUsageAlerts: true,
          requireVendorKeys: false,
          enableAnalytics: true,
          timezone: 'UTC',
        },
        rateLimits: {
          requestsPerMinute: 200,
          requestsPerHour: 5000,
          requestsPerDay: 50000,
        },
      };

      const mockAPIKey = {
        id: 'key_123',
        companyId: 'comp_123',
        name: 'Test API Key',
        keyHash: 'hashed-key',
        keyPreview: 'als_1234...0123',
        permissions: {
          allowedEndpoints: ['*'],
          allowedVendors: ['*'],
          canAccessAnalytics: true,
          canManageVendorKeys: true,
        },
        isActive: true,
        createdAt: '2024-01-01T00:00:00Z',
        usageCount: 50,
      };

      // Mock successful backend response
      vi.spyOn(global, 'fetch').mockImplementation(async (url) => {
        if (url.toString().includes('/auth/verify-key')) {
          return new Response(JSON.stringify({
            company: mockCompany,
            api_key: mockAPIKey,
          }), { status: 200 });
        }
        return new Response('OK');
      });

      const request = new Request('https://test.workers.dev/proxy/openai/models', {
        headers: {
          'Authorization': 'Bearer als_1234567890123456789012345678901234567890123',
        },
      });
      
      const result = await authenticator.authenticateRequest(request);
      
      expect(result.success).toBe(true);
      expect(result.company).toBeTruthy();
      expect(result.apiKey).toBeTruthy();
      expect(result.company?.name).toBe('Test Company');
    });

    it('should handle cache hit', async () => {
      const mockCachedData = {
        company: {
          id: 'comp_123',
          name: 'Cached Company',
          tier: CompanyTier.STARTER,
          isActive: true,
          currentMonthRequests: 50,
          currentMonthCost: 2.25,
          createdAt: '2024-01-01T00:00:00Z',
          updatedAt: '2024-01-15T00:00:00Z',
          settings: {
            allowedVendors: ['openai'],
            enableCostAlerts: true,
            enableUsageAlerts: true,
            requireVendorKeys: false,
            enableAnalytics: true,
            timezone: 'UTC',
          },
          rateLimits: {
            requestsPerMinute: 60,
            requestsPerHour: 1000,
            requestsPerDay: 10000,
          },
        },
        apiKey: {
          id: 'key_456',
          companyId: 'comp_123',
          name: 'Cached API Key',
          keyHash: 'cached-hash',
          keyPreview: 'als_5678...4567',
          permissions: {
            allowedEndpoints: ['*'],
            allowedVendors: ['openai'],
            canAccessAnalytics: true,
            canManageVendorKeys: false,
          },
          isActive: true,
          createdAt: '2024-01-01T00:00:00Z',
          usageCount: 25,
        },
      };

      // Mock cache hit
      mockEnv.CACHE_KV.get.mockResolvedValue(JSON.stringify({
        data: mockCachedData,
        timestamp: Date.now(),
        ttl: 300000, // 5 minutes
      }));

      const request = new Request('https://test.workers.dev/proxy/openai/models', {
        headers: {
          'Authorization': 'Bearer als_5678901234567890123456789012345678901234567',
        },
      });
      
      const result = await authenticator.authenticateRequest(request);
      
      expect(result.success).toBe(true);
      expect(result.cached).toBe(true);
      expect(result.company?.name).toBe('Cached Company');
    });
  });

  describe('Company Context', () => {
    it('should attach company context to request', () => {
      const mockCompany = {
        id: 'comp_123',
        name: 'Test Company',
        tier: CompanyTier.PROFESSIONAL,
        isActive: true,
        currentMonthRequests: 100,
        currentMonthCost: 5.50,
        createdAt: '2024-01-01T00:00:00Z',
        updatedAt: '2024-01-15T00:00:00Z',
        settings: {
          allowedVendors: ['openai', 'anthropic'],
          enableCostAlerts: true,
          enableUsageAlerts: true,
          requireVendorKeys: false,
          enableAnalytics: true,
          timezone: 'UTC',
        },
        rateLimits: {
          requestsPerMinute: 200,
          requestsPerHour: 5000,
          requestsPerDay: 50000,
        },
      };

      const mockAPIKey = {
        id: 'key_123',
        companyId: 'comp_123',
        name: 'Test API Key',
        keyHash: 'hashed-key',
        keyPreview: 'als_1234...0123',
        permissions: {
          allowedEndpoints: ['*'],
          allowedVendors: ['*'],
          canAccessAnalytics: true,
          canManageVendorKeys: true,
        },
        isActive: true,
        createdAt: '2024-01-01T00:00:00Z',
        usageCount: 50,
      };

      const request = new Request('https://test.workers.dev/proxy/openai/models', {
        headers: {
          'User-Agent': 'Test Client/1.0',
          'X-Forwarded-For': '192.168.1.1',
        },
      });

      const context = authenticator.attachCompanyContext(request, mockCompany, mockAPIKey);

      expect(context.company.id).toBe('comp_123');
      expect(context.apiKey.id).toBe('key_123');
      expect(context.ipAddress).toBeTruthy();
      expect(context.userAgent).toBe('Test Client/1.0');
      expect(context.requestId).toBeTruthy();
      expect(context.timestamp).toBeTruthy();
    });
  });

  describe('Permission Validation', () => {
    const mockCompany = {
      id: 'comp_123',
      name: 'Test Company',
      tier: CompanyTier.PROFESSIONAL,
      isActive: true,
      currentMonthRequests: 100,
      currentMonthCost: 5.50,
      createdAt: '2024-01-01T00:00:00Z',
      updatedAt: '2024-01-15T00:00:00Z',
      settings: {
        allowedVendors: ['openai', 'anthropic'],
        enableCostAlerts: true,
        enableUsageAlerts: true,
        requireVendorKeys: false,
        enableAnalytics: true,
        timezone: 'UTC',
      },
      rateLimits: {
        requestsPerMinute: 200,
        requestsPerHour: 5000,
        requestsPerDay: 50000,
      },
    };

    it('should reject suspended company', async () => {
      const suspendedCompany = { ...mockCompany, isActive: false };
      
      const result = (authenticator as any).validateCompanyAndKey(
        suspendedCompany,
        { isActive: true },
        new Request('https://test.workers.dev/')
      );

      expect(result?.code).toBe(AuthErrorCode.COMPANY_SUSPENDED);
    });

    it('should reject revoked API key', async () => {
      const result = (authenticator as any).validateCompanyAndKey(
        mockCompany,
        { isActive: false },
        new Request('https://test.workers.dev/')
      );

      expect(result?.code).toBe(AuthErrorCode.API_KEY_REVOKED);
    });

    it('should reject expired API key', async () => {
      const expiredKey = {
        isActive: true,
        expiresAt: '2023-12-31T23:59:59Z', // Past date
      };

      const result = (authenticator as any).validateCompanyAndKey(
        mockCompany,
        expiredKey,
        new Request('https://test.workers.dev/')
      );

      expect(result?.code).toBe(AuthErrorCode.API_KEY_EXPIRED);
    });

    it('should validate IP whitelist', async () => {
      const request = new Request('https://test.workers.dev/', {
        headers: { 'CF-Connecting-IP': '192.168.1.100' },
      });

      const restrictedKey = {
        isActive: true,
        ipWhitelist: ['192.168.1.1', '10.0.0.1'],
        permissions: { allowedEndpoints: ['*'], allowedVendors: ['*'] },
      };

      const result = (authenticator as any).validateCompanyAndKey(
        mockCompany,
        restrictedKey,
        request
      );

      expect(result?.code).toBe(AuthErrorCode.IP_NOT_ALLOWED);
    });

    it('should validate endpoint permissions', async () => {
      const request = new Request('https://test.workers.dev/admin/companies');

      const restrictedKey = {
        isActive: true,
        permissions: {
          allowedEndpoints: ['/proxy/*'],
          allowedVendors: ['*'],
        },
      };

      const result = (authenticator as any).validateCompanyAndKey(
        mockCompany,
        restrictedKey,
        request
      );

      expect(result?.code).toBe(AuthErrorCode.ENDPOINT_NOT_ALLOWED);
    });

    it('should validate vendor permissions', async () => {
      const request = new Request('https://test.workers.dev/proxy/unsupported-vendor/test');

      const restrictedKey = {
        isActive: true,
        permissions: {
          allowedEndpoints: ['*'],
          allowedVendors: ['openai', 'anthropic'],
        },
      };

      const result = (authenticator as any).validateCompanyAndKey(
        mockCompany,
        restrictedKey,
        request
      );

      expect(result?.code).toBe(AuthErrorCode.VENDOR_NOT_ALLOWED);
    });
  });
});

describe('Error Handling', () => {
  let errorHandler: AuthErrorHandler;

  beforeAll(() => {
    errorHandler = new AuthErrorHandler(mockEnv);
  });

  describe('AuthErrorHandler', () => {
    it('should create proper error response for missing API key', () => {
      const error = {
        code: AuthErrorCode.MISSING_API_KEY,
        message: 'API key is required',
        retryable: false,
      };

      const response = (errorHandler as any).createErrorResponse(
        error,
        'req_123',
        '2024-01-15T10:30:00Z'
      );

      expect(response.error).toBe('Missing API Key');
      expect(response.code).toBe(AuthErrorCode.MISSING_API_KEY);
      expect(response.requestId).toBe('req_123');
      expect(response.documentation).toContain('authentication');
    });

    it('should set correct status codes', () => {
      const testCases = [
        { code: AuthErrorCode.MISSING_API_KEY, expectedStatus: 400 },
        { code: AuthErrorCode.API_KEY_NOT_FOUND, expectedStatus: 401 },
        { code: AuthErrorCode.COMPANY_SUSPENDED, expectedStatus: 403 },
        { code: AuthErrorCode.COMPANY_NOT_FOUND, expectedStatus: 404 },
        { code: AuthErrorCode.QUOTA_EXCEEDED, expectedStatus: 429 },
        { code: AuthErrorCode.BACKEND_ERROR, expectedStatus: 502 },
      ];

      for (const { code, expectedStatus } of testCases) {
        const status = (errorHandler as any).getStatusCode(code);
        expect(status).toBe(expectedStatus);
      }
    });

    it('should include retry information for retryable errors', () => {
      const retryableError = {
        code: AuthErrorCode.BACKEND_ERROR,
        message: 'Backend service unavailable',
        retryable: true,
      };

      const response = (errorHandler as any).createErrorResponse(
        retryableError,
        'req_123',
        '2024-01-15T10:30:00Z'
      );

      expect(response.retryAfter).toBeTruthy();
      expect(typeof response.retryAfter).toBe('number');
    });
  });
});

describe('Cache Operations', () => {
  it('should handle cache get operations', async () => {
    const authenticator = new Authenticator(mockEnv);
    const cache = (authenticator as any).cache;

    // Mock cache miss
    mockEnv.CACHE_KV.get.mockResolvedValue(null);

    const result = await cache.getCachedCompany('test-hash');
    expect(result).toBeNull();
  });

  it('should handle cache set operations', async () => {
    const authenticator = new Authenticator(mockEnv);
    const cache = (authenticator as any).cache;

    const mockData = {
      company: { id: 'comp_123', name: 'Test' },
      apiKey: { id: 'key_123', name: 'Test Key' },
    };

    mockEnv.CACHE_KV.put.mockResolvedValue(undefined);

    await expect(cache.setCachedCompany('test-hash', mockData.company, mockData.apiKey)).resolves.not.toThrow();
  });
});
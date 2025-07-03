/**
 * API Lens Workers Proxy - Authentication Integration
 * 
 * Main authentication interface for the Workers proxy
 * This file integrates the new modular authentication system
 */

import { Context } from 'hono';
import {
  Env,
  HonoVariables,
  Company,
  APIKey,
  CompanyContext,
  AuthenticationResult,
  AuthErrorCode,
} from './types';

/**
 * Main authentication middleware
 */
export async function authenticate(c: Context<{ Bindings: Env; Variables: HonoVariables }>): Promise<{
  company: Company;
  apiKey: APIKey;
  context: CompanyContext;
}> {
  try {
    const apiKey = c.req.header('X-API-Key') || c.req.header('Authorization')?.replace('Bearer ', '');
    
    if (!apiKey) {
      throw new Response(JSON.stringify({
        error: 'MISSING_API_KEY',
        message: 'API key is required'
      }), { status: 401 });
    }
    
    // Mock authentication result for now - in real implementation this would
    // call the backend API to validate the API key
    const result = await authenticateAPIKey(c.env, apiKey);
    
    if (!result.success) {
      throw new Response(JSON.stringify({
        error: result.error?.code || 'INVALID_API_KEY',
        message: result.error?.message || 'Invalid API key'
      }), { status: result.error?.statusCode || 401 });
    }
    
    // Create company context
    const context: CompanyContext = {
      company: result.company!,
      apiKey: result.apiKey!,
      effectiveRateLimit: {
        requestsPerMinute: 100,
        requestsPerHour: 1000,
        requestsPerDay: 10000
      },
      effectiveCostLimit: {
        costPerMinute: 1.0,
        costPerHour: 10.0,
        costPerDay: 100.0,
        costPerMonth: 1000.0
      },
      features: {
        multiUserSupport: true,
        customModels: false,
        webhooks: true,
        analytics: true,
        prioritySupport: false,
        customRateLimits: false,
        bulkRequests: false,
        realTimeMetrics: true
      },
      usage: {
        currentMinuteRequests: 0,
        currentHourRequests: 0,
        currentDayRequests: 0,
        currentMinuteCost: 0,
        currentHourCost: 0,
        currentDayCost: 0,
        currentMonthCost: 0
      },
      permissions: []
    };
    
    // Store in Hono context for later use
    c.set('company', result.company);
    c.set('apiKey', result.apiKey);
    c.set('companyContext', context);
    c.set('authCached', result.cached);
    c.set('authResponseTime', result.responseTime);
    
    return {
      company: result.company!,
      apiKey: result.apiKey!,
      context,
    };
    
  } catch (error) {
    if (error instanceof Response) {
      throw error; // Already formatted error response
    }
    
    // Handle unexpected errors
    throw new Response(JSON.stringify({
      error: 'BACKEND_ERROR',
      message: 'Internal authentication error'
    }), { status: 500 });
  }
}

/**
 * Get authentication result from context
 */
export function getAuthResult(c: Context<{ Bindings: Env; Variables: HonoVariables }>): {
  company: Company;
  apiKey: APIKey;
  context: CompanyContext;
} | null {
  const company = c.get('company');
  const apiKey = c.get('apiKey');
  const context = c.get('companyContext');
  
  if (company && apiKey && context) {
    return { company, apiKey, context };
  }
  
  return null;
}

/**
 * Check if request is authenticated
 */
export function isAuthenticated(c: Context<{ Bindings: Env; Variables: HonoVariables }>): boolean {
  return !!(c.get('company') && c.get('apiKey'));
}

/**
 * Get company from context
 */
export function getCompany(c: Context<{ Bindings: Env; Variables: HonoVariables }>): Company | null {
  return c.get('company') || null;
}

/**
 * Get API key from context
 */
export function getAPIKey(c: Context<{ Bindings: Env; Variables: HonoVariables }>): APIKey | null {
  return c.get('apiKey') || null;
}

/**
 * Get company context from context
 */
export function getCompanyContext(c: Context<{ Bindings: Env; Variables: HonoVariables }>): CompanyContext | null {
  return c.get('companyContext') || null;
}

/**
 * Check if authentication was cached
 */
export function wasCached(c: Context<{ Bindings: Env; Variables: HonoVariables }>): boolean {
  return c.get('authCached') === true;
}

/**
 * Get authentication response time
 */
export function getAuthResponseTime(c: Context<{ Bindings: Env; Variables: HonoVariables }>): number {
  return c.get('authResponseTime') || 0;
}

/**
 * Validate vendor access for authenticated company
 */
export function validateVendorAccess(c: Context<{ Bindings: Env; Variables: HonoVariables }>, _vendor: string): boolean {
  const company = getCompany(c);
  const apiKey = getAPIKey(c);
  
  if (!company || !apiKey) {
    return false;
  }
  
  // For now, allow all vendors - this would be implemented based on company settings
  return true;
}

/**
 * Check quota limits for authenticated company
 */
export async function checkQuota(
  c: Context<{ Bindings: Env; Variables: HonoVariables }>,
  estimatedCost: number = 0
): Promise<{ hasQuota: boolean; remainingBudget?: number; message?: string }> {
  const company = getCompany(c);
  
  if (!company) {
    return { hasQuota: false, message: 'No company context' };
  }
  
  // Check monthly budget limit
  if (company.monthlyBudgetUsd) {
    const remainingBudget = company.monthlyBudgetUsd - 0; // Would need to track current usage
    
    if (remainingBudget <= 0) {
      return {
        hasQuota: false,
        remainingBudget: 0,
        message: 'Monthly budget limit exceeded',
      };
    }
    
    if (estimatedCost > remainingBudget) {
      return {
        hasQuota: false,
        remainingBudget,
        message: 'Request would exceed remaining budget',
      };
    }
    
    return {
      hasQuota: true,
      remainingBudget,
    };
  }
  
  // Check monthly quota
  if (company.monthlyQuota) {
    // Would need to track current usage
    const currentMonthRequests = 0;
    if (currentMonthRequests >= company.monthlyQuota) {
      return {
        hasQuota: false,
        message: 'Monthly request limit exceeded',
      };
    }
  }
  
  return { hasQuota: true };
}

/**
 * Invalidate authentication cache for current API key
 */
export async function invalidateAuthCache(c: Context<{ Bindings: Env; Variables: HonoVariables }>): Promise<void> {
  const apiKey = getAPIKey(c);
  
  if (apiKey) {
    // Invalidate cache entry for this API key
    await c.env.CACHE_KV.delete(`auth:${apiKey.keyHash}`);
  }
}

/**
 * Get authentication statistics
 */
export async function getAuthStats(_c: Context<{ Bindings: Env; Variables: HonoVariables }>): Promise<any> {
  // Return basic auth stats - in real implementation this would track metrics
  return {
    totalRequests: 0,
    successfulAuths: 0,
    failedAuths: 0,
    cacheHitRate: 0
  };
}

// Helper function to authenticate API key
async function authenticateAPIKey(env: Env, apiKey: string): Promise<AuthenticationResult> {
  try {
    // Check cache first
    const cacheKey = `auth:${apiKey}`;
    const cached = await env.CACHE_KV.get(cacheKey);
    
    if (cached) {
      const result = JSON.parse(cached);
      return { ...result, cached: true, responseTime: 0 };
    }
    
    // Mock authentication - in real implementation this would call the backend API
    const mockCompany: Company = {
      id: 'comp_123',
      name: 'Test Company',
      slug: 'test-company',
      tier: 'standard',
      isActive: true,
      contactEmail: 'test@example.com',
      createdAt: new Date().toISOString(),
      updatedAt: new Date().toISOString()
    };
    
    const mockAPIKey: APIKey = {
      id: 'key_123',
      companyId: 'comp_123',
      name: 'Test API Key',
      keyHash: apiKey,
      keyPrefix: apiKey.substring(0, 8),
      environment: 'production',
      scopes: ['proxy:read', 'proxy:write'],
      isActive: true,
      createdAt: new Date().toISOString()
    };
    
    const result: AuthenticationResult = {
      success: true,
      company: mockCompany,
      apiKey: mockAPIKey,
      cached: false,
      responseTime: 10
    };
    
    // Cache the result
    await env.CACHE_KV.put(cacheKey, JSON.stringify(result), { expirationTtl: 300 });
    
    return result;
    
  } catch (error) {
    return {
      success: false,
      cached: false,
      responseTime: 0,
      error: {
        code: AuthErrorCode.BACKEND_ERROR,
        message: 'Authentication failed',
        statusCode: 500
      }
    };
  }
}

// Re-export types for convenience
export type {
  Company,
  APIKey,
  CompanyContext,
  AuthenticationResult,
  AuthErrorCode,
} from './types';
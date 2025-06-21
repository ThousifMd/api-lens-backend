/**
 * API Lens Workers Proxy - Authentication Integration
 * 
 * Main authentication interface for the Workers proxy
 * This file integrates the new modular authentication system
 */

import { Context } from 'hono';
import { Env } from './index';
import {
  Authenticator,
  AuthErrorHandler,
  AuthenticationResult,
  Company,
  APIKey,
  CompanyContext,
  AuthErrorCode,
} from './auth/index';

/**
 * Main authentication middleware
 */
export async function authenticate(c: Context<{ Bindings: Env }>): Promise<{
  company: Company;
  apiKey: APIKey;
  context: CompanyContext;
}> {
  const authenticator = new Authenticator(c.env);
  const errorHandler = new AuthErrorHandler(c.env);
  
  try {
    const result = await authenticator.authenticateRequest(c.req.raw);
    
    if (!result.success) {
      throw await errorHandler.handleAuthError(c, result.error!);
    }
    
    // Attach company context to request
    const context = authenticator.attachCompanyContext(
      c.req.raw,
      result.company!,
      result.apiKey!
    );
    
    // Store in Hono context for later use
    c.set('company', result.company);
    c.set('apiKey', result.apiKey);
    c.set('companyContext', context);
    c.set('authCached', result.cached);
    c.set('authResponseTime', result.responseTime);
    
    // Update usage statistics (async)
    authenticator.updateAPIKeyUsage(result.apiKey!.keyHash).catch(() => {});
    
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
    const authError = {
      code: AuthErrorCode.BACKEND_ERROR,
      message: 'Internal authentication error',
      retryable: true,
    };
    
    throw await errorHandler.handleAuthError(c, authError);
  }
}

/**
 * Get authentication result from context
 */
export function getAuthResult(c: Context): {
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
export function isAuthenticated(c: Context): boolean {
  return !!(c.get('company') && c.get('apiKey'));
}

/**
 * Get company from context
 */
export function getCompany(c: Context): Company | null {
  return c.get('company') || null;
}

/**
 * Get API key from context
 */
export function getAPIKey(c: Context): APIKey | null {
  return c.get('apiKey') || null;
}

/**
 * Get company context from context
 */
export function getCompanyContext(c: Context): CompanyContext | null {
  return c.get('companyContext') || null;
}

/**
 * Check if authentication was cached
 */
export function wasCached(c: Context): boolean {
  return c.get('authCached') === true;
}

/**
 * Get authentication response time
 */
export function getAuthResponseTime(c: Context): number {
  return c.get('authResponseTime') || 0;
}

/**
 * Validate vendor access for authenticated company
 */
export function validateVendorAccess(c: Context, vendor: string): boolean {
  const company = getCompany(c);
  const apiKey = getAPIKey(c);
  
  if (!company || !apiKey) {
    return false;
  }
  
  // Check company level vendor restrictions
  if (company.settings.allowedVendors && company.settings.allowedVendors.length > 0) {
    if (!company.settings.allowedVendors.includes('*') && !company.settings.allowedVendors.includes(vendor)) {
      return false;
    }
  }
  
  // Check API key level vendor restrictions
  if (apiKey.permissions.allowedVendors && apiKey.permissions.allowedVendors.length > 0) {
    if (!apiKey.permissions.allowedVendors.includes('*') && !apiKey.permissions.allowedVendors.includes(vendor)) {
      return false;
    }
  }
  
  return true;
}

/**
 * Check quota limits for authenticated company
 */
export async function checkQuota(
  c: Context<{ Bindings: Env }>,
  estimatedCost: number = 0
): Promise<{ hasQuota: boolean; remainingBudget?: number; message?: string }> {
  const company = getCompany(c);
  
  if (!company) {
    return { hasQuota: false, message: 'No company context' };
  }
  
  // Check monthly budget limit
  if (company.monthlyBudgetLimit) {
    const remainingBudget = company.monthlyBudgetLimit - company.currentMonthCost;
    
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
  
  // Check monthly request limit
  if (company.monthlyRequestLimit) {
    if (company.currentMonthRequests >= company.monthlyRequestLimit) {
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
export async function invalidateAuthCache(c: Context<{ Bindings: Env }>): Promise<void> {
  const apiKey = getAPIKey(c);
  
  if (apiKey) {
    const authenticator = new Authenticator(c.env);
    await authenticator.invalidateCache(apiKey.keyHash);
  }
}

/**
 * Get authentication statistics
 */
export async function getAuthStats(c: Context<{ Bindings: Env }>): Promise<any> {
  const authenticator = new Authenticator(c.env);
  return authenticator.getAuthStats();
}

// Re-export types for convenience
export type {
  Company,
  APIKey,
  CompanyContext,
  AuthenticationResult,
  AuthenticationError,
} from './auth/index';

export {
  CompanyTier,
  AuthErrorCode,
} from './auth/index';
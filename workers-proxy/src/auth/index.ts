/**
 * API Lens Workers Proxy - Authentication Module
 * 
 * Main exports for the authentication system
 */

// Export main authenticator class
export { Authenticator } from './authenticator';

// Export individual components
export { AuthCache } from './cache';
export { BackendAuth } from './backend';
export { AuthErrorHandler } from './errors';

// Export utility functions
export {
  extractAPIKey,
  validateAPIKeyFormat,
  createKeyPreview,
  hashAPIKey,
  validateAPIKeySecurity,
  extractAuthContext,
  validateIPWhitelist,
} from './extractor';

// Export types
export type {
  Company,
  APIKey,
  CompanyContext,
  AuthenticationResult,
  AuthenticationError,
  CompanySettings,
  RateLimits,
  APIKeyPermissions,
  RedisAuthCache,
  CacheEntry,
  AuthMetrics,
  ExtractedAPIKey,
} from './types';

export {
  CompanyTier,
  AuthErrorCode,
} from './types';

// Export error response type
export type { AuthErrorResponse } from './errors';

/**
 * Main authentication function for use in middleware
 */
export async function authenticateRequest(
  request: Request,
  env: any
): Promise<AuthenticationResult> {
  const authenticator = new Authenticator(env);
  return authenticator.authenticateRequest(request);
}

/**
 * Get company context from authenticated request
 */
export function getCompanyContext(request: Request): CompanyContext | null {
  return (request as any).apiLensContext || null;
}

/**
 * Attach company context to request
 */
export function attachCompanyContext(
  request: Request,
  company: Company,
  apiKey: APIKey
): CompanyContext {
  const authenticator = new Authenticator({} as any);
  return authenticator.attachCompanyContext(request, company, apiKey);
}
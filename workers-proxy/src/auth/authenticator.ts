/**
 * API Lens Workers Proxy - Main Authentication Functions
 * 
 * Core authentication functions with company resolution and context attachment
 */

import { 
  Company, 
  APIKey, 
  CompanyContext,
  AuthenticationResult, 
  AuthenticationError, 
  AuthErrorCode 
} from './types';
import { Env } from '../index';
import { extractAPIKey, validateAPIKeySecurity, extractAuthContext, validateIPWhitelist } from './extractor';
import { AuthCache } from './cache';
import { BackendAuth } from './backend';

export class Authenticator {
  private cache: AuthCache;
  private backend: BackendAuth;
  private env: Env;
  
  constructor(env: Env) {
    this.env = env;
    this.cache = new AuthCache(env);
    this.backend = new BackendAuth(env);
  }
  
  /**
   * Main authentication function - validates API key and returns company context
   */
  async authenticateRequest(request: Request): Promise<AuthenticationResult> {
    const startTime = Date.now();
    const requestId = crypto.randomUUID();
    
    try {
      // Extract API key from request
      const extractedKey = await extractAPIKey(request);
      
      // Validate API key security
      const securityError = validateAPIKeySecurity(extractedKey.key, request);
      if (securityError) {
        return {
          success: false,
          error: securityError,
          cached: false,
          responseTime: Date.now() - startTime,
        };
      }
      
      // Get company from cache first
      let company: Company;
      let apiKey: APIKey;
      let cached = false;
      
      const cachedData = await this.getCachedCompany(extractedKey.hash);
      if (cachedData) {
        company = cachedData.company;
        apiKey = cachedData.apiKey;
        cached = true;
      } else {
        // Cache miss - get from backend
        const backendData = await this.getCompanyFromBackend(extractedKey.hash);
        if (!backendData) {
          return {
            success: false,
            error: {
              code: AuthErrorCode.API_KEY_NOT_FOUND,
              message: 'API key not found',
              retryable: false,
            },
            cached: false,
            responseTime: Date.now() - startTime,
          };
        }
        
        company = backendData.company;
        apiKey = backendData.apiKey;
        
        // Cache the result
        await this.cache.setCachedCompany(extractedKey.hash, company, apiKey, 300);
      }
      
      // Validate company and API key status
      const validationError = this.validateCompanyAndKey(company, apiKey, request);
      if (validationError) {
        return {
          success: false,
          error: validationError,
          cached,
          responseTime: Date.now() - startTime,
        };
      }
      
      // Log successful authentication (async)
      this.backend.logAuthEvent(
        extractedKey.hash,
        company.id,
        true,
        undefined,
        {
          source: extractedKey.source,
          cached,
          responseTime: Date.now() - startTime,
        }
      ).catch(() => {}); // Fire and forget
      
      return {
        success: true,
        company,
        apiKey,
        cached,
        responseTime: Date.now() - startTime,
      };
      
    } catch (error) {
      const responseTime = Date.now() - startTime;
      
      if (error instanceof AuthenticationError) {
        // Log authentication failure (async)
        this.backend.logAuthEvent(
          'unknown',
          'unknown',
          false,
          error.message,
          { responseTime }
        ).catch(() => {});
        
        return {
          success: false,
          error,
          cached: false,
          responseTime,
        };
      }
      
      console.error('Unexpected authentication error:', error);
      
      return {
        success: false,
        error: {
          code: AuthErrorCode.BACKEND_ERROR,
          message: 'Internal authentication error',
          retryable: true,
        },
        cached: false,
        responseTime,
      };
    }
  }
  
  /**
   * Get cached company data
   */
  async getCachedCompany(apiKeyHash: string): Promise<{ company: Company; apiKey: APIKey } | null> {
    return this.cache.getCachedCompany(apiKeyHash);
  }
  
  /**
   * Get company data from backend
   */
  async getCompanyFromBackend(apiKeyHash: string): Promise<{ company: Company; apiKey: APIKey } | null> {
    return this.backend.getCompanyFromBackend(apiKeyHash);
  }
  
  /**
   * Attach company context to request
   */
  attachCompanyContext(request: Request, company: Company, apiKey: APIKey): CompanyContext {
    const authContext = extractAuthContext(request);
    const requestId = crypto.randomUUID();
    
    const context: CompanyContext = {
      company,
      apiKey,
      requestId,
      ipAddress: authContext.ipAddress,
      userAgent: authContext.userAgent,
      timestamp: new Date().toISOString(),
      region: (request as any).cf?.region,
      country: (request as any).cf?.country,
    };
    
    // Attach context to request (using custom property)
    (request as any).apiLensContext = context;
    
    return context;
  }
  
  /**
   * Get company context from request
   */
  getCompanyContext(request: Request): CompanyContext | null {
    return (request as any).apiLensContext || null;
  }
  
  /**
   * Validate company and API key status
   */
  private validateCompanyAndKey(company: Company, apiKey: APIKey, request: Request): AuthenticationError | null {
    // Check if company is active
    if (!company.isActive) {
      return {
        code: AuthErrorCode.COMPANY_SUSPENDED,
        message: 'Company account is suspended',
        retryable: false,
      };
    }
    
    // Check if API key is active
    if (!apiKey.isActive) {
      return {
        code: AuthErrorCode.API_KEY_REVOKED,
        message: 'API key has been revoked',
        retryable: false,
      };
    }
    
    // Check API key expiration
    if (apiKey.expiresAt) {
      const expirationDate = new Date(apiKey.expiresAt);
      if (expirationDate < new Date()) {
        return {
          code: AuthErrorCode.API_KEY_EXPIRED,
          message: 'API key has expired',
          retryable: false,
        };
      }
    }
    
    // Check IP whitelist
    if (apiKey.ipWhitelist && apiKey.ipWhitelist.length > 0) {
      const authContext = extractAuthContext(request);
      if (!validateIPWhitelist(authContext.ipAddress, apiKey.ipWhitelist)) {
        return {
          code: AuthErrorCode.IP_NOT_ALLOWED,
          message: 'Request IP address is not allowed',
          details: { ipAddress: authContext.ipAddress },
          retryable: false,
        };
      }
    }
    
    // Check User-Agent restriction
    if (apiKey.userAgent) {
      const requestUserAgent = request.headers.get('User-Agent') || '';
      if (!requestUserAgent.includes(apiKey.userAgent)) {
        return {
          code: AuthErrorCode.USER_AGENT_NOT_ALLOWED,
          message: 'Request User-Agent is not allowed',
          retryable: false,
        };
      }
    }
    
    // Check endpoint permissions
    const url = new URL(request.url);
    const endpoint = url.pathname;
    
    if (!this.isEndpointAllowed(endpoint, apiKey.permissions.allowedEndpoints)) {
      return {
        code: AuthErrorCode.ENDPOINT_NOT_ALLOWED,
        message: `Access to endpoint '${endpoint}' is not allowed`,
        details: { endpoint, allowedEndpoints: apiKey.permissions.allowedEndpoints },
        retryable: false,
      };
    }
    
    // Check vendor permissions for proxy requests
    if (endpoint.startsWith('/proxy/')) {
      const vendor = endpoint.split('/')[2];
      if (vendor && !this.isVendorAllowed(vendor, apiKey.permissions.allowedVendors, company.settings.allowedVendors)) {
        return {
          code: AuthErrorCode.VENDOR_NOT_ALLOWED,
          message: `Access to vendor '${vendor}' is not allowed`,
          details: { vendor, allowedVendors: apiKey.permissions.allowedVendors },
          retryable: false,
        };
      }
    }
    
    return null; // All validations passed
  }
  
  /**
   * Check if endpoint is allowed
   */
  private isEndpointAllowed(endpoint: string, allowedEndpoints: string[]): boolean {
    // If no restrictions, allow all
    if (!allowedEndpoints || allowedEndpoints.length === 0) {
      return true;
    }
    
    // Check for wildcard permission
    if (allowedEndpoints.includes('*')) {
      return true;
    }
    
    // Check exact matches and patterns
    for (const allowed of allowedEndpoints) {
      if (allowed === endpoint) {
        return true;
      }
      
      // Support wildcard patterns
      if (allowed.endsWith('*')) {
        const prefix = allowed.slice(0, -1);
        if (endpoint.startsWith(prefix)) {
          return true;
        }
      }
      
      // Support regex patterns (if surrounded by forward slashes)
      if (allowed.startsWith('/') && allowed.endsWith('/')) {
        try {
          const regex = new RegExp(allowed.slice(1, -1));
          if (regex.test(endpoint)) {
            return true;
          }
        } catch (error) {
          console.warn(`Invalid regex pattern in allowedEndpoints: ${allowed}`);
        }
      }
    }
    
    return false;
  }
  
  /**
   * Check if vendor is allowed
   */
  private isVendorAllowed(vendor: string, apiKeyVendors: string[], companyVendors: string[]): boolean {
    // Check API key level permissions first
    if (apiKeyVendors && apiKeyVendors.length > 0) {
      if (!apiKeyVendors.includes('*') && !apiKeyVendors.includes(vendor)) {
        return false;
      }
    }
    
    // Check company level permissions
    if (companyVendors && companyVendors.length > 0) {
      if (!companyVendors.includes('*') && !companyVendors.includes(vendor)) {
        return false;
      }
    }
    
    return true;
  }
  
  /**
   * Update API key usage statistics
   */
  async updateAPIKeyUsage(apiKeyHash: string): Promise<void> {
    try {
      // Fire and forget - update usage in background
      fetch(`${this.env.API_LENS_BACKEND_URL}/auth/usage`, {
        method: 'POST',
        headers: {
          'Authorization': `Bearer ${this.env.API_LENS_BACKEND_TOKEN}`,
          'Content-Type': 'application/json',
        },
        body: JSON.stringify({
          api_key_hash: apiKeyHash,
          timestamp: new Date().toISOString(),
        }),
      }).catch(error => {
        console.error('Failed to update API key usage:', error);
      });
      
    } catch (error) {
      console.error('Error updating API key usage:', error);
    }
  }
  
  /**
   * Invalidate authentication cache for API key
   */
  async invalidateCache(apiKeyHash: string): Promise<void> {
    await this.cache.invalidateCachedCompany(apiKeyHash);
  }
  
  /**
   * Get authentication statistics
   */
  async getAuthStats(): Promise<{
    cacheStats: any;
    backendHealth: any;
  }> {
    const [cacheStats, backendHealth] = await Promise.all([
      this.cache.getCacheStats(),
      this.backend.healthCheck(),
    ]);
    
    return {
      cacheStats,
      backendHealth,
    };
  }
}
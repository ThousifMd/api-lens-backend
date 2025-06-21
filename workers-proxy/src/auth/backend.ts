/**
 * API Lens Workers Proxy - Backend Authentication
 * 
 * Authentication with Python backend API fallback
 */

import { Company, APIKey, AuthErrorCode, AuthenticationError } from './types';
import { Env } from '../index';

export class BackendAuth {
  private env: Env;
  private baseUrl: string;
  private authToken: string;
  
  constructor(env: Env) {
    this.env = env;
    this.baseUrl = env.API_LENS_BACKEND_URL;
    this.authToken = env.API_LENS_BACKEND_TOKEN;
  }
  
  /**
   * Get company data from backend API
   */
  async getCompanyFromBackend(apiKeyHash: string): Promise<{ company: Company; apiKey: APIKey } | null> {
    const startTime = Date.now();
    const requestId = crypto.randomUUID();
    
    try {
      const response = await fetch(`${this.baseUrl}/auth/verify-key`, {
        method: 'POST',
        headers: {
          'Authorization': `Bearer ${this.authToken}`,
          'Content-Type': 'application/json',
          'X-Request-ID': requestId,
          'User-Agent': 'API-Lens-Workers-Proxy/1.0.0',
        },
        body: JSON.stringify({
          api_key_hash: apiKeyHash,
          include_company: true,
          include_permissions: true,
        }),
      });
      
      const responseTime = Date.now() - startTime;
      
      if (response.status === 404) {
        console.log(`Backend: API key not found (${responseTime}ms)`);
        return null;
      }
      
      if (response.status === 401) {
        throw new AuthenticationError({
          code: AuthErrorCode.API_KEY_NOT_FOUND,
          message: 'API key not found or invalid',
          retryable: false,
        });
      }
      
      if (response.status === 403) {
        throw new AuthenticationError({
          code: AuthErrorCode.API_KEY_REVOKED,
          message: 'API key has been revoked',
          retryable: false,
        });
      }
      
      if (!response.ok) {
        throw new AuthenticationError({
          code: AuthErrorCode.BACKEND_ERROR,
          message: `Backend authentication error: ${response.status}`,
          retryable: response.status >= 500,
        });
      }
      
      const data = await response.json();
      console.log(`Backend auth success for ${apiKeyHash.slice(0, 8)}... (${responseTime}ms)`);
      
      return {
        company: this.transformBackendCompany(data.company),
        apiKey: this.transformBackendAPIKey(data.api_key),
      };
      
    } catch (error) {
      const responseTime = Date.now() - startTime;
      
      if (error instanceof AuthenticationError) {
        throw error;
      }
      
      console.error(`Backend auth error (${responseTime}ms):`, error);
      
      throw new AuthenticationError({
        code: AuthErrorCode.BACKEND_ERROR,
        message: 'Failed to authenticate with backend service',
        details: { error: error.message, responseTime },
        retryable: true,
      });
    }
  }
  
  /**
   * Verify API key with backend (lightweight check)
   */
  async verifyAPIKey(apiKey: string): Promise<{ valid: boolean; companyId?: string; reason?: string }> {
    const startTime = Date.now();
    const requestId = crypto.randomUUID();
    
    try {
      const response = await fetch(`${this.baseUrl}/auth/verify`, {
        method: 'GET',
        headers: {
          'Authorization': `Bearer ${apiKey}`,
          'X-Request-ID': requestId,
          'User-Agent': 'API-Lens-Workers-Proxy/1.0.0',
        },
      });
      
      const responseTime = Date.now() - startTime;
      
      if (response.ok) {
        const data = await response.json();
        console.log(`API key verification success (${responseTime}ms)`);
        return {
          valid: true,
          companyId: data.company_id,
        };
      }
      
      let reason = 'Unknown error';
      if (response.status === 401) {
        reason = 'Invalid or expired API key';
      } else if (response.status === 403) {
        reason = 'API key revoked or insufficient permissions';
      } else if (response.status >= 500) {
        reason = 'Backend service error';
      }
      
      console.log(`API key verification failed: ${reason} (${responseTime}ms)`);
      return {
        valid: false,
        reason,
      };
      
    } catch (error) {
      const responseTime = Date.now() - startTime;
      console.error(`API key verification error (${responseTime}ms):`, error);
      
      return {
        valid: false,
        reason: 'Network error or backend unavailable',
      };
    }
  }
  
  /**
   * Get company details by ID
   */
  async getCompanyById(companyId: string): Promise<Company | null> {
    const startTime = Date.now();
    const requestId = crypto.randomUUID();
    
    try {
      const response = await fetch(`${this.baseUrl}/companies/${companyId}`, {
        method: 'GET',
        headers: {
          'Authorization': `Bearer ${this.authToken}`,
          'X-Request-ID': requestId,
          'User-Agent': 'API-Lens-Workers-Proxy/1.0.0',
        },
      });
      
      const responseTime = Date.now() - startTime;
      
      if (response.status === 404) {
        console.log(`Company not found: ${companyId} (${responseTime}ms)`);
        return null;
      }
      
      if (!response.ok) {
        throw new Error(`Failed to get company: ${response.status}`);
      }
      
      const data = await response.json();
      console.log(`Got company details for ${companyId} (${responseTime}ms)`);
      
      return this.transformBackendCompany(data);
      
    } catch (error) {
      const responseTime = Date.now() - startTime;
      console.error(`Error getting company ${companyId} (${responseTime}ms):`, error);
      return null;
    }
  }
  
  /**
   * Log authentication event to backend
   */
  async logAuthEvent(
    apiKeyHash: string,
    companyId: string,
    success: boolean,
    error?: string,
    metadata?: Record<string, any>
  ): Promise<void> {
    try {
      // Fire and forget - don't wait for response
      fetch(`${this.baseUrl}/auth/events`, {
        method: 'POST',
        headers: {
          'Authorization': `Bearer ${this.authToken}`,
          'Content-Type': 'application/json',
        },
        body: JSON.stringify({
          api_key_hash: apiKeyHash,
          company_id: companyId,
          success,
          error,
          metadata,
          timestamp: new Date().toISOString(),
        }),
      }).catch(error => {
        console.error('Failed to log auth event:', error);
      });
      
    } catch (error) {
      console.error('Error logging auth event:', error);
    }
  }
  
  /**
   * Transform backend company data to our format
   */
  private transformBackendCompany(backendCompany: any): Company {
    return {
      id: backendCompany.id,
      name: backendCompany.name,
      tier: backendCompany.tier,
      isActive: backendCompany.is_active,
      contactEmail: backendCompany.contact_email,
      webhookUrl: backendCompany.webhook_url,
      currentMonthRequests: backendCompany.current_month_requests || 0,
      currentMonthCost: backendCompany.current_month_cost || 0,
      monthlyBudgetLimit: backendCompany.monthly_budget_limit,
      monthlyRequestLimit: backendCompany.monthly_request_limit,
      createdAt: backendCompany.created_at,
      updatedAt: backendCompany.updated_at,
      settings: {
        allowedVendors: backendCompany.settings?.allowed_vendors || ['openai', 'anthropic', 'google'],
        defaultModel: backendCompany.settings?.default_model,
        maxTokensPerRequest: backendCompany.settings?.max_tokens_per_request,
        enableCostAlerts: backendCompany.settings?.enable_cost_alerts !== false,
        enableUsageAlerts: backendCompany.settings?.enable_usage_alerts !== false,
        requireVendorKeys: backendCompany.settings?.require_vendor_keys === true,
        enableAnalytics: backendCompany.settings?.enable_analytics !== false,
        timezone: backendCompany.settings?.timezone || 'UTC',
      },
      rateLimits: {
        requestsPerMinute: backendCompany.rate_limits?.requests_per_minute || this.getDefaultRateLimit(backendCompany.tier, 'minute'),
        requestsPerHour: backendCompany.rate_limits?.requests_per_hour || this.getDefaultRateLimit(backendCompany.tier, 'hour'),
        requestsPerDay: backendCompany.rate_limits?.requests_per_day || this.getDefaultRateLimit(backendCompany.tier, 'day'),
        burstLimit: backendCompany.rate_limits?.burst_limit,
        concurrentRequests: backendCompany.rate_limits?.concurrent_requests,
      },
    };
  }
  
  /**
   * Transform backend API key data to our format
   */
  private transformBackendAPIKey(backendAPIKey: any): APIKey {
    return {
      id: backendAPIKey.id,
      companyId: backendAPIKey.company_id,
      name: backendAPIKey.name,
      keyHash: backendAPIKey.key_hash,
      keyPreview: backendAPIKey.key_preview,
      permissions: {
        allowedEndpoints: backendAPIKey.permissions?.allowed_endpoints || ['*'],
        allowedVendors: backendAPIKey.permissions?.allowed_vendors || ['*'],
        maxCostPerRequest: backendAPIKey.permissions?.max_cost_per_request,
        maxTokensPerRequest: backendAPIKey.permissions?.max_tokens_per_request,
        canAccessAnalytics: backendAPIKey.permissions?.can_access_analytics !== false,
        canManageVendorKeys: backendAPIKey.permissions?.can_manage_vendor_keys !== false,
      },
      isActive: backendAPIKey.is_active,
      lastUsedAt: backendAPIKey.last_used_at,
      expiresAt: backendAPIKey.expires_at,
      createdAt: backendAPIKey.created_at,
      usageCount: backendAPIKey.usage_count || 0,
      ipWhitelist: backendAPIKey.ip_whitelist,
      userAgent: backendAPIKey.user_agent,
    };
  }
  
  /**
   * Get default rate limits based on tier
   */
  private getDefaultRateLimit(tier: string, period: 'minute' | 'hour' | 'day'): number {
    const defaults = {
      free: { minute: 10, hour: 100, day: 1000 },
      starter: { minute: 60, hour: 1000, day: 10000 },
      professional: { minute: 200, hour: 5000, day: 50000 },
      enterprise: { minute: 1000, hour: 25000, day: 250000 },
    };
    
    return defaults[tier as keyof typeof defaults]?.[period] || defaults.free[period];
  }
  
  /**
   * Health check backend connectivity
   */
  async healthCheck(): Promise<{ healthy: boolean; responseTime: number; error?: string }> {
    const startTime = Date.now();
    
    try {
      const response = await fetch(`${this.baseUrl}/health`, {
        method: 'GET',
        headers: {
          'User-Agent': 'API-Lens-Workers-Proxy/1.0.0',
        },
      });
      
      const responseTime = Date.now() - startTime;
      
      return {
        healthy: response.ok,
        responseTime,
        error: response.ok ? undefined : `HTTP ${response.status}`,
      };
      
    } catch (error) {
      const responseTime = Date.now() - startTime;
      
      return {
        healthy: false,
        responseTime,
        error: error.message || 'Network error',
      };
    }
  }
}
/**
 * API Lens Workers Proxy - Authentication Error Handling
 * 
 * Comprehensive error handling and responses for authentication failures
 */

import { Context } from 'hono';
import { AuthErrorCode, AuthenticationError } from './types';
import { Env } from '../types';

export interface AuthErrorResponse {
  error: string;
  message: string;
  code: AuthErrorCode;
  details?: Record<string, any>;
  requestId: string;
  timestamp: string;
  retryAfter?: number;
  documentation?: string;
}

export class AuthErrorHandler {
  private env: Env;
  
  constructor(env: Env) {
    this.env = env;
  }
  
  /**
   * Handle authentication errors and return appropriate responses
   */
  async handleAuthError(
    c: Context<{ Bindings: Env }>,
    error: AuthenticationError,
    requestId?: string
  ): Promise<Response> {
    const id = requestId || crypto.randomUUID();
    const timestamp = new Date().toISOString();
    
    // Log the error (async)
    this.logAuthError(error, id).catch(() => {});
    
    // Create standardized error response
    const response = this.createErrorResponse(error, id, timestamp);
    
    // Determine HTTP status code
    const statusCode = this.getStatusCode(error.code);
    
    // Add security headers
    const headers = this.getSecurityHeaders(error.code);
    
    return c.json(response, statusCode, headers);
  }
  
  /**
   * Create standardized error response
   */
  private createErrorResponse(
    error: AuthenticationError,
    requestId: string,
    timestamp: string
  ): AuthErrorResponse {
    const response: AuthErrorResponse = {
      error: this.getErrorTitle(error.code),
      message: error.message,
      code: error.code,
      requestId,
      timestamp,
    };
    
    // Add details if available
    if (error.details) {
      response.details = error.details;
    }
    
    // Add retry information for retryable errors
    if (error.retryable) {
      response.retryAfter = this.getRetryDelay(error.code);
    }
    
    // Add documentation link
    response.documentation = this.getDocumentationUrl(error.code);
    
    return response;
  }
  
  /**
   * Get HTTP status code for error
   */
  private getStatusCode(code: AuthErrorCode): number {
    switch (code) {
      case AuthErrorCode.MISSING_API_KEY:
      case AuthErrorCode.INVALID_API_KEY_FORMAT:
        return 400; // Bad Request
      
      case AuthErrorCode.API_KEY_NOT_FOUND:
      case AuthErrorCode.API_KEY_EXPIRED:
      case AuthErrorCode.API_KEY_REVOKED:
        return 401; // Unauthorized
      
      case AuthErrorCode.COMPANY_SUSPENDED:
      case AuthErrorCode.IP_NOT_ALLOWED:
      case AuthErrorCode.USER_AGENT_NOT_ALLOWED:
      case AuthErrorCode.ENDPOINT_NOT_ALLOWED:
      case AuthErrorCode.VENDOR_NOT_ALLOWED:
        return 403; // Forbidden
      
      case AuthErrorCode.COMPANY_NOT_FOUND:
        return 404; // Not Found
      
      case AuthErrorCode.QUOTA_EXCEEDED:
        return 429; // Too Many Requests
      
      case AuthErrorCode.BACKEND_ERROR:
      case AuthErrorCode.REDIS_ERROR:
        return 502; // Bad Gateway
      
      default:
        return 500; // Internal Server Error
    }
  }
  
  /**
   * Get error title for display
   */
  private getErrorTitle(code: AuthErrorCode): string {
    switch (code) {
      case AuthErrorCode.MISSING_API_KEY:
        return 'Missing API Key';
      
      case AuthErrorCode.INVALID_API_KEY_FORMAT:
        return 'Invalid API Key Format';
      
      case AuthErrorCode.API_KEY_NOT_FOUND:
        return 'API Key Not Found';
      
      case AuthErrorCode.API_KEY_EXPIRED:
        return 'API Key Expired';
      
      case AuthErrorCode.API_KEY_REVOKED:
        return 'API Key Revoked';
      
      case AuthErrorCode.COMPANY_SUSPENDED:
        return 'Account Suspended';
      
      case AuthErrorCode.COMPANY_NOT_FOUND:
        return 'Company Not Found';
      
      case AuthErrorCode.IP_NOT_ALLOWED:
        return 'IP Address Not Allowed';
      
      case AuthErrorCode.USER_AGENT_NOT_ALLOWED:
        return 'User Agent Not Allowed';
      
      case AuthErrorCode.ENDPOINT_NOT_ALLOWED:
        return 'Endpoint Access Denied';
      
      case AuthErrorCode.VENDOR_NOT_ALLOWED:
        return 'Vendor Access Denied';
      
      case AuthErrorCode.QUOTA_EXCEEDED:
        return 'Quota Exceeded';
      
      case AuthErrorCode.BACKEND_ERROR:
        return 'Backend Service Error';
      
      case AuthErrorCode.REDIS_ERROR:
        return 'Cache Service Error';
      
      default:
        return 'Authentication Error';
    }
  }
  
  /**
   * Get retry delay for retryable errors
   */
  private getRetryDelay(code: AuthErrorCode): number {
    switch (code) {
      case AuthErrorCode.BACKEND_ERROR:
      case AuthErrorCode.REDIS_ERROR:
        return 60; // 1 minute
      
      case AuthErrorCode.QUOTA_EXCEEDED:
        return 3600; // 1 hour
      
      default:
        return 300; // 5 minutes
    }
  }
  
  /**
   * Get documentation URL for error
   */
  private getDocumentationUrl(code: AuthErrorCode): string {
    const baseUrl = 'https://docs.apilens.dev/errors';
    
    switch (code) {
      case AuthErrorCode.MISSING_API_KEY:
      case AuthErrorCode.INVALID_API_KEY_FORMAT:
        return `${baseUrl}/authentication#api-key-format`;
      
      case AuthErrorCode.API_KEY_NOT_FOUND:
      case AuthErrorCode.API_KEY_EXPIRED:
      case AuthErrorCode.API_KEY_REVOKED:
        return `${baseUrl}/authentication#api-key-issues`;
      
      case AuthErrorCode.COMPANY_SUSPENDED:
        return `${baseUrl}/account#suspension`;
      
      case AuthErrorCode.IP_NOT_ALLOWED:
        return `${baseUrl}/security#ip-whitelist`;
      
      case AuthErrorCode.ENDPOINT_NOT_ALLOWED:
      case AuthErrorCode.VENDOR_NOT_ALLOWED:
        return `${baseUrl}/permissions#access-control`;
      
      case AuthErrorCode.QUOTA_EXCEEDED:
        return `${baseUrl}/limits#quotas`;
      
      default:
        return `${baseUrl}/general`;
    }
  }
  
  /**
   * Get security headers for response
   */
  private getSecurityHeaders(code: AuthErrorCode): Record<string, string> {
    const headers: Record<string, string> = {
      'X-Content-Type-Options': 'nosniff',
      'X-Frame-Options': 'DENY',
      'X-XSS-Protection': '1; mode=block',
    };
    
    // Add WWW-Authenticate header for 401 responses
    if (this.getStatusCode(code) === 401) {
      headers['WWW-Authenticate'] = 'Bearer realm="API Lens", error="invalid_token"';
    }
    
    // Add Retry-After header for retryable errors
    if (this.isRetryable(code)) {
      headers['Retry-After'] = this.getRetryDelay(code).toString();
    }
    
    return headers;
  }
  
  /**
   * Check if error is retryable
   */
  private isRetryable(code: AuthErrorCode): boolean {
    switch (code) {
      case AuthErrorCode.BACKEND_ERROR:
      case AuthErrorCode.REDIS_ERROR:
      case AuthErrorCode.QUOTA_EXCEEDED:
        return true;
      
      default:
        return false;
    }
  }
  
  /**
   * Log authentication error
   */
  private async logAuthError(error: AuthenticationError, requestId: string): Promise<void> {
    try {
      const logEntry = {
        requestId,
        timestamp: new Date().toISOString(),
        error: {
          code: error.code,
          message: error.message,
          details: error.details,
          retryable: error.retryable,
        },
        environment: this.env.ENVIRONMENT || 'unknown',
      };
      
      // Log to console
      console.error('Authentication error:', logEntry);
      
      // Send to backend (fire and forget)
      fetch(`${this.env.API_LENS_BACKEND_URL}/logs/auth-errors`, {
        method: 'POST',
        headers: {
          'Authorization': `Bearer ${this.env.API_LENS_BACKEND_TOKEN}`,
          'Content-Type': 'application/json',
        },
        body: JSON.stringify(logEntry),
      }).catch(() => {
        // Ignore logging errors
      });
      
    } catch (logError) {
      console.error('Failed to log authentication error:', logError);
    }
  }
  
  /**
   * Create custom authentication error
   */
  static createError(
    code: AuthErrorCode,
    message: string,
    details?: Record<string, any>,
    retryable: boolean = false
  ): AuthenticationError {
    return {
      code,
      message,
      details,
      retryable,
    };
  }
  
  /**
   * Create missing API key error
   */
  static missingAPIKey(): AuthenticationError {
    return AuthErrorHandler.createError(
      AuthErrorCode.MISSING_API_KEY,
      'API key is required. Provide via Authorization header (Bearer token) or X-API-Key header.'
    );
  }
  
  /**
   * Create invalid API key format error
   */
  static invalidAPIKeyFormat(): AuthenticationError {
    return AuthErrorHandler.createError(
      AuthErrorCode.INVALID_API_KEY_FORMAT,
      'Invalid API key format. Expected format: als_[43 characters] or test_[39 characters]'
    );
  }
  
  /**
   * Create API key not found error
   */
  static apiKeyNotFound(): AuthenticationError {
    return AuthErrorHandler.createError(
      AuthErrorCode.API_KEY_NOT_FOUND,
      'API key not found or has been revoked'
    );
  }
  
  /**
   * Create API key expired error
   */
  static apiKeyExpired(expiresAt: string): AuthenticationError {
    return AuthErrorHandler.createError(
      AuthErrorCode.API_KEY_EXPIRED,
      'API key has expired',
      { expiresAt }
    );
  }
  
  /**
   * Create company suspended error
   */
  static companySuspended(): AuthenticationError {
    return AuthErrorHandler.createError(
      AuthErrorCode.COMPANY_SUSPENDED,
      'Company account has been suspended. Please contact support.'
    );
  }
  
  /**
   * Create IP not allowed error
   */
  static ipNotAllowed(ipAddress: string, allowedIPs: string[]): AuthenticationError {
    return AuthErrorHandler.createError(
      AuthErrorCode.IP_NOT_ALLOWED,
      'Request IP address is not in the allowed whitelist',
      { ipAddress, allowedIPs }
    );
  }
  
  /**
   * Create vendor not allowed error
   */
  static vendorNotAllowed(vendor: string, allowedVendors: string[]): AuthenticationError {
    return AuthErrorHandler.createError(
      AuthErrorCode.VENDOR_NOT_ALLOWED,
      `Access to vendor '${vendor}' is not allowed for this API key`,
      { vendor, allowedVendors }
    );
  }
  
  /**
   * Create backend error
   */
  static backendError(message: string): AuthenticationError {
    return AuthErrorHandler.createError(
      AuthErrorCode.BACKEND_ERROR,
      message,
      undefined,
      true // Retryable
    );
  }
}
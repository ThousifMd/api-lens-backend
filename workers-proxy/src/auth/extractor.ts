/**
 * API Lens Workers Proxy - API Key Extraction
 * 
 * Extract and validate API keys from various request sources
 */

import { AuthErrorCode, AuthenticationError } from './types';

export interface ExtractedAPIKey {
  key: string;
  source: 'authorization' | 'x-api-key' | 'query' | 'body';
  hash: string;
  preview: string;
}

/**
 * Extract API key from request headers, query parameters, or body
 */
export async function extractAPIKey(request: Request): Promise<ExtractedAPIKey> {
  // Try Authorization header first (Bearer token)
  const authHeader = request.headers.get('Authorization');
  if (authHeader) {
    const key = extractFromAuthorizationHeader(authHeader);
    if (key) {
      return {
        key,
        source: 'authorization',
        hash: await hashAPIKey(key),
        preview: createKeyPreview(key),
      };
    }
  }
  
  // Try X-API-Key header
  const apiKeyHeader = request.headers.get('X-API-Key');
  if (apiKeyHeader) {
    const key = sanitizeAPIKey(apiKeyHeader);
    if (validateAPIKeyFormat(key)) {
      return {
        key,
        source: 'x-api-key',
        hash: await hashAPIKey(key),
        preview: createKeyPreview(key),
      };
    }
  }
  
  // Try query parameter (not recommended for production)
  const url = new URL(request.url);
  const queryKey = url.searchParams.get('api_key') || url.searchParams.get('key');
  if (queryKey) {
    const key = sanitizeAPIKey(queryKey);
    if (validateAPIKeyFormat(key)) {
      console.warn('API key provided via query parameter - not recommended for production');
      return {
        key,
        source: 'query',
        hash: await hashAPIKey(key),
        preview: createKeyPreview(key),
      };
    }
  }
  
  // Try request body for specific endpoints (like webhooks)
  if (request.method === 'POST' && request.headers.get('Content-Type')?.includes('application/json')) {
    try {
      const body = await request.clone().json();
      if (body.api_key && typeof body.api_key === 'string') {
        const key = sanitizeAPIKey(body.api_key);
        if (validateAPIKeyFormat(key)) {
          return {
            key,
            source: 'body',
            hash: await hashAPIKey(key),
            preview: createKeyPreview(key),
          };
        }
      }
    } catch (error) {
      // Invalid JSON body, continue
    }
  }
  
  // No valid API key found
  throw new AuthenticationError({
    code: AuthErrorCode.MISSING_API_KEY,
    message: 'API key is required. Provide via Authorization header (Bearer token) or X-API-Key header.',
    retryable: false,
  });
}

/**
 * Extract API key from Authorization header
 */
function extractFromAuthorizationHeader(authHeader: string): string | null {
  // Handle Bearer token format
  if (authHeader.startsWith('Bearer ')) {
    const token = authHeader.slice(7).trim();
    return validateAPIKeyFormat(token) ? token : null;
  }
  
  // Handle Basic auth (decode and extract)
  if (authHeader.startsWith('Basic ')) {
    try {
      const encoded = authHeader.slice(6);
      const decoded = atob(encoded);
      const [username, password] = decoded.split(':');
      
      // Check if username or password is an API key
      if (validateAPIKeyFormat(username)) {
        return username;
      }
      if (validateAPIKeyFormat(password)) {
        return password;
      }
    } catch (error) {
      // Invalid Base64 encoding
    }
  }
  
  // Handle direct API key without Bearer prefix (legacy support)
  const directKey = authHeader.trim();
  return validateAPIKeyFormat(directKey) ? directKey : null;
}

/**
 * Validate API key format
 */
export function validateAPIKeyFormat(apiKey: string): boolean {
  if (!apiKey || typeof apiKey !== 'string') {
    return false;
  }
  
  // API Lens keys: als_[43 alphanumeric characters]
  const apiLensPattern = /^als_[a-zA-Z0-9]{43}$/;
  
  // Also support test keys for development
  const testPattern = /^test_[a-zA-Z0-9]{39}$/;
  
  return apiLensPattern.test(apiKey) || testPattern.test(apiKey);
}

/**
 * Sanitize API key input
 */
function sanitizeAPIKey(key: string): string {
  return key
    .trim()
    .replace(/[\r\n\t]/g, '') // Remove line breaks and tabs
    .replace(/[^\w_]/g, ''); // Remove non-alphanumeric chars except underscore
}

/**
 * Create API key preview for logging (first 8 + last 4 characters)
 */
export function createKeyPreview(apiKey: string): string {
  if (apiKey.length < 12) {
    return apiKey; // Don't preview short keys
  }
  
  return `${apiKey.slice(0, 8)}...${apiKey.slice(-4)}`;
}

/**
 * Hash API key for secure storage and lookup
 */
export async function hashAPIKey(apiKey: string): Promise<string> {
  const encoder = new TextEncoder();
  const data = encoder.encode(apiKey);
  const hashBuffer = await crypto.subtle.digest('SHA-256', data);
  const hashArray = Array.from(new Uint8Array(hashBuffer));
  return hashArray.map(b => b.toString(16).padStart(2, '0')).join('');
}

/**
 * Validate API key against security requirements
 */
export function validateAPIKeySecurity(apiKey: string, request: Request): AuthenticationError | null {
  // Check for common security issues
  if (apiKey.length < 20) {
    return {
      code: AuthErrorCode.INVALID_API_KEY_FORMAT,
      message: 'API key too short',
      retryable: false,
    };
  }
  
  // Check for obvious test/dummy keys
  const insecurePatterns = [
    /test123/i,
    /dummy/i,
    /example/i,
    /sample/i,
    /placeholder/i,
  ];
  
  for (const pattern of insecurePatterns) {
    if (pattern.test(apiKey)) {
      return {
        code: AuthErrorCode.INVALID_API_KEY_FORMAT,
        message: 'Invalid API key - appears to be a test or example key',
        retryable: false,
      };
    }
  }
  
  // Check request source for additional security
  const userAgent = request.headers.get('User-Agent');
  if (!userAgent || userAgent.length < 5) {
    console.warn('Request with missing or short User-Agent header');
  }
  
  return null; // No security issues found
}

/**
 * Extract additional authentication context from request
 */
export function extractAuthContext(request: Request): {
  ipAddress: string;
  userAgent: string;
  origin?: string;
  referer?: string;
  acceptLanguage?: string;
  fingerprint: string;
} {
  const headers = request.headers;
  const ipAddress = getClientIP(request);
  const userAgent = headers.get('User-Agent') || 'Unknown';
  const origin = headers.get('Origin') || undefined;
  const referer = headers.get('Referer') || undefined;
  const acceptLanguage = headers.get('Accept-Language') || undefined;
  
  // Create a simple fingerprint for request identification
  const fingerprint = createRequestFingerprint({
    ipAddress,
    userAgent,
    origin,
    acceptLanguage,
  });
  
  return {
    ipAddress,
    userAgent,
    origin,
    referer,
    acceptLanguage,
    fingerprint,
  };
}

/**
 * Get client IP address from request
 */
function getClientIP(request: Request): string {
  const headers = request.headers;
  
  // Try Cloudflare headers first
  const cfConnectingIP = headers.get('CF-Connecting-IP');
  if (cfConnectingIP) {
    return cfConnectingIP;
  }
  
  // Try standard proxy headers
  const xForwardedFor = headers.get('X-Forwarded-For');
  if (xForwardedFor) {
    // Take the first IP in the chain
    return xForwardedFor.split(',')[0]?.trim() || 'Unknown';
  }
  
  const xRealIP = headers.get('X-Real-IP');
  if (xRealIP) {
    return xRealIP;
  }
  
  // Fallback
  return 'Unknown';
}

/**
 * Create request fingerprint for identification and security
 */
function createRequestFingerprint(context: {
  ipAddress: string;
  userAgent: string;
  origin?: string;
  acceptLanguage?: string;
}): string {
  const parts = [
    context.ipAddress,
    context.userAgent,
    context.origin || '',
    context.acceptLanguage || '',
  ];
  
  // Create simple hash of combined parts
  const combined = parts.join('|');
  return btoa(combined).slice(0, 16);
}

/**
 * Validate IP address against whitelist
 */
export function validateIPWhitelist(ipAddress: string, whitelist: string[]): boolean {
  if (!whitelist || whitelist.length === 0) {
    return true; // No whitelist means all IPs allowed
  }
  
  for (const allowedIP of whitelist) {
    if (isIPMatch(ipAddress, allowedIP)) {
      return true;
    }
  }
  
  return false;
}

/**
 * Check if IP matches pattern (supports CIDR notation)
 */
function isIPMatch(ip: string, pattern: string): boolean {
  // Exact match
  if (ip === pattern) {
    return true;
  }
  
  // CIDR notation support (basic implementation)
  if (pattern.includes('/')) {
    // This is a simplified CIDR check - in production you'd want a proper CIDR library
    const [network, prefixLength] = pattern.split('/');
    const prefix = parseInt(prefixLength, 10);
    
    // For simplicity, just check if IP starts with network prefix
    // In production, implement proper CIDR matching
    if (prefix >= 24) {
      const networkPrefix = network.split('.').slice(0, 3).join('.');
      const ipPrefix = ip.split('.').slice(0, 3).join('.');
      return networkPrefix === ipPrefix;
    }
  }
  
  // Wildcard support (basic)
  if (pattern.includes('*')) {
    const regexPattern = pattern.replace(/\./g, '\\.').replace(/\*/g, '.*');
    const regex = new RegExp(`^${regexPattern}$`);
    return regex.test(ip);
  }
  
  return false;
}
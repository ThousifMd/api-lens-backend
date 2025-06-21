/**
 * API Lens Workers Proxy - Authentication Types
 * 
 * TypeScript interfaces and types for authentication system
 */

export interface Company {
  id: string;
  name: string;
  tier: CompanyTier;
  isActive: boolean;
  contactEmail?: string;
  webhookUrl?: string;
  currentMonthRequests: number;
  currentMonthCost: number;
  monthlyBudgetLimit?: number;
  monthlyRequestLimit?: number;
  createdAt: string;
  updatedAt: string;
  settings: CompanySettings;
  rateLimits: RateLimits;
}

export interface CompanySettings {
  allowedVendors: string[];
  defaultModel?: string;
  maxTokensPerRequest?: number;
  enableCostAlerts: boolean;
  enableUsageAlerts: boolean;
  requireVendorKeys: boolean; // BYOK requirement
  enableAnalytics: boolean;
  timezone: string;
}

export interface RateLimits {
  requestsPerMinute: number;
  requestsPerHour: number;
  requestsPerDay: number;
  burstLimit?: number;
  concurrentRequests?: number;
}

export interface APIKey {
  id: string;
  companyId: string;
  name: string;
  keyHash: string;
  keyPreview: string;
  permissions: APIKeyPermissions;
  isActive: boolean;
  lastUsedAt?: string;
  expiresAt?: string;
  createdAt: string;
  usageCount: number;
  ipWhitelist?: string[];
  userAgent?: string;
}

export interface APIKeyPermissions {
  allowedEndpoints: string[];
  allowedVendors: string[];
  maxCostPerRequest?: number;
  maxTokensPerRequest?: number;
  canAccessAnalytics: boolean;
  canManageVendorKeys: boolean;
}

export interface AuthenticationResult {
  success: boolean;
  company?: Company;
  apiKey?: APIKey;
  error?: AuthenticationError;
  cached: boolean;
  responseTime: number;
}

export interface AuthenticationError {
  code: AuthErrorCode;
  message: string;
  details?: Record<string, any>;
  retryable: boolean;
}

export class AuthenticationError extends Error {
  public code: AuthErrorCode;
  public details?: Record<string, any>;
  public retryable: boolean;

  constructor(options: {
    code: AuthErrorCode;
    message: string;
    details?: Record<string, any>;
    retryable?: boolean;
  }) {
    super(options.message);
    this.name = 'AuthenticationError';
    this.code = options.code;
    this.details = options.details;
    this.retryable = options.retryable ?? false;
  }
}

export interface CompanyContext {
  company: Company;
  apiKey: APIKey;
  requestId: string;
  ipAddress: string;
  userAgent: string;
  timestamp: string;
  region?: string;
  country?: string;
}

export enum CompanyTier {
  FREE = 'free',
  STARTER = 'starter',
  PROFESSIONAL = 'professional',
  ENTERPRISE = 'enterprise',
}

export enum AuthErrorCode {
  MISSING_API_KEY = 'MISSING_API_KEY',
  INVALID_API_KEY_FORMAT = 'INVALID_API_KEY_FORMAT',
  API_KEY_NOT_FOUND = 'API_KEY_NOT_FOUND',
  API_KEY_EXPIRED = 'API_KEY_EXPIRED',
  API_KEY_REVOKED = 'API_KEY_REVOKED',
  COMPANY_SUSPENDED = 'COMPANY_SUSPENDED',
  COMPANY_NOT_FOUND = 'COMPANY_NOT_FOUND',
  IP_NOT_ALLOWED = 'IP_NOT_ALLOWED',
  USER_AGENT_NOT_ALLOWED = 'USER_AGENT_NOT_ALLOWED',
  ENDPOINT_NOT_ALLOWED = 'ENDPOINT_NOT_ALLOWED',
  VENDOR_NOT_ALLOWED = 'VENDOR_NOT_ALLOWED',
  BACKEND_ERROR = 'BACKEND_ERROR',
  REDIS_ERROR = 'REDIS_ERROR',
  QUOTA_EXCEEDED = 'QUOTA_EXCEEDED',
}

export interface CacheEntry<T> {
  data: T;
  timestamp: number;
  ttl: number;
}

export interface RedisAuthCache {
  company: Company;
  apiKey: APIKey;
  cachedAt: number;
  expiresAt: number;
}

export interface AuthMetrics {
  totalRequests: number;
  cacheHits: number;
  cacheMisses: number;
  backendRequests: number;
  authErrors: number;
  averageResponseTime: number;
  errorsByCode: Record<AuthErrorCode, number>;
}
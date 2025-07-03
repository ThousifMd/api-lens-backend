/**
 * API Lens Workers Proxy - Type Definitions
 * 
 * Centralized type definitions for the entire Workers proxy
 */

// Environment bindings interface
export interface Env {
  // KV Namespaces
  RATE_LIMIT_KV: any;
  CACHE_KV: any;
  
  // Durable Objects
  RATE_LIMITER: any;
  
  // Analytics Engine
  API_ANALYTICS: any;
  
  // Environment Variables
  ENVIRONMENT: string;
  CORS_ORIGINS: string;
  DEFAULT_RATE_LIMIT: string;
  MAX_REQUEST_SIZE: string;
  REQUEST_TIMEOUT: string;
  
  // Rate Limiting Configuration
  DEFAULT_RATE_LIMIT_PER_MINUTE?: string;
  DEFAULT_RATE_LIMIT_PER_HOUR?: string;
  DEFAULT_RATE_LIMIT_PER_DAY?: string;
  DEFAULT_COST_LIMIT_PER_MINUTE?: string;
  DEFAULT_COST_LIMIT_PER_HOUR?: string;
  DEFAULT_COST_LIMIT_PER_DAY?: string;
  
  // Secrets (configured via wrangler secret)
  API_LENS_BACKEND_URL: string;
  API_LENS_BACKEND_TOKEN: string;
  
  // Vendor API Keys (configured via wrangler secret)
  OPENAI_API_KEY?: string;
  ANTHROPIC_API_KEY?: string;
  GOOGLE_API_KEY?: string;
  AZURE_API_KEY?: string;
  
  // Cache Configuration
  CACHE_TTL_AUTH?: string;
  CACHE_TTL_PRICING?: string;
  CACHE_TTL_MODELS?: string;
  
  // Monitoring
  ENABLE_ANALYTICS?: string;
  ENABLE_DETAILED_LOGGING?: string;
  LOG_LEVEL?: string;
  
  // Security
  ENABLE_RATE_LIMITING?: string;
  ENABLE_COST_LIMITING?: string;
  ALLOW_CORS?: string;
  
  // Performance
  WORKER_TIMEOUT?: string;
  MAX_RETRIES?: string;
  RETRY_DELAY?: string;
  
  // Index signature for string keys
  [key: string]: string | any | undefined;
}

// Hono Context Variables
export interface HonoVariables {
  company?: Company;
  apiKey?: APIKey;
  companyContext?: CompanyContext;
  authCached?: boolean;
  authResponseTime?: number;
  requestId?: string;
  startTime?: number;
  rateLimitInfo?: RateLimitInfo;
  costInfo?: CostInfo;
  vendorResponse?: VendorResponse;
  [key: string]: unknown;
}

// Company interface
export interface Company {
  id: string;
  name: string;
  slug: string;
  tier: string;
  isActive: boolean;
  contactEmail?: string;
  billingEmail?: string;
  rateLimitRps?: number;
  monthlyQuota?: number;
  monthlyBudgetUsd?: number;
  webhookUrl?: string;
  webhookEvents?: string[];
  dashboardSettings?: Record<string, unknown>;
  requireUserId?: boolean;
  userIdHeaderName?: string;
  additionalHeaders?: Record<string, string>;
  createdAt: string;
  updatedAt: string;
}

// API Key interface
export interface APIKey {
  id: string;
  companyId: string;
  name: string;
  keyHash: string;
  keyPrefix: string;
  environment: string;
  scopes: string[];
  allowedIps?: string[];
  isActive: boolean;
  createdAt: string;
  lastUsedAt?: string;
  expiresAt?: string;
  createdBy?: string;
  metadata?: Record<string, unknown>;
}

// Company Context interface
export interface CompanyContext {
  company: Company;
  apiKey: APIKey;
  effectiveRateLimit: RateLimit;
  effectiveCostLimit: CostLimit;
  features: CompanyFeatures;
  usage: UsageInfo;
  permissions: string[];
}

// Rate Limit interface
export interface RateLimit {
  requestsPerMinute: number;
  requestsPerHour: number;
  requestsPerDay: number;
  tokensPerMinute?: number;
  tokensPerHour?: number;
  tokensPerDay?: number;
}

// Cost Limit interface
export interface CostLimit {
  costPerMinute: number;
  costPerHour: number;
  costPerDay: number;
  costPerMonth: number;
}

// Company Features interface
export interface CompanyFeatures {
  multiUserSupport: boolean;
  customModels: boolean;
  webhooks: boolean;
  analytics: boolean;
  prioritySupport: boolean;
  customRateLimits: boolean;
  bulkRequests: boolean;
  realTimeMetrics: boolean;
}

// Usage Info interface
export interface UsageInfo {
  currentMinuteRequests: number;
  currentHourRequests: number;
  currentDayRequests: number;
  currentMinuteCost: number;
  currentHourCost: number;
  currentDayCost: number;
  currentMonthCost: number;
  lastRequestAt?: string;
}

// Rate Limit Info interface
export interface RateLimitInfo {
  allowed: boolean;
  limit: number;
  remaining: number;
  resetTime: number;
  retryAfter?: number;
  limitType: 'requests' | 'tokens' | 'cost';
}

// Cost Info interface
export interface CostInfo {
  inputTokens: number;
  outputTokens: number;
  totalTokens: number;
  inputCost: number;
  outputCost: number;
  totalCost: number;
  currency: string;
  pricingTier: string;
  costSource: string;
}

// Vendor Response interface
export interface VendorResponse {
  vendor: string;
  model: string;
  statusCode: number;
  success: boolean;
  responseTime: number;
  inputTokens: number;
  outputTokens: number;
  totalTokens: number;
  cost: CostInfo;
  cached: boolean;
  errorType?: string;
  errorMessage?: string;
}

// Authentication Result interface
export interface AuthenticationResult {
  success: boolean;
  company?: Company;
  apiKey?: APIKey;
  context?: CompanyContext;
  cached: boolean;
  responseTime: number;
  error?: AuthError;
}

// Auth Error interface
export interface AuthError {
  code: AuthErrorCode;
  message: string;
  details?: Record<string, unknown>;
  statusCode: number;
}

// Auth Error Codes enum
export enum AuthErrorCode {
  MISSING_API_KEY = 'MISSING_API_KEY',
  INVALID_API_KEY = 'INVALID_API_KEY',
  EXPIRED_API_KEY = 'EXPIRED_API_KEY',
  INACTIVE_API_KEY = 'INACTIVE_API_KEY',
  INACTIVE_COMPANY = 'INACTIVE_COMPANY',
  IP_NOT_ALLOWED = 'IP_NOT_ALLOWED',
  SCOPE_NOT_ALLOWED = 'SCOPE_NOT_ALLOWED',
  BACKEND_ERROR = 'BACKEND_ERROR',
  RATE_LIMITED = 'RATE_LIMITED',
  COST_LIMITED = 'COST_LIMITED',
  QUOTA_EXCEEDED = 'QUOTA_EXCEEDED',
}

// Vendor Types
export type VendorName = 'openai' | 'anthropic' | 'google' | 'azure' | 'cohere' | 'huggingface';

export interface VendorConfig {
  name: VendorName;
  baseUrl: string;
  apiKeyHeader: string;
  models: VendorModel[];
  rateLimits: VendorRateLimit;
  defaultTimeout: number;
  maxRetries: number;
  supportedFeatures: VendorFeatures;
}

export interface VendorModel {
  name: string;
  displayName: string;
  type: ModelType;
  contextWindow: number;
  maxOutputTokens: number;
  supportsStreaming: boolean;
  supportsFunctions: boolean;
  supportsVision: boolean;
  pricing: ModelPricing;
}

export type ModelType = 'chat' | 'completion' | 'embedding' | 'image' | 'audio' | 'video';

export interface ModelPricing {
  input: number;
  output: number;
  image?: number;
  audio?: number;
  video?: number;
  currency: string;
}

export interface VendorRateLimit {
  requestsPerMinute: number;
  tokensPerMinute: number;
  requestsPerDay: number;
}

export interface VendorFeatures {
  streaming: boolean;
  functionCalling: boolean;
  vision: boolean;
  imageGeneration: boolean;
  audioProcessing: boolean;
  videoProcessing: boolean;
  embedding: boolean;
  fineTuning: boolean;
}

// Request/Response Types
export interface ProxyRequest {
  vendor: VendorName;
  model: string;
  endpoint: string;
  method: string;
  headers: Record<string, string>;
  body: unknown;
  userId?: string;
  sessionId?: string;
  metadata?: Record<string, unknown>;
}

export interface ProxyResponse {
  statusCode: number;
  headers: Record<string, string>;
  body: unknown;
  success: boolean;
  cached: boolean;
  vendor: VendorName;
  model: string;
  usage: TokenUsage;
  cost: CostInfo;
  responseTime: number;
  requestId: string;
}

export interface TokenUsage {
  promptTokens: number;
  completionTokens: number;
  totalTokens: number;
}

// Analytics Types
export interface AnalyticsEvent {
  timestamp: number;
  requestId: string;
  companyId: string;
  apiKeyId: string;
  vendor: VendorName;
  model: string;
  endpoint: string;
  method: string;
  statusCode: number;
  success: boolean;
  cached: boolean;
  inputTokens: number;
  outputTokens: number;
  totalTokens: number;
  inputCost: number;
  outputCost: number;
  totalCost: number;
  currency: string;
  responseTime: number;
  rateLimited: boolean;
  costLimited: boolean;
  userAgent?: string;
  ipAddress?: string;
  userId?: string;
  sessionId?: string;
  errorType?: string;
  errorMessage?: string;
}

// Cache Types
export interface CacheConfig {
  authTtl: number;
  pricingTtl: number;
  modelsTtl: number;
  defaultTtl: number;
}

export interface CacheEntry<T> {
  data: T;
  timestamp: number;
  ttl: number;
  key: string;
}

// Health Check Types
export interface HealthCheck {
  status: 'healthy' | 'degraded' | 'unhealthy';
  timestamp: number;
  version: string;
  environment: string;
  checks: {
    auth: HealthCheckResult;
    rateLimit: HealthCheckResult;
    vendors: Record<VendorName, HealthCheckResult>;
    cache: HealthCheckResult;
    analytics: HealthCheckResult;
  };
  responseTime: number;
}

export interface HealthCheckResult {
  status: 'healthy' | 'degraded' | 'unhealthy';
  responseTime: number;
  error?: string;
  details?: Record<string, unknown>;
}

// Error Types
export interface APIError {
  code: string;
  message: string;
  details?: Record<string, unknown>;
  statusCode: number;
  timestamp: number;
  requestId: string;
  path?: string;
  method?: string;
}

// Validation Types
export interface ValidationRule {
  field: string;
  type: 'string' | 'number' | 'boolean' | 'array' | 'object';
  required: boolean;
  minLength?: number;
  maxLength?: number;
  min?: number;
  max?: number;
  pattern?: RegExp;
  allowedValues?: unknown[];
  customValidator?: (value: unknown) => boolean;
}

export interface ValidationResult {
  valid: boolean;
  errors: ValidationError[];
}

export interface ValidationError {
  field: string;
  message: string;
  value?: unknown;
}

// Utility Types
export type Optional<T, K extends keyof T> = Omit<T, K> & Partial<Pick<T, K>>;
export type RequiredFields<T, K extends keyof T> = T & Required<Pick<T, K>>;
export type PartialFields<T, K extends keyof T> = Omit<T, K> & Partial<Pick<T, K>>;

// Event Types for async operations
export interface AsyncEvent {
  type: string;
  data: unknown;
  timestamp: number;
  requestId: string;
  companyId: string;
}

// Configuration Types
export interface WorkerConfig {
  environment: string;
  version: string;
  features: {
    rateLimiting: boolean;
    costLimiting: boolean;
    analytics: boolean;
    caching: boolean;
    detailedLogging: boolean;
  };
  timeouts: {
    request: number;
    vendor: number;
    auth: number;
    cache: number;
  };
  retries: {
    maxAttempts: number;
    delay: number;
    backoff: number;
  };
}
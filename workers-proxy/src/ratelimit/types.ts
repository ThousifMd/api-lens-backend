/**
 * API Lens Workers Proxy - Rate Limiting Types
 * 
 * Type definitions for distributed rate limiting system
 */

export interface RateLimitResult {
  allowed: boolean;
  limit: number;
  remaining: number;
  resetTime: number;
  retryAfter?: number;
  limitType: RateLimitType;
  windowStart: number;
  windowEnd: number;
  cost?: number;
  costRemaining?: number;
}

export interface RateLimitConfig {
  requestsPerMinute?: number;
  requestsPerHour?: number;
  requestsPerDay?: number;
  costPerMinute?: number;
  costPerHour?: number;
  costPerDay?: number;
  enabled: boolean;
}

export interface SlidingWindowData {
  timestamps: number[];
  costs: number[];
  lastCleanup: number;
}

export interface RedisRateLimitData {
  count: number;
  cost: number;
  windowStart: number;
  lastUpdate: number;
  history: Array<{
    timestamp: number;
    count: number;
    cost: number;
  }>;
}

export enum RateLimitType {
  REQUESTS_PER_MINUTE = 'requests_per_minute',
  REQUESTS_PER_HOUR = 'requests_per_hour',
  REQUESTS_PER_DAY = 'requests_per_day',
  COST_PER_MINUTE = 'cost_per_minute',
  COST_PER_HOUR = 'cost_per_hour',
  COST_PER_DAY = 'cost_per_day',
}

export enum RateLimitAlgorithm {
  SLIDING_WINDOW_LOG = 'sliding_window_log',
  SLIDING_WINDOW_COUNTER = 'sliding_window_counter',
  TOKEN_BUCKET = 'token_bucket',
  FIXED_WINDOW = 'fixed_window',
}

export interface RateLimitError {
  code: string;
  message: string;
  retryAfter: number;
  limit: number;
  remaining: number;
  resetTime: number;
  limitType: RateLimitType;
}

export interface RateLimitMetrics {
  totalRequests: number;
  totalBlocked: number;
  averageLatency: number;
  peakRequestsPerSecond: number;
  currentActiveWindows: number;
  cacheHitRate: number;
  redisLatency: number;
}

export interface RateLimitOptions {
  algorithm?: RateLimitAlgorithm;
  windowSizeMs: number;
  maxRequests: number;
  maxCost?: number;
  keyPrefix?: string;
  enableMetrics?: boolean;
  enableCleanup?: boolean;
  cleanupIntervalMs?: number;
}

export interface CompanyRateLimits {
  companyId: string;
  tier: string;
  limits: RateLimitConfig;
  customLimits?: Partial<RateLimitConfig>;
  effectiveDate: string;
}

export interface RateLimitCache {
  get(key: string): Promise<string | null>;
  set(key: string, value: string, ttlSeconds?: number): Promise<void>;
  incr(key: string): Promise<number>;
  expire(key: string, ttlSeconds: number): Promise<void>;
  pipeline(): RateLimitPipeline;
}

export interface RateLimitPipeline {
  get(key: string): this;
  set(key: string, value: string, ttlSeconds?: number): this;
  incr(key: string): this;
  expire(key: string, ttlSeconds: number): this;
  zadd(key: string, score: number, member: string): this;
  zremrangebyscore(key: string, min: number, max: number): this;
  zcard(key: string): this;
  exec(): Promise<any[]>;
}
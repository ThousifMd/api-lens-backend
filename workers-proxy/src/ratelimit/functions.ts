/**
 * API Lens Workers Proxy - Rate Limiting Functions
 * 
 * Core rate limiting functions as specified in Phase 6.3.1
 */

import { Context } from 'hono';
import {
  RateLimitResult,
  RateLimitType,
  RateLimitError,
} from './types';
import { RateLimitService } from './rate-limiter';
import { getAuthResult } from '../auth';
import { Env } from '../index';

let rateLimitService: RateLimitService | null = null;

/**
 * Get or create rate limit service instance
 */
function getRateLimitService(env: Env): RateLimitService {
  if (!rateLimitService) {
    rateLimitService = new RateLimitService(env);
  }
  return rateLimitService;
}

/**
 * Check rate limit for a company and limit type
 * 
 * @param companyId - The company ID to check limits for
 * @param limitType - The type of rate limit to check
 * @param cost - Optional cost for cost-based limits (default: 1)
 * @param env - Environment bindings
 * @returns Promise<RateLimitResult>
 */
export async function checkRateLimit(
  companyId: string,
  limitType: string,
  cost: number = 1,
  env: Env
): Promise<RateLimitResult> {
  const service = getRateLimitService(env);
  
  // Convert string to RateLimitType enum
  const rateLimitType = limitType as RateLimitType;
  
  if (!Object.values(RateLimitType).includes(rateLimitType)) {
    throw new Error(`Invalid limit type: ${limitType}`);
  }

  return service.checkRateLimit(companyId, rateLimitType, cost);
}

/**
 * Increment rate counter atomically
 * 
 * @param companyId - The company ID to increment counter for
 * @param limitType - The type of rate limit counter to increment
 * @param cost - Optional cost for cost-based limits (default: 1)
 * @param env - Environment bindings
 * @returns Promise<number> - New counter value
 */
export async function incrementRateCounter(
  companyId: string,
  limitType: string = RateLimitType.REQUESTS_PER_MINUTE,
  cost: number = 1,
  env: Env
): Promise<number> {
  const service = getRateLimitService(env);
  
  // Convert string to RateLimitType enum
  const rateLimitType = limitType as RateLimitType;
  
  if (!Object.values(RateLimitType).includes(rateLimitType)) {
    throw new Error(`Invalid limit type: ${limitType}`);
  }

  return service.incrementRateCounter(companyId, rateLimitType, cost);
}

/**
 * Get rate limit headers for response
 * 
 * @param rateLimitResult - Single rate limit result or array of results
 * @returns Headers object for HTTP response
 */
export function getRateLimitHeaders(
  rateLimitResult: RateLimitResult | RateLimitResult[]
): Headers {
  const service = getRateLimitService({} as Env); // Headers don't need env
  
  const results = Array.isArray(rateLimitResult) ? rateLimitResult : [rateLimitResult];
  const headerMap = service.getRateLimitHeaders(results);
  
  const headers = new Headers();
  for (const [key, value] of Object.entries(headerMap)) {
    headers.set(key, value);
  }
  
  return headers;
}

/**
 * Handle rate limit exceeded - create error response
 * 
 * @param result - The rate limit result that was exceeded
 * @param c - Hono context for creating response
 * @returns Promise<Response> - HTTP error response
 */
export async function handleRateLimitExceeded(
  result: RateLimitResult,
  c: Context<{ Bindings: Env }>
): Promise<Response> {
  const service = getRateLimitService(c.env);
  const error = service.handleRateLimitExceeded(result);
  
  const headers = getRateLimitHeaders(result);
  
  // Add security headers
  headers.set('X-Content-Type-Options', 'nosniff');
  headers.set('X-Frame-Options', 'DENY');
  headers.set('X-XSS-Protection', '1; mode=block');
  
  const response = {
    error: error.code,
    message: error.message,
    retryAfter: error.retryAfter,
    limit: error.limit,
    remaining: error.remaining,
    resetTime: error.resetTime,
    limitType: error.limitType,
    timestamp: new Date().toISOString(),
    requestId: c.get('requestId') || crypto.randomUUID(),
    documentation: 'https://docs.apilens.dev/errors/rate-limits',
  };

  return c.json(response, 429, Object.fromEntries(headers.entries()));
}

/**
 * Check rate limits for authenticated request (middleware helper)
 * 
 * @param c - Hono context with authentication
 * @param estimatedCost - Optional estimated cost for the request
 * @returns Promise<{ allowed: boolean; results: RateLimitResult[]; blockedBy?: RateLimitType }>
 */
export async function checkAuthenticatedRateLimit(
  c: Context<{ Bindings: Env }>,
  estimatedCost: number = 0
): Promise<{
  allowed: boolean;
  results: RateLimitResult[];
  blockedBy?: RateLimitType;
}> {
  const authResult = getAuthResult(c);
  
  if (!authResult) {
    throw new Error('Request not authenticated');
  }

  const service = getRateLimitService(c.env);
  return service.checkAllRateLimits(
    authResult.company,
    authResult.apiKey,
    estimatedCost
  );
}

/**
 * Increment all rate limit counters after successful request
 * 
 * @param c - Hono context with authentication
 * @param actualCost - Actual cost of the completed request
 * @returns Promise<void>
 */
export async function incrementAuthenticatedCounters(
  c: Context<{ Bindings: Env }>,
  actualCost: number = 0
): Promise<void> {
  const authResult = getAuthResult(c);
  
  if (!authResult) {
    throw new Error('Request not authenticated');
  }

  const service = getRateLimitService(c.env);
  await service.incrementAllCounters(authResult.company, actualCost);
}

/**
 * Utility function to check specific rate limit type
 * 
 * @param c - Hono context with authentication
 * @param limitType - Specific limit type to check
 * @param cost - Cost for the check (default: 1)
 * @returns Promise<RateLimitResult>
 */
export async function checkSpecificRateLimit(
  c: Context<{ Bindings: Env }>,
  limitType: RateLimitType,
  cost: number = 1
): Promise<RateLimitResult> {
  const authResult = getAuthResult(c);
  
  if (!authResult) {
    throw new Error('Request not authenticated');
  }

  const service = getRateLimitService(c.env);
  return service.checkRateLimit(authResult.company.id, limitType, cost);
}

/**
 * Get rate limiting metrics
 * 
 * @param env - Environment bindings
 * @returns Rate limiting metrics
 */
export function getRateLimitMetrics(env: Env) {
  const service = getRateLimitService(env);
  return service.getMetrics();
}

/**
 * Create a rate limit result for testing purposes
 * 
 * @param allowed - Whether the request is allowed
 * @param limit - The rate limit
 * @param remaining - Remaining requests/cost
 * @param limitType - Type of rate limit
 * @returns RateLimitResult
 */
export function createTestRateLimitResult(
  allowed: boolean,
  limit: number,
  remaining: number,
  limitType: RateLimitType = RateLimitType.REQUESTS_PER_MINUTE
): RateLimitResult {
  const now = Date.now();
  return {
    allowed,
    limit,
    remaining,
    resetTime: now + 60000, // 1 minute from now
    retryAfter: allowed ? undefined : 60,
    limitType,
    windowStart: now - 60000,
    windowEnd: now,
  };
}

/**
 * Parse rate limit type from string with validation
 * 
 * @param limitTypeString - String representation of limit type
 * @returns RateLimitType
 * @throws Error if invalid limit type
 */
export function parseRateLimitType(limitTypeString: string): RateLimitType {
  const normalizedType = limitTypeString.toLowerCase().replace(/-/g, '_');
  
  // Map common string formats to enum values
  const typeMap: Record<string, RateLimitType> = {
    'requests_per_minute': RateLimitType.REQUESTS_PER_MINUTE,
    'requests_per_hour': RateLimitType.REQUESTS_PER_HOUR,
    'requests_per_day': RateLimitType.REQUESTS_PER_DAY,
    'cost_per_minute': RateLimitType.COST_PER_MINUTE,
    'cost_per_hour': RateLimitType.COST_PER_HOUR,
    'cost_per_day': RateLimitType.COST_PER_DAY,
    'minute': RateLimitType.REQUESTS_PER_MINUTE,
    'hour': RateLimitType.REQUESTS_PER_HOUR,
    'day': RateLimitType.REQUESTS_PER_DAY,
    'rpm': RateLimitType.REQUESTS_PER_MINUTE,
    'rph': RateLimitType.REQUESTS_PER_HOUR,
    'rpd': RateLimitType.REQUESTS_PER_DAY,
  };

  const rateLimitType = typeMap[normalizedType] || (limitTypeString as RateLimitType);
  
  if (!Object.values(RateLimitType).includes(rateLimitType)) {
    throw new Error(`Invalid rate limit type: ${limitTypeString}`);
  }

  return rateLimitType;
}

// Export types for convenience
export type {
  RateLimitResult,
  RateLimitType,
  RateLimitError,
} from './types';
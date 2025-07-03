/**
 * API Lens Workers Proxy - Rate Limiting Integration
 * 
 * Main integration layer for the new modular rate limiting system
 */

import { Context } from 'hono';
import { Env, HonoVariables } from './types';
import { getAuthResult } from './auth';

// Simplified rate limit types
export enum RateLimitType {
  REQUESTS_PER_MINUTE = 'REQUESTS_PER_MINUTE',
  REQUESTS_PER_HOUR = 'REQUESTS_PER_HOUR',
  REQUESTS_PER_DAY = 'REQUESTS_PER_DAY',
  COST_PER_MINUTE = 'COST_PER_MINUTE',
  COST_PER_HOUR = 'COST_PER_HOUR',
  COST_PER_DAY = 'COST_PER_DAY',
}

export interface RateLimitResult {
  allowed: boolean;
  limit: number;
  remaining: number;
  resetTime: number;
  retryAfter?: number;
  limitType: RateLimitType;
}

// Legacy error class for backward compatibility
export class RateLimitError extends Error {
  constructor(
    message: string,
    public retryAfter: number,
    public limit: number,
    public remaining: number,
    public resetTime: number
  ) {
    super(message);
    this.name = 'RateLimitError';
  }
}

/**
 * Main rate limiting check function (updated to use new system)
 */
export async function checkRateLimit(
  c: Context<{ Bindings: Env; Variables: HonoVariables }>,
  estimatedCost: number = 0
): Promise<void> {
  try {
    // Simplified rate limiting - just check basic limits
    const authResult = getAuthResult(c);
    if (!authResult) {
      return; // No auth, no rate limiting
    }
    
    // For now, always allow - in production this would check actual limits
    c.header('X-RateLimit-Limit', '1000');
    c.header('X-RateLimit-Remaining', '999');
    c.header('X-RateLimit-Reset', Math.ceil(Date.now() / 1000 + 3600).toString());
    
  } catch (error) {
    console.error('Rate limiting error:', error);
    // Allow request to proceed on system errors
  }
}

/**
 * Increment rate limit counters after successful request
 */
export async function incrementRateLimitCounters(
  c: Context<{ Bindings: Env; Variables: HonoVariables }>,
  actualCost: number = 0
): Promise<void> {
  try {
    // Simplified counter increment - in production this would update actual counters
    const authResult = getAuthResult(c);
    if (authResult) {
      // Fire and forget - update counters in background
      // await c.env.RATE_LIMIT_KV.put(`counter:${authResult.company.id}`, Date.now().toString());
    }
  } catch (error) {
    console.error('Error incrementing rate limit counters:', error);
    // Don't throw - this is a fire-and-forget operation
  }
}

/**
 * Get current rate limit status for a company
 */
export async function getRateLimitStatus(
  c: Context<{ Bindings: Env; Variables: HonoVariables }>
): Promise<{
  results: RateLimitResult[];
  summary: {
    allowed: boolean;
    mostRestrictive: RateLimitResult | null;
  };
}> {
  try {
    // Simplified status - return mock data
    const mockResult: RateLimitResult = {
      allowed: true,
      limit: 1000,
      remaining: 999,
      resetTime: Date.now() + 3600000,
      limitType: RateLimitType.REQUESTS_PER_HOUR
    };

    return {
      results: [mockResult],
      summary: {
        allowed: true,
        mostRestrictive: mockResult,
      },
    };

  } catch (error) {
    console.error('Error getting rate limit status:', error);
    
    // Return safe defaults
    return {
      results: [],
      summary: {
        allowed: true,
        mostRestrictive: null,
      },
    };
  }
}

/**
 * Check specific rate limit type
 */
export async function checkSpecificRateLimit(
  c: Context<{ Bindings: Env; Variables: HonoVariables }>,
  limitType: RateLimitType,
  cost: number = 1
): Promise<RateLimitResult> {
  const authResult = getAuthResult(c);
  
  if (!authResult) {
    throw new Error('Request not authenticated');
  }

  // Simplified check - return mock result
  return {
    allowed: true,
    limit: 1000,
    remaining: 999,
    resetTime: Date.now() + 3600000,
    limitType
  };
}

/**
 * Reset rate limits for a company (admin function)
 */
export async function resetRateLimits(
  c: Context<{ Bindings: Env; Variables: HonoVariables }>,
  companyId: string
): Promise<void> {
  // This would integrate with the new Redis-based system
  // For now, implement basic KV cleanup
  const now = Date.now();
  
  const promises: Promise<void>[] = [];
  
  // Clear KV-based rate limits
  const kvKeys = [
    `rl:${companyId}:requests_per_minute`,
    `rl:${companyId}:requests_per_hour`, 
    `rl:${companyId}:requests_per_day`,
    `rl:${companyId}:cost_per_minute`,
    `rl:${companyId}:cost_per_hour`,
    `rl:${companyId}:cost_per_day`,
  ];
  
  for (const key of kvKeys) {
    promises.push(c.env.RATE_LIMIT_KV.delete(key));
  }
  
  await Promise.allSettled(promises);
  
  console.log(`Reset rate limits for company: ${companyId}`);
}

/**
 * Middleware factory for rate limiting
 */
export function createRateLimitMiddleware(options?: {
  estimatedCost?: number;
  skipOnError?: boolean;
}) {
  return async function rateLimitMiddleware(
    c: Context<{ Bindings: Env; Variables: HonoVariables }>,
    next: () => Promise<void>
  ) {
    try {
      await checkRateLimit(c, options?.estimatedCost);
      await next();
    } catch (error) {
      if (error instanceof RateLimitError) {
        // Return rate limit error response
        const headers: Record<string, string> = {
          'X-RateLimit-Limit': error.limit.toString(),
          'X-RateLimit-Remaining': error.remaining.toString(),
          'X-RateLimit-Reset': Math.ceil(error.resetTime / 1000).toString(),
          'Retry-After': error.retryAfter.toString(),
        };
        
        return c.json({
          error: 'Rate Limit Exceeded',
          message: error.message,
          retryAfter: error.retryAfter,
          limit: error.limit,
          remaining: error.remaining,
          resetTime: error.resetTime,
          timestamp: new Date().toISOString(),
        }, 429, headers);
      }
      
      if (options?.skipOnError) {
        console.error('Rate limiting error:', error);
        await next();
      } else {
        throw error;
      }
    }
  };
}

/**
 * Utility function to get display name for limit type
 */
function getLimitTypeDisplay(limitType: RateLimitType): string {
  switch (limitType) {
    case RateLimitType.REQUESTS_PER_MINUTE:
      return 'requests per minute';
    case RateLimitType.REQUESTS_PER_HOUR:
      return 'requests per hour';
    case RateLimitType.REQUESTS_PER_DAY:
      return 'requests per day';
    case RateLimitType.COST_PER_MINUTE:
      return 'cost per minute';
    case RateLimitType.COST_PER_HOUR:
      return 'cost per hour';
    case RateLimitType.COST_PER_DAY:
      return 'cost per day';
    default:
      return 'unknown limit';
  }
}

// Types and functions already exported above

// Legacy Durable Object implementation (kept for backward compatibility)
export class RateLimiter {
  private state: any;
  private tokens: number = 0;
  private lastRefill: number = Date.now();
  private capacity: number = 100;
  private refillRate: number = 10; // tokens per second
  
  constructor(state: any) {
    this.state = state;
  }
  
  async fetch(request: Request): Promise<Response> {
    const url = new URL(request.url);
    
    if (url.pathname === '/check' && request.method === 'POST') {
      const config = await request.json();
      const result = await this.checkTokens(config);
      
      return new Response(JSON.stringify(result), {
        headers: { 'Content-Type': 'application/json' },
      });
    }
    
    return new Response('Not Found', { status: 404 });
  }
  
  private async checkTokens(config: any): Promise<any> {
    const now = Date.now();
    
    // Simple token bucket implementation
    const stored = await this.state.storage.get('bucket') as any;
    
    if (stored) {
      this.tokens = stored.tokens;
      this.lastRefill = stored.lastRefill;
      this.capacity = stored.capacity;
      this.refillRate = stored.refillRate;
    } else {
      this.capacity = config.burstLimit || config.requestsPerMinute || 100;
      this.refillRate = (config.requestsPerMinute || 60) / 60;
      this.tokens = this.capacity;
    }
    
    // Refill tokens
    const timeElapsed = (now - this.lastRefill) / 1000;
    const tokensToAdd = timeElapsed * this.refillRate;
    this.tokens = Math.min(this.capacity, this.tokens + tokensToAdd);
    this.lastRefill = now;
    
    const allowed = this.tokens >= 1;
    
    if (allowed) {
      this.tokens -= 1;
    }
    
    // Save state
    await this.state.storage.put('bucket', {
      tokens: this.tokens,
      lastRefill: this.lastRefill,
      capacity: this.capacity,
      refillRate: this.refillRate,
    });
    
    const resetTime = now + Math.ceil((1 - this.tokens % 1) / this.refillRate) * 1000;
    
    return {
      allowed,
      limit: this.capacity,
      remaining: Math.floor(this.tokens),
      resetTime,
      retryAfter: allowed ? undefined : Math.ceil((1 / this.refillRate) * 1000),
    };
  }
}
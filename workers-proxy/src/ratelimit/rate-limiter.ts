/**
 * API Lens Workers Proxy - Rate Limiting Service
 * 
 * Main rate limiting service with multiple limit types and algorithms
 */

import { Context } from 'hono';
import {
  RateLimitResult,
  RateLimitType,
  RateLimitConfig,
  CompanyRateLimits,
  RateLimitError,
  RateLimitAlgorithm,
} from './types';
import { RedisRateLimiter } from './redis-limiter';
import { Company, APIKey } from '../auth/types';
import { Env } from '../index';

export class RateLimitService {
  private redisLimiter: RedisRateLimiter;
  private defaultConfig: RateLimitConfig;

  constructor(private env: Env) {
    this.redisLimiter = new RedisRateLimiter(env);
    
    this.defaultConfig = {
      requestsPerMinute: parseInt(env.DEFAULT_RATE_LIMIT_PER_MINUTE || '60'),
      requestsPerHour: parseInt(env.DEFAULT_RATE_LIMIT_PER_HOUR || '1000'),
      requestsPerDay: parseInt(env.DEFAULT_RATE_LIMIT_PER_DAY || '10000'),
      costPerMinute: parseFloat(env.DEFAULT_COST_LIMIT_PER_MINUTE || '10.0'),
      costPerHour: parseFloat(env.DEFAULT_COST_LIMIT_PER_HOUR || '100.0'),
      costPerDay: parseFloat(env.DEFAULT_COST_LIMIT_PER_DAY || '500.0'),
      enabled: true,
    };
  }

  /**
   * Check rate limit for a company with multiple limit types
   */
  async checkRateLimit(
    companyId: string,
    limitType: RateLimitType,
    cost: number = 1,
    customLimits?: Partial<RateLimitConfig>
  ): Promise<RateLimitResult> {
    const config = this.getEffectiveConfig(customLimits);
    
    if (!config.enabled) {
      return this.createPassedResult(limitType, 999999);
    }

    const { limit, windowMs } = this.getLimitAndWindow(limitType, config);
    
    if (limit === undefined) {
      return this.createPassedResult(limitType, 999999);
    }

    return this.redisLimiter.checkRateLimit(
      companyId,
      limitType,
      limit,
      windowMs,
      cost
    );
  }

  /**
   * Check all applicable rate limits for a request
   */
  async checkAllRateLimits(
    company: Company,
    apiKey: APIKey,
    estimatedCost: number = 0
  ): Promise<{
    allowed: boolean;
    results: RateLimitResult[];
    blockedBy?: RateLimitType;
  }> {
    const config = this.getCompanyConfig(company);
    const results: RateLimitResult[] = [];
    
    // Define all limit types to check
    const limitsToCheck: RateLimitType[] = [
      RateLimitType.REQUESTS_PER_MINUTE,
      RateLimitType.REQUESTS_PER_HOUR,
      RateLimitType.REQUESTS_PER_DAY,
    ];

    // Add cost limits if cost is provided
    if (estimatedCost > 0) {
      limitsToCheck.push(
        RateLimitType.COST_PER_MINUTE,
        RateLimitType.COST_PER_HOUR,
        RateLimitType.COST_PER_DAY
      );
    }

    // Check each limit type
    for (const limitType of limitsToCheck) {
      const cost = limitType.includes('cost') ? estimatedCost : 1;
      const result = await this.checkRateLimit(
        company.id,
        limitType,
        cost,
        config
      );
      
      results.push(result);
      
      if (!result.allowed) {
        return {
          allowed: false,
          results,
          blockedBy: limitType,
        };
      }
    }

    return {
      allowed: true,
      results,
    };
  }

  /**
   * Increment rate counter for successful requests
   */
  async incrementRateCounter(
    companyId: string,
    limitType: RateLimitType,
    cost: number = 1
  ): Promise<number> {
    return this.redisLimiter.incrementRateCounter(companyId, limitType, cost);
  }

  /**
   * Increment all applicable counters after successful request
   */
  async incrementAllCounters(
    company: Company,
    actualCost: number = 0
  ): Promise<void> {
    const promises: Promise<any>[] = [
      // Request counters
      this.incrementRateCounter(company.id, RateLimitType.REQUESTS_PER_MINUTE, 1),
      this.incrementRateCounter(company.id, RateLimitType.REQUESTS_PER_HOUR, 1),
      this.incrementRateCounter(company.id, RateLimitType.REQUESTS_PER_DAY, 1),
    ];

    // Cost counters if cost is provided
    if (actualCost > 0) {
      promises.push(
        this.incrementRateCounter(company.id, RateLimitType.COST_PER_MINUTE, actualCost),
        this.incrementRateCounter(company.id, RateLimitType.COST_PER_HOUR, actualCost),
        this.incrementRateCounter(company.id, RateLimitType.COST_PER_DAY, actualCost)
      );
    }

    // Execute all increments concurrently
    await Promise.allSettled(promises);
  }

  /**
   * Get rate limit headers for response
   */
  getRateLimitHeaders(results: RateLimitResult[]): Record<string, string> {
    const headers: Record<string, string> = {};
    
    // Find the most restrictive limit
    const mostRestrictive = results.reduce((prev, current) => {
      if (!prev) return current;
      
      // Prefer blocked limits
      if (!current.allowed && prev.allowed) return current;
      if (current.allowed && !prev.allowed) return prev;
      
      // Prefer lower remaining ratios
      const currentRatio = current.remaining / current.limit;
      const prevRatio = prev.remaining / prev.limit;
      
      return currentRatio < prevRatio ? current : prev;
    });

    if (mostRestrictive) {
      headers['X-RateLimit-Limit'] = mostRestrictive.limit.toString();
      headers['X-RateLimit-Remaining'] = mostRestrictive.remaining.toString();
      headers['X-RateLimit-Reset'] = Math.ceil(mostRestrictive.resetTime / 1000).toString();
      headers['X-RateLimit-Type'] = mostRestrictive.limitType;
      
      if (mostRestrictive.retryAfter) {
        headers['Retry-After'] = mostRestrictive.retryAfter.toString();
      }

      if (mostRestrictive.cost !== undefined) {
        headers['X-RateLimit-Cost'] = mostRestrictive.cost.toString();
      }

      if (mostRestrictive.costRemaining !== undefined) {
        headers['X-RateLimit-Cost-Remaining'] = mostRestrictive.costRemaining.toString();
      }
    }

    // Add detailed headers for each limit type
    for (const result of results) {
      const prefix = this.getHeaderPrefix(result.limitType);
      headers[`${prefix}-Limit`] = result.limit.toString();
      headers[`${prefix}-Remaining`] = result.remaining.toString();
      headers[`${prefix}-Reset`] = Math.ceil(result.resetTime / 1000).toString();
    }

    return headers;
  }

  /**
   * Handle rate limit exceeded - create error response
   */
  handleRateLimitExceeded(result: RateLimitResult): RateLimitError {
    const limitTypeDisplay = this.getLimitTypeDisplay(result.limitType);
    
    return {
      code: 'RATE_LIMIT_EXCEEDED',
      message: `Rate limit exceeded for ${limitTypeDisplay}. Limit: ${result.limit}, Remaining: ${result.remaining}`,
      retryAfter: result.retryAfter || 60,
      limit: result.limit,
      remaining: result.remaining,
      resetTime: result.resetTime,
      limitType: result.limitType,
    };
  }

  /**
   * Get company-specific rate limit configuration
   */
  private getCompanyConfig(company: Company): RateLimitConfig {
    // Use company tier to determine base limits
    const tierLimits = this.getTierLimits(company.tier);
    
    // Apply company-specific rate limits if they exist
    return {
      ...this.defaultConfig,
      ...tierLimits,
      ...company.rateLimits,
    };
  }

  /**
   * Get tier-based rate limits
   */
  private getTierLimits(tier: string): Partial<RateLimitConfig> {
    switch (tier) {
      case 'STARTER':
        return {
          requestsPerMinute: 30,
          requestsPerHour: 500,
          requestsPerDay: 2000,
          costPerMinute: 2.0,
          costPerHour: 20.0,
          costPerDay: 100.0,
        };
      
      case 'PROFESSIONAL':
        return {
          requestsPerMinute: 100,
          requestsPerHour: 2000,
          requestsPerDay: 20000,
          costPerMinute: 10.0,
          costPerHour: 100.0,
          costPerDay: 1000.0,
        };
      
      case 'ENTERPRISE':
        return {
          requestsPerMinute: 500,
          requestsPerHour: 10000,
          requestsPerDay: 100000,
          costPerMinute: 50.0,
          costPerHour: 500.0,
          costPerDay: 5000.0,
        };
      
      default:
        return {};
    }
  }

  /**
   * Get effective configuration with custom overrides
   */
  private getEffectiveConfig(customLimits?: Partial<RateLimitConfig>): RateLimitConfig {
    return {
      ...this.defaultConfig,
      ...customLimits,
    };
  }

  /**
   * Get limit value and window size for a limit type
   */
  private getLimitAndWindow(
    limitType: RateLimitType,
    config: RateLimitConfig
  ): { limit: number | undefined; windowMs: number } {
    switch (limitType) {
      case RateLimitType.REQUESTS_PER_MINUTE:
        return { limit: config.requestsPerMinute, windowMs: 60 * 1000 };
      
      case RateLimitType.REQUESTS_PER_HOUR:
        return { limit: config.requestsPerHour, windowMs: 60 * 60 * 1000 };
      
      case RateLimitType.REQUESTS_PER_DAY:
        return { limit: config.requestsPerDay, windowMs: 24 * 60 * 60 * 1000 };
      
      case RateLimitType.COST_PER_MINUTE:
        return { limit: config.costPerMinute, windowMs: 60 * 1000 };
      
      case RateLimitType.COST_PER_HOUR:
        return { limit: config.costPerHour, windowMs: 60 * 60 * 1000 };
      
      case RateLimitType.COST_PER_DAY:
        return { limit: config.costPerDay, windowMs: 24 * 60 * 60 * 1000 };
      
      default:
        return { limit: undefined, windowMs: 60 * 1000 };
    }
  }

  /**
   * Create a passed result for unlimited scenarios
   */
  private createPassedResult(limitType: RateLimitType, limit: number): RateLimitResult {
    const now = Date.now();
    return {
      allowed: true,
      limit,
      remaining: limit,
      resetTime: now + 3600000, // 1 hour
      limitType,
      windowStart: now,
      windowEnd: now + 3600000,
    };
  }

  /**
   * Get header prefix for limit type
   */
  private getHeaderPrefix(limitType: RateLimitType): string {
    switch (limitType) {
      case RateLimitType.REQUESTS_PER_MINUTE:
        return 'X-RateLimit-Requests-Minute';
      case RateLimitType.REQUESTS_PER_HOUR:
        return 'X-RateLimit-Requests-Hour';
      case RateLimitType.REQUESTS_PER_DAY:
        return 'X-RateLimit-Requests-Day';
      case RateLimitType.COST_PER_MINUTE:
        return 'X-RateLimit-Cost-Minute';
      case RateLimitType.COST_PER_HOUR:
        return 'X-RateLimit-Cost-Hour';
      case RateLimitType.COST_PER_DAY:
        return 'X-RateLimit-Cost-Day';
      default:
        return 'X-RateLimit';
    }
  }

  /**
   * Get display name for limit type
   */
  private getLimitTypeDisplay(limitType: RateLimitType): string {
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

  /**
   * Get rate limiting metrics
   */
  getMetrics() {
    return this.redisLimiter.getMetrics();
  }
}
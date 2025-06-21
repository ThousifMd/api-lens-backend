/**
 * API Lens Workers Proxy - Redis Rate Limiter
 * 
 * Distributed rate limiting using Redis with sliding window algorithms
 */

import {
  RateLimitResult,
  RateLimitType,
  RateLimitOptions,
  RateLimitAlgorithm,
  SlidingWindowData,
  RedisRateLimitData,
  RateLimitMetrics,
} from './types';
import { Env } from '../index';

export class RedisRateLimiter {
  private redisUrl: string;
  private redisToken: string;
  private keyPrefix: string;
  private metrics: RateLimitMetrics;
  private lastCleanup: number = 0;
  private readonly CLEANUP_INTERVAL = 300000; // 5 minutes

  constructor(
    private env: Env,
    options: Partial<RateLimitOptions> = {}
  ) {
    this.redisUrl = env.REDIS_URL || '';
    this.redisToken = env.REDIS_TOKEN || '';
    this.keyPrefix = options.keyPrefix || 'rl';
    
    this.metrics = {
      totalRequests: 0,
      totalBlocked: 0,
      averageLatency: 0,
      peakRequestsPerSecond: 0,
      currentActiveWindows: 0,
      cacheHitRate: 0,
      redisLatency: 0,
    };
  }

  /**
   * Check rate limit using sliding window log algorithm
   */
  async checkRateLimit(
    companyId: string,
    limitType: RateLimitType,
    limit: number,
    windowMs: number,
    cost: number = 1
  ): Promise<RateLimitResult> {
    const startTime = Date.now();
    this.metrics.totalRequests++;

    try {
      const result = await this.slidingWindowCheck(
        companyId,
        limitType,
        limit,
        windowMs,
        cost
      );

      this.updateMetrics(startTime, result.allowed);
      return result;

    } catch (error) {
      console.error('Rate limit check failed:', error);
      
      // Fallback to KV storage if Redis fails
      return this.fallbackToKV(companyId, limitType, limit, windowMs, cost);
    }
  }

  /**
   * Sliding window log implementation with Redis
   */
  private async slidingWindowCheck(
    companyId: string,
    limitType: RateLimitType,
    limit: number,
    windowMs: number,
    cost: number
  ): Promise<RateLimitResult> {
    const now = Date.now();
    const windowStart = now - windowMs;
    const key = this.buildKey(companyId, limitType);
    
    // Redis pipeline for atomic operations
    const commands = [
      // Remove expired entries
      ['ZREMRANGEBYSCORE', key, '-inf', windowStart.toString()],
      // Count current entries
      ['ZCARD', key],
      // Get total cost in window (for cost-based limits)
      ['ZRANGE', key, '0', '-1', 'WITHSCORES'],
      // Add current request
      ['ZADD', key, now.toString(), `${now}:${cost}`],
      // Set expiration
      ['EXPIRE', key, Math.ceil(windowMs / 1000) + 60], // Add buffer
    ];

    const results = await this.executeRedisPipeline(commands);
    
    if (!results || results.length < 3) {
      throw new Error('Invalid Redis response');
    }

    const currentCount = results[1] as number;
    const entries = results[2] as string[];
    
    // Calculate current cost from entries
    let currentCost = 0;
    if (limitType.includes('cost') && entries) {
      for (let i = 1; i < entries.length; i += 2) {
        const entry = entries[i - 1];
        if (entry && entry.includes(':')) {
          const [, entryCost] = entry.split(':');
          currentCost += parseFloat(entryCost) || 0;
        }
      }
    }

    const effectiveLimit = limitType.includes('cost') ? limit : limit;
    const effectiveUsage = limitType.includes('cost') ? currentCost + cost : currentCount + 1;
    const allowed = effectiveUsage <= effectiveLimit;

    // If not allowed, remove the request we just added
    if (!allowed) {
      await this.executeRedisCommand(['ZREM', key, `${now}:${cost}`]);
    }

    const resetTime = now + windowMs;
    const remaining = Math.max(0, effectiveLimit - (limitType.includes('cost') ? currentCost : currentCount));
    
    return {
      allowed,
      limit: effectiveLimit,
      remaining,
      resetTime,
      retryAfter: allowed ? undefined : Math.ceil((windowStart + windowMs - now) / 1000),
      limitType,
      windowStart,
      windowEnd: now + windowMs,
      cost: limitType.includes('cost') ? cost : undefined,
      costRemaining: limitType.includes('cost') ? Math.max(0, limit - currentCost) : undefined,
    };
  }

  /**
   * Increment rate counter atomically
   */
  async incrementRateCounter(
    companyId: string,
    limitType: RateLimitType,
    cost: number = 1
  ): Promise<number> {
    const now = Date.now();
    const key = this.buildKey(companyId, limitType);
    
    try {
      // Add to sliding window
      await this.executeRedisCommand([
        'ZADD',
        key,
        now.toString(),
        `${now}:${cost}`
      ]);

      // Get current count
      const count = await this.executeRedisCommand(['ZCARD', key]) as number;
      return count;

    } catch (error) {
      console.error('Failed to increment rate counter:', error);
      
      // Fallback to KV increment
      const kvKey = `${this.keyPrefix}:${companyId}:${limitType}:count`;
      const currentValue = await this.env.RATE_LIMIT_KV.get(kvKey);
      const newValue = (parseInt(currentValue || '0') + 1).toString();
      await this.env.RATE_LIMIT_KV.put(kvKey, newValue, { expirationTtl: 3600 });
      return parseInt(newValue);
    }
  }

  /**
   * Sliding window counter algorithm (more memory efficient)
   */
  async slidingWindowCounter(
    companyId: string,
    limitType: RateLimitType,
    limit: number,
    windowMs: number,
    cost: number = 1
  ): Promise<RateLimitResult> {
    const now = Date.now();
    const currentWindow = Math.floor(now / windowMs);
    const previousWindow = currentWindow - 1;
    
    const currentKey = `${this.buildKey(companyId, limitType)}:${currentWindow}`;
    const previousKey = `${this.buildKey(companyId, limitType)}:${previousWindow}`;
    
    const commands = [
      // Get current and previous window counts
      ['GET', currentKey],
      ['GET', previousKey],
      // Increment current window
      ['INCR', currentKey],
      // Set expiration for current window
      ['EXPIRE', currentKey, Math.ceil(windowMs / 1000) * 2],
    ];

    const results = await this.executeRedisPipeline(commands);
    
    const currentCount = parseInt(results[0] as string || '0');
    const previousCount = parseInt(results[1] as string || '0');
    const newCurrentCount = results[2] as number;
    
    // Calculate sliding window count
    const windowProgress = (now % windowMs) / windowMs;
    const estimatedCount = Math.floor(
      previousCount * (1 - windowProgress) + currentCount
    );

    const allowed = estimatedCount + cost <= limit;
    const remaining = Math.max(0, limit - estimatedCount);
    const resetTime = (currentWindow + 1) * windowMs;

    return {
      allowed,
      limit,
      remaining,
      resetTime,
      retryAfter: allowed ? undefined : Math.ceil((resetTime - now) / 1000),
      limitType,
      windowStart: currentWindow * windowMs,
      windowEnd: resetTime,
      cost: limitType.includes('cost') ? cost : undefined,
    };
  }

  /**
   * Execute Redis command with error handling
   */
  private async executeRedisCommand(command: (string | number)[]): Promise<any> {
    if (!this.redisUrl || !this.redisToken) {
      throw new Error('Redis not configured');
    }

    const startTime = Date.now();
    
    try {
      const response = await fetch(`${this.redisUrl}/pipeline`, {
        method: 'POST',
        headers: {
          'Authorization': `Bearer ${this.redisToken}`,
          'Content-Type': 'application/json',
        },
        body: JSON.stringify([command]),
      });

      if (!response.ok) {
        throw new Error(`Redis request failed: ${response.status}`);
      }

      const results = await response.json();
      this.metrics.redisLatency = Date.now() - startTime;
      
      return results[0]?.result;

    } catch (error) {
      this.metrics.redisLatency = Date.now() - startTime;
      throw error;
    }
  }

  /**
   * Execute Redis pipeline
   */
  private async executeRedisPipeline(commands: (string | number)[][]): Promise<any[]> {
    if (!this.redisUrl || !this.redisToken) {
      throw new Error('Redis not configured');
    }

    const startTime = Date.now();
    
    try {
      const response = await fetch(`${this.redisUrl}/pipeline`, {
        method: 'POST',
        headers: {
          'Authorization': `Bearer ${this.redisToken}`,
          'Content-Type': 'application/json',
        },
        body: JSON.stringify(commands),
      });

      if (!response.ok) {
        throw new Error(`Redis pipeline failed: ${response.status}`);
      }

      const results = await response.json();
      this.metrics.redisLatency = Date.now() - startTime;
      
      return results.map((r: any) => r.result);

    } catch (error) {
      this.metrics.redisLatency = Date.now() - startTime;
      throw error;
    }
  }

  /**
   * Fallback to KV storage when Redis is unavailable
   */
  private async fallbackToKV(
    companyId: string,
    limitType: RateLimitType,
    limit: number,
    windowMs: number,
    cost: number
  ): Promise<RateLimitResult> {
    const now = Date.now();
    const key = `${this.keyPrefix}:${companyId}:${limitType}`;
    
    // Get current window data
    const dataJson = await this.env.RATE_LIMIT_KV.get(key);
    let data: SlidingWindowData = dataJson 
      ? JSON.parse(dataJson)
      : { timestamps: [], costs: [], lastCleanup: now };

    // Clean expired entries
    const windowStart = now - windowMs;
    data.timestamps = data.timestamps.filter(ts => ts > windowStart);
    data.costs = data.costs.slice(-data.timestamps.length);

    // Check if request would exceed limit
    const currentUsage = limitType.includes('cost')
      ? data.costs.reduce((sum, c) => sum + c, 0)
      : data.timestamps.length;
    
    const allowed = currentUsage + (limitType.includes('cost') ? cost : 1) <= limit;

    if (allowed) {
      // Add current request
      data.timestamps.push(now);
      data.costs.push(cost);
      data.lastCleanup = now;

      // Store updated data
      await this.env.RATE_LIMIT_KV.put(
        key,
        JSON.stringify(data),
        { expirationTtl: Math.ceil(windowMs / 1000) + 60 }
      );
    }

    const remaining = Math.max(0, limit - currentUsage);
    const resetTime = Math.min(...data.timestamps) + windowMs;

    return {
      allowed,
      limit,
      remaining,
      resetTime,
      retryAfter: allowed ? undefined : Math.ceil((resetTime - now) / 1000),
      limitType,
      windowStart,
      windowEnd: now + windowMs,
      cost: limitType.includes('cost') ? cost : undefined,
      costRemaining: limitType.includes('cost') ? Math.max(0, limit - data.costs.reduce((sum, c) => sum + c, 0)) : undefined,
    };
  }

  /**
   * Build Redis key for rate limiting
   */
  private buildKey(companyId: string, limitType: RateLimitType): string {
    return `${this.keyPrefix}:${companyId}:${limitType}`;
  }

  /**
   * Update metrics
   */
  private updateMetrics(startTime: number, allowed: boolean): void {
    const latency = Date.now() - startTime;
    
    if (!allowed) {
      this.metrics.totalBlocked++;
    }

    // Update average latency (simple moving average)
    this.metrics.averageLatency = (this.metrics.averageLatency * 0.9) + (latency * 0.1);
    
    // Periodic cleanup
    if (Date.now() - this.lastCleanup > this.CLEANUP_INTERVAL) {
      this.performCleanup().catch(() => {});
      this.lastCleanup = Date.now();
    }
  }

  /**
   * Perform periodic cleanup of expired keys
   */
  private async performCleanup(): Promise<void> {
    try {
      // This would implement cleanup logic for expired keys
      // In a real implementation, you might scan for keys and remove expired ones
      console.log('Performing rate limit cleanup...');
    } catch (error) {
      console.error('Cleanup failed:', error);
    }
  }

  /**
   * Get current metrics
   */
  getMetrics(): RateLimitMetrics {
    return { ...this.metrics };
  }

  /**
   * Reset metrics
   */
  resetMetrics(): void {
    this.metrics = {
      totalRequests: 0,
      totalBlocked: 0,
      averageLatency: 0,
      peakRequestsPerSecond: 0,
      currentActiveWindows: 0,
      cacheHitRate: 0,
      redisLatency: 0,
    };
  }
}
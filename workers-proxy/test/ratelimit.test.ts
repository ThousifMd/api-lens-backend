/**
 * Rate Limiting System Tests for API Lens Workers Proxy
 */

import { describe, it, expect, beforeAll, vi, beforeEach } from 'vitest';
import {
  checkRateLimit,
  incrementRateCounter,
  getRateLimitHeaders,
  handleRateLimitExceeded,
  createTestRateLimitResult,
  parseRateLimitType,
  RateLimitType,
  RateLimitService,
  RedisRateLimiter,
} from '../src/ratelimit';

// Mock environment for testing
const mockEnv = {
  ENVIRONMENT: 'test',
  REDIS_URL: 'https://redis.test.apilens.dev',
  REDIS_TOKEN: 'test-redis-token',
  DEFAULT_RATE_LIMIT_PER_MINUTE: '60',
  DEFAULT_RATE_LIMIT_PER_HOUR: '1000',
  DEFAULT_RATE_LIMIT_PER_DAY: '10000',
  DEFAULT_COST_LIMIT_PER_MINUTE: '10.0',
  DEFAULT_COST_LIMIT_PER_HOUR: '100.0',
  DEFAULT_COST_LIMIT_PER_DAY: '500.0',
  
  // Mock KV bindings
  RATE_LIMIT_KV: {
    get: vi.fn(),
    put: vi.fn(),
    delete: vi.fn(),
    list: vi.fn(),
  },
} as any;

describe('Rate Limiting Core Functions', () => {
  describe('parseRateLimitType', () => {
    it('should parse standard rate limit types', () => {
      expect(parseRateLimitType('requests_per_minute')).toBe(RateLimitType.REQUESTS_PER_MINUTE);
      expect(parseRateLimitType('requests_per_hour')).toBe(RateLimitType.REQUESTS_PER_HOUR);
      expect(parseRateLimitType('requests_per_day')).toBe(RateLimitType.REQUESTS_PER_DAY);
      expect(parseRateLimitType('cost_per_minute')).toBe(RateLimitType.COST_PER_MINUTE);
    });

    it('should parse abbreviated rate limit types', () => {
      expect(parseRateLimitType('minute')).toBe(RateLimitType.REQUESTS_PER_MINUTE);
      expect(parseRateLimitType('hour')).toBe(RateLimitType.REQUESTS_PER_HOUR);
      expect(parseRateLimitType('day')).toBe(RateLimitType.REQUESTS_PER_DAY);
      expect(parseRateLimitType('rpm')).toBe(RateLimitType.REQUESTS_PER_MINUTE);
    });

    it('should throw error for invalid rate limit types', () => {
      expect(() => parseRateLimitType('invalid')).toThrow('Invalid rate limit type');
      expect(() => parseRateLimitType('')).toThrow('Invalid rate limit type');
    });
  });

  describe('createTestRateLimitResult', () => {
    it('should create valid rate limit result for allowed request', () => {
      const result = createTestRateLimitResult(true, 100, 50);
      
      expect(result.allowed).toBe(true);
      expect(result.limit).toBe(100);
      expect(result.remaining).toBe(50);
      expect(result.limitType).toBe(RateLimitType.REQUESTS_PER_MINUTE);
      expect(result.retryAfter).toBeUndefined();
    });

    it('should create valid rate limit result for blocked request', () => {
      const result = createTestRateLimitResult(false, 100, 0);
      
      expect(result.allowed).toBe(false);
      expect(result.limit).toBe(100);
      expect(result.remaining).toBe(0);
      expect(result.retryAfter).toBe(60);
    });
  });

  describe('getRateLimitHeaders', () => {
    it('should create headers for single rate limit result', () => {
      const result = createTestRateLimitResult(true, 100, 50);
      const headers = getRateLimitHeaders(result);
      
      expect(headers.get('X-RateLimit-Limit')).toBe('100');
      expect(headers.get('X-RateLimit-Remaining')).toBe('50');
      expect(headers.get('X-RateLimit-Type')).toBe(RateLimitType.REQUESTS_PER_MINUTE);
    });

    it('should create headers for multiple rate limit results', () => {
      const results = [
        createTestRateLimitResult(true, 100, 50, RateLimitType.REQUESTS_PER_MINUTE),
        createTestRateLimitResult(true, 1000, 800, RateLimitType.REQUESTS_PER_HOUR),
        createTestRateLimitResult(false, 10000, 0, RateLimitType.REQUESTS_PER_DAY),
      ];
      
      const headers = getRateLimitHeaders(results);
      
      // Should show the most restrictive (blocked) limit
      expect(headers.get('X-RateLimit-Limit')).toBe('10000');
      expect(headers.get('X-RateLimit-Remaining')).toBe('0');
      expect(headers.get('Retry-After')).toBe('60');
      
      // Should include detailed headers for each type
      expect(headers.get('X-RateLimit-Requests-Minute-Limit')).toBe('100');
      expect(headers.get('X-RateLimit-Requests-Hour-Limit')).toBe('1000');
      expect(headers.get('X-RateLimit-Requests-Day-Limit')).toBe('10000');
    });
  });

  describe('checkRateLimit function', () => {
    it('should check rate limit for valid parameters', async () => {
      // Mock Redis response
      vi.spyOn(global, 'fetch').mockImplementation(async () => 
        new Response(JSON.stringify([
          { result: 0 }, // ZREMRANGEBYSCORE
          { result: 10 }, // ZCARD  
          { result: [] }, // ZRANGE
          { result: 1 }, // ZADD
          { result: 1 }, // EXPIRE
        ]), { status: 200 })
      );

      const result = await checkRateLimit(
        'comp_123',
        RateLimitType.REQUESTS_PER_MINUTE,
        1,
        mockEnv
      );

      expect(result.allowed).toBe(true);
      expect(result.limitType).toBe(RateLimitType.REQUESTS_PER_MINUTE);
    });

    it('should reject invalid limit type', async () => {
      await expect(checkRateLimit('comp_123', 'invalid_type', 1, mockEnv))
        .rejects.toThrow('Invalid limit type');
    });
  });

  describe('incrementRateCounter function', () => {
    it('should increment counter and return new value', async () => {
      // Mock Redis response
      vi.spyOn(global, 'fetch').mockImplementation(async () => 
        new Response(JSON.stringify([
          { result: 1 }, // ZADD
        ]), { status: 200 })
      );

      // Mock ZCARD response
      vi.spyOn(global, 'fetch').mockImplementation(async () => 
        new Response(JSON.stringify([
          { result: 11 }, // ZCARD
        ]), { status: 200 })
      );

      const newCount = await incrementRateCounter(
        'comp_123',
        RateLimitType.REQUESTS_PER_MINUTE,
        1,
        mockEnv
      );

      expect(typeof newCount).toBe('number');
      expect(newCount).toBeGreaterThan(0);
    });

    it('should fallback to KV on Redis failure', async () => {
      // Mock Redis failure
      vi.spyOn(global, 'fetch').mockRejectedValue(new Error('Redis unavailable'));
      
      // Mock KV get and put
      mockEnv.RATE_LIMIT_KV.get.mockResolvedValue('5');
      mockEnv.RATE_LIMIT_KV.put.mockResolvedValue(undefined);

      const newCount = await incrementRateCounter(
        'comp_123',
        RateLimitType.REQUESTS_PER_MINUTE,
        1,
        mockEnv
      );

      expect(newCount).toBe(6);
      expect(mockEnv.RATE_LIMIT_KV.put).toHaveBeenCalled();
    });
  });
});

describe('RateLimitService', () => {
  let service: RateLimitService;

  beforeEach(() => {
    service = new RateLimitService(mockEnv);
  });

  describe('checkRateLimit', () => {
    it('should allow request within limits', async () => {
      // Mock Redis success response
      vi.spyOn(global, 'fetch').mockImplementation(async () => 
        new Response(JSON.stringify([
          { result: 0 }, // ZREMRANGEBYSCORE
          { result: 5 }, // ZCARD  
          { result: [] }, // ZRANGE
          { result: 1 }, // ZADD
          { result: 1 }, // EXPIRE
        ]), { status: 200 })
      );

      const result = await service.checkRateLimit(
        'comp_123',
        RateLimitType.REQUESTS_PER_MINUTE,
        1
      );

      expect(result.allowed).toBe(true);
      expect(result.limitType).toBe(RateLimitType.REQUESTS_PER_MINUTE);
    });

    it('should block request when limit exceeded', async () => {
      // Mock Redis response indicating limit exceeded
      vi.spyOn(global, 'fetch').mockImplementation(async () => 
        new Response(JSON.stringify([
          { result: 0 }, // ZREMRANGEBYSCORE
          { result: 60 }, // ZCARD (at limit)
          { result: [] }, // ZRANGE
          { result: 1 }, // ZADD
          { result: 1 }, // EXPIRE
        ]), { status: 200 })
      );

      const result = await service.checkRateLimit(
        'comp_123',
        RateLimitType.REQUESTS_PER_MINUTE,
        1
      );

      expect(result.allowed).toBe(false);
      expect(result.remaining).toBe(0);
      expect(result.retryAfter).toBeDefined();
    });
  });

  describe('checkAllRateLimits', () => {
    const mockCompany = {
      id: 'comp_123',
      tier: 'PROFESSIONAL',
      rateLimits: {
        requestsPerMinute: 100,
        requestsPerHour: 2000,
        requestsPerDay: 20000,
      },
    };

    const mockApiKey = {
      id: 'key_123',
      permissions: {
        allowedVendors: ['*'],
      },
    };

    it('should check all applicable rate limits', async () => {
      // Mock all Redis responses as successful
      vi.spyOn(global, 'fetch').mockImplementation(async () => 
        new Response(JSON.stringify([
          { result: 0 }, // ZREMRANGEBYSCORE
          { result: 10 }, // ZCARD
          { result: [] }, // ZRANGE
          { result: 1 }, // ZADD
          { result: 1 }, // EXPIRE
        ]), { status: 200 })
      );

      const result = await service.checkAllRateLimits(
        mockCompany as any,
        mockApiKey as any,
        0
      );

      expect(result.allowed).toBe(true);
      expect(result.results).toHaveLength(3); // minute, hour, day
      expect(result.blockedBy).toBeUndefined();
    });

    it('should include cost limits when cost is provided', async () => {
      // Mock Redis responses
      vi.spyOn(global, 'fetch').mockImplementation(async () => 
        new Response(JSON.stringify([
          { result: 0 },
          { result: 5 },
          { result: [] },
          { result: 1 },
          { result: 1 },
        ]), { status: 200 })
      );

      const result = await service.checkAllRateLimits(
        mockCompany as any,
        mockApiKey as any,
        5.0 // estimated cost
      );

      expect(result.allowed).toBe(true);
      expect(result.results).toHaveLength(6); // requests + cost limits
    });

    it('should return blocked when any limit is exceeded', async () => {
      let callCount = 0;
      vi.spyOn(global, 'fetch').mockImplementation(async () => {
        callCount++;
        // Second call (hour limit) indicates exceeded
        if (callCount === 2) {
          return new Response(JSON.stringify([
            { result: 0 },
            { result: 2000 }, // At hour limit
            { result: [] },
            { result: 1 },
            { result: 1 },
          ]), { status: 200 });
        }
        // Other calls are successful
        return new Response(JSON.stringify([
          { result: 0 },
          { result: 10 },
          { result: [] },
          { result: 1 },
          { result: 1 },
        ]), { status: 200 });
      });

      const result = await service.checkAllRateLimits(
        mockCompany as any,
        mockApiKey as any,
        0
      );

      expect(result.allowed).toBe(false);
      expect(result.blockedBy).toBe(RateLimitType.REQUESTS_PER_HOUR);
    });
  });

  describe('getRateLimitHeaders', () => {
    it('should generate comprehensive headers', () => {
      const results = [
        createTestRateLimitResult(true, 100, 80, RateLimitType.REQUESTS_PER_MINUTE),
        createTestRateLimitResult(true, 1000, 500, RateLimitType.REQUESTS_PER_HOUR),
      ];

      const headers = service.getRateLimitHeaders(results);

      expect(headers['X-RateLimit-Limit']).toBeDefined();
      expect(headers['X-RateLimit-Remaining']).toBeDefined();
      expect(headers['X-RateLimit-Reset']).toBeDefined();
      expect(headers['X-RateLimit-Requests-Minute-Limit']).toBe('100');
      expect(headers['X-RateLimit-Requests-Hour-Limit']).toBe('1000');
    });
  });

  describe('handleRateLimitExceeded', () => {
    it('should create proper error object', () => {
      const result = createTestRateLimitResult(false, 100, 0);
      const error = service.handleRateLimitExceeded(result);

      expect(error.code).toBe('RATE_LIMIT_EXCEEDED');
      expect(error.message).toContain('requests per minute');
      expect(error.limit).toBe(100);
      expect(error.remaining).toBe(0);
      expect(error.retryAfter).toBeDefined();
    });
  });
});

describe('RedisRateLimiter', () => {
  let limiter: RedisRateLimiter;

  beforeEach(() => {
    limiter = new RedisRateLimiter(mockEnv);
  });

  describe('checkRateLimit', () => {
    it('should handle successful Redis responses', async () => {
      vi.spyOn(global, 'fetch').mockImplementation(async () => 
        new Response(JSON.stringify([
          { result: 0 }, // ZREMRANGEBYSCORE
          { result: 15 }, // ZCARD
          { result: [] }, // ZRANGE
          { result: 1 }, // ZADD
          { result: 1 }, // EXPIRE
        ]), { status: 200 })
      );

      const result = await limiter.checkRateLimit(
        'comp_123',
        RateLimitType.REQUESTS_PER_MINUTE,
        60,
        60000,
        1
      );

      expect(result.allowed).toBe(true);
      expect(result.limit).toBe(60);
    });

    it('should fallback to KV when Redis fails', async () => {
      // Mock Redis failure
      vi.spyOn(global, 'fetch').mockRejectedValue(new Error('Redis down'));
      
      // Mock KV fallback
      mockEnv.RATE_LIMIT_KV.get.mockResolvedValue(null);
      mockEnv.RATE_LIMIT_KV.put.mockResolvedValue(undefined);

      const result = await limiter.checkRateLimit(
        'comp_123',
        RateLimitType.REQUESTS_PER_MINUTE,
        60,
        60000,
        1
      );

      expect(result.allowed).toBe(true);
      expect(mockEnv.RATE_LIMIT_KV.put).toHaveBeenCalled();
    });
  });

  describe('slidingWindowCounter', () => {
    it('should implement sliding window counter algorithm', async () => {
      vi.spyOn(global, 'fetch').mockImplementation(async () => 
        new Response(JSON.stringify([
          { result: '10' }, // Current window
          { result: '5' }, // Previous window  
          { result: 11 }, // INCR
          { result: 1 }, // EXPIRE
        ]), { status: 200 })
      );

      const result = await limiter.slidingWindowCounter(
        'comp_123',
        RateLimitType.REQUESTS_PER_MINUTE,
        60,
        60000,
        1
      );

      expect(result.allowed).toBe(true);
      expect(result.limit).toBe(60);
    });
  });

  describe('incrementRateCounter', () => {
    it('should increment counter atomically', async () => {
      vi.spyOn(global, 'fetch').mockImplementation(async (url) => {
        if (url.toString().includes('pipeline')) {
          return new Response(JSON.stringify([
            { result: 1 }, // ZADD
          ]), { status: 200 });
        }
        // ZCARD call
        return new Response(JSON.stringify([
          { result: 25 }, // ZCARD
        ]), { status: 200 });
      });

      const count = await limiter.incrementRateCounter(
        'comp_123',
        RateLimitType.REQUESTS_PER_MINUTE,
        1
      );

      expect(typeof count).toBe('number');
      expect(count).toBeGreaterThan(0);
    });
  });

  describe('metrics', () => {
    it('should track and return metrics', () => {
      const metrics = limiter.getMetrics();

      expect(metrics).toHaveProperty('totalRequests');
      expect(metrics).toHaveProperty('totalBlocked');
      expect(metrics).toHaveProperty('averageLatency');
      expect(metrics).toHaveProperty('redisLatency');
    });

    it('should reset metrics', () => {
      limiter.resetMetrics();
      const metrics = limiter.getMetrics();

      expect(metrics.totalRequests).toBe(0);
      expect(metrics.totalBlocked).toBe(0);
      expect(metrics.averageLatency).toBe(0);
    });
  });
});

describe('Rate Limiting Integration', () => {
  describe('Load Testing Scenarios', () => {
    it('should handle burst traffic within limits', async () => {
      const limiter = new RedisRateLimiter(mockEnv);
      
      // Mock Redis to allow first few requests then block
      let requestCount = 0;
      vi.spyOn(global, 'fetch').mockImplementation(async () => {
        requestCount++;
        const remaining = Math.max(0, 60 - requestCount);
        
        return new Response(JSON.stringify([
          { result: 0 },
          { result: requestCount },
          { result: [] },
          { result: 1 },
          { result: 1 },
        ]), { status: 200 });
      });

      const promises = [];
      for (let i = 0; i < 70; i++) {
        promises.push(
          limiter.checkRateLimit(
            'comp_123',
            RateLimitType.REQUESTS_PER_MINUTE,
            60,
            60000,
            1
          )
        );
      }

      const results = await Promise.all(promises);
      const allowed = results.filter(r => r.allowed).length;
      const blocked = results.filter(r => !r.allowed).length;

      expect(allowed).toBeGreaterThan(0);
      expect(blocked).toBeGreaterThan(0);
      expect(allowed + blocked).toBe(70);
    });

    it('should handle concurrent requests correctly', async () => {
      const service = new RateLimitService(mockEnv);
      
      // Mock company and API key
      const mockCompany = {
        id: 'comp_concurrent',
        tier: 'PROFESSIONAL',
        rateLimits: { requestsPerMinute: 10 },
      };
      const mockApiKey = { id: 'key_123', permissions: {} };

      // Mock Redis responses
      let requestCount = 0;
      vi.spyOn(global, 'fetch').mockImplementation(async () => {
        requestCount++;
        return new Response(JSON.stringify([
          { result: 0 },
          { result: Math.min(requestCount, 10) },
          { result: [] },
          { result: 1 },
          { result: 1 },
        ]), { status: 200 });
      });

      // Fire 20 concurrent requests
      const promises = Array(20).fill(0).map(() =>
        service.checkAllRateLimits(mockCompany as any, mockApiKey as any, 0)
      );

      const results = await Promise.allSettled(promises);
      const successful = results.filter(r => 
        r.status === 'fulfilled' && r.value.allowed
      ).length;

      expect(successful).toBeGreaterThan(0);
      expect(successful).toBeLessThanOrEqual(10);
    });
  });

  describe('Cost-based Rate Limiting', () => {
    it('should handle cost-based limits correctly', async () => {
      const service = new RateLimitService(mockEnv);
      
      // Mock Redis to track costs
      let totalCost = 0;
      vi.spyOn(global, 'fetch').mockImplementation(async () => {
        totalCost += 5.0; // Each request costs $5
        
        return new Response(JSON.stringify([
          { result: 0 },
          { result: 1 },
          { result: [`${Date.now()}:5.0`] }, // Cost tracking
          { result: 1 },
          { result: 1 },
        ]), { status: 200 });
      });

      const result = await service.checkRateLimit(
        'comp_123',
        RateLimitType.COST_PER_MINUTE,
        5.0 // $5 cost
      );

      expect(result.allowed).toBe(true);
      expect(result.cost).toBe(5.0);
    });
  });

  describe('Error Handling', () => {
    it('should gracefully handle Redis timeouts', async () => {
      const limiter = new RedisRateLimiter(mockEnv);
      
      // Mock Redis timeout
      vi.spyOn(global, 'fetch').mockImplementation(async () => {
        await new Promise(resolve => setTimeout(resolve, 100));
        throw new Error('Request timeout');
      });

      // Mock KV fallback
      mockEnv.RATE_LIMIT_KV.get.mockResolvedValue(null);
      mockEnv.RATE_LIMIT_KV.put.mockResolvedValue(undefined);

      const result = await limiter.checkRateLimit(
        'comp_123',
        RateLimitType.REQUESTS_PER_MINUTE,
        60,
        60000,
        1
      );

      expect(result.allowed).toBe(true); // Should fallback gracefully
    });
  });
});

describe('Performance Tests', () => {
  it('should handle high-throughput scenarios', async () => {
    const limiter = new RedisRateLimiter(mockEnv);
    
    // Mock fast Redis responses
    vi.spyOn(global, 'fetch').mockImplementation(async () => {
      await new Promise(resolve => setTimeout(resolve, 1)); // 1ms delay
      return new Response(JSON.stringify([
        { result: 0 }, { result: 10 }, { result: [] }, { result: 1 }, { result: 1 },
      ]), { status: 200 });
    });

    const startTime = Date.now();
    const promises = Array(100).fill(0).map((_, i) =>
      limiter.checkRateLimit(
        `comp_${i % 10}`, // 10 different companies
        RateLimitType.REQUESTS_PER_MINUTE,
        60,
        60000,
        1
      )
    );

    await Promise.all(promises);
    const duration = Date.now() - startTime;

    // Should complete 100 rate limit checks in reasonable time
    expect(duration).toBeLessThan(5000); // 5 seconds max
  });
});
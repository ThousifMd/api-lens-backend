/**
 * API Lens Workers Proxy - Rate Limiting Module
 * 
 * Main exports for the rate limiting system
 */

// Export main service classes
export { RateLimitService } from './rate-limiter';
export { RedisRateLimiter } from './redis-limiter';

// Export core functions
export {
  checkRateLimit,
  incrementRateCounter,
  getRateLimitHeaders,
  handleRateLimitExceeded,
  checkAuthenticatedRateLimit,
  incrementAuthenticatedCounters,
  checkSpecificRateLimit,
  getRateLimitMetrics,
  createTestRateLimitResult,
  parseRateLimitType,
} from './functions';

// Export types
export type {
  RateLimitResult,
  RateLimitConfig,
  RateLimitOptions,
  RateLimitError,
  RateLimitMetrics,
  SlidingWindowData,
  RedisRateLimitData,
  CompanyRateLimits,
  RateLimitCache,
  RateLimitPipeline,
} from './types';

export {
  RateLimitType,
  RateLimitAlgorithm,
} from './types';

/**
 * Main rate limiting middleware factory
 */
export function createRateLimitMiddleware(options?: {
  estimatedCost?: number;
  skipOnError?: boolean;
}) {
  return async function rateLimitMiddleware(c: any, next: any) {
    const { estimatedCost = 0, skipOnError = true } = options || {};
    
    try {
      // Import dynamically to avoid circular dependencies
      const { checkAuthenticatedRateLimit, handleRateLimitExceeded } = await import('./functions');
      
      // Check rate limits
      const rateLimitResult = await checkAuthenticatedRateLimit(c, estimatedCost);
      
      if (!rateLimitResult.allowed && rateLimitResult.blockedBy) {
        const blockedResult = rateLimitResult.results.find(r => !r.allowed);
        if (blockedResult) {
          return handleRateLimitExceeded(blockedResult, c);
        }
      }
      
      // Store rate limit results in context for later use
      c.set('rateLimitResults', rateLimitResult.results);
      
      // Continue to next middleware
      await next();
      
    } catch (error) {
      if (skipOnError) {
        console.error('Rate limiting error:', error);
        await next();
      } else {
        throw error;
      }
    }
  };
}

/**
 * Utility function to create rate limit headers middleware
 */
export function createRateLimitHeadersMiddleware() {
  return async function rateLimitHeadersMiddleware(c: any, next: any) {
    await next();
    
    try {
      const rateLimitResults = c.get('rateLimitResults');
      if (rateLimitResults && Array.isArray(rateLimitResults)) {
        const { getRateLimitHeaders } = await import('./functions');
        const headers = getRateLimitHeaders(rateLimitResults);
        
        // Add headers to response
        for (const [key, value] of headers.entries()) {
          c.header(key, value);
        }
      }
    } catch (error) {
      console.error('Error adding rate limit headers:', error);
    }
  };
}

/**
 * Utility function to increment counters after successful request
 */
export function createCounterIncrementMiddleware() {
  return async function counterIncrementMiddleware(c: any, next: any) {
    let actualCost = 0;
    
    // Execute the request
    await next();
    
    try {
      // Get actual cost from context if available
      actualCost = c.get('actualCost') || c.get('requestCost') || 0;
      
      // Only increment on successful responses
      if (c.res && c.res.status < 400) {
        const { incrementAuthenticatedCounters } = await import('./functions');
        await incrementAuthenticatedCounters(c, actualCost);
      }
    } catch (error) {
      console.error('Error incrementing rate limit counters:', error);
    }
  };
}
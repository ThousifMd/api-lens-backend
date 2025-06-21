/**
 * API Lens Workers Proxy - Redis-based Authentication Cache
 * 
 * Redis caching layer for authentication with KV fallback
 */

import { Company, APIKey, RedisAuthCache, CacheEntry, AuthErrorCode } from './types';
import { Env } from '../index';

export class AuthCache {
  private env: Env;
  private redisUrl?: string;
  private redisToken?: string;
  
  constructor(env: Env) {
    this.env = env;
    this.redisUrl = env.REDIS_URL;
    this.redisToken = env.REDIS_TOKEN;
  }
  
  /**
   * Get cached company data by API key hash
   */
  async getCachedCompany(apiKeyHash: string): Promise<{ company: Company; apiKey: APIKey } | null> {
    const startTime = Date.now();
    
    try {
      // Try Redis first if available
      if (this.redisUrl && this.redisToken) {
        const redisResult = await this.getFromRedis(apiKeyHash);
        if (redisResult) {
          console.log(`Redis cache hit for ${apiKeyHash.slice(0, 8)}... (${Date.now() - startTime}ms)`);
          return redisResult;
        }
      }
      
      // Fallback to KV storage
      const kvResult = await this.getFromKV(apiKeyHash);
      if (kvResult) {
        console.log(`KV cache hit for ${apiKeyHash.slice(0, 8)}... (${Date.now() - startTime}ms)`);
        
        // Async backfill to Redis if available
        if (this.redisUrl && this.redisToken) {
          this.setInRedis(apiKeyHash, kvResult).catch(error => {
            console.warn('Failed to backfill Redis cache:', error);
          });
        }
        
        return kvResult;
      }
      
      console.log(`Cache miss for ${apiKeyHash.slice(0, 8)}... (${Date.now() - startTime}ms)`);
      return null;
      
    } catch (error) {
      console.error('Error getting cached company:', error);
      return null;
    }
  }
  
  /**
   * Set company data in cache
   */
  async setCachedCompany(
    apiKeyHash: string, 
    company: Company, 
    apiKey: APIKey, 
    ttlSeconds: number = 300
  ): Promise<void> {
    const data = { company, apiKey };
    
    try {
      // Set in both Redis and KV in parallel
      await Promise.allSettled([
        this.setInRedis(apiKeyHash, data, ttlSeconds),
        this.setInKV(apiKeyHash, data, ttlSeconds),
      ]);
    } catch (error) {
      console.error('Error setting cached company:', error);
    }
  }
  
  /**
   * Invalidate cached company data
   */
  async invalidateCachedCompany(apiKeyHash: string): Promise<void> {
    try {
      await Promise.allSettled([
        this.deleteFromRedis(apiKeyHash),
        this.deleteFromKV(apiKeyHash),
      ]);
    } catch (error) {
      console.error('Error invalidating cached company:', error);
    }
  }
  
  /**
   * Get data from Redis
   */
  private async getFromRedis(apiKeyHash: string): Promise<{ company: Company; apiKey: APIKey } | null> {
    if (!this.redisUrl || !this.redisToken) {
      return null;
    }
    
    try {
      const response = await fetch(`${this.redisUrl}/get/auth:${apiKeyHash}`, {
        headers: {
          'Authorization': `Bearer ${this.redisToken}`,
        },
      });
      
      if (response.status === 404) {
        return null; // Key not found
      }
      
      if (!response.ok) {
        throw new Error(`Redis GET failed: ${response.status}`);
      }
      
      const data = await response.json();
      const cacheEntry = data.result as RedisAuthCache;
      
      // Check if cache entry is expired
      if (Date.now() > cacheEntry.expiresAt) {
        // Async delete expired entry
        this.deleteFromRedis(apiKeyHash).catch(() => {});
        return null;
      }
      
      return {
        company: cacheEntry.company,
        apiKey: cacheEntry.apiKey,
      };
      
    } catch (error) {
      console.error('Redis GET error:', error);
      return null;
    }
  }
  
  /**
   * Set data in Redis
   */
  private async setInRedis(
    apiKeyHash: string, 
    data: { company: Company; apiKey: APIKey }, 
    ttlSeconds: number = 300
  ): Promise<void> {
    if (!this.redisUrl || !this.redisToken) {
      return;
    }
    
    try {
      const cacheEntry: RedisAuthCache = {
        company: data.company,
        apiKey: data.apiKey,
        cachedAt: Date.now(),
        expiresAt: Date.now() + (ttlSeconds * 1000),
      };
      
      const response = await fetch(`${this.redisUrl}/set/auth:${apiKeyHash}`, {
        method: 'POST',
        headers: {
          'Authorization': `Bearer ${this.redisToken}`,
          'Content-Type': 'application/json',
        },
        body: JSON.stringify({
          value: JSON.stringify(cacheEntry),
          ex: ttlSeconds, // Redis expiration
        }),
      });
      
      if (!response.ok) {
        throw new Error(`Redis SET failed: ${response.status}`);
      }
      
    } catch (error) {
      console.error('Redis SET error:', error);
      throw error;
    }
  }
  
  /**
   * Delete data from Redis
   */
  private async deleteFromRedis(apiKeyHash: string): Promise<void> {
    if (!this.redisUrl || !this.redisToken) {
      return;
    }
    
    try {
      await fetch(`${this.redisUrl}/del/auth:${apiKeyHash}`, {
        method: 'DELETE',
        headers: {
          'Authorization': `Bearer ${this.redisToken}`,
        },
      });
    } catch (error) {
      console.error('Redis DELETE error:', error);
    }
  }
  
  /**
   * Get data from KV storage
   */
  private async getFromKV(apiKeyHash: string): Promise<{ company: Company; apiKey: APIKey } | null> {
    try {
      const cacheKey = `auth:${apiKeyHash}`;
      const cached = await this.env.CACHE_KV.get(cacheKey, 'json');
      
      if (!cached) {
        return null;
      }
      
      const cacheEntry = cached as CacheEntry<{ company: Company; apiKey: APIKey }>;
      
      // Check if cache entry is expired
      if (Date.now() > cacheEntry.timestamp + cacheEntry.ttl) {
        // Async delete expired entry
        this.env.CACHE_KV.delete(cacheKey).catch(() => {});
        return null;
      }
      
      return cacheEntry.data;
      
    } catch (error) {
      console.error('KV GET error:', error);
      return null;
    }
  }
  
  /**
   * Set data in KV storage
   */
  private async setInKV(
    apiKeyHash: string, 
    data: { company: Company; apiKey: APIKey }, 
    ttlSeconds: number = 300
  ): Promise<void> {
    try {
      const cacheKey = `auth:${apiKeyHash}`;
      const cacheEntry: CacheEntry<{ company: Company; apiKey: APIKey }> = {
        data,
        timestamp: Date.now(),
        ttl: ttlSeconds * 1000,
      };
      
      await this.env.CACHE_KV.put(cacheKey, JSON.stringify(cacheEntry), {
        expirationTtl: ttlSeconds,
      });
      
    } catch (error) {
      console.error('KV SET error:', error);
      throw error;
    }
  }
  
  /**
   * Delete data from KV storage
   */
  private async deleteFromKV(apiKeyHash: string): Promise<void> {
    try {
      const cacheKey = `auth:${apiKeyHash}`;
      await this.env.CACHE_KV.delete(cacheKey);
    } catch (error) {
      console.error('KV DELETE error:', error);
    }
  }
  
  /**
   * Get cache statistics
   */
  async getCacheStats(): Promise<{
    redisAvailable: boolean;
    kvAvailable: boolean;
    totalKeys: number;
    estimatedSize: number;
  }> {
    const stats = {
      redisAvailable: !!(this.redisUrl && this.redisToken),
      kvAvailable: true,
      totalKeys: 0,
      estimatedSize: 0,
    };
    
    try {
      // Get KV stats
      const kvList = await this.env.CACHE_KV.list({ prefix: 'auth:' });
      stats.totalKeys = kvList.keys.length;
      
      // Estimate size (rough calculation)
      stats.estimatedSize = kvList.keys.length * 2048; // Assume avg 2KB per entry
      
    } catch (error) {
      console.error('Error getting cache stats:', error);
    }
    
    return stats;
  }
  
  /**
   * Cleanup expired entries
   */
  async cleanupExpiredEntries(): Promise<{ deleted: number; errors: number }> {
    let deleted = 0;
    let errors = 0;
    
    try {
      // List all auth cache keys
      const kvList = await this.env.CACHE_KV.list({ prefix: 'auth:' });
      
      for (const key of kvList.keys) {
        try {
          const cached = await this.env.CACHE_KV.get(key.name, 'json');
          if (cached) {
            const cacheEntry = cached as CacheEntry<any>;
            
            // Check if expired
            if (Date.now() > cacheEntry.timestamp + cacheEntry.ttl) {
              await this.env.CACHE_KV.delete(key.name);
              deleted++;
            }
          }
        } catch (error) {
          console.error(`Error checking cache entry ${key.name}:`, error);
          errors++;
        }
      }
      
    } catch (error) {
      console.error('Error during cache cleanup:', error);
      errors++;
    }
    
    return { deleted, errors };
  }
  
  /**
   * Warm cache with frequently used entries
   */
  async warmCache(frequentApiKeys: string[]): Promise<void> {
    // This would be called during startup or scheduled maintenance
    // to pre-populate cache with frequently accessed API keys
    
    for (const apiKeyHash of frequentApiKeys) {
      try {
        // Check if already cached
        const cached = await this.getCachedCompany(apiKeyHash);
        if (!cached) {
          // Would trigger backend lookup and cache population
          console.log(`Warming cache for ${apiKeyHash.slice(0, 8)}...`);
        }
      } catch (error) {
        console.error(`Error warming cache for ${apiKeyHash.slice(0, 8)}:`, error);
      }
    }
  }
}
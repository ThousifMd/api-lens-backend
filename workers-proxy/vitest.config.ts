import { defineConfig } from 'vitest/config';

export default defineConfig({
  test: {
    globals: true,
    environment: 'miniflare',
    environmentOptions: {
      // Miniflare options for testing Workers
      compatibilityDate: '2024-01-15',
      compatibilityFlags: ['nodejs_compat'],
      kvNamespaces: ['RATE_LIMIT_KV', 'CACHE_KV'],
      durableObjects: {
        RATE_LIMITER: 'RateLimiter',
      },
    },
    coverage: {
      provider: 'v8',
      reporter: ['text', 'json', 'html'],
      exclude: [
        'node_modules/',
        'dist/',
        '**/*.config.*',
        '**/*.test.*',
        '**/*.spec.*',
      ],
    },
  },
});
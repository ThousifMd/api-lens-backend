/**
 * API Lens JavaScript SDK - Async Client
 * 
 * Note: In JavaScript/TypeScript, all HTTP operations are naturally async,
 * so this is essentially the same as the main client but with a different
 * interface for consistency with other language SDKs.
 */

import { APILensClient, APILensClientConfig } from './client';

/**
 * Async API Lens client (alias for main client since JS is naturally async)
 */
export class AsyncAPILensClient extends APILensClient {
  constructor(config: APILensClientConfig) {
    super(config);
  }

  /**
   * Initialize async client with configuration
   */
  static async create(config: APILensClientConfig): Promise<AsyncAPILensClient> {
    const client = new AsyncAPILensClient(config);
    
    // Verify connection on creation
    try {
      await client.getCompany();
    } catch (error) {
      throw new Error(`Failed to initialize API Lens client: ${error.message}`);
    }
    
    return client;
  }

  /**
   * Close any persistent connections
   */
  async close(): Promise<void> {
    // In axios, there's no explicit close method needed for basic usage
    // But we could add cleanup logic here if needed for advanced features
  }
}
/**
 * API Lens JavaScript SDK - API Key Service
 */

import { APILensClient } from '../client';
import { APIKey } from '../types';

/**
 * API key management service
 */
export class APIKeyService {
  constructor(private client: APILensClient) {}

  /**
   * List all API keys for the company
   */
  async list(): Promise<APIKey[]> {
    return this.client.request<APIKey[]>({
      method: 'GET',
      url: '/companies/me/api-keys',
    });
  }

  /**
   * Create a new API key
   */
  async create(name: string): Promise<APIKey> {
    return this.client.request<APIKey>({
      method: 'POST',
      url: '/companies/me/api-keys',
      data: { name },
    });
  }

  /**
   * Revoke an API key
   */
  async revoke(keyId: string): Promise<void> {
    await this.client.request<void>({
      method: 'DELETE',
      url: `/companies/me/api-keys/${keyId}`,
    });
  }

  /**
   * Get API key details
   */
  async get(keyId: string): Promise<APIKey> {
    return this.client.request<APIKey>({
      method: 'GET',
      url: `/companies/me/api-keys/${keyId}`,
    });
  }

  /**
   * Update API key (name, description, etc.)
   */
  async update(keyId: string, updates: Partial<APIKey>): Promise<APIKey> {
    return this.client.request<APIKey>({
      method: 'PUT',
      url: `/companies/me/api-keys/${keyId}`,
      data: updates,
    });
  }
}
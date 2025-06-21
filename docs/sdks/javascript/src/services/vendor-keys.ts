/**
 * API Lens JavaScript SDK - Vendor Key Service
 */

import { APILensClient } from '../client';
import { VendorKey, VendorType } from '../types';

/**
 * Vendor key management service (BYOK - Bring Your Own Keys)
 */
export class VendorKeyService {
  constructor(private client: APILensClient) {}

  /**
   * List all vendor keys
   */
  async list(): Promise<VendorKey[]> {
    return this.client.request<VendorKey[]>({
      method: 'GET',
      url: '/companies/me/vendor-keys',
    });
  }

  /**
   * Store a vendor API key
   */
  async store(vendor: VendorType | string, apiKey: string, description?: string): Promise<VendorKey> {
    const payload: any = {
      vendor,
      api_key: apiKey,
    };

    if (description) {
      payload.description = description;
    }

    return this.client.request<VendorKey>({
      method: 'POST',
      url: '/companies/me/vendor-keys',
      data: payload,
    });
  }

  /**
   * Update a vendor API key
   */
  async update(vendor: VendorType | string, apiKey: string, description?: string): Promise<VendorKey> {
    const payload: any = {
      vendor,
      api_key: apiKey,
    };

    if (description) {
      payload.description = description;
    }

    return this.client.request<VendorKey>({
      method: 'PUT',
      url: `/companies/me/vendor-keys/${vendor}`,
      data: payload,
    });
  }

  /**
   * Remove a vendor API key
   */
  async remove(vendor: VendorType | string): Promise<void> {
    await this.client.request<void>({
      method: 'DELETE',
      url: `/companies/me/vendor-keys/${vendor}`,
    });
  }

  /**
   * Get vendor key details
   */
  async get(vendor: VendorType | string): Promise<VendorKey> {
    return this.client.request<VendorKey>({
      method: 'GET',
      url: `/companies/me/vendor-keys/${vendor}`,
    });
  }

  /**
   * Test vendor key validity
   */
  async test(vendor: VendorType | string): Promise<{ valid: boolean; error?: string }> {
    return this.client.request<{ valid: boolean; error?: string }>({
      method: 'POST',
      url: `/companies/me/vendor-keys/${vendor}/test`,
    });
  }
}
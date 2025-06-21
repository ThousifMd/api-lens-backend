/**
 * API Lens JavaScript SDK - Google AI Client
 */

import { APILensClient } from '../client';
import { GoogleGenerateContentRequest, GoogleGenerateContentResponse } from '../types';

/**
 * Google AI-compatible client that routes through API Lens
 */
export class GoogleClient {
  constructor(private client: APILensClient) {}

  /**
   * Make request to Google AI endpoint through API Lens
   */
  async request<T = any>(endpoint: string, data?: any): Promise<T> {
    return this.client.request<T>({
      method: 'POST',
      url: `/proxy/google${endpoint}`,
      data,
    });
  }

  /**
   * Generate content
   */
  async generateContent(
    model: string,
    request: GoogleGenerateContentRequest
  ): Promise<GoogleGenerateContentResponse> {
    return this.request<GoogleGenerateContentResponse>(
      `/v1/models/${model}:generateContent`,
      request
    );
  }

  /**
   * Generate content stream
   */
  async generateContentStream(
    model: string,
    request: GoogleGenerateContentRequest
  ): Promise<AsyncIterable<any>> {
    const response = await this.request(
      `/v1/models/${model}:streamGenerateContent`,
      request
    );
    
    // Return a simple async iterable wrapper
    return {
      async *[Symbol.asyncIterator]() {
        yield response;
      }
    };
  }

  /**
   * List available models
   */
  async listModels(): Promise<{
    models: Array<{
      name: string;
      displayName: string;
      description: string;
      inputTokenLimit: number;
      outputTokenLimit: number;
      supportedGenerationMethods: string[];
    }>;
  }> {
    return this.client.request({
      method: 'GET',
      url: '/proxy/google/v1/models',
    });
  }

  /**
   * Get model details
   */
  async getModel(modelName: string): Promise<{
    name: string;
    displayName: string;
    description: string;
    inputTokenLimit: number;
    outputTokenLimit: number;
    supportedGenerationMethods: string[];
  }> {
    return this.client.request({
      method: 'GET',
      url: `/proxy/google/v1/models/${modelName}`,
    });
  }

  /**
   * Count tokens
   */
  async countTokens(
    model: string,
    request: { contents: GoogleGenerateContentRequest['contents'] }
  ): Promise<{
    totalTokens: number;
  }> {
    return this.request(`/v1/models/${model}:countTokens`, request);
  }

  /**
   * Embed content
   */
  async embedContent(
    model: string,
    request: {
      content: {
        parts: Array<{ text: string }>;
      };
      taskType?: string;
      title?: string;
    }
  ): Promise<{
    embedding: {
      values: number[];
    };
  }> {
    return this.request(`/v1/models/${model}:embedContent`, request);
  }

  /**
   * Batch embed content
   */
  async batchEmbedContents(
    model: string,
    request: {
      requests: Array<{
        content: {
          parts: Array<{ text: string }>;
        };
        taskType?: string;
        title?: string;
      }>;
    }
  ): Promise<{
    embeddings: Array<{
      values: number[];
    }>;
  }> {
    return this.request(`/v1/models/${model}:batchEmbedContents`, request);
  }
}
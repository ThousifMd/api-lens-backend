/**
 * API Lens JavaScript SDK - Anthropic Client
 */

import { APILensClient } from '../client';
import { AnthropicMessageRequest, AnthropicMessageResponse } from '../types';

/**
 * Anthropic-compatible client that routes through API Lens
 */
export class AnthropicClient {
  public readonly messages: AnthropicMessagesClient;

  constructor(private client: APILensClient) {
    this.messages = new AnthropicMessagesClient(this);
  }

  /**
   * Make request to Anthropic endpoint through API Lens
   */
  async request<T = any>(endpoint: string, data?: any): Promise<T> {
    return this.client.request<T>({
      method: 'POST',
      url: `/proxy/anthropic${endpoint}`,
      data,
    });
  }

  /**
   * Legacy method for creating messages
   */
  async createMessage(request: AnthropicMessageRequest): Promise<AnthropicMessageResponse> {
    return this.messages.create(request);
  }
}

/**
 * Anthropic Messages API
 */
export class AnthropicMessagesClient {
  constructor(private anthropicClient: AnthropicClient) {}

  /**
   * Create message
   */
  async create(request: AnthropicMessageRequest): Promise<AnthropicMessageResponse> {
    return this.anthropicClient.request<AnthropicMessageResponse>('/messages', request);
  }

  /**
   * Create streaming message
   */
  async createStream(request: AnthropicMessageRequest): Promise<AsyncIterable<any>> {
    const streamRequest = { ...request, stream: true };
    
    // Note: In a real implementation, you'd handle Server-Sent Events here
    // For now, we'll return the response as-is
    const response = await this.anthropicClient.request('/messages', streamRequest);
    
    // Return a simple async iterable wrapper
    return {
      async *[Symbol.asyncIterator]() {
        yield response;
      }
    };
  }
}
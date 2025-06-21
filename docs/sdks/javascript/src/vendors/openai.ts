/**
 * API Lens JavaScript SDK - OpenAI Client
 */

import { APILensClient } from '../client';
import { ChatCompletionRequest, ChatCompletionResponse, ChatMessage } from '../types';

/**
 * OpenAI-compatible client that routes through API Lens
 */
export class OpenAIClient {
  public readonly chat: OpenAIChatClient;
  public readonly completions: OpenAICompletionsClient;
  public readonly embeddings: OpenAIEmbeddingsClient;
  public readonly images: OpenAIImagesClient;
  public readonly models: OpenAIModelsClient;

  constructor(private client: APILensClient) {
    this.chat = new OpenAIChatClient(this);
    this.completions = new OpenAICompletionsClient(this);
    this.embeddings = new OpenAIEmbeddingsClient(this);
    this.images = new OpenAIImagesClient(this);
    this.models = new OpenAIModelsClient(this);
  }

  /**
   * Make request to OpenAI endpoint through API Lens
   */
  async request<T = any>(endpoint: string, data?: any): Promise<T> {
    return this.client.request<T>({
      method: 'POST',
      url: `/proxy/openai${endpoint}`,
      data,
    });
  }

  /**
   * Legacy method for chat completions
   */
  async createChatCompletion(request: ChatCompletionRequest): Promise<ChatCompletionResponse> {
    return this.chat.completions.create(request);
  }
}

/**
 * OpenAI Chat API client
 */
export class OpenAIChatClient {
  public readonly completions: OpenAIChatCompletionsClient;

  constructor(private openaiClient: OpenAIClient) {
    this.completions = new OpenAIChatCompletionsClient(openaiClient);
  }
}

/**
 * OpenAI Chat Completions API
 */
export class OpenAIChatCompletionsClient {
  constructor(private openaiClient: OpenAIClient) {}

  /**
   * Create chat completion
   */
  async create(request: ChatCompletionRequest): Promise<ChatCompletionResponse> {
    return this.openaiClient.request<ChatCompletionResponse>('/chat/completions', request);
  }

  /**
   * Create streaming chat completion
   */
  async createStream(request: ChatCompletionRequest): Promise<AsyncIterable<any>> {
    const streamRequest = { ...request, stream: true };
    
    // Note: In a real implementation, you'd handle Server-Sent Events here
    // For now, we'll return the response as-is
    const response = await this.openaiClient.request('/chat/completions', streamRequest);
    
    // Return a simple async iterable wrapper
    return {
      async *[Symbol.asyncIterator]() {
        yield response;
      }
    };
  }
}

/**
 * OpenAI Text Completions API
 */
export class OpenAICompletionsClient {
  constructor(private openaiClient: OpenAIClient) {}

  /**
   * Create text completion
   */
  async create(request: {
    model: string;
    prompt: string;
    maxTokens?: number;
    temperature?: number;
    topP?: number;
    frequencyPenalty?: number;
    presencePenalty?: number;
    stop?: string | string[];
    [key: string]: any;
  }): Promise<any> {
    return this.openaiClient.request('/completions', request);
  }
}

/**
 * OpenAI Embeddings API
 */
export class OpenAIEmbeddingsClient {
  constructor(private openaiClient: OpenAIClient) {}

  /**
   * Create embeddings
   */
  async create(request: {
    model: string;
    input: string | string[];
    user?: string;
    [key: string]: any;
  }): Promise<{
    object: 'list';
    data: Array<{
      object: 'embedding';
      index: number;
      embedding: number[];
    }>;
    model: string;
    usage: {
      promptTokens: number;
      totalTokens: number;
    };
  }> {
    return this.openaiClient.request('/embeddings', request);
  }
}

/**
 * OpenAI Images API
 */
export class OpenAIImagesClient {
  constructor(private openaiClient: OpenAIClient) {}

  /**
   * Generate images
   */
  async generate(request: {
    prompt: string;
    n?: number;
    size?: '256x256' | '512x512' | '1024x1024';
    responseFormat?: 'url' | 'b64_json';
    user?: string;
    [key: string]: any;
  }): Promise<{
    created: number;
    data: Array<{
      url?: string;
      b64Json?: string;
    }>;
  }> {
    return this.openaiClient.request('/images/generations', request);
  }

  /**
   * Edit images
   */
  async edit(request: {
    image: File | Blob;
    mask?: File | Blob;
    prompt: string;
    n?: number;
    size?: '256x256' | '512x512' | '1024x1024';
    responseFormat?: 'url' | 'b64_json';
    user?: string;
  }): Promise<any> {
    // Note: File upload would require FormData handling
    return this.openaiClient.request('/images/edits', request);
  }

  /**
   * Create image variations
   */
  async createVariation(request: {
    image: File | Blob;
    n?: number;
    size?: '256x256' | '512x512' | '1024x1024';
    responseFormat?: 'url' | 'b64_json';
    user?: string;
  }): Promise<any> {
    return this.openaiClient.request('/images/variations', request);
  }
}

/**
 * OpenAI Models API
 */
export class OpenAIModelsClient {
  constructor(private openaiClient: OpenAIClient) {}

  /**
   * List available models
   */
  async list(): Promise<{
    object: 'list';
    data: Array<{
      id: string;
      object: 'model';
      created: number;
      ownedBy: string;
    }>;
  }> {
    return this.openaiClient.client.request({
      method: 'GET',
      url: '/proxy/openai/models',
    });
  }

  /**
   * Retrieve model details
   */
  async retrieve(modelId: string): Promise<{
    id: string;
    object: 'model';
    created: number;
    ownedBy: string;
  }> {
    return this.openaiClient.client.request({
      method: 'GET',
      url: `/proxy/openai/models/${modelId}`,
    });
  }
}
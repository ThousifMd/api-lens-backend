/**
 * API Lens Workers Proxy - Vendor Configurations
 * 
 * Configuration for different AI vendors and their APIs
 */

import {
  VendorConfig,
  VendorType,
  ModelMapping,
  VendorRequestFormat,
  VendorResponseFormat,
  RetryConfig,
} from './types';

/**
 * Default retry configuration
 */
const DEFAULT_RETRY_CONFIG: RetryConfig = {
  maxRetries: 3,
  baseDelay: 1000,
  maxDelay: 30000,
  backoffMultiplier: 2,
  retryableStatusCodes: [429, 500, 502, 503, 504],
  retryableErrors: ['timeout', 'network_error', 'server_error'],
};

/**
 * OpenAI vendor configuration
 */
const OPENAI_CONFIG: VendorConfig = {
  name: VendorType.OPENAI,
  baseUrl: 'https://api.openai.com/v1',
  authHeaderName: 'Authorization',
  authHeaderPrefix: 'Bearer',
  supportedModels: [
    'gpt-4o',
    'gpt-4o-mini',
    'gpt-4-turbo',
    'gpt-4',
    'gpt-3.5-turbo',
    'text-embedding-3-large',
    'text-embedding-3-small',
    'text-embedding-ada-002',
  ],
  defaultModel: 'gpt-3.5-turbo',
  endpoints: {
    chat: '/chat/completions',
    completions: '/completions',
    embeddings: '/embeddings',
    models: '/models',
  },
  requestFormat: {
    messageField: 'messages',
    modelField: 'model',
    streamField: 'stream',
    temperatureField: 'temperature',
    maxTokensField: 'max_tokens',
    stopField: 'stop',
  },
  responseFormat: {
    messageField: 'choices[0].message.content',
    usageField: 'usage',
    modelField: 'model',
    finishReasonField: 'choices[0].finish_reason',
    idField: 'id',
    createdField: 'created',
    choicesField: 'choices',
    deltaField: 'choices[0].delta',
    transformations: {
      usage: (usage) => ({
        inputTokens: usage.prompt_tokens || 0,
        outputTokens: usage.completion_tokens || 0,
        totalTokens: usage.total_tokens || 0,
        model: usage.model || 'unknown',
      }),
    },
  },
  errorCodes: {
    400: 'invalid_request',
    401: 'invalid_api_key',
    403: 'forbidden',
    404: 'not_found',
    429: 'rate_limit_exceeded',
    500: 'server_error',
    502: 'bad_gateway',
    503: 'service_unavailable',
  },
  retryConfig: DEFAULT_RETRY_CONFIG,
};

/**
 * Anthropic vendor configuration
 */
const ANTHROPIC_CONFIG: VendorConfig = {
  name: VendorType.ANTHROPIC,
  baseUrl: 'https://api.anthropic.com/v1',
  authHeaderName: 'x-api-key',
  authHeaderPrefix: '',
  supportedModels: [
    'claude-3-5-sonnet-20241022',
    'claude-3-5-haiku-20241022',
    'claude-3-opus-20240229',
    'claude-3-sonnet-20240229',
    'claude-3-haiku-20240307',
  ],
  defaultModel: 'claude-3-5-sonnet-20241022',
  endpoints: {
    chat: '/messages',
    models: '/models',
  },
  requestFormat: {
    messageField: 'messages',
    modelField: 'model',
    streamField: 'stream',
    temperatureField: 'temperature',
    maxTokensField: 'max_tokens',
    stopField: 'stop_sequences',
    customFields: {
      'anthropic-version': '2023-06-01',
      'anthropic-beta': 'messages-2023-12-15',
    },
    transformations: {
      messages: (messages) => {
        // Remove system messages and convert to Anthropic format
        return messages
          .filter(msg => msg.role !== 'system')
          .map(msg => ({
            role: msg.role === 'assistant' ? 'assistant' : 'user',
            content: msg.content,
          }));
      },
      parameters: (params) => {
        const transformed: any = { ...params };
        
        // Extract system message
        const systemMessage = params.messages?.find((msg: any) => msg.role === 'system');
        if (systemMessage) {
          transformed.system = systemMessage.content;
        }
        
        // Transform messages
        if (params.messages) {
          transformed.messages = ANTHROPIC_CONFIG.requestFormat.transformations!.messages!(params.messages);
        }
        
        return transformed;
      },
    },
  },
  responseFormat: {
    messageField: 'content[0].text',
    usageField: 'usage',
    modelField: 'model',
    finishReasonField: 'stop_reason',
    idField: 'id',
    choicesField: 'content',
    deltaField: 'delta',
    transformations: {
      usage: (usage) => ({
        inputTokens: usage.input_tokens || 0,
        outputTokens: usage.output_tokens || 0,
        totalTokens: (usage.input_tokens || 0) + (usage.output_tokens || 0),
        model: usage.model || 'unknown',
      }),
      content: (content) => {
        if (Array.isArray(content)) {
          return content.map(c => c.text || c.content || '').join('');
        }
        return content?.text || content?.content || '';
      },
    },
  },
  errorCodes: {
    400: 'invalid_request',
    401: 'invalid_api_key',
    403: 'forbidden',
    404: 'not_found',
    429: 'rate_limit_exceeded',
    500: 'server_error',
    529: 'overloaded',
  },
  retryConfig: {
    ...DEFAULT_RETRY_CONFIG,
    retryableStatusCodes: [429, 500, 502, 503, 504, 529],
  },
};

/**
 * Google AI vendor configuration
 */
const GOOGLE_CONFIG: VendorConfig = {
  name: VendorType.GOOGLE,
  baseUrl: 'https://generativelanguage.googleapis.com/v1beta',
  authHeaderName: 'Authorization',
  authHeaderPrefix: 'Bearer',
  supportedModels: [
    'gemini-1.5-pro',
    'gemini-1.5-flash',
    'gemini-1.0-pro',
    'text-embedding-004',
  ],
  defaultModel: 'gemini-1.5-flash',
  endpoints: {
    chat: '/models/{model}:generateContent',
    embeddings: '/models/{model}:embedContent',
    models: '/models',
  },
  requestFormat: {
    messageField: 'contents',
    modelField: 'model',
    streamField: 'stream',
    temperatureField: 'generationConfig.temperature',
    maxTokensField: 'generationConfig.maxOutputTokens',
    stopField: 'generationConfig.stopSequences',
    transformations: {
      messages: (messages) => {
        return messages.map((msg: any) => ({
          role: msg.role === 'assistant' ? 'model' : 'user',
          parts: [{ text: msg.content }],
        }));
      },
      parameters: (params) => {
        const transformed: any = {
          contents: params.messages ? GOOGLE_CONFIG.requestFormat.transformations!.messages!(params.messages) : [],
        };
        
        if (params.temperature !== undefined || params.max_tokens !== undefined) {
          transformed.generationConfig = {};
          if (params.temperature !== undefined) {
            transformed.generationConfig.temperature = params.temperature;
          }
          if (params.max_tokens !== undefined) {
            transformed.generationConfig.maxOutputTokens = params.max_tokens;
          }
          if (params.stop !== undefined) {
            transformed.generationConfig.stopSequences = Array.isArray(params.stop) ? params.stop : [params.stop];
          }
        }
        
        return transformed;
      },
    },
  },
  responseFormat: {
    messageField: 'candidates[0].content.parts[0].text',
    usageField: 'usageMetadata',
    modelField: 'modelVersion',
    finishReasonField: 'candidates[0].finishReason',
    choicesField: 'candidates',
    transformations: {
      usage: (usage) => ({
        inputTokens: usage.promptTokenCount || 0,
        outputTokens: usage.candidatesTokenCount || 0,
        totalTokens: usage.totalTokenCount || 0,
        model: usage.model || 'unknown',
      }),
      content: (content) => {
        if (content?.parts && Array.isArray(content.parts)) {
          return content.parts.map((part: any) => part.text || '').join('');
        }
        return content?.text || '';
      },
    },
  },
  errorCodes: {
    400: 'invalid_request',
    401: 'invalid_api_key',
    403: 'forbidden',
    404: 'not_found',
    429: 'quota_exceeded',
    500: 'server_error',
    503: 'service_unavailable',
  },
  retryConfig: DEFAULT_RETRY_CONFIG,
};

/**
 * Model mappings for routing
 */
export const MODEL_MAPPINGS: ModelMapping[] = [
  // OpenAI Models
  {
    model: 'gpt-4o',
    vendor: VendorType.OPENAI,
    vendorModel: 'gpt-4o',
    category: 'chat',
    inputCostPer1kTokens: 0.015,
    outputCostPer1kTokens: 0.06,
    contextLength: 128000,
    supportedFeatures: ['chat', 'function_calling', 'vision'],
  },
  {
    model: 'gpt-4o-mini',
    vendor: VendorType.OPENAI,
    vendorModel: 'gpt-4o-mini',
    category: 'chat',
    inputCostPer1kTokens: 0.00015,
    outputCostPer1kTokens: 0.0006,
    contextLength: 128000,
    supportedFeatures: ['chat', 'function_calling'],
  },
  {
    model: 'gpt-3.5-turbo',
    vendor: VendorType.OPENAI,
    vendorModel: 'gpt-3.5-turbo',
    category: 'chat',
    inputCostPer1kTokens: 0.0015,
    outputCostPer1kTokens: 0.002,
    contextLength: 16385,
    supportedFeatures: ['chat', 'function_calling'],
  },
  
  // Anthropic Models
  {
    model: 'claude-3-5-sonnet',
    vendor: VendorType.ANTHROPIC,
    vendorModel: 'claude-3-5-sonnet-20241022',
    category: 'chat',
    inputCostPer1kTokens: 0.003,
    outputCostPer1kTokens: 0.015,
    contextLength: 200000,
    supportedFeatures: ['chat', 'vision', 'artifacts'],
  },
  {
    model: 'claude-3-5-haiku',
    vendor: VendorType.ANTHROPIC,
    vendorModel: 'claude-3-5-haiku-20241022',
    category: 'chat',
    inputCostPer1kTokens: 0.001,
    outputCostPer1kTokens: 0.005,
    contextLength: 200000,
    supportedFeatures: ['chat'],
  },
  {
    model: 'claude-3-opus',
    vendor: VendorType.ANTHROPIC,
    vendorModel: 'claude-3-opus-20240229',
    category: 'chat',
    inputCostPer1kTokens: 0.015,
    outputCostPer1kTokens: 0.075,
    contextLength: 200000,
    supportedFeatures: ['chat', 'vision'],
  },
  
  // Google Models
  {
    model: 'gemini-1.5-pro',
    vendor: VendorType.GOOGLE,
    vendorModel: 'gemini-1.5-pro',
    category: 'chat',
    inputCostPer1kTokens: 0.00125,
    outputCostPer1kTokens: 0.005,
    contextLength: 2097152,
    supportedFeatures: ['chat', 'vision', 'function_calling'],
  },
  {
    model: 'gemini-1.5-flash',
    vendor: VendorType.GOOGLE,
    vendorModel: 'gemini-1.5-flash',
    category: 'chat',
    inputCostPer1kTokens: 0.000075,
    outputCostPer1kTokens: 0.0003,
    contextLength: 1048576,
    supportedFeatures: ['chat', 'vision'],
  },
];

/**
 * Vendor configurations map
 */
export const VENDOR_CONFIGS: Record<VendorType, VendorConfig> = {
  [VendorType.OPENAI]: OPENAI_CONFIG,
  [VendorType.ANTHROPIC]: ANTHROPIC_CONFIG,
  [VendorType.GOOGLE]: GOOGLE_CONFIG,
  [VendorType.COHERE]: {
    ...DEFAULT_RETRY_CONFIG,
    name: VendorType.COHERE,
    baseUrl: 'https://api.cohere.ai/v1',
    authHeaderName: 'Authorization',
    authHeaderPrefix: 'Bearer',
    supportedModels: ['command-r', 'command-r-plus', 'command-light'],
    defaultModel: 'command-r',
    endpoints: { chat: '/chat' },
    requestFormat: { messageField: 'message', modelField: 'model' },
    responseFormat: { messageField: 'text', usageField: 'meta.billed_units', modelField: 'meta.api_version.version' },
    errorCodes: {},
    retryConfig: DEFAULT_RETRY_CONFIG,
  } as VendorConfig,
  [VendorType.MISTRAL]: {
    ...DEFAULT_RETRY_CONFIG,
    name: VendorType.MISTRAL,
    baseUrl: 'https://api.mistral.ai/v1',
    authHeaderName: 'Authorization',
    authHeaderPrefix: 'Bearer',
    supportedModels: ['mistral-large', 'mistral-medium', 'mistral-small'],
    defaultModel: 'mistral-small',
    endpoints: { chat: '/chat/completions' },
    requestFormat: { messageField: 'messages', modelField: 'model' },
    responseFormat: { messageField: 'choices[0].message.content', usageField: 'usage', modelField: 'model' },
    errorCodes: {},
    retryConfig: DEFAULT_RETRY_CONFIG,
  } as VendorConfig,
  [VendorType.OLLAMA]: {
    ...DEFAULT_RETRY_CONFIG,
    name: VendorType.OLLAMA,
    baseUrl: 'http://localhost:11434/api',
    authHeaderName: '',
    authHeaderPrefix: '',
    supportedModels: ['llama2', 'codellama', 'mistral'],
    defaultModel: 'llama2',
    endpoints: { chat: '/chat' },
    requestFormat: { messageField: 'messages', modelField: 'model' },
    responseFormat: { messageField: 'message.content', usageField: 'usage', modelField: 'model' },
    errorCodes: {},
    retryConfig: DEFAULT_RETRY_CONFIG,
  } as VendorConfig,
};

/**
 * Get vendor configuration by vendor type
 */
export function getVendorConfig(vendor: VendorType): VendorConfig {
  const config = VENDOR_CONFIGS[vendor];
  if (!config) {
    throw new Error(`Unsupported vendor: ${vendor}`);
  }
  return config;
}

/**
 * Get model mapping by model name
 */
export function getModelMapping(model: string): ModelMapping | null {
  return MODEL_MAPPINGS.find(mapping => 
    mapping.model === model || mapping.vendorModel === model
  ) || null;
}

/**
 * Get all supported models
 */
export function getAllSupportedModels(): string[] {
  return MODEL_MAPPINGS.map(mapping => mapping.model);
}

/**
 * Get models by vendor
 */
export function getModelsByVendor(vendor: VendorType): ModelMapping[] {
  return MODEL_MAPPINGS.filter(mapping => mapping.vendor === vendor);
}
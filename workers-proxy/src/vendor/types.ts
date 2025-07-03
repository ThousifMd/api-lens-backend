/**
 * API Lens Workers Proxy - Vendor Integration Types
 * 
 * Type definitions for vendor integration system
 */

export interface VendorConfig {
  name: string;
  baseUrl: string;
  authHeaderName: string;
  authHeaderPrefix: string;
  supportedModels: string[];
  defaultModel?: string;
  rateLimits?: {
    requestsPerSecond: number;
    requestsPerMinute: number;
  };
  endpoints: {
    chat?: string;
    completions?: string;
    embeddings?: string;
    models?: string;
  };
  requestFormat: VendorRequestFormat;
  responseFormat: VendorResponseFormat;
  errorCodes: Record<number, string>;
  retryConfig: RetryConfig;
}

export interface VendorRequestFormat {
  messageField: string;
  modelField: string;
  streamField?: string;
  temperatureField?: string;
  maxTokensField?: string;
  stopField?: string;
  customFields?: Record<string, string>;
  transformations?: {
    messages?: (messages: any[]) => any[];
    parameters?: (params: any) => any;
  };
}

export interface VendorResponseFormat {
  messageField: string;
  usageField: string;
  modelField: string;
  finishReasonField?: string;
  idField?: string;
  createdField?: string;
  choicesField?: string;
  deltaField?: string;
  transformations?: {
    usage?: (usage: any) => UsageData;
    content?: (content: any) => string;
  };
}

export interface RetryConfig {
  maxRetries: number;
  baseDelay: number;
  maxDelay: number;
  backoffMultiplier: number;
  retryableStatusCodes: number[];
  retryableErrors: string[];
}

export interface UsageData {
  inputTokens: number;
  outputTokens: number;
  totalTokens: number;
  model: string;
  finishReason?: string;
  requestId?: string;
  processingTime?: number;
}

export interface VendorRequest {
  model: string;
  messages?: any[];
  prompt?: string;
  stream?: boolean;
  temperature?: number;
  max_tokens?: number;
  stop?: string | string[];
  [key: string]: any;
}

export interface VendorResponse {
  id?: string;
  object?: string;
  created?: number;
  model?: string;
  choices?: any[];
  usage?: any;
  error?: VendorError;
  [key: string]: any;
}

export interface VendorError {
  name: string;
  type: string;
  code: string;
  message: string;
  param?: string;
  details?: any;
}

export class VendorError extends Error {
  public type: string;
  public code: string;
  public param?: string;
  public details?: any;

  constructor(options: {
    type: string;
    code: string;
    message: string;
    param?: string;
    details?: any;
  }) {
    super(options.message);
    this.name = 'VendorError';
    this.type = options.type;
    this.code = options.code;
    this.param = options.param;
    this.details = options.details;
  }
}

export interface VendorKey {
  id: string;
  companyId: string;
  vendor: string;
  keyName: string;
  encryptedKey: string;
  isActive: boolean;
  createdAt: string;
  lastUsed?: string;
  usageCount: number;
  metadata?: {
    keyType?: string;
    permissions?: string[];
    limits?: any;
  };
}

export interface VendorMetrics {
  vendor: string;
  totalRequests: number;
  successfulRequests: number;
  failedRequests: number;
  averageLatency: number;
  totalCost: number;
  totalTokens: number;
  retryCount: number;
  errorCounts: Record<string, number>;
}

export interface ModelMapping {
  model: string;
  vendor: string;
  vendorModel: string;
  category: string;
  inputCostPer1kTokens: number;
  outputCostPer1kTokens: number;
  contextLength: number;
  supportedFeatures: string[];
}

export enum VendorType {
  OPENAI = 'openai',
  ANTHROPIC = 'anthropic',
  GOOGLE = 'google',
  COHERE = 'cohere',
  MISTRAL = 'mistral',
  OLLAMA = 'ollama',
}

export enum EndpointType {
  CHAT_COMPLETIONS = 'chat/completions',
  COMPLETIONS = 'completions',
  EMBEDDINGS = 'embeddings',
  MODELS = 'models',
}

export interface VendorEndpointConfig {
  vendor: VendorType;
  endpoint: EndpointType;
  path: string;
  method: string;
  supportedModels: string[];
}

export interface RequestContext {
  requestId: string;
  companyId: string;
  apiKeyId: string;
  vendor: string;
  model: string;
  endpoint: string;
  startTime: number;
  metadata?: Record<string, any>;
}

export interface VendorCallResult {
  success: boolean;
  response?: VendorResponse;
  usage?: UsageData;
  error?: VendorError;
  retryCount: number;
  totalLatency: number;
  vendor: string;
  model: string;
}

export interface StreamChunk {
  id: string;
  object: string;
  created: number;
  model: string;
  choices: Array<{
    index: number;
    delta: {
      content?: string;
      role?: string;
    };
    finish_reason?: string;
  }>;
}

export interface VendorHealthCheck {
  vendor: string;
  status: 'healthy' | 'degraded' | 'down';
  latency: number;
  lastCheck: number;
  errorRate: number;
  details?: {
    endpoints?: Record<string, boolean>;
    models?: Record<string, boolean>;
  };
}
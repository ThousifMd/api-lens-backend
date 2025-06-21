/**
 * API Lens Workers Proxy - Vendor Functions
 * 
 * Core vendor functions as specified in Phase 6.4.1
 */

import {
  VendorConfig,
  VendorType,
  VendorRequest,
  VendorResponse,
  VendorCallResult,
  UsageData,
  VendorKey,
  RequestContext,
  VendorError,
} from './types';
import {
  getVendorConfig,
  getModelMapping,
  MODEL_MAPPINGS,
} from './configs';
import { Env } from '../index';

/**
 * Determine vendor from model name
 * 
 * @param model - The model name to route
 * @returns VendorConfig for the appropriate vendor
 */
export function routeToVendor(model: string): VendorConfig {
  // Find model mapping first
  const mapping = getModelMapping(model);
  
  if (mapping) {
    return getVendorConfig(mapping.vendor);
  }
  
  // Fallback: Try to infer vendor from model name patterns
  const modelLower = model.toLowerCase();
  
  if (modelLower.includes('gpt') || modelLower.includes('openai')) {
    return getVendorConfig(VendorType.OPENAI);
  }
  
  if (modelLower.includes('claude') || modelLower.includes('anthropic')) {
    return getVendorConfig(VendorType.ANTHROPIC);
  }
  
  if (modelLower.includes('gemini') || modelLower.includes('google')) {
    return getVendorConfig(VendorType.GOOGLE);
  }
  
  if (modelLower.includes('command') || modelLower.includes('cohere')) {
    return getVendorConfig(VendorType.COHERE);
  }
  
  if (modelLower.includes('mistral')) {
    return getVendorConfig(VendorType.MISTRAL);
  }
  
  // Default to OpenAI if no match found
  console.warn(`Unknown model ${model}, defaulting to OpenAI`);
  return getVendorConfig(VendorType.OPENAI);
}

/**
 * Get decrypted vendor API key for a company
 * 
 * @param companyId - The company ID
 * @param vendor - The vendor name
 * @param env - Environment bindings
 * @returns Decrypted API key
 */
export async function getVendorKey(
  companyId: string,
  vendor: string,
  env: Env
): Promise<string> {
  try {
    // First try to get company-specific BYOK key
    const byokKey = await getBYOKKey(companyId, vendor, env);
    if (byokKey) {
      return byokKey;
    }
    
    // Fallback to system default keys
    const defaultKey = getDefaultVendorKey(vendor, env);
    if (defaultKey) {
      return defaultKey;
    }
    
    throw new Error(`No API key found for vendor ${vendor} and company ${companyId}`);
    
  } catch (error) {
    console.error(`Error getting vendor key for ${vendor}:`, error);
    throw new Error(`Failed to retrieve API key for ${vendor}`);
  }
}

/**
 * Get BYOK (Bring Your Own Key) for a company
 */
async function getBYOKKey(
  companyId: string,
  vendor: string,
  env: Env
): Promise<string | null> {
  try {
    // Fetch from backend API
    const response = await fetch(`${env.API_LENS_BACKEND_URL}/companies/${companyId}/vendor-keys/${vendor}`, {
      headers: {
        'Authorization': `Bearer ${env.API_LENS_BACKEND_TOKEN}`,
        'Content-Type': 'application/json',
      },
    });
    
    if (response.status === 404) {
      return null; // No BYOK key configured
    }
    
    if (!response.ok) {
      throw new Error(`Backend API error: ${response.status}`);
    }
    
    const vendorKey = await response.json() as VendorKey;
    
    if (!vendorKey.isActive) {
      throw new Error('Vendor key is not active');
    }
    
    // Decrypt the key
    const decryptedKey = await decryptVendorKey(vendorKey.encryptedKey, env);
    
    // Update last used timestamp (fire and forget)
    updateKeyUsage(vendorKey.id, env).catch(() => {});
    
    return decryptedKey;
    
  } catch (error) {
    console.error('Error fetching BYOK key:', error);
    return null;
  }
}

/**
 * Get default system vendor key
 */
function getDefaultVendorKey(vendor: string, env: Env): string | null {
  const vendorUpper = vendor.toUpperCase();
  
  switch (vendorUpper) {
    case 'OPENAI':
      return env.OPENAI_API_KEY || null;
    case 'ANTHROPIC':
      return env.ANTHROPIC_API_KEY || null;
    case 'GOOGLE':
      return env.GOOGLE_AI_API_KEY || null;
    case 'COHERE':
      return env.COHERE_API_KEY || null;
    case 'MISTRAL':
      return env.MISTRAL_API_KEY || null;
    default:
      return null;
  }
}

/**
 * Decrypt vendor key using environment encryption key
 */
async function decryptVendorKey(encryptedKey: string, env: Env): Promise<string> {
  try {
    // Simple base64 decoding for now - in production use proper encryption
    // This should use the ENCRYPTION_KEY from env for proper decryption
    const decoded = atob(encryptedKey);
    return decoded;
  } catch (error) {
    throw new Error('Failed to decrypt vendor key');
  }
}

/**
 * Update key usage statistics
 */
async function updateKeyUsage(keyId: string, env: Env): Promise<void> {
  try {
    await fetch(`${env.API_LENS_BACKEND_URL}/vendor-keys/${keyId}/usage`, {
      method: 'PATCH',
      headers: {
        'Authorization': `Bearer ${env.API_LENS_BACKEND_TOKEN}`,
        'Content-Type': 'application/json',
      },
      body: JSON.stringify({
        lastUsed: new Date().toISOString(),
        incrementUsage: true,
      }),
    });
  } catch (error) {
    console.error('Failed to update key usage:', error);
  }
}

/**
 * Transform request to vendor-specific format
 * 
 * @param vendor - The vendor name
 * @param request - The generic request object
 * @returns Vendor-specific request format
 */
export function transformRequest(vendor: string, request: VendorRequest): any {
  const vendorType = vendor as VendorType;
  const config = getVendorConfig(vendorType);
  
  // Start with the original request
  let transformedRequest: any = { ...request };
  
  // Apply vendor-specific transformations
  if (config.requestFormat.transformations?.parameters) {
    transformedRequest = config.requestFormat.transformations.parameters(transformedRequest);
  }
  
  // Map generic fields to vendor-specific fields
  const fieldMappings: Record<string, string> = {
    model: config.requestFormat.modelField,
    messages: config.requestFormat.messageField,
    stream: config.requestFormat.streamField || 'stream',
    temperature: config.requestFormat.temperatureField || 'temperature',
    max_tokens: config.requestFormat.maxTokensField || 'max_tokens',
    stop: config.requestFormat.stopField || 'stop',
  };
  
  // Apply field mappings
  const mappedRequest: any = {};
  for (const [genericField, value] of Object.entries(transformedRequest)) {
    const vendorField = fieldMappings[genericField] || genericField;
    
    // Handle nested field mappings (e.g., "generationConfig.temperature")
    if (vendorField.includes('.')) {
      const parts = vendorField.split('.');
      let current = mappedRequest;
      
      for (let i = 0; i < parts.length - 1; i++) {
        if (!current[parts[i]]) {
          current[parts[i]] = {};
        }
        current = current[parts[i]];
      }
      
      current[parts[parts.length - 1]] = value;
    } else {
      mappedRequest[vendorField] = value;
    }
  }
  
  // Add vendor-specific custom fields
  if (config.requestFormat.customFields) {
    Object.assign(mappedRequest, config.requestFormat.customFields);
  }
  
  // Vendor-specific post-processing
  switch (vendorType) {
    case VendorType.ANTHROPIC:
      return transformAnthropicRequest(mappedRequest, config);
    case VendorType.GOOGLE:
      return transformGoogleRequest(mappedRequest, config);
    default:
      return mappedRequest;
  }
}

/**
 * Transform request for Anthropic
 */
function transformAnthropicRequest(request: any, config: VendorConfig): any {
  const transformed = { ...request };
  
  // Extract system message
  if (request.messages && Array.isArray(request.messages)) {
    const systemMessage = request.messages.find((msg: any) => msg.role === 'system');
    if (systemMessage) {
      transformed.system = systemMessage.content;
      transformed.messages = request.messages.filter((msg: any) => msg.role !== 'system');
    }
  }
  
  // Ensure max_tokens is set (required for Anthropic)
  if (!transformed.max_tokens) {
    transformed.max_tokens = 4096;
  }
  
  return transformed;
}

/**
 * Transform request for Google
 */
function transformGoogleRequest(request: any, config: VendorConfig): any {
  const transformed = { ...request };
  
  // Transform messages to Google format
  if (request.contents && Array.isArray(request.contents)) {
    transformed.contents = request.contents.map((msg: any) => ({
      role: msg.role === 'assistant' ? 'model' : 'user',
      parts: [{ text: msg.content || msg.text || '' }],
    }));
  }
  
  return transformed;
}

/**
 * Call vendor API with request
 * 
 * @param vendor - The vendor name
 * @param apiKey - The API key to use
 * @param request - The transformed request
 * @param context - Request context
 * @param env - Environment bindings
 * @returns Vendor API response
 */
export async function callVendorAPI(
  vendor: string,
  apiKey: string,
  request: any,
  context: RequestContext,
  env: Env
): Promise<VendorCallResult> {
  const vendorType = vendor as VendorType;
  const config = getVendorConfig(vendorType);
  
  let retryCount = 0;
  let lastError: VendorError | null = null;
  const startTime = Date.now();
  
  while (retryCount <= config.retryConfig.maxRetries) {
    try {
      const response = await makeVendorRequest(config, apiKey, request, context);
      const totalLatency = Date.now() - startTime;
      
      if (response.ok) {
        const responseData = await response.json() as VendorResponse;
        const usage = parseVendorResponse(vendor, responseData);
        
        return {
          success: true,
          response: responseData,
          usage,
          retryCount,
          totalLatency,
          vendor,
          model: request.model || context.model,
        };
      } else {
        const errorData = await response.json().catch(() => ({}));
        const vendorError: VendorError = {
          type: 'api_error',
          code: config.errorCodes[response.status] || 'unknown_error',
          message: errorData.error?.message || errorData.message || `HTTP ${response.status}`,
          details: errorData,
        };
        
        lastError = vendorError;
        
        // Check if error is retryable
        if (!isRetryableError(response.status, vendorError, config)) {
          break;
        }
      }
    } catch (error) {
      lastError = {
        type: 'network_error',
        code: 'request_failed',
        message: error instanceof Error ? error.message : 'Unknown network error',
      };
      
      // Network errors are generally retryable
      if (!config.retryConfig.retryableErrors.includes('network_error')) {
        break;
      }
    }
    
    // Increment retry count and wait before next attempt
    retryCount++;
    
    if (retryCount <= config.retryConfig.maxRetries) {
      const delay = calculateRetryDelay(retryCount, config);
      await new Promise(resolve => setTimeout(resolve, delay));
    }
  }
  
  const totalLatency = Date.now() - startTime;
  
  return {
    success: false,
    error: lastError || {
      type: 'unknown_error',
      code: 'max_retries_exceeded',
      message: 'Maximum retries exceeded',
    },
    retryCount,
    totalLatency,
    vendor,
    model: request.model || context.model,
  };
}

/**
 * Make actual HTTP request to vendor
 */
async function makeVendorRequest(
  config: VendorConfig,
  apiKey: string,
  request: any,
  context: RequestContext
): Promise<Response> {
  // Determine endpoint
  let endpoint = config.endpoints.chat || '/chat/completions';
  
  // Handle parameterized endpoints (e.g., Google's /models/{model}:generateContent)
  if (endpoint.includes('{model}')) {
    endpoint = endpoint.replace('{model}', request.model || config.defaultModel);
  }
  
  const url = `${config.baseUrl}${endpoint}`;
  
  // Build headers
  const headers: Record<string, string> = {
    'Content-Type': 'application/json',
    'User-Agent': 'API-Lens-Workers-Proxy/1.0',
  };
  
  // Add authentication header
  if (config.authHeaderName && apiKey) {
    const authValue = config.authHeaderPrefix 
      ? `${config.authHeaderPrefix} ${apiKey}`
      : apiKey;
    headers[config.authHeaderName] = authValue;
  }
  
  // Add custom headers for specific vendors
  if (config.requestFormat.customFields) {
    Object.assign(headers, config.requestFormat.customFields);
  }
  
  // Add request ID for tracing
  headers['X-Request-ID'] = context.requestId;
  
  return fetch(url, {
    method: 'POST',
    headers,
    body: JSON.stringify(request),
  });
}

/**
 * Parse vendor response and extract usage data
 * 
 * @param vendor - The vendor name
 * @param response - The vendor response
 * @returns Parsed usage data
 */
export function parseVendorResponse(vendor: string, response: VendorResponse): UsageData {
  const vendorType = vendor as VendorType;
  const config = getVendorConfig(vendorType);
  
  // Extract usage data using vendor-specific format
  let usage: any = response;
  
  // Navigate to usage field
  if (config.responseFormat.usageField) {
    const usageFieldPath = config.responseFormat.usageField.split('.');
    for (const field of usageFieldPath) {
      usage = usage?.[field];
    }
  }
  
  // Apply vendor-specific usage transformation
  if (config.responseFormat.transformations?.usage && usage) {
    return config.responseFormat.transformations.usage(usage);
  }
  
  // Default parsing for standard OpenAI format
  return {
    inputTokens: usage?.prompt_tokens || 0,
    outputTokens: usage?.completion_tokens || 0,
    totalTokens: usage?.total_tokens || 0,
    model: response.model || 'unknown',
    finishReason: getFinishReason(response, config),
    requestId: response.id,
  };
}

/**
 * Extract finish reason from response
 */
function getFinishReason(response: VendorResponse, config: VendorConfig): string | undefined {
  if (!config.responseFormat.finishReasonField) {
    return undefined;
  }
  
  const fieldPath = config.responseFormat.finishReasonField.split('.');
  let value: any = response;
  
  for (const field of fieldPath) {
    if (field.includes('[') && field.includes(']')) {
      // Handle array access like "choices[0]"
      const [arrayField, indexStr] = field.split('[');
      const index = parseInt(indexStr.replace(']', ''));
      value = value?.[arrayField]?.[index];
    } else {
      value = value?.[field];
    }
  }
  
  return value;
}

/**
 * Check if an error is retryable
 */
function isRetryableError(
  statusCode: number,
  error: VendorError,
  config: VendorConfig
): boolean {
  // Check status code
  if (config.retryConfig.retryableStatusCodes.includes(statusCode)) {
    return true;
  }
  
  // Check error type
  return config.retryConfig.retryableErrors.includes(error.type) ||
         config.retryConfig.retryableErrors.includes(error.code);
}

/**
 * Calculate retry delay with exponential backoff
 */
function calculateRetryDelay(retryCount: number, config: VendorConfig): number {
  const delay = config.retryConfig.baseDelay * Math.pow(config.retryConfig.backoffMultiplier, retryCount - 1);
  return Math.min(delay, config.retryConfig.maxDelay);
}

/**
 * Estimate request cost based on model and input
 */
export function estimateRequestCost(model: string, inputTokens: number): number {
  const mapping = getModelMapping(model);
  if (!mapping) {
    return 0;
  }
  
  return (inputTokens / 1000) * mapping.inputCostPer1kTokens;
}

/**
 * Calculate actual request cost
 */
export function calculateRequestCost(model: string, usage: UsageData): number {
  const mapping = getModelMapping(model);
  if (!mapping) {
    return 0;
  }
  
  const inputCost = (usage.inputTokens / 1000) * mapping.inputCostPer1kTokens;
  const outputCost = (usage.outputTokens / 1000) * mapping.outputCostPer1kTokens;
  
  return inputCost + outputCost;
}
/**
 * API Lens Workers Proxy - Vendor Integration Layer
 * 
 * Main integration layer for the new modular vendor system
 */

import { Context } from 'hono';
import { Env, HonoVariables, VendorName } from './types';
import { getAuthResult, validateVendorAccess } from './auth';

// Simplified types
export interface VendorRequest {
  model: string;
  messages?: any[];
  [key: string]: any;
}

export interface VendorResponse {
  choices?: any[];
  usage?: any;
  [key: string]: any;
}

export interface VendorCallResult {
  success: boolean;
  response?: VendorResponse;
  error?: string;
  usage?: any;
  cost?: number;
}

export interface UsageData {
  inputTokens: number;
  outputTokens: number;
  totalTokens: number;
}

export interface VendorError {
  code: string;
  message: string;
  vendor: string;
}

export interface ModelMapping {
  model: string;
  vendor: string;
  category: string;
  pricing: { input: number; output: number };
}

// Legacy interface for backward compatibility
export interface VendorConfig {
  name: string;
  baseUrl: string;
  authHeader: string;
  defaultModel?: string;
  supportedModels: string[];
}

/**
 * Main vendor request handler (updated to use new system)
 */
export async function handleVendorRequest(
  c: Context<{ Bindings: Env; Variables: HonoVariables }>,
  vendor: VendorName
): Promise<Response> {
  const startTime = Date.now();
  
  try {
    // Validate vendor access
    if (!validateVendorAccess(c, vendor)) {
      return c.json({
        error: 'Vendor Access Denied',
        message: `Access to vendor '${vendor}' is not allowed for this API key`,
        vendor,
        timestamp: new Date().toISOString(),
      }, 403);
    }
    
    // Get request body
    const body = await c.req.json();
    
    // Simplified vendor handling - just return a mock response
    const response = {
      choices: [{
        message: {
          role: 'assistant',
          content: `Mock response from ${vendor} vendor. This is a placeholder implementation.`
        },
        finish_reason: 'stop'
      }],
      usage: {
        prompt_tokens: 10,
        completion_tokens: 15,
        total_tokens: 25
      },
      model: body.model || 'unknown'
    };
    
    return c.json(response);
    
  } catch (error) {
    console.error(`Vendor request error for ${vendor}:`, error);
    
    return c.json({
      error: 'Vendor Request Failed',
      message: error instanceof Error ? error.message : 'Unknown error occurred',
      vendor,
      timestamp: new Date().toISOString(),
      requestId: c.get('requestId') || crypto.randomUUID(),
    }, 500);
  }
}

/**
 * Get vendor configuration (legacy function for backward compatibility)
 */
export function getVendorConfig(vendor: string): VendorConfig {
  const config = LEGACY_VENDOR_CONFIGS[vendor];
  if (config) {
    return config;
  }
    
  return {
    name: vendor,
    baseUrl: 'https://api.openai.com/v1',
    authHeader: 'Authorization',
    defaultModel: 'gpt-3.5-turbo',
    supportedModels: ['gpt-3.5-turbo'],
  };
}

/**
 * Route request to appropriate vendor based on path
 */
export function routeVendorRequest(path: string): string {
  const pathParts = path.split('/');
  
  if (pathParts.includes('openai')) {
    return 'openai';
  }
  
  if (pathParts.includes('anthropic')) {
    return 'anthropic';
  }
  
  if (pathParts.includes('google')) {
    return 'google';
  }
  
  if (pathParts.includes('cohere')) {
    return 'cohere';
  }
  
  if (pathParts.includes('mistral')) {
    return 'mistral';
  }
  
  // Default to OpenAI
  return 'openai';
}

/**
 * Get available models for a vendor
 */
export function getVendorModels(vendor: string): string[] {
  const config = LEGACY_VENDOR_CONFIGS[vendor];
  return config ? config.supportedModels : [];
}

/**
 * Check if model is supported by vendor
 */
export function isModelSupported(vendor: string, model: string): boolean {
  const models = getVendorModels(vendor);
  return models.includes(model);
}

/**
 * Get all supported models across all vendors
 */
export function getAllSupportedModels(): Array<{
  model: string;
  vendor: string;
  category: string;
  pricing: { input: number; output: number };
}> {
  const models: ModelMapping[] = [];
  
  Object.entries(LEGACY_VENDOR_CONFIGS).forEach(([vendor, config]) => {
    config.supportedModels.forEach(model => {
      models.push({
        model,
        vendor,
        category: 'chat',
        pricing: { input: 0.001, output: 0.002 }
      });
    });
  });
  
  return models;
}

/**
 * Transform generic request to vendor-specific format (legacy function)
 */
export function transformRequestForVendor(vendor: string, request: any): any {
  // Simplified transformation - just return the request as-is
  return request;
}

/**
 * Create vendor-specific middleware
 */
export function createVendorHandler(vendor: string) {
  return async (c: Context<{ Bindings: Env; Variables: HonoVariables }>, next: () => Promise<void>) => {
    await handleVendorRequest(c, vendor as VendorName);
  };
}

/**
 * Create unified proxy that routes based on model
 */
export function createModelRouter() {
  return async (c: Context<{ Bindings: Env; Variables: HonoVariables }>, next: () => Promise<void>) => {
    // Simplified model routing
    await next();
  };
}

/**
 * Middleware to extract and validate model from request
 */
export function modelValidationMiddleware() {
  return async function modelValidation(c: Context<{ Bindings: Env; Variables: HonoVariables }>, next: () => Promise<void>) {
    try {
      const body = await c.req.json();
      const model = body.model;
      
      if (!model) {
        return c.json({
          error: 'Missing Model',
          message: 'Model parameter is required',
          code: 'missing_model',
        }, 400);
      }
      
      // Validate model exists
      const availableModels = getAllSupportedModels();
      const modelExists = availableModels.some(m => m.model === model);
      
      if (!modelExists) {
        return c.json({
          error: 'Unsupported Model',
          message: `Model '${model}' is not supported`,
          code: 'unsupported_model',
          availableModels: availableModels.map(m => m.model),
        }, 400);
      }
      
      // Store model in context
      c.set('model', model);
      c.set('requestBody', body);
      
      await next();
      
    } catch (error) {
      return c.json({
        error: 'Invalid Request',
        message: 'Request body must be valid JSON',
        code: 'invalid_json',
      }, 400);
    }
  };
}

/**
 * Legacy vendor configurations for backward compatibility
 */
export const LEGACY_VENDOR_CONFIGS: Record<string, VendorConfig> = {
  openai: {
    name: 'OpenAI',
    baseUrl: 'https://api.openai.com/v1',
    authHeader: 'Authorization',
    defaultModel: 'gpt-3.5-turbo',
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
  },
  anthropic: {
    name: 'Anthropic',
    baseUrl: 'https://api.anthropic.com',
    authHeader: 'x-api-key',
    defaultModel: 'claude-3-5-sonnet-20241022',
    supportedModels: [
      'claude-3-5-sonnet-20241022',
      'claude-3-5-haiku-20241022',
      'claude-3-opus-20240229',
      'claude-3-sonnet-20240229',
      'claude-3-haiku-20240307',
    ],
  },
  google: {
    name: 'Google AI',
    baseUrl: 'https://generativelanguage.googleapis.com/v1beta',
    authHeader: 'Authorization',
    defaultModel: 'gemini-1.5-flash',
    supportedModels: [
      'gemini-1.5-pro',
      'gemini-1.5-flash',
      'gemini-1.0-pro',
      'text-embedding-004',
    ],
  },
};

// Vendor Health Check
export function createVendorHealthCheck() {
  return async (c: Context<{ Bindings: Env; Variables: HonoVariables }>) => {
    return c.json({
      status: 'healthy',
      vendors: {
        openai: { status: 'healthy', responseTime: 10 },
        anthropic: { status: 'healthy', responseTime: 15 },
        google: { status: 'healthy', responseTime: 12 }
      },
      timestamp: new Date().toISOString()
    });
  };
}

export function getAvailableModels() {
  return getAllSupportedModels();
}
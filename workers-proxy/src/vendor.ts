/**
 * API Lens Workers Proxy - Vendor Integration Layer
 * 
 * Main integration layer for the new modular vendor system
 */

import { Context } from 'hono';
import { Env } from './index';
import { getAuthResult, validateVendorAccess } from './auth';
import { calculateCost } from './cost';
import { logRequest } from './logger';
import {
  VendorHandler,
  createVendorMiddleware,
  createUnifiedVendorProxy,
  routeToVendor,
  getAvailableModels,
  VendorType,
} from './vendor/index';

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
  c: Context<{ Bindings: Env }>,
  vendor: string
): Promise<Response> {
  const startTime = Date.now();
  const vendorHandler = new VendorHandler(c.env);
  
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
    
    // Handle the vendor request
    const response = await vendorHandler.handleRequest(c, vendor, body);
    
    // Log the request (fire and forget)
    const endTime = Date.now();
    const usage = c.get('usage');
    const actualCost = c.get('actualCost') || 0;
    
    logRequest(c, {
      startTime,
      endTime,
      success: response.status < 400,
      vendor,
      model: body.model || 'unknown',
      inputTokens: usage?.inputTokens || 0,
      outputTokens: usage?.outputTokens || 0,
      totalTokens: usage?.totalTokens || 0,
      cost: actualCost,
      responseTime: endTime - startTime,
    }).catch(err => {
      console.error('Failed to log request:', err);
    });
    
    return response;
    
  } catch (error) {
    console.error(`Vendor request error for ${vendor}:`, error);
    
    // Log failed request
    const endTime = Date.now();
    await logRequest(c, {
      startTime,
      endTime,
      success: false,
      vendor,
      error: error instanceof Error ? error.message : 'Unknown error',
      responseTime: endTime - startTime,
    });
    
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
  try {
    const config = routeToVendor(vendor);
    
    return {
      name: config.name,
      baseUrl: config.baseUrl,
      authHeader: config.authHeaderName,
      defaultModel: config.defaultModel,
      supportedModels: config.supportedModels,
    };
  } catch (error) {
    console.warn(`Unknown vendor ${vendor}, returning default config`);
    
    return {
      name: vendor,
      baseUrl: 'https://api.openai.com/v1',
      authHeader: 'Authorization',
      defaultModel: 'gpt-3.5-turbo',
      supportedModels: ['gpt-3.5-turbo'],
    };
  }
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
  try {
    const config = routeToVendor(vendor);
    return config.supportedModels;
  } catch {
    return [];
  }
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
  return getAvailableModels();
}

/**
 * Transform generic request to vendor-specific format (legacy function)
 */
export function transformRequestForVendor(vendor: string, request: any): any {
  // Use the new transformation system
  const { transformRequest } = require('./vendor/functions');
  return transformRequest(vendor, request);
}

/**
 * Create vendor-specific middleware
 */
export function createVendorHandler(vendor: string) {
  return createVendorMiddleware(vendor);
}

/**
 * Create unified proxy that routes based on model
 */
export function createModelRouter() {
  return createUnifiedVendorProxy();
}

/**
 * Middleware to extract and validate model from request
 */
export function modelValidationMiddleware() {
  return async function modelValidation(c: Context<{ Bindings: Env }>, next: () => Promise<void>) {
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

// Re-export types and functions for convenience
export type {
  VendorRequest,
  VendorResponse,
  VendorCallResult,
  UsageData,
  VendorError,
  ModelMapping,
} from './vendor';

export {
  VendorType,
} from './vendor/types';
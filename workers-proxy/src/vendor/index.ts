/**
 * API Lens Workers Proxy - Vendor Integration Module
 * 
 * Main exports for the vendor integration system
 */

// Export main service classes
export { VendorHandler } from './handler';

// Export core functions
export {
  routeToVendor,
  getVendorKey,
  transformRequest,
  callVendorAPI,
  parseVendorResponse,
  estimateRequestCost,
  calculateRequestCost,
} from './functions';

// Export configurations
export {
  getVendorConfig,
  getModelMapping,
  getAllSupportedModels,
  getModelsByVendor,
  VENDOR_CONFIGS,
  MODEL_MAPPINGS,
} from './configs';

// Export types
export type {
  VendorConfig,
  VendorRequest,
  VendorResponse,
  VendorCallResult,
  UsageData,
  VendorKey,
  VendorError,
  VendorMetrics,
  ModelMapping,
  RequestContext,
  StreamChunk,
  VendorHealthCheck,
} from './types';

export {
  VendorType,
  EndpointType,
} from './types';

/**
 * Create vendor handler middleware for specific vendor
 */
export function createVendorMiddleware(vendorName: string) {
  return async function vendorMiddleware(c: any, next: any) {
    const vendorHandler = new VendorHandler(c.env);
    
    try {
      // Get the request body
      const body = await c.req.json();
      
      // Handle the vendor request
      const response = await vendorHandler.handleRequest(c, vendorName, body);
      
      // Return the response
      return response;
      
    } catch (error) {
      console.error(`${vendorName} middleware error:`, error);
      
      return c.json({
        error: {
          type: 'middleware_error',
          code: 'request_processing_failed',
          message: error instanceof Error ? error.message : 'Unknown error',
        },
        vendor: vendorName,
        request_id: c.get('requestId') || crypto.randomUUID(),
      }, 500);
    }
  };
}

/**
 * Utility function to validate model compatibility
 */
export function validateModelForVendor(model: string, vendor: string): boolean {
  try {
    const vendorConfig = getVendorConfig(vendor as any);
    return vendorConfig.supportedModels.includes(model);
  } catch {
    return false;
  }
}

/**
 * Get all available models with their metadata
 */
export function getAvailableModels(): Array<{
  model: string;
  vendor: string;
  category: string;
  contextLength: number;
  features: string[];
  pricing: {
    input: number;
    output: number;
  };
}> {
  return MODEL_MAPPINGS.map(mapping => ({
    model: mapping.model,
    vendor: mapping.vendor,
    category: mapping.category,
    contextLength: mapping.contextLength,
    features: mapping.supportedFeatures,
    pricing: {
      input: mapping.inputCostPer1kTokens,
      output: mapping.outputCostPer1kTokens,
    },
  }));
}

/**
 * Create a unified vendor proxy that routes to the appropriate vendor
 */
export function createUnifiedVendorProxy() {
  return async function unifiedVendorProxy(c: any) {
    const vendorHandler = new VendorHandler(c.env);
    
    try {
      // Get the request body
      const body = await c.req.json();
      
      // Determine vendor from model
      const vendor = routeToVendor(body.model);
      
      // Handle the vendor request
      return await vendorHandler.handleRequest(c, vendor.name, body);
      
    } catch (error) {
      console.error('Unified vendor proxy error:', error);
      
      return c.json({
        error: {
          type: 'proxy_error',
          code: 'routing_failed',
          message: error instanceof Error ? error.message : 'Unknown error',
        },
        request_id: c.get('requestId') || crypto.randomUUID(),
      }, 500);
    }
  };
}

/**
 * Health check endpoint for all vendors
 */
export function createVendorHealthCheck() {
  return async function vendorHealthCheck(c: any) {
    const vendorHandler = new VendorHandler(c.env);
    
    try {
      const checks = await Promise.allSettled([
        vendorHandler.healthCheck('openai'),
        vendorHandler.healthCheck('anthropic'),
        vendorHandler.healthCheck('google'),
      ]);
      
      const results = checks.map(check => 
        check.status === 'fulfilled' ? check.value : {
          vendor: 'unknown',
          status: 'down' as const,
          latency: 0,
          details: { error: 'Health check failed' },
        }
      );
      
      const overallStatus = results.every(r => r.status === 'healthy') 
        ? 'healthy' 
        : results.some(r => r.status !== 'down') 
          ? 'degraded' 
          : 'down';
      
      return c.json({
        status: overallStatus,
        timestamp: new Date().toISOString(),
        vendors: results,
        summary: {
          total: results.length,
          healthy: results.filter(r => r.status === 'healthy').length,
          degraded: results.filter(r => r.status === 'degraded').length,
          down: results.filter(r => r.status === 'down').length,
        },
      });
      
    } catch (error) {
      return c.json({
        status: 'error',
        timestamp: new Date().toISOString(),
        error: error instanceof Error ? error.message : 'Unknown error',
      }, 500);
    }
  };
}

/**
 * Utility to test BYOK key for a vendor
 */
export async function testVendorKey(
  vendor: string,
  apiKey: string,
  env: any
): Promise<{
  valid: boolean;
  error?: string;
  details?: any;
}> {
  try {
    const vendorConfig = getVendorConfig(vendor as any);
    
    // Make a simple test request (usually to models endpoint)
    const testUrl = `${vendorConfig.baseUrl}/models`;
    const headers: Record<string, string> = {
      'User-Agent': 'API-Lens-Key-Test/1.0',
    };
    
    if (vendorConfig.authHeaderName) {
      const authValue = vendorConfig.authHeaderPrefix 
        ? `${vendorConfig.authHeaderPrefix} ${apiKey}`
        : apiKey;
      headers[vendorConfig.authHeaderName] = authValue;
    }
    
    const response = await fetch(testUrl, {
      method: 'GET',
      headers,
    });
    
    if (response.ok) {
      const data = await response.json();
      return {
        valid: true,
        details: {
          models: data.data?.length || 0,
          organization: data.organization,
        },
      };
    } else {
      const errorData = await response.json().catch(() => ({}));
      return {
        valid: false,
        error: errorData.error?.message || `HTTP ${response.status}`,
        details: errorData,
      };
    }
    
  } catch (error) {
    return {
      valid: false,
      error: error instanceof Error ? error.message : 'Unknown error',
    };
  }
}
/**
 * API Lens Workers Proxy - Vendor Handler Service
 * 
 * Main service for handling vendor requests with BYOK, transformations, and error handling
 */

import { Context } from 'hono';
import {
  VendorRequest,
  VendorCallResult,
  RequestContext,
  VendorError,
  StreamChunk,
  VendorResponse,
} from './types';
import {
  routeToVendor,
  getVendorKey,
  transformRequest,
  callVendorAPI,
  parseVendorResponse,
  estimateRequestCost,
  calculateRequestCost,
} from './functions';
import { getAuthResult } from '../auth';
import { Env } from '../index';

export class VendorHandler {
  private env: Env;
  
  constructor(env: Env) {
    this.env = env;
  }
  
  /**
   * Handle a vendor request end-to-end
   */
  async handleRequest(
    c: Context<{ Bindings: Env }>,
    vendor: string,
    originalRequest: any
  ): Promise<Response> {
    const startTime = Date.now();
    const requestId = c.get('requestId') || crypto.randomUUID();
    
    try {
      // Get authentication context
      const authResult = getAuthResult(c);
      if (!authResult) {
        throw new Error('Request not authenticated');
      }
      
      // Parse the original request
      const vendorRequest = await this.parseIncomingRequest(originalRequest);
      
      // Route to appropriate vendor
      const vendorConfig = routeToVendor(vendorRequest.model);
      
      // Create request context
      const context: RequestContext = {
        requestId,
        companyId: authResult.company.id,
        apiKeyId: authResult.apiKey.id,
        vendor: vendorConfig.name,
        model: vendorRequest.model,
        endpoint: this.determineEndpoint(vendorRequest),
        startTime,
        metadata: {
          userAgent: c.req.header('User-Agent'),
          ipAddress: c.req.header('CF-Connecting-IP'),
        },
      };
      
      // Estimate cost for rate limiting
      const estimatedCost = this.estimateCost(vendorRequest);
      c.set('estimatedCost', estimatedCost);
      
      // Get vendor API key (BYOK or default)
      const apiKey = await getVendorKey(
        authResult.company.id,
        vendorConfig.name,
        this.env
      );
      
      // Transform request to vendor format
      const transformedRequest = transformRequest(vendorConfig.name, vendorRequest);
      
      // Call vendor API
      const result = await callVendorAPI(
        vendorConfig.name,
        apiKey,
        transformedRequest,
        context,
        this.env
      );
      
      // Handle the result
      if (result.success) {
        return this.handleSuccessResponse(c, result, context);
      } else {
        return this.handleErrorResponse(c, result, context);
      }
      
    } catch (error) {
      console.error('Vendor handler error:', error);
      return this.handleUnexpectedError(c, error, requestId);
    }
  }
  
  /**
   * Parse incoming request from various formats
   */
  private async parseIncomingRequest(request: any): Promise<VendorRequest> {
    // Handle different request formats
    if (typeof request === 'string') {
      return JSON.parse(request);
    }
    
    if (request instanceof Request) {
      return await request.json();
    }
    
    return request as VendorRequest;
  }
  
  /**
   * Determine the endpoint type from request
   */
  private determineEndpoint(request: VendorRequest): string {
    if (request.messages || request.prompt) {
      return 'chat';
    }
    
    if (request.input && typeof request.input === 'string') {
      return 'embeddings';
    }
    
    return 'completions';
  }
  
  /**
   * Estimate request cost for rate limiting
   */
  private estimateCost(request: VendorRequest): number {
    // Simple estimation based on input length
    let inputTokens = 0;
    
    if (request.messages) {
      inputTokens = request.messages.reduce((total, msg) => {
        return total + (msg.content?.length || 0) / 4; // Rough token estimation
      }, 0);
    } else if (request.prompt) {
      inputTokens = request.prompt.length / 4;
    } else if (request.input) {
      inputTokens = request.input.length / 4;
    }
    
    return estimateRequestCost(request.model, Math.ceil(inputTokens));
  }
  
  /**
   * Handle successful vendor response
   */
  private async handleSuccessResponse(
    c: Context<{ Bindings: Env }>,
    result: VendorCallResult,
    context: RequestContext
  ): Promise<Response> {
    const response = result.response!;
    const usage = result.usage!;
    
    // Calculate actual cost
    const actualCost = calculateRequestCost(context.model, usage);
    c.set('actualCost', actualCost);
    c.set('usage', usage);
    
    // Add API Lens headers
    const headers: Record<string, string> = {
      'X-API-Lens-Request-ID': context.requestId,
      'X-API-Lens-Vendor': result.vendor,
      'X-API-Lens-Model': result.model,
      'X-API-Lens-Cost': actualCost.toFixed(6),
      'X-API-Lens-Input-Tokens': usage.inputTokens.toString(),
      'X-API-Lens-Output-Tokens': usage.outputTokens.toString(),
      'X-API-Lens-Total-Tokens': usage.totalTokens.toString(),
      'X-API-Lens-Latency': result.totalLatency.toString(),
    };
    
    if (result.retryCount > 0) {
      headers['X-API-Lens-Retry-Count'] = result.retryCount.toString();
    }
    
    // Handle streaming responses
    if (this.isStreamingRequest(context) && this.isStreamingResponse(response)) {
      return this.handleStreamingResponse(c, response, headers);
    }
    
    // Return standard JSON response
    return c.json(response, 200, headers);
  }
  
  /**
   * Handle vendor error response
   */
  private handleErrorResponse(
    c: Context<{ Bindings: Env }>,
    result: VendorCallResult,
    context: RequestContext
  ): Response {
    const error = result.error!;
    
    // Map vendor error to appropriate HTTP status
    const statusCode = this.mapErrorToStatus(error);
    
    const errorResponse = {
      error: {
        type: error.type,
        code: error.code,
        message: error.message,
        param: error.param,
      },
      vendor: result.vendor,
      model: result.model,
      request_id: context.requestId,
      retry_count: result.retryCount,
      latency: result.totalLatency,
    };
    
    const headers: Record<string, string> = {
      'X-API-Lens-Request-ID': context.requestId,
      'X-API-Lens-Vendor': result.vendor,
      'X-API-Lens-Error-Code': error.code,
      'X-API-Lens-Retry-Count': result.retryCount.toString(),
    };
    
    return c.json(errorResponse, statusCode, headers);
  }
  
  /**
   * Handle unexpected errors
   */
  private handleUnexpectedError(
    c: Context<{ Bindings: Env }>,
    error: unknown,
    requestId: string
  ): Response {
    const errorMessage = error instanceof Error ? error.message : 'Unknown error';
    
    const errorResponse = {
      error: {
        type: 'internal_error',
        code: 'unexpected_error',
        message: errorMessage,
      },
      request_id: requestId,
    };
    
    const headers: Record<string, string> = {
      'X-API-Lens-Request-ID': requestId,
      'X-API-Lens-Error-Code': 'unexpected_error',
    };
    
    return c.json(errorResponse, 500, headers);
  }
  
  /**
   * Check if request is streaming
   */
  private isStreamingRequest(context: RequestContext): boolean {
    return context.metadata?.stream === true;
  }
  
  /**
   * Check if response is streaming
   */
  private isStreamingResponse(response: VendorResponse): boolean {
    return response.object === 'chat.completion.chunk';
  }
  
  /**
   * Handle streaming response
   */
  private async handleStreamingResponse(
    c: Context<{ Bindings: Env }>,
    response: VendorResponse,
    headers: Record<string, string>
  ): Promise<Response> {
    // For streaming, we need to create a ReadableStream
    const encoder = new TextEncoder();
    
    const stream = new ReadableStream({
      async start(controller) {
        try {
          // This is a simplified streaming implementation
          // In a real scenario, you'd process the vendor's streaming response
          
          const chunk: StreamChunk = {
            id: response.id || 'chunk-1',
            object: 'chat.completion.chunk',
            created: Date.now(),
            model: response.model || 'unknown',
            choices: [{
              index: 0,
              delta: {
                content: 'Streaming response...',
              },
              finish_reason: null,
            }],
          };
          
          const data = `data: ${JSON.stringify(chunk)}\n\n`;
          controller.enqueue(encoder.encode(data));
          
          // Send final chunk
          const finalChunk = {
            ...chunk,
            choices: [{
              index: 0,
              delta: {},
              finish_reason: 'stop',
            }],
          };
          
          const finalData = `data: ${JSON.stringify(finalChunk)}\n\n`;
          controller.enqueue(encoder.encode(finalData));
          
          const endData = 'data: [DONE]\n\n';
          controller.enqueue(encoder.encode(endData));
          
          controller.close();
        } catch (error) {
          controller.error(error);
        }
      },
    });
    
    return new Response(stream, {
      status: 200,
      headers: {
        ...headers,
        'Content-Type': 'text/event-stream',
        'Cache-Control': 'no-cache',
        'Connection': 'keep-alive',
      },
    });
  }
  
  /**
   * Map vendor error to HTTP status code
   */
  private mapErrorToStatus(error: VendorError): number {
    switch (error.code) {
      case 'invalid_request':
      case 'invalid_request_error':
        return 400;
      
      case 'invalid_api_key':
      case 'authentication_error':
        return 401;
      
      case 'forbidden':
      case 'permission_error':
        return 403;
      
      case 'not_found':
      case 'model_not_found':
        return 404;
      
      case 'rate_limit_exceeded':
      case 'quota_exceeded':
        return 429;
      
      case 'server_error':
      case 'internal_error':
        return 500;
      
      case 'bad_gateway':
        return 502;
      
      case 'service_unavailable':
      case 'overloaded':
        return 503;
      
      default:
        return 500;
    }
  }
  
  /**
   * Health check for a specific vendor
   */
  async healthCheck(vendor: string): Promise<{
    vendor: string;
    status: 'healthy' | 'degraded' | 'down';
    latency: number;
    details?: any;
  }> {
    const startTime = Date.now();
    
    try {
      const vendorConfig = routeToVendor(vendor);
      
      // Try to get models endpoint as health check
      const response = await fetch(`${vendorConfig.baseUrl}/models`, {
        method: 'GET',
        headers: {
          'User-Agent': 'API-Lens-Health-Check/1.0',
        },
      });
      
      const latency = Date.now() - startTime;
      
      if (response.ok) {
        return {
          vendor,
          status: latency > 5000 ? 'degraded' : 'healthy',
          latency,
        };
      } else {
        return {
          vendor,
          status: 'down',
          latency,
          details: {
            statusCode: response.status,
            statusText: response.statusText,
          },
        };
      }
    } catch (error) {
      return {
        vendor,
        status: 'down',
        latency: Date.now() - startTime,
        details: {
          error: error instanceof Error ? error.message : 'Unknown error',
        },
      };
    }
  }
}
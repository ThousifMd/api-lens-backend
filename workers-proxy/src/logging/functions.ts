/**
 * API Lens Workers Proxy - Logging Functions
 * 
 * Core logging functions as specified in Phase 6.6.1
 */

import { Context } from 'hono';
import {
  RequestMetadata,
  ResponseMetadata,
  PerformanceMetrics,
  ErrorLog,
  LogEntry,
  LogBatch,
  LoggingConfig,
  LoggingStats,
  LoggingHealthCheck,
} from './types';
import { Env } from '../index';
import { getAuthResult } from '../auth';

/**
 * Generate unique request ID
 */
export function generateRequestId(): string {
  return crypto.randomUUID();
}

/**
 * Collect request metadata from incoming request
 * 
 * @param request - The incoming Request object
 * @returns Promise<RequestMetadata> - Collected request metadata
 */
export async function collectRequestMetadata(request: Request): Promise<RequestMetadata> {
  const requestId = generateRequestId();
  const timestamp = Date.now();
  const url = new URL(request.url);
  
  // Extract basic request information
  const method = request.method;
  const userAgent = request.headers.get('user-agent') || undefined;
  const origin = request.headers.get('origin') || undefined;
  const referer = request.headers.get('referer') || undefined;
  const contentType = request.headers.get('content-type') || undefined;
  const contentLength = parseInt(request.headers.get('content-length') || '0');
  
  // Collect headers (excluding sensitive ones)
  const headers: Record<string, string> = {};
  const excludeHeaders = [
    'authorization',
    'x-api-key',
    'cookie',
    'set-cookie',
    'x-forwarded-for',
    'x-real-ip',
  ];
  
  for (const [key, value] of request.headers.entries()) {
    if (!excludeHeaders.includes(key.toLowerCase())) {
      headers[key] = value;
    }
  }
  
  // Extract vendor and model from URL path
  const pathParts = url.pathname.split('/').filter(Boolean);
  const vendor = pathParts[0] || 'unknown';
  const endpoint = pathParts.slice(1).join('/') || 'unknown';
  
  // Try to extract IP from headers (Cloudflare specific)
  const ip = request.headers.get('cf-connecting-ip') || 
             request.headers.get('x-forwarded-for')?.split(',')[0] || 
             undefined;
  
  // Extract geographical data from Cloudflare headers
  const country = request.headers.get('cf-ipcountry') || undefined;
  const region = request.headers.get('cf-region') || undefined;
  const city = request.headers.get('cf-ipcity') || undefined;
  const timezone = request.headers.get('cf-timezone') || undefined;
  
  // Clone request to read body if needed
  let requestBody: any = undefined;
  let bodyHash: string | undefined;
  let bodySize = 0;
  
  if (request.method !== 'GET' && request.method !== 'HEAD') {
    try {
      const clonedRequest = request.clone();
      const body = await clonedRequest.text();
      bodySize = new TextEncoder().encode(body).length;
      
      // Parse JSON body if possible
      if (contentType?.includes('application/json') && body) {
        try {
          requestBody = JSON.parse(body);
        } catch {
          requestBody = body;
        }
      } else {
        requestBody = body;
      }
      
      // Generate hash of body for privacy
      if (body) {
        const encoder = new TextEncoder();
        const data = encoder.encode(body);
        const hashBuffer = await crypto.subtle.digest('SHA-256', data);
        const hashArray = Array.from(new Uint8Array(hashBuffer));
        bodyHash = hashArray.map(b => b.toString(16).padStart(2, '0')).join('');
      }
    } catch (error) {
      console.warn('Failed to read request body:', error);
    }
  }
  
  // Extract model from request body
  let model: string | undefined;
  if (requestBody && typeof requestBody === 'object' && requestBody.model) {
    model = requestBody.model;
  }
  
  return {
    requestId,
    timestamp,
    method,
    url: request.url,
    userAgent,
    origin,
    referer,
    ip,
    headers,
    contentLength: contentLength || undefined,
    contentType,
    vendor,
    model,
    endpoint,
    requestBody,
    bodyHash,
    bodySize,
    country,
    region,
    city,
    timezone,
  };
}

/**
 * Collect response metadata from outgoing response
 * 
 * @param response - The outgoing Response object
 * @param startTime - Request start timestamp
 * @param requestId - Associated request ID
 * @returns Promise<ResponseMetadata> - Collected response metadata
 */
export async function collectResponseMetadata(
  response: Response,
  startTime: number,
  requestId: string,
  vendorLatency?: number
): Promise<ResponseMetadata> {
  const timestamp = Date.now();
  const totalLatency = timestamp - startTime;
  const processingLatency = vendorLatency ? totalLatency - vendorLatency : totalLatency;
  
  // Extract basic response information
  const statusCode = response.status;
  const statusText = response.statusText;
  const contentType = response.headers.get('content-type') || undefined;
  const contentLength = parseInt(response.headers.get('content-length') || '0');
  
  // Collect headers (excluding sensitive ones)
  const headers: Record<string, string> = {};
  const excludeHeaders = [
    'set-cookie',
    'authorization',
    'x-api-key',
  ];
  
  for (const [key, value] of response.headers.entries()) {
    if (!excludeHeaders.includes(key.toLowerCase())) {
      headers[key] = value;
    }
  }
  
  // Try to read response body for analysis
  let responseBody: any = undefined;
  let bodyHash: string | undefined;
  let bodySize = 0;
  let inputTokens: number | undefined;
  let outputTokens: number | undefined;
  let totalTokens: number | undefined;
  
  try {
    const clonedResponse = response.clone();
    const body = await clonedResponse.text();
    bodySize = new TextEncoder().encode(body).length;
    
    // Parse JSON response if possible
    if (contentType?.includes('application/json') && body) {
      try {
        responseBody = JSON.parse(body);
        
        // Extract token usage from common API response formats
        if (responseBody.usage) {
          // OpenAI format
          inputTokens = responseBody.usage.prompt_tokens || responseBody.usage.input_tokens;
          outputTokens = responseBody.usage.completion_tokens || responseBody.usage.output_tokens;
          totalTokens = responseBody.usage.total_tokens;
        } else if (responseBody.usageMetadata) {
          // Google AI format
          inputTokens = responseBody.usageMetadata.promptTokenCount;
          outputTokens = responseBody.usageMetadata.candidatesTokenCount;
          totalTokens = responseBody.usageMetadata.totalTokenCount;
        }
      } catch {
        responseBody = body;
      }
    } else {
      responseBody = body;
    }
    
    // Generate hash of body for privacy
    if (body) {
      const encoder = new TextEncoder();
      const data = encoder.encode(body);
      const hashBuffer = await crypto.subtle.digest('SHA-256', data);
      const hashArray = Array.from(new Uint8Array(hashBuffer));
      bodyHash = hashArray.map(b => b.toString(16).padStart(2, '0')).join('');
    }
  } catch (error) {
    console.warn('Failed to read response body:', error);
  }
  
  // Determine success status
  const success = statusCode >= 200 && statusCode < 400;
  
  // Extract error information from response
  let errorCode: string | undefined;
  let errorMessage: string | undefined;
  let errorType: string | undefined;
  
  if (!success && responseBody && typeof responseBody === 'object') {
    errorCode = responseBody.error?.code || responseBody.code || statusCode.toString();
    errorMessage = responseBody.error?.message || responseBody.message || statusText;
    errorType = responseBody.error?.type || responseBody.type || 'http_error';
  }
  
  // Check for cache information
  const cacheHit = response.headers.get('x-cache') === 'HIT' || 
                   response.headers.get('cf-cache-status') === 'HIT';
  const cacheKey = response.headers.get('x-cache-key') || undefined;
  
  return {
    requestId,
    timestamp,
    statusCode,
    statusText,
    headers,
    contentLength: contentLength || undefined,
    contentType,
    responseBody,
    bodyHash,
    bodySize,
    totalLatency,
    vendorLatency,
    processingLatency,
    success,
    errorCode,
    errorMessage,
    errorType,
    inputTokens,
    outputTokens,
    totalTokens,
    cacheHit,
    cacheKey,
  };
}

/**
 * Collect performance metrics for the request
 * 
 * @param requestId - Request identifier
 * @param companyId - Company identifier
 * @param startTime - Request start time
 * @param success - Whether request was successful
 * @param metrics - Additional timing metrics
 * @returns PerformanceMetrics - Collected performance data
 */
export function collectPerformanceMetrics(
  requestId: string,
  companyId: string,
  startTime: number,
  success: boolean,
  metrics: {
    vendorLatency?: number;
    authLatency?: number;
    ratelimitLatency?: number;
    costLatency?: number;
    loggingLatency?: number;
    errorType?: string;
    retryCount?: number;
    bytesIn?: number;
    bytesOut?: number;
    cacheHitRate?: number;
    rateLimitRemaining?: number;
    queueDepth?: number;
  } = {}
): PerformanceMetrics {
  const timestamp = Date.now();
  const totalLatency = timestamp - startTime;
  
  return {
    requestId,
    companyId,
    timestamp,
    totalLatency,
    vendorLatency: metrics.vendorLatency || 0,
    authLatency: metrics.authLatency || 0,
    ratelimitLatency: metrics.ratelimitLatency || 0,
    costLatency: metrics.costLatency || 0,
    loggingLatency: metrics.loggingLatency || 0,
    success,
    errorType: metrics.errorType as any,
    retryCount: metrics.retryCount,
    bytesIn: metrics.bytesIn || 0,
    bytesOut: metrics.bytesOut || 0,
    cacheHitRate: metrics.cacheHitRate,
    rateLimitRemaining: metrics.rateLimitRemaining,
    queueDepth: metrics.queueDepth,
  };
}

/**
 * Create error log entry
 * 
 * @param error - Error object or message
 * @param context - Additional context information
 * @returns ErrorLog - Formatted error log
 */
export function createErrorLog(
  error: Error | string,
  context: {
    requestId: string;
    companyId?: string;
    component: string;
    function?: string;
    vendor?: string;
    model?: string;
    severity?: 'low' | 'medium' | 'high' | 'critical';
    level?: 'error' | 'warn' | 'info' | 'debug';
    metadata?: Record<string, any>;
  }
): ErrorLog {
  const timestamp = Date.now();
  const isError = error instanceof Error;
  
  return {
    requestId: context.requestId,
    companyId: context.companyId,
    timestamp,
    level: context.level || 'error',
    errorType: isError ? error.constructor.name : 'GeneralError',
    errorMessage: isError ? error.message : String(error),
    stackTrace: isError ? error.stack : undefined,
    component: context.component,
    function: context.function,
    vendor: context.vendor,
    model: context.model,
    metadata: context.metadata,
    severity: context.severity || 'medium',
  };
}

/**
 * Async log function for complete request/response logging
 * 
 * @param companyId - Company identifier
 * @param requestData - Request data including metadata
 * @param responseData - Response data including metadata
 * @param env - Environment bindings
 */
export async function logRequest(
  companyId: string,
  requestData: any,
  responseData: any,
  env: Env
): Promise<void> {
  try {
    const logEntry: LogEntry = {
      requestId: requestData.requestId || generateRequestId(),
      companyId,
      timestamp: Date.now(),
      request: requestData,
      response: responseData,
      performance: requestData.performance || collectPerformanceMetrics(
        requestData.requestId,
        companyId,
        requestData.startTime,
        responseData.success
      ),
      cost: responseData.cost,
    };
    
    // Send to backend asynchronously
    await sendToBackend(logEntry, env);
    
  } catch (error) {
    await handleLoggingErrors(error, {
      component: 'logRequest',
      companyId,
      requestId: requestData.requestId,
    });
  }
}

/**
 * Send log data to Python backend
 * 
 * @param logData - Log data to send
 * @param env - Environment bindings
 */
export async function sendToBackend(logData: any, env: Env): Promise<void> {
  try {
    const startTime = Date.now();
    
    const response = await fetch(`${env.API_LENS_BACKEND_URL}/logs/requests`, {
      method: 'POST',
      headers: {
        'Authorization': `Bearer ${env.API_LENS_BACKEND_TOKEN}`,
        'Content-Type': 'application/json',
        'X-Worker-Version': '1.0.0',
        'X-Log-Source': 'workers-proxy',
        'X-Log-Timestamp': Date.now().toString(),
      },
      body: JSON.stringify(logData),
    });
    
    if (!response.ok) {
      throw new Error(`Backend logging failed: ${response.status} ${response.statusText}`);
    }
    
    const latency = Date.now() - startTime;
    console.debug(`Log sent to backend successfully in ${latency}ms`);
    
  } catch (error) {
    await handleLoggingErrors(error, {
      component: 'sendToBackend',
      function: 'sendToBackend',
      metadata: { logDataType: typeof logData },
    });
  }
}

/**
 * Handle logging errors gracefully
 * 
 * @param error - The error that occurred
 * @param context - Context information about the error
 */
export async function handleLoggingErrors(
  error: any,
  context: {
    component: string;
    function?: string;
    companyId?: string;
    requestId?: string;
    metadata?: Record<string, any>;
  }
): Promise<void> {
  try {
    // Log to console for immediate visibility
    console.error('Logging error occurred:', {
      error: error instanceof Error ? error.message : String(error),
      context,
      timestamp: new Date().toISOString(),
    });
    
    // Try to send error to a separate error logging endpoint
    // This prevents recursive error loops
    const errorLog = createErrorLog(error, {
      requestId: context.requestId || 'unknown',
      companyId: context.companyId,
      component: context.component,
      function: context.function,
      severity: 'high',
      metadata: context.metadata,
    });
    
    // Store error in KV for later analysis if backend is down
    if (context.requestId) {
      const errorKey = `logging_error:${context.requestId}:${Date.now()}`;
      // We'll implement KV storage in the service layer
      console.warn(`Storing logging error in KV: ${errorKey}`);
    }
    
  } catch (nestedError) {
    // If error handling itself fails, just log to console
    console.error('Critical: Error handling failed:', nestedError);
  }
}

/**
 * Create a log batch for efficient transmission
 * 
 * @param entries - Array of log entries
 * @param metadata - Batch metadata
 * @returns LogBatch - Formatted log batch
 */
export function createLogBatch(
  entries: LogEntry[],
  metadata: {
    workerVersion: string;
    region: string;
    datacenter?: string;
  }
): LogBatch {
  const batchId = crypto.randomUUID();
  const timestamp = Date.now();
  
  return {
    batchId,
    timestamp,
    entries,
    metadata: {
      ...metadata,
      batchSize: entries.length,
    },
  };
}

/**
 * Calculate content hash for data integrity
 * 
 * @param data - Data to hash
 * @returns Promise<string> - SHA-256 hash
 */
export async function calculateContentHash(data: string): Promise<string> {
  const encoder = new TextEncoder();
  const dataBuffer = encoder.encode(data);
  const hashBuffer = await crypto.subtle.digest('SHA-256', dataBuffer);
  const hashArray = Array.from(new Uint8Array(hashBuffer));
  return hashArray.map(b => b.toString(16).padStart(2, '0')).join('');
}

/**
 * Compress log data for efficient transmission
 * 
 * @param data - Data to compress
 * @returns Promise<Uint8Array> - Compressed data
 */
export async function compressLogData(data: string): Promise<Uint8Array> {
  const encoder = new TextEncoder();
  const dataBuffer = encoder.encode(data);
  
  // Use CompressionStream if available (Cloudflare Workers support)
  if (typeof CompressionStream !== 'undefined') {
    const compressionStream = new CompressionStream('gzip');
    const writer = compressionStream.writable.getWriter();
    const reader = compressionStream.readable.getReader();
    
    writer.write(dataBuffer);
    writer.close();
    
    const chunks: Uint8Array[] = [];
    let done = false;
    
    while (!done) {
      const { value, done: readerDone } = await reader.read();
      done = readerDone;
      if (value) {
        chunks.push(value);
      }
    }
    
    // Combine chunks
    const totalLength = chunks.reduce((sum, chunk) => sum + chunk.length, 0);
    const result = new Uint8Array(totalLength);
    let offset = 0;
    
    for (const chunk of chunks) {
      result.set(chunk, offset);
      offset += chunk.length;
    }
    
    return result;
  }
  
  // Fallback to uncompressed data
  return dataBuffer;
}

/**
 * Sanitize sensitive data from logs
 * 
 * @param data - Data to sanitize
 * @param config - Sanitization rules
 * @returns Sanitized data
 */
export function sanitizeLogData(
  data: any,
  config: {
    enableBodyRedaction?: boolean;
    enableIpHashing?: boolean;
    redactionRules?: Record<string, string>;
  } = {}
): any {
  if (!data || typeof data !== 'object') {
    return data;
  }
  
  const sanitized = JSON.parse(JSON.stringify(data));
  
  // Redact sensitive fields
  const sensitiveFields = [
    'password',
    'token',
    'key',
    'secret',
    'authorization',
    'api_key',
    'apikey',
    'auth',
    'credential',
    'private',
    'ssn',
    'social_security',
    'credit_card',
    'cc_number',
  ];
  
  function redactObject(obj: any): void {
    if (!obj || typeof obj !== 'object') return;
    
    for (const [key, value] of Object.entries(obj)) {
      const lowerKey = key.toLowerCase();
      
      // Check if field should be redacted
      if (sensitiveFields.some(field => lowerKey.includes(field))) {
        obj[key] = '[REDACTED]';
      } else if (typeof value === 'object' && value !== null) {
        redactObject(value);
      }
    }
  }
  
  if (config.enableBodyRedaction) {
    redactObject(sanitized);
  }
  
  // Hash IP addresses if enabled
  if (config.enableIpHashing && sanitized.request?.ip) {
    sanitized.request.ip = hashString(sanitized.request.ip);
  }
  
  // Apply custom redaction rules
  if (config.redactionRules) {
    for (const [pattern, replacement] of Object.entries(config.redactionRules)) {
      const regex = new RegExp(pattern, 'gi');
      const jsonStr = JSON.stringify(sanitized);
      const redactedStr = jsonStr.replace(regex, replacement);
      try {
        Object.assign(sanitized, JSON.parse(redactedStr));
      } catch {
        // If parsing fails, skip this rule
      }
    }
  }
  
  return sanitized;
}

/**
 * Hash a string using SHA-256
 * 
 * @param input - String to hash
 * @returns Promise<string> - Hashed string
 */
async function hashString(input: string): Promise<string> {
  const encoder = new TextEncoder();
  const data = encoder.encode(input);
  const hashBuffer = await crypto.subtle.digest('SHA-256', data);
  const hashArray = Array.from(new Uint8Array(hashBuffer));
  return hashArray.map(b => b.toString(16).padStart(2, '0')).join('');
}

/**
 * Get logging statistics
 * 
 * @param timeWindow - Time window in milliseconds
 * @returns LoggingStats - Current logging statistics
 */
export function getLoggingStats(timeWindow: number = 300000): LoggingStats {
  const timestamp = Date.now();
  
  // This would be implemented with actual metrics collection
  // For now, return mock data structure
  return {
    timestamp,
    totalRequests: 0,
    totalLogs: 0,
    totalBytes: 0,
    averageLatency: 0,
    p95Latency: 0,
    p99Latency: 0,
    successRate: 100,
    queueSize: 0,
    queueDepth: 0,
    averageQueueTime: 0,
    droppedLogs: 0,
    errorRate: 0,
    errorsByType: {},
    retryRate: 0,
    backendLatency: 0,
    backendSuccessRate: 100,
    backendErrorRate: 0,
  };
}

/**
 * Perform health check on logging system
 * 
 * @param env - Environment bindings
 * @returns Promise<LoggingHealthCheck> - Health check results
 */
export async function performLoggingHealthCheck(env: Env): Promise<LoggingHealthCheck> {
  const timestamp = Date.now();
  let backendHealthy = true;
  let backendLatency: number | undefined;
  
  try {
    const startTime = Date.now();
    const response = await fetch(`${env.API_LENS_BACKEND_URL}/health`, {
      headers: {
        'Authorization': `Bearer ${env.API_LENS_BACKEND_TOKEN}`,
      },
    });
    backendLatency = Date.now() - startTime;
    backendHealthy = response.ok;
  } catch {
    backendHealthy = false;
  }
  
  return {
    healthy: backendHealthy,
    timestamp,
    queue: {
      healthy: true,
      size: 0,
      maxSize: 1000,
    },
    backend: {
      healthy: backendHealthy,
      latency: backendLatency,
      consecutiveFailures: backendHealthy ? 0 : 1,
    },
    storage: {
      healthy: true,
      usage: 0,
      maxUsage: 1000000,
    },
    successRate: 100,
    errorRate: 0,
    averageLatency: backendLatency || 0,
    issues: backendHealthy ? [] : ['Backend unreachable'],
    recommendations: backendHealthy ? [] : ['Check backend connectivity'],
  };
}
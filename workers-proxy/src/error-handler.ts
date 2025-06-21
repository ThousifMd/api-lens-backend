/**
 * API Lens Workers Proxy - Error Handling
 * 
 * Centralized error handling and response formatting
 */

import { Context } from 'hono';
import { Env } from './index';
import { AuthenticationError } from './auth/types';
import { RateLimitError } from './ratelimit';
import { VendorError } from './vendor/types';
import { ValidationError } from './validation';
import { logAuthEvent, logRateLimit, logVendorError } from './logger';

export interface ErrorResponse {
  error: string;
  message: string;
  code?: string;
  details?: any;
  requestId: string;
  timestamp: string;
  retryAfter?: number;
}

/**
 * Handle different types of errors and return appropriate responses
 */
export async function handleError(
  c: Context<{ Bindings: Env }>,
  error: Error
): Promise<Response> {
  const requestId = c.get('requestId') || crypto.randomUUID();
  const timestamp = new Date().toISOString();
  
  console.error(`Error handling request ${requestId}:`, error);
  
  // Handle specific error types
  if (error instanceof AuthenticationError) {
    return handleAuthenticationError(c, error, requestId, timestamp);
  }
  
  if (error instanceof RateLimitError) {
    return handleRateLimitError(c, error, requestId, timestamp);
  }
  
  if (error instanceof VendorError) {
    return handleVendorError(c, error, requestId, timestamp);
  }
  
  if (error instanceof ValidationError) {
    return handleValidationError(c, error, requestId, timestamp);
  }
  
  // Handle generic errors
  return handleGenericError(c, error, requestId, timestamp);
}

/**
 * Handle authentication errors
 */
async function handleAuthenticationError(
  c: Context<{ Bindings: Env }>,
  error: AuthenticationError,
  requestId: string,
  timestamp: string
): Promise<Response> {
  // Log authentication failure
  await logAuthEvent(c, 'authentication_failed', false, {
    error: error.message,
    status: error.status,
  });
  
  const response: ErrorResponse = {
    error: 'Authentication Failed',
    message: error.message,
    code: 'AUTH_ERROR',
    requestId,
    timestamp,
  };
  
  return c.json(response, error.status);
}

/**
 * Handle rate limit errors
 */
async function handleRateLimitError(
  c: Context<{ Bindings: Env }>,
  error: RateLimitError,
  requestId: string,
  timestamp: string
): Promise<Response> {
  const authResult = c.get('auth');
  
  // Log rate limit event
  if (authResult) {
    await logRateLimit(
      c,
      authResult.companyId,
      'requests',
      error.remaining,
      error.resetTime
    );
  }
  
  const response: ErrorResponse = {
    error: 'Rate Limit Exceeded',
    message: error.message,
    code: 'RATE_LIMIT_ERROR',
    details: {
      limit: error.limit,
      remaining: error.remaining,
      resetTime: error.resetTime,
    },
    requestId,
    timestamp,
    retryAfter: error.retryAfter,
  };
  
  // Set rate limit headers
  const headers: Record<string, string> = {
    'X-RateLimit-Limit': error.limit.toString(),
    'X-RateLimit-Remaining': error.remaining.toString(),
    'X-RateLimit-Reset': error.resetTime.toString(),
  };
  
  if (error.retryAfter) {
    headers['Retry-After'] = error.retryAfter.toString();
  }
  
  return c.json(response, 429, headers);
}

/**
 * Handle vendor API errors
 */
async function handleVendorError(
  c: Context<{ Bindings: Env }>,
  error: VendorError,
  requestId: string,
  timestamp: string
): Promise<Response> {
  // Log vendor error
  await logVendorError(c, error.vendor, error);
  
  const response: ErrorResponse = {
    error: 'Vendor API Error',
    message: error.message,
    code: 'VENDOR_ERROR',
    details: {
      vendor: error.vendor,
      vendorStatus: error.status,
      vendorResponse: error.vendorResponse,
    },
    requestId,
    timestamp,
  };
  
  // Map vendor status codes to appropriate proxy status codes
  let statusCode = 500;
  
  switch (error.status) {
    case 400:
      statusCode = 400; // Bad request
      break;
    case 401:
      statusCode = 401; // Unauthorized
      response.error = 'Vendor Authentication Failed';
      response.message = 'Invalid vendor API key';
      break;
    case 403:
      statusCode = 403; // Forbidden
      break;
    case 404:
      statusCode = 404; // Not found
      break;
    case 429:
      statusCode = 429; // Rate limited by vendor
      response.error = 'Vendor Rate Limit Exceeded';
      break;
    case 500:
    case 502:
    case 503:
    case 504:
      statusCode = 502; // Bad gateway
      response.error = 'Vendor Service Unavailable';
      break;
    default:
      statusCode = 500;
  }
  
  return c.json(response, statusCode);
}

/**
 * Handle validation errors
 */
async function handleValidationError(
  c: Context<{ Bindings: Env }>,
  error: ValidationError,
  requestId: string,
  timestamp: string
): Promise<Response> {
  const response: ErrorResponse = {
    error: 'Validation Error',
    message: error.message,
    code: 'VALIDATION_ERROR',
    requestId,
    timestamp,
  };
  
  return c.json(response, error.status);
}

/**
 * Handle generic/unknown errors
 */
async function handleGenericError(
  c: Context<{ Bindings: Env }>,
  error: Error,
  requestId: string,
  timestamp: string
): Promise<Response> {
  // Don't expose internal error details in production
  const isProduction = c.env.ENVIRONMENT === 'production';
  
  const response: ErrorResponse = {
    error: 'Internal Server Error',
    message: isProduction 
      ? 'An unexpected error occurred' 
      : error.message,
    code: 'INTERNAL_ERROR',
    requestId,
    timestamp,
  };
  
  // Include stack trace in development
  if (!isProduction) {
    response.details = {
      stack: error.stack,
      name: error.name,
    };
  }
  
  return c.json(response, 500);
}

/**
 * Create standardized error response
 */
export function createErrorResponse(
  message: string,
  code: string,
  status: number = 500,
  details?: any
): ErrorResponse {
  return {
    error: getErrorTitle(status),
    message,
    code,
    details,
    requestId: crypto.randomUUID(),
    timestamp: new Date().toISOString(),
  };
}

/**
 * Get error title based on status code
 */
function getErrorTitle(status: number): string {
  switch (status) {
    case 400:
      return 'Bad Request';
    case 401:
      return 'Unauthorized';
    case 403:
      return 'Forbidden';
    case 404:
      return 'Not Found';
    case 405:
      return 'Method Not Allowed';
    case 408:
      return 'Request Timeout';
    case 409:
      return 'Conflict';
    case 413:
      return 'Payload Too Large';
    case 415:
      return 'Unsupported Media Type';
    case 422:
      return 'Unprocessable Entity';
    case 429:
      return 'Too Many Requests';
    case 500:
      return 'Internal Server Error';
    case 501:
      return 'Not Implemented';
    case 502:
      return 'Bad Gateway';
    case 503:
      return 'Service Unavailable';
    case 504:
      return 'Gateway Timeout';
    default:
      return 'Error';
  }
}

/**
 * Handle CORS preflight errors
 */
export function handleCorsError(c: Context): Response {
  return c.json({
    error: 'CORS Error',
    message: 'Cross-Origin Resource Sharing (CORS) error',
    code: 'CORS_ERROR',
    requestId: crypto.randomUUID(),
    timestamp: new Date().toISOString(),
  }, 403);
}

/**
 * Handle timeout errors
 */
export function handleTimeoutError(c: Context, timeout: number): Response {
  const response: ErrorResponse = {
    error: 'Request Timeout',
    message: `Request timed out after ${timeout}ms`,
    code: 'TIMEOUT_ERROR',
    details: {
      timeoutMs: timeout,
    },
    requestId: c.get('requestId') || crypto.randomUUID(),
    timestamp: new Date().toISOString(),
  };
  
  return c.json(response, 408);
}

/**
 * Handle quota exceeded errors
 */
export function handleQuotaError(
  c: Context,
  quotaType: string,
  current: number,
  limit: number
): Response {
  const response: ErrorResponse = {
    error: 'Quota Exceeded',
    message: `${quotaType} quota exceeded`,
    code: 'QUOTA_ERROR',
    details: {
      quotaType,
      current,
      limit,
    },
    requestId: c.get('requestId') || crypto.randomUUID(),
    timestamp: new Date().toISOString(),
  };
  
  return c.json(response, 429);
}

/**
 * Create error for unsupported HTTP methods
 */
export function handleMethodNotAllowed(c: Context, allowedMethods: string[]): Response {
  const response: ErrorResponse = {
    error: 'Method Not Allowed',
    message: `HTTP method ${c.req.method} is not allowed for this endpoint`,
    code: 'METHOD_NOT_ALLOWED',
    details: {
      method: c.req.method,
      allowedMethods,
    },
    requestId: c.get('requestId') || crypto.randomUUID(),
    timestamp: new Date().toISOString(),
  };
  
  return c.json(response, 405, {
    'Allow': allowedMethods.join(', '),
  });
}
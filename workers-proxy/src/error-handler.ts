/**
 * API Lens Workers Proxy - Error Handling
 * 
 * Centralized error handling and response formatting
 */

import { Context } from 'hono';
import { Env, HonoVariables } from './types';
import { ValidationError } from './validation';

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
  c: Context<{ Bindings: Env; Variables: HonoVariables }>,
  error: unknown
): Promise<Response> {
  console.error('Request error:', error);
  
  let status = 500;
  let message = 'Internal Server Error';
  
  if (error instanceof Error) {
    message = error.message;
    
    // Determine status code based on error message
    if (message.includes('too large')) {
      status = 413;
    } else if (message.includes('not found')) {
      status = 404;
    } else if (message.includes('unauthorized') || message.includes('invalid api key')) {
      status = 401;
    } else if (message.includes('forbidden') || message.includes('access denied')) {
      status = 403;
    } else if (message.includes('rate limit')) {
      status = 429;
    }
  }
  
  if (error instanceof ValidationError) {
    status = error.status;
    message = error.message;
  }
  
  return c.json({
    error: 'Request Failed',
    message,
    requestId: c.get('requestId') || 'unknown',
    timestamp: new Date().toISOString()
  }, status);
}

/**
 * Handle authentication errors
 */

/**
 * Handle rate limit errors
 */

/**
 * Handle vendor API errors
 */

/**
 * Handle validation errors
 */

/**
 * Handle generic/unknown errors
 */

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
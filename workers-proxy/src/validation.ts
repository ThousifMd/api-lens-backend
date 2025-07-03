/**
 * API Lens Workers Proxy - Request Validation
 * 
 * Validates incoming requests for size, format, and security
 */

import { Context } from 'hono';
import { Env, HonoVariables } from './types';

export class ValidationError extends Error {
  constructor(message: string, public status: number = 400) {
    super(message);
    this.name = 'ValidationError';
  }
}

/**
 * Validate incoming request
 */
export async function validateRequest(c: Context<{ Bindings: Env; Variables: HonoVariables }>): Promise<void> {
  // Simplified validation - check request size and content type
  const contentLength = c.req.header('content-length');
  const maxSize = parseInt(c.env.MAX_REQUEST_SIZE || '10485760'); // 10MB default
  
  if (contentLength && parseInt(contentLength) > maxSize) {
    throw new Error('Request too large');
  }
  
  // Set request ID
  c.set('requestId', c.req.header('X-Request-ID') || crypto.randomUUID());
  c.set('startTime', Date.now());
}

/**
 * Validate request body size
 */

/**
 * Validate content type for POST/PUT requests
 */

/**
 * Validate request headers
 */

/**
 * Validate request path
 */

/**
 * Validate JSON body
 */
export function validateJsonBody(body: any): void {
  if (typeof body !== 'object' || body === null) {
    throw new ValidationError('Request body must be a valid JSON object', 400);
  }
  
  // Check for overly nested objects
  const maxDepth = 10;
  if (getObjectDepth(body) > maxDepth) {
    throw new ValidationError(`JSON object too deeply nested. Maximum depth: ${maxDepth}`, 400);
  }
  
  // Check for circular references
  try {
    JSON.stringify(body);
  } catch (error) {
    throw new ValidationError('JSON contains circular references', 400);
  }
}

/**
 * Get object nesting depth
 */
function getObjectDepth(obj: any, depth: number = 0): number {
  if (depth > 20) return depth; // Prevent infinite recursion
  
  if (typeof obj !== 'object' || obj === null) {
    return depth;
  }
  
  let maxDepth = depth;
  for (const key in obj) {
    if (obj.hasOwnProperty(key)) {
      const childDepth = getObjectDepth(obj[key], depth + 1);
      maxDepth = Math.max(maxDepth, childDepth);
    }
  }
  
  return maxDepth;
}

/**
 * Validate API key format
 */
export function validateApiKeyFormat(apiKey: string): boolean {
  // API Lens keys: als_[43 alphanumeric characters]
  return /^als_[a-zA-Z0-9]{43}$/.test(apiKey);
}

/**
 * Sanitize input string
 */
export function sanitizeInput(input: string): string {
  return input
    .replace(/[<>]/g, '') // Remove angle brackets
    .replace(/javascript:/gi, '') // Remove javascript protocol
    .replace(/data:/gi, '') // Remove data protocol
    .replace(/vbscript:/gi, '') // Remove vbscript protocol
    .trim();
}

/**
 * Validate rate limiting parameters
 */
export function validateRateLimit(limit: number, window: number): void {
  if (limit < 1 || limit > 100000) {
    throw new ValidationError('Rate limit must be between 1 and 100,000', 400);
  }
  
  if (window < 60 || window > 86400) {
    throw new ValidationError('Rate limit window must be between 60 seconds and 24 hours', 400);
  }
}

/**
 * Validate vendor-specific request bodies
 */
export function validateVendorRequest(vendor: string, body: any): void {
  switch (vendor) {
    case 'openai':
      validateOpenAIRequest(body);
      break;
    case 'anthropic':
      validateAnthropicRequest(body);
      break;
    case 'google':
      validateGoogleRequest(body);
      break;
  }
}

function validateOpenAIRequest(body: any): void {
  if (body.messages) {
    if (!Array.isArray(body.messages)) {
      throw new ValidationError('messages must be an array', 400);
    }
    
    if (body.messages.length === 0) {
      throw new ValidationError('messages array cannot be empty', 400);
    }
    
    for (const message of body.messages) {
      if (!message.role || !message.content) {
        throw new ValidationError('Each message must have role and content', 400);
      }
      
      if (!['system', 'user', 'assistant'].includes(message.role)) {
        throw new ValidationError('Invalid message role', 400);
      }
    }
  }
  
  if (body.max_tokens && (body.max_tokens < 1 || body.max_tokens > 4096)) {
    throw new ValidationError('max_tokens must be between 1 and 4096', 400);
  }
  
  if (body.temperature && (body.temperature < 0 || body.temperature > 2)) {
    throw new ValidationError('temperature must be between 0 and 2', 400);
  }
}

function validateAnthropicRequest(body: any): void {
  if (body.messages) {
    if (!Array.isArray(body.messages)) {
      throw new ValidationError('messages must be an array', 400);
    }
    
    for (const message of body.messages) {
      if (!message.role || !message.content) {
        throw new ValidationError('Each message must have role and content', 400);
      }
      
      if (!['user', 'assistant'].includes(message.role)) {
        throw new ValidationError('Invalid message role for Anthropic', 400);
      }
    }
  }
  
  if (body.max_tokens) {
    if (typeof body.max_tokens !== 'number' || body.max_tokens < 1) {
      throw new ValidationError('max_tokens must be a positive number', 400);
    }
  }
}

function validateGoogleRequest(body: any): void {
  if (body.contents) {
    if (!Array.isArray(body.contents)) {
      throw new ValidationError('contents must be an array', 400);
    }
    
    for (const content of body.contents) {
      if (!content.parts || !Array.isArray(content.parts)) {
        throw new ValidationError('Each content must have parts array', 400);
      }
    }
  }
}
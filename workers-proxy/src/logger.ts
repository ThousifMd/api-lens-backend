/**
 * API Lens Workers Proxy - Async Logging to Backend
 * 
 * Handles logging request data to the backend API and Analytics Engine
 */

import { Context } from 'hono';
import { Env, HonoVariables } from './types';

export interface LogData {
  startTime: number;
  endTime: number;
  success: boolean;
  vendor?: string;
  model?: string;
  inputTokens?: number;
  outputTokens?: number;
  totalTokens?: number;
  cost?: number;
  responseTime?: number;
  error?: string;
  statusCode?: number;
}

export interface RequestLog {
  requestId: string;
  companyId: string;
  companyName: string;
  tier: string;
  timestamp: string;
  method: string;
  path: string;
  userAgent: string;
  ipAddress: string;
  country?: string;
  region?: string;
  vendor?: string;
  model?: string;
  inputTokens: number;
  outputTokens: number;
  totalTokens: number;
  cost: number;
  responseTime: number;
  success: boolean;
  statusCode?: number;
  error?: string;
  apiKeyId: string;
}

/**
 * Log request to backend API and Analytics Engine
 */
export async function logRequest(
  c: Context<{ Bindings: Env; Variables: HonoVariables }>,
  data: LogData
): Promise<void> {
  try {
    // Simplified logging - just console log
    console.log('Request log:', {
      timestamp: new Date().toISOString(),
      requestId: c.get('requestId') || 'unknown',
      method: c.req.method,
      path: c.req.path,
      ...data
    });
  } catch (error) {
    console.error('Failed to log request:', error);
  }
}

/**
 * Log to backend API for persistent storage
 */

/**
 * Log to Cloudflare Analytics Engine for real-time analytics
 */

/**
 * Log to console for debugging
 */

/**
 * Get client IP address from request
 */
function getClientIP(c: Context): string {
  return c.req.header('CF-Connecting-IP') || 'Unknown';
}

/**
 * Log rate limit events
 */
export async function logRateLimit(
  c: Context<{ Bindings: Env; Variables: HonoVariables }>,
  companyId: string,
  limitType: string,
  remaining: number,
  resetTime: number
): Promise<void> {
  console.warn(`Rate limit exceeded for company ${companyId}: ${limitType}`);
}

/**
 * Log authentication events
 */
export async function logAuthEvent(
  c: Context<{ Bindings: Env; Variables: HonoVariables }>,
  event: string,
  success: boolean,
  details?: any
): Promise<void> {
  const status = success ? '✅' : '❌';
  console.log(`${status} Auth event: ${event}`);
}

/**
 * Log vendor API errors
 */
export async function logVendorError(
  c: Context<{ Bindings: Env; Variables: HonoVariables }>,
  vendor: string,
  error: any,
  requestBody?: any
): Promise<void> {
  console.error(`❌ Vendor error (${vendor}):`, error.message);
}

/**
 * Batch log multiple events for efficiency
 */
export async function batchLog(
  c: Context<{ Bindings: Env; Variables: HonoVariables }>,
  events: any[]
): Promise<void> {
  console.log('Batch log:', events);
}

/**
 * Create structured log entry for different event types
 */
export function createLogEntry(
  type: 'request' | 'error' | 'auth' | 'rate_limit',
  data: any
): any {
  const baseEntry = {
    timestamp: new Date().toISOString(),
    type,
    ...data,
  };
  
  return baseEntry;
}
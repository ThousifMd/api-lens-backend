/**
 * API Lens Workers Proxy - Async Logging to Backend
 * 
 * Handles logging request data to the backend API and Analytics Engine
 */

import { Context } from 'hono';
import { Env } from './index';

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
  c: Context<{ Bindings: Env }>,
  data: LogData
): Promise<void> {
  const requestId = c.get('requestId') || crypto.randomUUID();
  const authResult = c.get('auth');
  
  if (!authResult) {
    console.warn('No auth result available for logging');
    return;
  }
  
  const logEntry: RequestLog = {
    requestId,
    companyId: authResult.companyId,
    companyName: authResult.companyName,
    tier: authResult.tier,
    timestamp: new Date(data.startTime).toISOString(),
    method: c.req.method,
    path: c.req.path,
    userAgent: c.req.header('User-Agent') || 'Unknown',
    ipAddress: getClientIP(c),
    country: c.cf?.country || 'Unknown',
    region: c.cf?.region || 'Unknown',
    vendor: data.vendor || 'unknown',
    model: data.model || 'unknown',
    inputTokens: data.inputTokens || 0,
    outputTokens: data.outputTokens || 0,
    totalTokens: data.totalTokens || 0,
    cost: data.cost || 0,
    responseTime: data.responseTime || (data.endTime - data.startTime),
    success: data.success,
    statusCode: data.statusCode,
    error: data.error,
    apiKeyId: authResult.apiKeyId,
  };
  
  // Execute logging operations in parallel
  await Promise.all([
    logToBackend(c, logEntry),
    logToAnalyticsEngine(c, logEntry),
    logToConsole(logEntry),
  ]);
}

/**
 * Log to backend API for persistent storage
 */
async function logToBackend(
  c: Context<{ Bindings: Env }>,
  logEntry: RequestLog
): Promise<void> {
  try {
    const response = await fetch(`${c.env.API_LENS_BACKEND_URL}/proxy/logs`, {
      method: 'POST',
      headers: {
        'Authorization': `Bearer ${c.env.API_LENS_BACKEND_TOKEN}`,
        'Content-Type': 'application/json',
        'X-Request-ID': logEntry.requestId,
      },
      body: JSON.stringify(logEntry),
    });
    
    if (!response.ok) {
      console.error(`Failed to log to backend: ${response.status}`, await response.text());
    }
  } catch (error) {
    console.error('Error logging to backend:', error);
    // Don't throw - logging failures shouldn't break the request
  }
}

/**
 * Log to Cloudflare Analytics Engine for real-time analytics
 */
async function logToAnalyticsEngine(
  c: Context<{ Bindings: Env }>,
  logEntry: RequestLog
): Promise<void> {
  try {
    // Prepare data for Analytics Engine
    const analyticsData = {
      indexes: [logEntry.companyId, logEntry.vendor, logEntry.model],
      doubles: [
        logEntry.cost,
        logEntry.responseTime,
        logEntry.inputTokens,
        logEntry.outputTokens,
        logEntry.totalTokens,
      ],
      blobs: [
        logEntry.requestId,
        logEntry.method,
        logEntry.path,
        logEntry.error || '',
        logEntry.apiKeyId,
      ],
    };
    
    c.env.API_ANALYTICS.writeDataPoint(analyticsData);
  } catch (error) {
    console.error('Error logging to Analytics Engine:', error);
    // Don't throw - logging failures shouldn't break the request
  }
}

/**
 * Log to console for debugging
 */
function logToConsole(logEntry: RequestLog): void {
  const logLevel = logEntry.success ? 'info' : 'error';
  const message = `${logEntry.method} ${logEntry.path} - ${logEntry.vendor}/${logEntry.model} - ${logEntry.responseTime}ms - $${logEntry.cost.toFixed(6)}`;
  
  if (logLevel === 'error') {
    console.error(`❌ ${message} - ${logEntry.error}`);
  } else {
    console.log(`✅ ${message}`);
  }
}

/**
 * Get client IP address from request
 */
function getClientIP(c: Context): string {
  // Try various headers for real IP
  const headers = [
    'CF-Connecting-IP',
    'X-Forwarded-For',
    'X-Real-IP',
    'X-Client-IP',
  ];
  
  for (const header of headers) {
    const ip = c.req.header(header);
    if (ip) {
      // Handle comma-separated IPs (take the first one)
      return ip.split(',')[0]?.trim() || 'Unknown';
    }
  }
  
  return 'Unknown';
}

/**
 * Log rate limit events
 */
export async function logRateLimit(
  c: Context<{ Bindings: Env }>,
  companyId: string,
  limitType: string,
  remaining: number,
  resetTime: number
): Promise<void> {
  try {
    const logEntry = {
      requestId: c.get('requestId') || crypto.randomUUID(),
      companyId,
      timestamp: new Date().toISOString(),
      event: 'rate_limit_exceeded',
      limitType,
      remaining,
      resetTime,
      ipAddress: getClientIP(c),
      userAgent: c.req.header('User-Agent') || 'Unknown',
      path: c.req.path,
    };
    
    // Log to backend
    await fetch(`${c.env.API_LENS_BACKEND_URL}/proxy/events`, {
      method: 'POST',
      headers: {
        'Authorization': `Bearer ${c.env.API_LENS_BACKEND_TOKEN}`,
        'Content-Type': 'application/json',
      },
      body: JSON.stringify(logEntry),
    });
    
    console.warn(`Rate limit exceeded for company ${companyId}: ${limitType}`);
  } catch (error) {
    console.error('Error logging rate limit event:', error);
  }
}

/**
 * Log authentication events
 */
export async function logAuthEvent(
  c: Context<{ Bindings: Env }>,
  event: string,
  success: boolean,
  details?: any
): Promise<void> {
  try {
    const logEntry = {
      requestId: c.get('requestId') || crypto.randomUUID(),
      timestamp: new Date().toISOString(),
      event,
      success,
      details,
      ipAddress: getClientIP(c),
      userAgent: c.req.header('User-Agent') || 'Unknown',
      path: c.req.path,
    };
    
    // Log to backend
    await fetch(`${c.env.API_LENS_BACKEND_URL}/proxy/events`, {
      method: 'POST',
      headers: {
        'Authorization': `Bearer ${c.env.API_LENS_BACKEND_TOKEN}`,
        'Content-Type': 'application/json',
      },
      body: JSON.stringify(logEntry),
    });
    
    const status = success ? '✅' : '❌';
    console.log(`${status} Auth event: ${event}`);
  } catch (error) {
    console.error('Error logging auth event:', error);
  }
}

/**
 * Log vendor API errors
 */
export async function logVendorError(
  c: Context<{ Bindings: Env }>,
  vendor: string,
  error: any,
  requestBody?: any
): Promise<void> {
  try {
    const logEntry = {
      requestId: c.get('requestId') || crypto.randomUUID(),
      companyId: c.get('auth')?.companyId || 'unknown',
      timestamp: new Date().toISOString(),
      event: 'vendor_error',
      vendor,
      error: {
        message: error.message || 'Unknown error',
        status: error.status || 0,
        response: error.vendorResponse,
      },
      requestBody: requestBody ? JSON.stringify(requestBody).substring(0, 1000) : undefined,
      ipAddress: getClientIP(c),
      userAgent: c.req.header('User-Agent') || 'Unknown',
    };
    
    // Log to backend
    await fetch(`${c.env.API_LENS_BACKEND_URL}/proxy/events`, {
      method: 'POST',
      headers: {
        'Authorization': `Bearer ${c.env.API_LENS_BACKEND_TOKEN}`,
        'Content-Type': 'application/json',
      },
      body: JSON.stringify(logEntry),
    });
    
    console.error(`❌ Vendor error (${vendor}):`, error.message);
  } catch (logError) {
    console.error('Error logging vendor error:', logError);
  }
}

/**
 * Batch log multiple events for efficiency
 */
export async function batchLog(
  c: Context<{ Bindings: Env }>,
  events: any[]
): Promise<void> {
  if (events.length === 0) return;
  
  try {
    await fetch(`${c.env.API_LENS_BACKEND_URL}/proxy/logs/batch`, {
      method: 'POST',
      headers: {
        'Authorization': `Bearer ${c.env.API_LENS_BACKEND_TOKEN}`,
        'Content-Type': 'application/json',
      },
      body: JSON.stringify({ events }),
    });
  } catch (error) {
    console.error('Error batch logging:', error);
  }
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
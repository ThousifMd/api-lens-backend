/**
 * API Lens Workers Proxy - Logging Types
 * 
 * TypeScript interfaces for async logging system
 */

/**
 * Request metadata collected from incoming requests
 */
export interface RequestMetadata {
  requestId: string;
  timestamp: number;
  method: string;
  url: string;
  userAgent?: string;
  origin?: string;
  referer?: string;
  ip?: string;
  headers: Record<string, string>;
  contentLength?: number;
  contentType?: string;
  vendor: string;
  model?: string;
  endpoint: string;
  
  // Authentication context
  companyId?: string;
  apiKeyId?: string;
  userId?: string;
  
  // Request specifics
  requestBody?: any;
  bodyHash?: string;
  bodySize: number;
  
  // Geographical data
  country?: string;
  region?: string;
  city?: string;
  timezone?: string;
  
  // Performance tracking
  dnsTime?: number;
  connectTime?: number;
  tlsTime?: number;
}

/**
 * Response metadata collected from outgoing responses
 */
export interface ResponseMetadata {
  requestId: string;
  timestamp: number;
  statusCode: number;
  statusText: string;
  headers: Record<string, string>;
  contentLength?: number;
  contentType?: string;
  
  // Response specifics
  responseBody?: any;
  bodyHash?: string;
  bodySize: number;
  
  // Performance metrics
  totalLatency: number;
  vendorLatency?: number;
  processingLatency: number;
  queueTime?: number;
  
  // Success/Error indicators
  success: boolean;
  errorCode?: string;
  errorMessage?: string;
  errorType?: string;
  
  // Usage and cost data
  inputTokens?: number;
  outputTokens?: number;
  totalTokens?: number;
  cost?: number;
  
  // Cache information
  cacheHit?: boolean;
  cacheKey?: string;
  cacheTtl?: number;
}

/**
 * Performance metrics for tracking system health
 */
export interface PerformanceMetrics {
  requestId: string;
  companyId: string;
  timestamp: number;
  
  // Latency metrics (in milliseconds)
  totalLatency: number;
  vendorLatency: number;
  authLatency: number;
  ratelimitLatency: number;
  costLatency: number;
  loggingLatency: number;
  
  // Success/Error rates
  success: boolean;
  errorType?: 'auth' | 'ratelimit' | 'vendor' | 'cost' | 'internal' | 'timeout';
  retryCount?: number;
  
  // Resource usage
  memoryUsage?: number;
  cpuTime?: number;
  
  // Network metrics
  bytesIn: number;
  bytesOut: number;
  connectionReused?: boolean;
  
  // Cache performance
  cacheHitRate?: number;
  cacheLatency?: number;
  
  // Rate limiting
  rateLimitRemaining?: number;
  rateLimitReset?: number;
  
  // Queue metrics
  queueDepth?: number;
  queueWaitTime?: number;
}

/**
 * Error log entry for monitoring and debugging
 */
export interface ErrorLog {
  requestId: string;
  companyId?: string;
  timestamp: number;
  level: 'error' | 'warn' | 'info' | 'debug';
  
  // Error details
  errorType: string;
  errorCode?: string;
  errorMessage: string;
  stackTrace?: string;
  
  // Context information
  component: string;
  function?: string;
  vendor?: string;
  model?: string;
  
  // Request context
  method?: string;
  url?: string;
  userAgent?: string;
  
  // Additional metadata
  metadata?: Record<string, any>;
  
  // Severity and impact
  severity: 'low' | 'medium' | 'high' | 'critical';
  impact?: 'user' | 'system' | 'business';
  
  // Recovery information
  recovered?: boolean;
  recoveryAction?: string;
  retryAttempt?: number;
}

/**
 * Complete log entry combining request, response, performance, and errors
 */
export interface LogEntry {
  // Basic identifiers
  requestId: string;
  companyId: string;
  timestamp: number;
  
  // Request/Response data
  request: RequestMetadata;
  response: ResponseMetadata;
  performance: PerformanceMetrics;
  
  // Error information (if any)
  errors?: ErrorLog[];
  warnings?: ErrorLog[];
  
  // Business metrics
  cost?: number;
  revenue?: number;
  
  // Feature flags and experiments
  features?: string[];
  experiments?: Record<string, string>;
  
  // Custom metadata
  metadata?: Record<string, any>;
}

/**
 * Logging configuration options
 */
export interface LoggingConfig {
  // Backend settings
  backendUrl: string;
  backendToken: string;
  
  // Sampling and filtering
  samplingRate: number;
  logLevel: 'debug' | 'info' | 'warn' | 'error';
  enableRequestBody: boolean;
  enableResponseBody: boolean;
  enableHeaders: boolean;
  enablePerformanceMetrics: boolean;
  
  // Buffer and batch settings
  batchSize: number;
  batchTimeout: number;
  maxRetries: number;
  retryDelay: number;
  
  // Storage settings
  enableLocalStorage: boolean;
  localStorageKey: string;
  maxLocalStorageSize: number;
  
  // Filtering rules
  excludeHeaders?: string[];
  excludeEndpoints?: string[];
  excludeUserAgents?: string[];
  
  // Privacy and security
  enableBodyHashing: boolean;
  enableIpHashing: boolean;
  enableDataRedaction: boolean;
  redactionRules?: Record<string, string>;
}

/**
 * Logging batch for efficient backend transmission
 */
export interface LogBatch {
  batchId: string;
  timestamp: number;
  entries: LogEntry[];
  metadata: {
    workerVersion: string;
    region: string;
    datacenter?: string;
    batchSize: number;
    compressionType?: string;
    checksumMd5?: string;
  };
}

/**
 * Logging queue item for async processing
 */
export interface LogQueueItem {
  id: string;
  timestamp: number;
  priority: 'low' | 'normal' | 'high' | 'urgent';
  retryCount: number;
  lastAttempt?: number;
  data: LogEntry;
  
  // Processing metadata
  processingTime?: number;
  error?: string;
  status: 'pending' | 'processing' | 'completed' | 'failed' | 'discarded';
}

/**
 * Logging statistics for monitoring
 */
export interface LoggingStats {
  timestamp: number;
  
  // Volume metrics
  totalRequests: number;
  totalLogs: number;
  totalBytes: number;
  
  // Performance metrics
  averageLatency: number;
  p95Latency: number;
  p99Latency: number;
  successRate: number;
  
  // Queue metrics
  queueSize: number;
  queueDepth: number;
  averageQueueTime: number;
  droppedLogs: number;
  
  // Error metrics
  errorRate: number;
  errorsByType: Record<string, number>;
  retryRate: number;
  
  // Backend metrics
  backendLatency: number;
  backendSuccessRate: number;
  backendErrorRate: number;
}

/**
 * Health check result for logging system
 */
export interface LoggingHealthCheck {
  healthy: boolean;
  timestamp: number;
  
  // Component health
  queue: {
    healthy: boolean;
    size: number;
    maxSize: number;
    oldestItem?: number;
  };
  
  backend: {
    healthy: boolean;
    latency?: number;
    lastSuccessful?: number;
    consecutiveFailures: number;
  };
  
  storage: {
    healthy: boolean;
    usage: number;
    maxUsage: number;
    fragmentationRate?: number;
  };
  
  // Overall metrics
  successRate: number;
  errorRate: number;
  averageLatency: number;
  
  // Issues and recommendations
  issues?: string[];
  recommendations?: string[];
}

/**
 * Log entry builder for fluent interface
 */
export interface LogEntryBuilder {
  setRequestId(requestId: string): LogEntryBuilder;
  setCompanyId(companyId: string): LogEntryBuilder;
  setRequest(request: RequestMetadata): LogEntryBuilder;
  setResponse(response: ResponseMetadata): LogEntryBuilder;
  setPerformance(performance: PerformanceMetrics): LogEntryBuilder;
  addError(error: ErrorLog): LogEntryBuilder;
  addWarning(warning: ErrorLog): LogEntryBuilder;
  setCost(cost: number): LogEntryBuilder;
  setMetadata(key: string, value: any): LogEntryBuilder;
  addFeature(feature: string): LogEntryBuilder;
  setExperiment(name: string, variant: string): LogEntryBuilder;
  build(): LogEntry;
}

/**
 * Event types for logging system notifications
 */
export enum LoggingEventType {
  LOG_CREATED = 'log_created',
  LOG_QUEUED = 'log_queued',
  LOG_SENT = 'log_sent',
  LOG_FAILED = 'log_failed',
  LOG_DROPPED = 'log_dropped',
  BATCH_CREATED = 'batch_created',
  BATCH_SENT = 'batch_sent',
  BATCH_FAILED = 'batch_failed',
  QUEUE_FULL = 'queue_full',
  BACKEND_DOWN = 'backend_down',
  BACKEND_RECOVERED = 'backend_recovered',
  HEALTH_CHECK = 'health_check',
}

/**
 * Logging event for system monitoring
 */
export interface LoggingEvent {
  type: LoggingEventType;
  timestamp: number;
  data?: any;
  metadata?: Record<string, any>;
}

/**
 * Async logging interface
 */
export interface AsyncLogger {
  log(entry: LogEntry): Promise<void>;
  logRequest(companyId: string, requestData: any, responseData: any): Promise<void>;
  logError(error: ErrorLog): Promise<void>;
  logPerformance(metrics: PerformanceMetrics): Promise<void>;
  flush(): Promise<void>;
  getStats(): LoggingStats;
  getHealth(): LoggingHealthCheck;
  configure(config: Partial<LoggingConfig>): void;
}
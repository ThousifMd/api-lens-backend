/**
 * API Lens JavaScript SDK - Custom Exceptions
 */

/**
 * Base exception for all API Lens errors
 */
export class APILensError extends Error {
  public readonly statusCode?: number;
  public readonly responseData?: Record<string, any>;
  public readonly requestId?: string;

  constructor(
    message: string,
    statusCode?: number,
    responseData?: Record<string, any>,
    requestId?: string
  ) {
    super(message);
    this.name = this.constructor.name;
    this.statusCode = statusCode;
    this.responseData = responseData || {};
    this.requestId = requestId;
    
    // Ensure the error is properly captured in stack traces
    if (Error.captureStackTrace) {
      Error.captureStackTrace(this, this.constructor);
    }
  }

  toString(): string {
    let message = this.message;
    if (this.statusCode) {
      message = `[${this.statusCode}] ${message}`;
    }
    if (this.requestId) {
      message = `${message} (Request ID: ${this.requestId})`;
    }
    return message;
  }
}

/**
 * Authentication failed - invalid or expired API key
 */
export class AuthenticationError extends APILensError {
  constructor(
    message: string = 'Authentication failed',
    statusCode?: number,
    responseData?: Record<string, any>,
    requestId?: string
  ) {
    super(message, statusCode, responseData, requestId);
  }
}

/**
 * Authorization failed - insufficient permissions
 */
export class AuthorizationError extends APILensError {
  constructor(
    message: string = 'Insufficient permissions',
    statusCode?: number,
    responseData?: Record<string, any>,
    requestId?: string
  ) {
    super(message, statusCode, responseData, requestId);
  }
}

/**
 * Request validation failed
 */
export class ValidationError extends APILensError {
  constructor(
    message: string = 'Request validation failed',
    statusCode?: number,
    responseData?: Record<string, any>,
    requestId?: string
  ) {
    super(message, statusCode, responseData, requestId);
  }

  /**
   * Get validation error details from response
   */
  get validationErrors(): Record<string, any> {
    return this.responseData?.detail || {};
  }
}

/**
 * Resource not found
 */
export class NotFoundError extends APILensError {
  constructor(
    message: string = 'Resource not found',
    statusCode?: number,
    responseData?: Record<string, any>,
    requestId?: string
  ) {
    super(message, statusCode, responseData, requestId);
  }
}

/**
 * Rate limit exceeded
 */
export class RateLimitError extends APILensError {
  public readonly retryAfter?: number;

  constructor(
    message: string = 'Rate limit exceeded',
    retryAfter?: number,
    statusCode?: number,
    responseData?: Record<string, any>,
    requestId?: string
  ) {
    super(message, statusCode, responseData, requestId);
    this.retryAfter = retryAfter;
  }

  static fromResponse(
    responseData: Record<string, any>,
    statusCode?: number,
    requestId?: string
  ): RateLimitError {
    const retryAfter = responseData.retry_after;
    const limitType = responseData.limit_type || 'requests';
    const currentUsage = responseData.current_usage || 0;
    const limit = responseData.limit || 0;

    let message = `Rate limit exceeded for ${limitType}: ${currentUsage}/${limit}`;
    if (retryAfter) {
      message += `. Retry after ${retryAfter} seconds`;
    }

    return new RateLimitError(message, retryAfter, statusCode, responseData, requestId);
  }
}

/**
 * Usage quota exceeded
 */
export class QuotaExceededError extends APILensError {
  public readonly quotaType?: string;
  public readonly currentUsage?: number;
  public readonly quotaLimit?: number;

  constructor(
    message: string = 'Usage quota exceeded',
    quotaType?: string,
    currentUsage?: number,
    quotaLimit?: number,
    statusCode?: number,
    responseData?: Record<string, any>,
    requestId?: string
  ) {
    super(message, statusCode, responseData, requestId);
    this.quotaType = quotaType;
    this.currentUsage = currentUsage;
    this.quotaLimit = quotaLimit;
  }

  static fromResponse(
    responseData: Record<string, any>,
    statusCode?: number,
    requestId?: string
  ): QuotaExceededError {
    const quotaType = responseData.quota_type || 'requests';
    const currentUsage = responseData.current_usage || 0;
    const quotaLimit = responseData.quota_limit || 0;

    const message = `Quota exceeded for ${quotaType}: ${currentUsage}/${quotaLimit}`;

    return new QuotaExceededError(
      message,
      quotaType,
      currentUsage,
      quotaLimit,
      statusCode,
      responseData,
      requestId
    );
  }
}

/**
 * Server-side error occurred
 */
export class ServerError extends APILensError {
  constructor(
    message: string = 'Internal server error',
    statusCode?: number,
    responseData?: Record<string, any>,
    requestId?: string
  ) {
    super(message, statusCode, responseData, requestId);
  }
}

/**
 * API Lens service is temporarily unavailable
 */
export class ServiceUnavailableError extends ServerError {
  constructor(
    message: string = 'Service temporarily unavailable',
    statusCode?: number,
    responseData?: Record<string, any>,
    requestId?: string
  ) {
    super(message, statusCode, responseData, requestId);
  }
}

/**
 * Error from AI vendor (OpenAI, Anthropic, etc.)
 */
export class VendorError extends APILensError {
  public readonly vendor?: string;
  public readonly vendorErrorCode?: string;
  public readonly vendorMessage?: string;

  constructor(
    message: string,
    vendor?: string,
    vendorErrorCode?: string,
    vendorMessage?: string,
    statusCode?: number,
    responseData?: Record<string, any>,
    requestId?: string
  ) {
    super(message, statusCode, responseData, requestId);
    this.vendor = vendor;
    this.vendorErrorCode = vendorErrorCode;
    this.vendorMessage = vendorMessage;
  }

  static fromResponse(
    responseData: Record<string, any>,
    statusCode?: number,
    requestId?: string
  ): VendorError {
    const vendor = responseData.vendor;
    const vendorError = responseData.vendor_error || {};
    const vendorErrorCode = vendorError.code;
    const vendorMessage = vendorError.message;

    const message = `Vendor error from ${vendor}: ${vendorMessage || 'Unknown error'}`;

    return new VendorError(
      message,
      vendor,
      vendorErrorCode,
      vendorMessage,
      statusCode,
      responseData,
      requestId
    );
  }
}

/**
 * Error related to vendor API keys (BYOK)
 */
export class VendorKeyError extends APILensError {
  public readonly vendor?: string;
  public readonly keyIssue?: string;

  constructor(
    message: string,
    vendor?: string,
    keyIssue?: string,
    statusCode?: number,
    responseData?: Record<string, any>,
    requestId?: string
  ) {
    super(message, statusCode, responseData, requestId);
    this.vendor = vendor;
    this.keyIssue = keyIssue;
  }
}

/**
 * Network connectivity error
 */
export class NetworkError extends APILensError {
  constructor(
    message: string = 'Network connection failed',
    statusCode?: number,
    responseData?: Record<string, any>,
    requestId?: string
  ) {
    super(message, statusCode, responseData, requestId);
  }
}

/**
 * Request timeout
 */
export class TimeoutError extends NetworkError {
  public readonly timeout?: number;

  constructor(
    message: string = 'Request timed out',
    timeout?: number,
    statusCode?: number,
    responseData?: Record<string, any>,
    requestId?: string
  ) {
    super(message, statusCode, responseData, requestId);
    this.timeout = timeout;
  }
}

/**
 * SDK configuration error
 */
export class ConfigurationError extends APILensError {
  constructor(
    message: string = 'SDK configuration error',
    statusCode?: number,
    responseData?: Record<string, any>,
    requestId?: string
  ) {
    super(message, statusCode, responseData, requestId);
  }
}

/**
 * Data export operation failed
 */
export class ExportError extends APILensError {
  public readonly exportType?: string;
  public readonly exportFormat?: string;

  constructor(
    message: string = 'Export operation failed',
    exportType?: string,
    exportFormat?: string,
    statusCode?: number,
    responseData?: Record<string, any>,
    requestId?: string
  ) {
    super(message, statusCode, responseData, requestId);
    this.exportType = exportType;
    this.exportFormat = exportFormat;
  }
}

/**
 * Exception mapping for HTTP status codes
 */
export const STATUS_CODE_TO_EXCEPTION: Record<number, typeof APILensError> = {
  400: ValidationError,
  401: AuthenticationError,
  403: AuthorizationError,
  404: NotFoundError,
  422: ValidationError,
  429: RateLimitError,
  500: ServerError,
  502: ServiceUnavailableError,
  503: ServiceUnavailableError,
  504: TimeoutError,
};

/**
 * Create appropriate exception from HTTP response
 */
export function createExceptionFromResponse(
  statusCode: number,
  responseData: Record<string, any>,
  defaultMessage: string = 'API request failed'
): APILensError {
  // Get error details from response
  const errorMessage = responseData.detail || responseData.message || defaultMessage;
  const errorCode = responseData.error_code;
  const requestId = responseData.request_id;

  // Handle specific error types
  if (statusCode === 429) {
    return RateLimitError.fromResponse(responseData, statusCode, requestId);
  }

  if (responseData.vendor_error) {
    return VendorError.fromResponse(responseData, statusCode, requestId);
  }

  if (responseData.quota_exceeded) {
    return QuotaExceededError.fromResponse(responseData, statusCode, requestId);
  }

  // Use status code mapping
  const ExceptionClass = STATUS_CODE_TO_EXCEPTION[statusCode] || APILensError;

  return new ExceptionClass(errorMessage, statusCode, responseData, requestId);
}

/**
 * Check if an error is retryable
 */
export function isRetryableError(error: Error): boolean {
  if (error instanceof NetworkError || error instanceof TimeoutError || error instanceof ServerError) {
    return true;
  }

  if (error instanceof RateLimitError) {
    return true;
  }

  if (error instanceof APILensError && error.statusCode) {
    // Retry on server errors and rate limits
    return error.statusCode >= 500 || error.statusCode === 429;
  }

  return false;
}

/**
 * Calculate retry delay for an exception
 */
export function getRetryDelay(error: Error, attempt: number, baseDelay: number = 1000): number {
  if (error instanceof RateLimitError && error.retryAfter) {
    return error.retryAfter * 1000; // Convert to milliseconds
  }

  // Exponential backoff with jitter
  const delay = baseDelay * Math.pow(2, attempt);
  const jitter = Math.random() * 0.3 * delay;
  return delay + jitter;
}
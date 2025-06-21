/**
 * API Lens JavaScript SDK - Main Client
 */

import axios, { AxiosInstance, AxiosRequestConfig, AxiosResponse } from 'axios';
import { APILensError, AuthenticationError, RateLimitError, ServerError, ValidationError, NotFoundError } from './exceptions';
import { 
  APILensClientConfig, 
  Company, 
  APIKey, 
  VendorKey,
  UsageAnalytics,
  CostAnalytics,
  PerformanceAnalytics,
  CostOptimizationRecommendation
} from './types';
import { APIKeyService } from './services/api-keys';
import { VendorKeyService } from './services/vendor-keys';
import { AnalyticsService } from './services/analytics';
import { OpenAIClient } from './vendors/openai';
import { AnthropicClient } from './vendors/anthropic';
import { GoogleClient } from './vendors/google';

/**
 * Main API Lens client for synchronous operations
 */
export class APILensClient {
  private readonly httpClient: AxiosInstance;
  private readonly config: Required<APILensClientConfig>;
  
  // Service clients
  public readonly apiKeys: APIKeyService;
  public readonly vendorKeys: VendorKeyService;
  public readonly analytics: AnalyticsService;
  
  // Vendor clients
  public readonly openai: OpenAIClient;
  public readonly anthropic: AnthropicClient;
  public readonly google: GoogleClient;

  constructor(config: APILensClientConfig) {
    // Set defaults
    this.config = {
      apiKey: config.apiKey || process.env.API_LENS_API_KEY || '',
      baseURL: config.baseURL || 'https://api.apilens.dev',
      timeout: config.timeout || 30000,
      maxRetries: config.maxRetries || 3,
      retryDelay: config.retryDelay || 1000,
      userAgent: config.userAgent || `apilens-javascript/1.0.0`,
      debug: config.debug || false,
      defaultHeaders: config.defaultHeaders || {},
    };

    if (!this.config.apiKey) {
      throw new APILensError('API key is required. Set API_LENS_API_KEY environment variable or pass apiKey in config.');
    }

    // Create HTTP client
    this.httpClient = axios.create({
      baseURL: this.config.baseURL,
      timeout: this.config.timeout,
      headers: {
        'Authorization': `Bearer ${this.config.apiKey}`,
        'Content-Type': 'application/json',
        'User-Agent': this.config.userAgent,
        ...this.config.defaultHeaders,
      },
    });

    // Add request interceptor for debugging
    if (this.config.debug) {
      this.httpClient.interceptors.request.use(
        (config) => {
          console.log('API Lens Request:', config.method?.toUpperCase(), config.url, config.data);
          return config;
        },
        (error) => {
          console.error('API Lens Request Error:', error);
          return Promise.reject(error);
        }
      );
    }

    // Add response interceptor for error handling
    this.httpClient.interceptors.response.use(
      (response) => {
        if (this.config.debug) {
          console.log('API Lens Response:', response.status, response.data);
        }
        return response;
      },
      (error) => {
        if (this.config.debug) {
          console.error('API Lens Response Error:', error.response?.status, error.response?.data);
        }
        throw this.handleResponseError(error);
      }
    );

    // Initialize service clients
    this.apiKeys = new APIKeyService(this);
    this.vendorKeys = new VendorKeyService(this);
    this.analytics = new AnalyticsService(this);
    
    // Initialize vendor clients
    this.openai = new OpenAIClient(this);
    this.anthropic = new AnthropicClient(this);
    this.google = new GoogleClient(this);
  }

  /**
   * Make HTTP request with retry logic
   */
  async request<T = any>(config: AxiosRequestConfig): Promise<T> {
    let lastError: Error;
    
    for (let attempt = 0; attempt <= this.config.maxRetries; attempt++) {
      try {
        const response: AxiosResponse<T> = await this.httpClient.request(config);
        return response.data;
      } catch (error) {
        lastError = error as Error;
        
        // Don't retry on certain errors
        if (error instanceof AuthenticationError || 
            error instanceof ValidationError || 
            error instanceof NotFoundError) {
          throw error;
        }
        
        // Don't retry on last attempt
        if (attempt === this.config.maxRetries) {
          break;
        }
        
        // Calculate retry delay with exponential backoff
        const delay = this.config.retryDelay * Math.pow(2, attempt);
        await new Promise(resolve => setTimeout(resolve, delay));
      }
    }
    
    throw lastError!;
  }

  /**
   * Handle response errors and convert to appropriate exceptions
   */
  private handleResponseError(error: any): APILensError {
    if (!error.response) {
      return new APILensError(`Network error: ${error.message}`);
    }

    const { status, data } = error.response;
    const message = data?.detail || data?.message || `HTTP ${status} error`;
    const requestId = data?.request_id;

    switch (status) {
      case 401:
        return new AuthenticationError(message, status, data, requestId);
      case 403:
        return new AuthenticationError(message, status, data, requestId);
      case 404:
        return new NotFoundError(message, status, data, requestId);
      case 422:
        return new ValidationError(message, status, data, requestId);
      case 429:
        const retryAfter = error.response.headers['retry-after'];
        return new RateLimitError(message, retryAfter, status, data, requestId);
      case 500:
      case 502:
      case 503:
      case 504:
        return new ServerError(message, status, data, requestId);
      default:
        return new APILensError(message, status, data, requestId);
    }
  }

  /**
   * Get current company information
   */
  async getCompany(): Promise<Company> {
    return this.request<Company>({
      method: 'GET',
      url: '/companies/me',
    });
  }

  /**
   * Update company profile
   */
  async updateCompany(updates: Partial<Company>): Promise<Company> {
    return this.request<Company>({
      method: 'PUT',
      url: '/companies/me',
      data: updates,
    });
  }

  /**
   * Build full URL from path
   */
  buildUrl(path: string): string {
    return `${this.config.baseURL}${path.startsWith('/') ? path : '/' + path}`;
  }

  /**
   * Get HTTP client instance (for advanced usage)
   */
  getHttpClient(): AxiosInstance {
    return this.httpClient;
  }

  /**
   * Get client configuration
   */
  getConfig(): Required<APILensClientConfig> {
    return { ...this.config };
  }
}
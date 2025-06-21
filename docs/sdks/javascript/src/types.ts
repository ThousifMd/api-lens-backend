/**
 * API Lens JavaScript SDK - Type Definitions
 */

/**
 * Client configuration options
 */
export interface APILensClientConfig {
  /** API Lens API key */
  apiKey?: string;
  /** Base URL for API Lens */
  baseURL?: string;
  /** Request timeout in milliseconds */
  timeout?: number;
  /** Maximum number of retry attempts */
  maxRetries?: number;
  /** Delay between retries in milliseconds */
  retryDelay?: number;
  /** Custom User-Agent string */
  userAgent?: string;
  /** Enable debug logging */
  debug?: boolean;
  /** Additional default headers */
  defaultHeaders?: Record<string, string>;
}

/**
 * Company subscription tiers
 */
export enum CompanyTier {
  FREE = 'free',
  STARTER = 'starter',
  PROFESSIONAL = 'professional',
  ENTERPRISE = 'enterprise',
}

/**
 * Supported AI vendors
 */
export enum VendorType {
  OPENAI = 'openai',
  ANTHROPIC = 'anthropic',
  GOOGLE = 'google',
  COHERE = 'cohere',
  HUGGINGFACE = 'huggingface',
}

/**
 * Company profile
 */
export interface Company {
  id: string;
  name: string;
  description?: string;
  tier: CompanyTier;
  isActive: boolean;
  contactEmail?: string;
  webhookUrl?: string;
  currentMonthRequests: number;
  currentMonthCost: number;
  monthlyBudgetLimit?: number;
  monthlyRequestLimit?: number;
  createdAt: string;
  updatedAt: string;
}

/**
 * API key
 */
export interface APIKey {
  id: string;
  name: string;
  secretKey?: string; // Only included when first created
  keyPreview: string; // First 8 and last 4 characters
  isActive: boolean;
  lastUsedAt?: string;
  usageCount: number;
  createdAt: string;
  expiresAt?: string;
}

/**
 * Vendor API key (BYOK)
 */
export interface VendorKey {
  vendor: VendorType;
  keyPreview: string; // Encrypted key preview
  description?: string;
  isActive: boolean;
  createdAt: string;
  updatedAt: string;
  lastUsedAt?: string;
  usageCount: number;
}

/**
 * Usage metrics for a specific period
 */
export interface UsageMetrics {
  requests: number;
  tokens: number;
  cost: number;
}

/**
 * Usage breakdown by vendor
 */
export interface VendorBreakdown {
  vendor: VendorType;
  requests: number;
  tokens: number;
  cost: number;
  models: Array<{
    model: string;
    requests: number;
    tokens: number;
    cost: number;
  }>;
}

/**
 * Usage breakdown by AI model
 */
export interface ModelBreakdown {
  vendor: VendorType;
  model: string;
  requests: number;
  inputTokens: number;
  outputTokens: number;
  totalTokens: number;
  cost: number;
  averageCostPerRequest: number;
}

/**
 * Time series data point
 */
export interface TimeSeriesPoint {
  timestamp: string;
  requests: number;
  tokens: number;
  cost: number;
}

/**
 * Comprehensive usage analytics
 */
export interface UsageAnalytics {
  period: string;
  startDate: string;
  endDate: string;
  totalRequests: number;
  totalTokens: number;
  totalCost: number;
  averageRequestsPerDay: number;
  averageCostPerRequest: number;
  peakRequestsPerHour: number;
  vendorBreakdown: VendorBreakdown[];
  modelBreakdown: ModelBreakdown[];
  timeSeries: TimeSeriesPoint[];
}

/**
 * Cost breakdown by vendor or model
 */
export interface CostBreakdown {
  vendor: VendorType;
  model?: string;
  totalCost: number;
  costPercentage: number;
  requests: number;
  costPerRequest: number;
  costPerToken: number;
}

/**
 * Cost trend analysis
 */
export interface CostTrend {
  currentPeriodCost: number;
  previousPeriodCost: number;
  costChange: number;
  costChangePercentage: number;
  trendDirection: 'up' | 'down' | 'stable';
}

/**
 * Comprehensive cost analytics
 */
export interface CostAnalytics {
  period: string;
  startDate: string;
  endDate: string;
  totalCost: number;
  averageCostPerRequest: number;
  costTrendPercentage: number;
  projectedMonthlyCost: number;
  costEfficiencyScore: number;
  vendorCosts: CostBreakdown[];
  modelCosts: CostBreakdown[];
  costTrend: CostTrend;
  dailyCosts: TimeSeriesPoint[];
}

/**
 * Performance metrics by vendor
 */
export interface VendorPerformance {
  vendor: VendorType;
  avgLatencyMs: number;
  p95LatencyMs: number;
  p99LatencyMs: number;
  successRatePercentage: number;
  errorRatePercentage: number;
  requests: number;
}

/**
 * Comprehensive performance analytics
 */
export interface PerformanceAnalytics {
  period: string;
  startDate: string;
  endDate: string;
  totalRequests: number;
  successfulRequests: number;
  failedRequests: number;
  averageLatencyMs: number;
  p95LatencyMs: number;
  p99LatencyMs: number;
  successRatePercentage: number;
  errorRatePercentage: number;
  vendorPerformance: VendorPerformance[];
  latencyTrend: TimeSeriesPoint[];
}

/**
 * Individual cost optimization recommendation
 */
export interface OptimizationRecommendation {
  id: string;
  title: string;
  description: string;
  category: string; // model_optimization, usage_pattern, cost_reduction
  impactLevel: string; // high, medium, low
  potentialSavings: number;
  savingsPercentage: number;
  confidenceScore: number;
  implementationEffort: string; // easy, medium, hard
  actionableSteps: string[];
  affectedVendors: VendorType[];
  affectedModels: string[];
  createdAt: string;
}

/**
 * Complete cost optimization analysis
 */
export interface CostOptimizationRecommendation {
  totalPotentialSavings: number;
  totalSavingsPercentage: number;
  recommendations: OptimizationRecommendation[];
  analysisDate: string;
  periodAnalyzed: string;
}

/**
 * Data export request
 */
export interface ExportRequest {
  exportType: string; // usage, costs, performance, recommendations
  format?: string; // json, csv, excel
  dateRange: {
    period?: string;
    startDate?: string;
    endDate?: string;
  };
  filters?: Record<string, any>;
  includeRawData?: boolean;
}

/**
 * System health status
 */
export interface SystemHealth {
  status: string; // healthy, degraded, down
  version: string;
  uptimeSeconds: number;
  databaseStatus: string;
  redisStatus: string;
  vendorApiStatus: Record<string, string>;
  responseTimeMs: number;
  activeCompanies: number;
  totalRequests24h: number;
  errorRate24h: number;
}

/**
 * Rate limit information
 */
export interface RateLimit {
  requestsPerMinute: number;
  requestsPerHour: number;
  requestsPerDay: number;
  currentUsage: Record<string, number>;
  resetTimes: Record<string, string>;
}

/**
 * Authentication information
 */
export interface AuthInfo {
  valid: boolean;
  companyId: string;
  companyName: string;
  tier: CompanyTier;
  rateLimits: RateLimit;
  expiresAt?: string;
}

/**
 * API error detail
 */
export interface ErrorDetail {
  error: string;
  errorCode: string;
  message: string;
  details?: Record<string, any>;
  requestId?: string;
  timestamp: string;
}

/**
 * Paginated API response
 */
export interface PaginatedResponse<T> {
  items: T[];
  total: number;
  page: number;
  perPage: number;
  totalPages: number;
  hasNext: boolean;
  hasPrev: boolean;
}

/**
 * OpenAI Chat Completion Message
 */
export interface ChatMessage {
  role: 'system' | 'user' | 'assistant';
  content: string;
  name?: string;
}

/**
 * OpenAI Chat Completion Request
 */
export interface ChatCompletionRequest {
  model: string;
  messages: ChatMessage[];
  maxTokens?: number;
  temperature?: number;
  topP?: number;
  frequencyPenalty?: number;
  presencePenalty?: number;
  stop?: string | string[];
  stream?: boolean;
  [key: string]: any;
}

/**
 * OpenAI Chat Completion Response
 */
export interface ChatCompletionResponse {
  id: string;
  object: 'chat.completion';
  created: number;
  model: string;
  choices: Array<{
    index: number;
    message: ChatMessage;
    finishReason: string;
  }>;
  usage: {
    promptTokens: number;
    completionTokens: number;
    totalTokens: number;
  };
}

/**
 * Anthropic Message Request
 */
export interface AnthropicMessageRequest {
  model: string;
  messages: Array<{
    role: 'user' | 'assistant';
    content: string;
  }>;
  maxTokens: number;
  temperature?: number;
  topP?: number;
  stopSequences?: string[];
  stream?: boolean;
  [key: string]: any;
}

/**
 * Anthropic Message Response
 */
export interface AnthropicMessageResponse {
  id: string;
  type: 'message';
  role: 'assistant';
  content: Array<{
    type: 'text';
    text: string;
  }>;
  model: string;
  stopReason: string;
  stopSequence?: string;
  usage: {
    inputTokens: number;
    outputTokens: number;
  };
}

/**
 * Google AI Generate Content Request
 */
export interface GoogleGenerateContentRequest {
  contents: Array<{
    parts: Array<{
      text: string;
    }>;
    role?: string;
  }>;
  generationConfig?: {
    temperature?: number;
    topP?: number;
    topK?: number;
    maxOutputTokens?: number;
    stopSequences?: string[];
  };
  safetySettings?: Array<{
    category: string;
    threshold: string;
  }>;
}

/**
 * Google AI Generate Content Response
 */
export interface GoogleGenerateContentResponse {
  candidates: Array<{
    content: {
      parts: Array<{
        text: string;
      }>;
      role: string;
    };
    finishReason: string;
    safetyRatings: Array<{
      category: string;
      probability: string;
    }>;
  }>;
  usageMetadata: {
    promptTokenCount: number;
    candidatesTokenCount: number;
    totalTokenCount: number;
  };
}
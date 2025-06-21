/**
 * API Lens Workers Proxy - Cost Calculation Types
 * 
 * Type definitions for cost calculation and tracking system
 */

export interface CostCalculation {
  inputCost: number;
  outputCost: number;
  totalCost: number;
  currency: string;
  vendor: string;
  model: string;
  timestamp: number;
  breakdown: CostBreakdown;
}

export interface CostBreakdown {
  inputTokens: number;
  outputTokens: number;
  inputRate: number;
  outputRate: number;
  baseRate?: number;
  multiplier?: number;
  discountApplied?: number;
}

export interface UsageData {
  inputTokens: number;
  outputTokens: number;
  totalTokens: number;
  model: string;
  finishReason?: string;
  requestId?: string;
  processingTime?: number;
}

export interface CostQuota {
  daily: number;
  monthly: number;
  yearly?: number;
  alertThresholds: {
    warning: number; // percentage (e.g., 80)
    critical: number; // percentage (e.g., 95)
  };
}

export interface CostUsage {
  current: {
    hourly: number;
    daily: number;
    monthly: number;
    yearly: number;
  };
  period: {
    startDate: string;
    endDate: string;
    timezone: string;
  };
  limits: CostQuota;
  projections: {
    dailyProjection: number;
    monthlyProjection: number;
  };
}

export interface CostMetrics {
  totalRequests: number;
  totalCost: number;
  averageCostPerRequest: number;
  averageCostPerToken: number;
  costByVendor: Record<string, number>;
  costByModel: Record<string, number>;
  costTrends: {
    hourly: number[];
    daily: number[];
    monthly: number[];
  };
}

export interface CostAlert {
  type: 'warning' | 'critical' | 'quota_exceeded';
  threshold: number;
  currentUsage: number;
  quotaLimit: number;
  period: 'hourly' | 'daily' | 'monthly';
  timestamp: string;
  companyId: string;
  message: string;
}

export interface CostTrackingConfig {
  enableRealTimeTracking: boolean;
  trackingGranularity: 'minute' | 'hour' | 'day';
  retentionPeriod: number; // days
  alertsEnabled: boolean;
  currency: string;
  timezone: string;
  roundingPrecision: number; // decimal places
}

export interface VendorPricing {
  vendor: string;
  model: string;
  pricing: {
    inputCostPer1kTokens: number;
    outputCostPer1kTokens: number;
    minimumCost?: number;
    currency: string;
    effectiveDate: string;
    deprecated?: boolean;
  };
  features?: {
    contextLength: number;
    supportedFeatures: string[];
    rateLimits?: {
      requestsPerMinute: number;
      tokensPerMinute: number;
    };
  };
}

export interface CostEstimate {
  estimatedInputTokens: number;
  estimatedOutputTokens: number;
  estimatedInputCost: number;
  estimatedOutputCost: number;
  estimatedTotalCost: number;
  confidence: number; // 0-1
  model: string;
  vendor: string;
}

export interface CostSummary {
  period: 'hour' | 'day' | 'month' | 'year';
  startDate: string;
  endDate: string;
  totalCost: number;
  totalRequests: number;
  totalTokens: number;
  averageCostPerRequest: number;
  averageCostPerToken: number;
  breakdown: {
    byVendor: Record<string, CostBreakdown>;
    byModel: Record<string, CostBreakdown>;
    byHour?: Record<string, number>;
    byDay?: Record<string, number>;
  };
}

export interface RealTimeCostData {
  companyId: string;
  currentHour: number;
  currentDay: number;
  currentMonth: number;
  lastUpdated: number;
  requestCount: number;
  tokenCount: number;
  recentCosts: Array<{
    timestamp: number;
    cost: number;
    vendor: string;
    model: string;
  }>;
}

export interface CostOptimization {
  recommendations: Array<{
    type: 'model_switch' | 'vendor_switch' | 'usage_reduction';
    currentModel: string;
    recommendedModel: string;
    potentialSavings: number;
    impactRating: 'low' | 'medium' | 'high';
    description: string;
  }>;
  efficientModels: Array<{
    model: string;
    vendor: string;
    costEfficiencyScore: number;
    useCases: string[];
  }>;
  budgetProjections: {
    currentTrend: number;
    optimizedProjection: number;
    savingsPotential: number;
  };
}

export enum CostPeriod {
  HOUR = 'hour',
  DAY = 'day',
  MONTH = 'month',
  YEAR = 'year',
}

export enum CostAlertType {
  WARNING = 'warning',
  CRITICAL = 'critical',
  QUOTA_EXCEEDED = 'quota_exceeded',
  BUDGET_EXCEEDED = 'budget_exceeded',
}

export interface CostHeaders {
  'X-Cost-Input': string;
  'X-Cost-Output': string;
  'X-Cost-Total': string;
  'X-Cost-Currency': string;
  'X-Cost-Monthly-Total': string;
  'X-Cost-Monthly-Limit'?: string;
  'X-Cost-Monthly-Remaining'?: string;
  'X-Cost-Daily-Total': string;
  'X-Cost-Tokens-Input': string;
  'X-Cost-Tokens-Output': string;
  'X-Cost-Rate-Input': string;
  'X-Cost-Rate-Output': string;
}
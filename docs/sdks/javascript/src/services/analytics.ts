/**
 * API Lens JavaScript SDK - Analytics Service
 */

import { APILensClient } from '../client';
import { 
  UsageAnalytics, 
  CostAnalytics, 
  PerformanceAnalytics, 
  CostOptimizationRecommendation,
  VendorType,
  ExportRequest
} from '../types';

/**
 * Analytics query parameters
 */
export interface AnalyticsParams {
  period?: string;
  startDate?: string;
  endDate?: string;
  vendors?: VendorType[] | string[];
  models?: string[];
  groupBy?: string;
}

/**
 * Analytics and reporting service
 */
export class AnalyticsService {
  constructor(private client: APILensClient) {}

  /**
   * Get usage analytics
   */
  async getUsage(params: AnalyticsParams = {}): Promise<UsageAnalytics> {
    const queryParams: Record<string, string> = {};

    if (params.period) queryParams.period = params.period;
    if (params.startDate) queryParams.start_date = params.startDate;
    if (params.endDate) queryParams.end_date = params.endDate;
    if (params.vendors) queryParams.vendors = Array.isArray(params.vendors) ? params.vendors.join(',') : params.vendors;
    if (params.models) queryParams.models = params.models.join(',');
    if (params.groupBy) queryParams.group_by = params.groupBy;

    return this.client.request<UsageAnalytics>({
      method: 'GET',
      url: '/companies/me/analytics/usage',
      params: queryParams,
    });
  }

  /**
   * Get cost analytics
   */
  async getCosts(params: AnalyticsParams = {}): Promise<CostAnalytics> {
    const queryParams: Record<string, string> = {};

    if (params.period) queryParams.period = params.period;
    if (params.startDate) queryParams.start_date = params.startDate;
    if (params.endDate) queryParams.end_date = params.endDate;
    if (params.vendors) queryParams.vendors = Array.isArray(params.vendors) ? params.vendors.join(',') : params.vendors;
    if (params.models) queryParams.models = params.models.join(',');
    if (params.groupBy) queryParams.group_by = params.groupBy;

    return this.client.request<CostAnalytics>({
      method: 'GET',
      url: '/companies/me/analytics/costs',
      params: queryParams,
    });
  }

  /**
   * Get performance analytics
   */
  async getPerformance(params: AnalyticsParams = {}): Promise<PerformanceAnalytics> {
    const queryParams: Record<string, string> = {};

    if (params.period) queryParams.period = params.period;
    if (params.startDate) queryParams.start_date = params.startDate;
    if (params.endDate) queryParams.end_date = params.endDate;
    if (params.vendors) queryParams.vendors = Array.isArray(params.vendors) ? params.vendors.join(',') : params.vendors;
    if (params.models) queryParams.models = params.models.join(',');

    return this.client.request<PerformanceAnalytics>({
      method: 'GET',
      url: '/companies/me/analytics/performance',
      params: queryParams,
    });
  }

  /**
   * Get cost optimization recommendations
   */
  async getRecommendations(minSavings: number = 10.0): Promise<CostOptimizationRecommendation> {
    return this.client.request<CostOptimizationRecommendation>({
      method: 'GET',
      url: '/companies/me/analytics/recommendations',
      params: { min_savings: minSavings.toString() },
    });
  }

  /**
   * Export analytics data
   */
  async export(exportRequest: ExportRequest): Promise<string> {
    const payload = {
      export_type: exportRequest.exportType,
      format: exportRequest.format || 'json',
      date_range: exportRequest.dateRange,
      ...exportRequest.filters,
    };

    if (exportRequest.includeRawData !== undefined) {
      payload.include_raw_data = exportRequest.includeRawData;
    }

    // Make request directly to get raw response
    const response = await this.client.getHttpClient().post(
      '/companies/me/analytics/export',
      payload
    );

    if (response.status === 200) {
      return response.data;
    } else {
      throw new Error(`Export failed with status ${response.status}`);
    }
  }

  /**
   * Get usage summary for dashboard
   */
  async getSummary(period: string = '7d'): Promise<{
    usage: UsageAnalytics;
    costs: CostAnalytics;
    performance: PerformanceAnalytics;
  }> {
    const [usage, costs, performance] = await Promise.all([
      this.getUsage({ period }),
      this.getCosts({ period }),
      this.getPerformance({ period }),
    ]);

    return { usage, costs, performance };
  }

  /**
   * Get real-time metrics
   */
  async getRealTimeMetrics(): Promise<{
    requestsLastHour: number;
    costLastHour: number;
    averageLatency: number;
    errorRate: number;
  }> {
    return this.client.request<{
      requestsLastHour: number;
      costLastHour: number;
      averageLatency: number;
      errorRate: number;
    }>({
      method: 'GET',
      url: '/companies/me/analytics/realtime',
    });
  }

  /**
   * Get vendor comparison
   */
  async getVendorComparison(params: AnalyticsParams = {}): Promise<{
    vendors: Array<{
      vendor: VendorType;
      requests: number;
      cost: number;
      averageLatency: number;
      successRate: number;
      costPerRequest: number;
    }>;
  }> {
    const queryParams: Record<string, string> = {};

    if (params.period) queryParams.period = params.period;
    if (params.startDate) queryParams.start_date = params.startDate;
    if (params.endDate) queryParams.end_date = params.endDate;

    return this.client.request({
      method: 'GET',
      url: '/companies/me/analytics/vendor-comparison',
      params: queryParams,
    });
  }

  /**
   * Get model comparison
   */
  async getModelComparison(params: AnalyticsParams = {}): Promise<{
    models: Array<{
      vendor: VendorType;
      model: string;
      requests: number;
      cost: number;
      averageLatency: number;
      costPerToken: number;
      efficiency: number;
    }>;
  }> {
    const queryParams: Record<string, string> = {};

    if (params.period) queryParams.period = params.period;
    if (params.startDate) queryParams.start_date = params.startDate;
    if (params.endDate) queryParams.end_date = params.endDate;
    if (params.vendors) queryParams.vendors = Array.isArray(params.vendors) ? params.vendors.join(',') : params.vendors;

    return this.client.request({
      method: 'GET',
      url: '/companies/me/analytics/model-comparison',
      params: queryParams,
    });
  }
}
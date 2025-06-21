/**
 * API Lens Workers Proxy - Cost Calculation Module
 * 
 * Main exports for the cost calculation and tracking system
 */

// Export main service class
export { CostService } from './service';

// Export core functions
export {
  calculateRequestCost,
  calculateDetailedCost,
  updateRealTimeCost,
  checkCostQuota,
  getCostHeaders,
  estimateRequestCost,
  formatCost,
  getCostEfficiencyScore,
} from './functions';

// Export pricing utilities
export {
  getModelPricing,
  getVendorPricing,
  getAvailableVendors,
  getPricingSummary,
  findCheapestModel,
  resolveModelName,
  VENDOR_PRICING,
  MODEL_ALIASES,
} from './pricing';

// Export types
export type {
  CostCalculation,
  CostBreakdown,
  UsageData,
  CostQuota,
  CostUsage,
  CostHeaders,
  CostMetrics,
  CostSummary,
  CostAlert,
  CostEstimate,
  CostOptimization,
  VendorPricing,
  RealTimeCostData,
  CostTrackingConfig,
} from './types';

export {
  CostPeriod,
  CostAlertType,
} from './types';

/**
 * Create cost tracking middleware
 */
export function createCostTrackingMiddleware() {
  return async function costTrackingMiddleware(c: any, next: any) {
    const costService = new CostService(c.env);
    
    // Store cost service in context
    c.set('costService', costService);
    
    // Continue to next middleware
    await next();
    
    // After request completion, process cost if usage data is available
    const usage = c.get('usage');
    const vendor = c.get('vendor');
    const model = c.get('model');
    
    if (usage && vendor && model) {
      try {
        const costResult = await costService.processRequestCost(
          c,
          vendor,
          model,
          usage,
          false // Don't pre-check since request is already completed
        );
        
        // Add cost headers to response
        for (const [key, value] of costResult.headers.entries()) {
          c.header(key, value);
        }
        
        // Store cost in context for logging
        c.set('requestCost', costResult.cost.totalCost);
        c.set('costBreakdown', costResult.cost);
        
      } catch (error) {
        console.error('Cost tracking middleware error:', error);
        // Don't fail the request due to cost tracking issues
      }
    }
  };
}

/**
 * Create cost quota enforcement middleware
 */
export function createCostQuotaMiddleware() {
  return async function costQuotaMiddleware(c: any, next: any) {
    try {
      const costService = new CostService(c.env);
      const authResult = c.get('auth');
      const estimatedCost = c.get('estimatedCost') || 0;
      
      if (authResult && estimatedCost > 0) {
        const companyId = authResult.company.id;
        const withinQuota = await costService.checkQuota(companyId, estimatedCost);
        
        if (!withinQuota) {
          const usage = await costService.getCurrentUsage(companyId);
          const quotas = await costService.getCompanyQuotas(companyId);
          
          return c.json({
            error: 'Cost Quota Exceeded',
            message: 'Request would exceed your cost quota limits',
            code: 'cost_quota_exceeded',
            current_usage: {
              daily: usage.current.daily,
              monthly: usage.current.monthly,
            },
            limits: quotas ? {
              daily: quotas.daily,
              monthly: quotas.monthly,
            } : null,
            estimated_cost: estimatedCost,
            timestamp: new Date().toISOString(),
          }, 429, {
            'X-Cost-Quota-Exceeded': 'true',
            'X-Cost-Monthly-Usage': usage.current.monthly.toFixed(6),
            'X-Cost-Monthly-Limit': quotas?.monthly?.toFixed(2) || '0',
          });
        }
      }
      
      await next();
      
    } catch (error) {
      console.error('Cost quota middleware error:', error);
      // Allow request to proceed on quota check error
      await next();
    }
  };
}

/**
 * Create cost estimation middleware
 */
export function createCostEstimationMiddleware() {
  return async function costEstimationMiddleware(c: any, next: any) {
    try {
      const body = c.get('requestBody') || await c.req.json().catch(() => ({}));
      const model = body.model || c.get('model');
      const vendor = c.get('vendor') || 'openai'; // Default vendor
      
      if (model && body.messages) {
        const costService = new CostService(c.env);
        
        // Estimate input text length
        const inputText = body.messages
          .map((msg: any) => msg.content || '')
          .join(' ');
        
        const estimate = costService.estimateCost(vendor, model, inputText);
        
        // Store estimate in context
        c.set('estimatedCost', estimate.estimatedTotalCost);
        c.set('costEstimate', estimate);
        
        // Add estimation headers
        c.header('X-Cost-Estimate-Input', estimate.estimatedInputCost.toFixed(6));
        c.header('X-Cost-Estimate-Output', estimate.estimatedOutputCost.toFixed(6));
        c.header('X-Cost-Estimate-Total', estimate.estimatedTotalCost.toFixed(6));
        c.header('X-Cost-Estimate-Confidence', estimate.confidence.toFixed(2));
      }
      
      await next();
      
    } catch (error) {
      console.error('Cost estimation middleware error:', error);
      await next();
    }
  };
}

/**
 * Utility function to get cost summary for a company
 */
export async function getCostSummary(
  companyId: string,
  period: 'hour' | 'day' | 'month' | 'year',
  env: any,
  startDate?: string,
  endDate?: string
) {
  const costService = new CostService(env);
  return costService.getCostSummary(companyId, period, startDate, endDate);
}

/**
 * Utility function to get cost optimization recommendations
 */
export async function getCostOptimization(companyId: string, env: any) {
  const costService = new CostService(env);
  const metrics = await costService.getCostMetrics(companyId);
  return costService.getCostOptimization(metrics);
}

/**
 * Utility function to create cost response headers
 */
export function createCostHeaders(
  costCalculation: CostCalculation,
  monthlyTotal: number,
  quotas?: CostQuota
): Record<string, string> {
  const headers = getCostHeaders(
    costCalculation.totalCost,
    monthlyTotal,
    costCalculation,
    quotas
  );
  
  // Convert Headers object to plain object
  const headerObj: Record<string, string> = {};
  for (const [key, value] of headers.entries()) {
    headerObj[key] = value;
  }
  
  return headerObj;
}

/**
 * Middleware to add cost analytics endpoint
 */
export function createCostAnalyticsEndpoint() {
  return async function costAnalyticsEndpoint(c: any) {
    try {
      const authResult = c.get('auth');
      if (!authResult) {
        return c.json({ error: 'Authentication required' }, 401);
      }
      
      const companyId = authResult.company.id;
      const costService = new CostService(c.env);
      
      // Get query parameters
      const period = c.req.query('period') || 'month';
      const startDate = c.req.query('start');
      const endDate = c.req.query('end');
      
      // Get cost data
      const [summary, metrics, usage, optimization] = await Promise.all([
        costService.getCostSummary(companyId, period as any, startDate, endDate),
        costService.getCostMetrics(companyId),
        costService.getCurrentUsage(companyId),
        costService.getCostOptimization(await costService.getCostMetrics(companyId)),
      ]);
      
      return c.json({
        summary,
        metrics,
        current_usage: usage,
        optimization,
        timestamp: new Date().toISOString(),
      });
      
    } catch (error) {
      console.error('Cost analytics endpoint error:', error);
      return c.json({
        error: 'Cost Analytics Error',
        message: error instanceof Error ? error.message : 'Unknown error',
      }, 500);
    }
  };
}

// Legacy compatibility exports
export { calculateCost } from './functions';
export type { CostCalculation as Cost } from './types';
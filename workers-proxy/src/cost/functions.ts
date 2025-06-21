/**
 * API Lens Workers Proxy - Cost Calculation Functions
 * 
 * Core cost calculation functions as specified in Phase 6.5.1
 */

import {
  CostCalculation,
  CostBreakdown,
  UsageData,
  CostQuota,
  CostUsage,
  CostHeaders,
  RealTimeCostData,
  CostEstimate,
} from './types';
import {
  getModelPricing,
  resolveModelName,
  VendorPricing,
} from './pricing';
import { Env } from '../index';

/**
 * Calculate request cost based on vendor, model, and usage data
 * 
 * @param vendor - The vendor name (e.g., 'openai', 'anthropic')
 * @param model - The model name
 * @param usage - Usage data containing token counts
 * @returns Calculated cost in USD
 */
export function calculateRequestCost(
  vendor: string,
  model: string,
  usage: UsageData
): number {
  const resolvedModel = resolveModelName(model);
  const pricing = getModelPricing(vendor, resolvedModel);
  
  if (!pricing) {
    console.warn(`No pricing found for ${vendor}/${model}, returning 0 cost`);
    return 0;
  }
  
  const inputCost = (usage.inputTokens / 1000) * pricing.pricing.inputCostPer1kTokens;
  const outputCost = (usage.outputTokens / 1000) * pricing.pricing.outputCostPer1kTokens;
  const totalCost = inputCost + outputCost;
  
  // Apply minimum cost if specified
  const finalCost = pricing.pricing.minimumCost 
    ? Math.max(totalCost, pricing.pricing.minimumCost)
    : totalCost;
  
  return Math.round(finalCost * 1000000) / 1000000; // Round to 6 decimal places
}

/**
 * Calculate detailed cost breakdown
 */
export function calculateDetailedCost(
  vendor: string,
  model: string,
  usage: UsageData
): CostCalculation {
  const resolvedModel = resolveModelName(model);
  const pricing = getModelPricing(vendor, resolvedModel);
  
  if (!pricing) {
    return {
      inputCost: 0,
      outputCost: 0,
      totalCost: 0,
      currency: 'USD',
      vendor,
      model,
      timestamp: Date.now(),
      breakdown: {
        inputTokens: usage.inputTokens,
        outputTokens: usage.outputTokens,
        inputRate: 0,
        outputRate: 0,
      },
    };
  }
  
  const inputCost = (usage.inputTokens / 1000) * pricing.pricing.inputCostPer1kTokens;
  const outputCost = (usage.outputTokens / 1000) * pricing.pricing.outputCostPer1kTokens;
  const totalCost = inputCost + outputCost;
  
  const breakdown: CostBreakdown = {
    inputTokens: usage.inputTokens,
    outputTokens: usage.outputTokens,
    inputRate: pricing.pricing.inputCostPer1kTokens,
    outputRate: pricing.pricing.outputCostPer1kTokens,
  };
  
  return {
    inputCost: Math.round(inputCost * 1000000) / 1000000,
    outputCost: Math.round(outputCost * 1000000) / 1000000,
    totalCost: Math.round(totalCost * 1000000) / 1000000,
    currency: pricing.pricing.currency,
    vendor,
    model: resolvedModel,
    timestamp: Date.now(),
    breakdown,
  };
}

/**
 * Update real-time cost counters in Redis
 * 
 * @param companyId - The company ID
 * @param cost - The cost to add
 * @param env - Environment bindings
 */
export async function updateRealTimeCost(
  companyId: string,
  cost: number,
  env: Env
): Promise<void> {
  const now = new Date();
  const hourKey = `cost:${companyId}:hour:${now.getUTCFullYear()}-${String(now.getUTCMonth() + 1).padStart(2, '0')}-${String(now.getUTCDate()).padStart(2, '0')}-${String(now.getUTCHours()).padStart(2, '0')}`;
  const dayKey = `cost:${companyId}:day:${now.getUTCFullYear()}-${String(now.getUTCMonth() + 1).padStart(2, '0')}-${String(now.getUTCDate()).padStart(2, '0')}`;
  const monthKey = `cost:${companyId}:month:${now.getUTCFullYear()}-${String(now.getUTCMonth() + 1).padStart(2, '0')}`;
  
  try {
    // Try Redis first
    if (env.REDIS_URL && env.REDIS_TOKEN) {
      await updateCostInRedis([hourKey, dayKey, monthKey], cost, env);
    } else {
      // Fallback to KV
      await updateCostInKV([hourKey, dayKey, monthKey], cost, env);
    }
    
    // Also update backend (fire and forget)
    updateCostInBackend(companyId, cost, env).catch(err => {
      console.error('Failed to update cost in backend:', err);
    });
    
  } catch (error) {
    console.error('Failed to update real-time cost:', error);
    // Don't throw - cost tracking failure shouldn't break the request
  }
}

/**
 * Update cost in Redis
 */
async function updateCostInRedis(
  keys: string[],
  cost: number,
  env: Env
): Promise<void> {
  const commands = keys.flatMap(key => [
    ['INCRBYFLOAT', key, cost.toString()],
    ['EXPIRE', key, '2592000'], // 30 days
  ]);
  
  const response = await fetch(`${env.REDIS_URL}/pipeline`, {
    method: 'POST',
    headers: {
      'Authorization': `Bearer ${env.REDIS_TOKEN}`,
      'Content-Type': 'application/json',
    },
    body: JSON.stringify(commands),
  });
  
  if (!response.ok) {
    throw new Error(`Redis update failed: ${response.status}`);
  }
}

/**
 * Update cost in KV (fallback)
 */
async function updateCostInKV(
  keys: string[],
  cost: number,
  env: Env
): Promise<void> {
  const promises = keys.map(async key => {
    try {
      const currentValue = await env.CACHE_KV.get(key);
      const newValue = (parseFloat(currentValue || '0') + cost).toString();
      await env.CACHE_KV.put(key, newValue, { expirationTtl: 2592000 }); // 30 days
    } catch (error) {
      console.error(`Failed to update KV key ${key}:`, error);
    }
  });
  
  await Promise.allSettled(promises);
}

/**
 * Update cost in backend
 */
async function updateCostInBackend(
  companyId: string,
  cost: number,
  env: Env
): Promise<void> {
  await fetch(`${env.API_LENS_BACKEND_URL}/companies/${companyId}/usage/cost`, {
    method: 'POST',
    headers: {
      'Authorization': `Bearer ${env.API_LENS_BACKEND_TOKEN}`,
      'Content-Type': 'application/json',
    },
    body: JSON.stringify({
      cost,
      timestamp: new Date().toISOString(),
      currency: 'USD',
    }),
  });
}

/**
 * Check if additional cost would exceed quota
 * 
 * @param companyId - The company ID
 * @param additionalCost - The cost to check
 * @param env - Environment bindings
 * @returns Promise<boolean> - true if within quota, false if would exceed
 */
export async function checkCostQuota(
  companyId: string,
  additionalCost: number,
  env: Env
): Promise<boolean> {
  try {
    // Get current usage and quotas
    const [currentUsage, quotas] = await Promise.all([
      getCurrentCostUsage(companyId, env),
      getCompanyCostQuotas(companyId, env),
    ]);
    
    if (!quotas) {
      return true; // No quotas defined, allow request
    }
    
    // Check daily quota
    if (quotas.daily > 0) {
      const newDailyCost = currentUsage.current.daily + additionalCost;
      if (newDailyCost > quotas.daily) {
        return false;
      }
    }
    
    // Check monthly quota
    if (quotas.monthly > 0) {
      const newMonthlyCost = currentUsage.current.monthly + additionalCost;
      if (newMonthlyCost > quotas.monthly) {
        return false;
      }
    }
    
    return true;
    
  } catch (error) {
    console.error('Error checking cost quota:', error);
    return true; // Allow request on error
  }
}

/**
 * Get current cost usage for a company
 */
async function getCurrentCostUsage(companyId: string, env: Env): Promise<CostUsage> {
  const now = new Date();
  const hourKey = `cost:${companyId}:hour:${now.getUTCFullYear()}-${String(now.getUTCMonth() + 1).padStart(2, '0')}-${String(now.getUTCDate()).padStart(2, '0')}-${String(now.getUTCHours()).padStart(2, '0')}`;
  const dayKey = `cost:${companyId}:day:${now.getUTCFullYear()}-${String(now.getUTCMonth() + 1).padStart(2, '0')}-${String(now.getUTCDate()).padStart(2, '0')}`;
  const monthKey = `cost:${companyId}:month:${now.getUTCFullYear()}-${String(now.getUTCMonth() + 1).padStart(2, '0')}`;
  
  try {
    // Try Redis first
    let hourlyCost = 0;
    let dailyCost = 0;
    let monthlyCost = 0;
    
    if (env.REDIS_URL && env.REDIS_TOKEN) {
      const response = await fetch(`${env.REDIS_URL}/pipeline`, {
        method: 'POST',
        headers: {
          'Authorization': `Bearer ${env.REDIS_TOKEN}`,
          'Content-Type': 'application/json',
        },
        body: JSON.stringify([
          ['GET', hourKey],
          ['GET', dayKey],
          ['GET', monthKey],
        ]),
      });
      
      if (response.ok) {
        const results = await response.json();
        hourlyCost = parseFloat(results[0]?.result || '0');
        dailyCost = parseFloat(results[1]?.result || '0');
        monthlyCost = parseFloat(results[2]?.result || '0');
      }
    } else {
      // Fallback to KV
      const [hourValue, dayValue, monthValue] = await Promise.all([
        env.CACHE_KV.get(hourKey),
        env.CACHE_KV.get(dayKey),
        env.CACHE_KV.get(monthKey),
      ]);
      
      hourlyCost = parseFloat(hourValue || '0');
      dailyCost = parseFloat(dayValue || '0');
      monthlyCost = parseFloat(monthValue || '0');
    }
    
    return {
      current: {
        hourly: hourlyCost,
        daily: dailyCost,
        monthly: monthlyCost,
        yearly: 0, // TODO: Implement yearly tracking
      },
      period: {
        startDate: new Date(now.getUTCFullYear(), now.getUTCMonth(), 1).toISOString(),
        endDate: new Date(now.getUTCFullYear(), now.getUTCMonth() + 1, 0).toISOString(),
        timezone: 'UTC',
      },
      limits: {
        daily: 0,
        monthly: 0,
        alertThresholds: { warning: 80, critical: 95 },
      },
      projections: {
        dailyProjection: calculateDailyProjection(hourlyCost),
        monthlyProjection: calculateMonthlyProjection(dailyCost, now),
      },
    };
    
  } catch (error) {
    console.error('Error getting current cost usage:', error);
    return {
      current: { hourly: 0, daily: 0, monthly: 0, yearly: 0 },
      period: {
        startDate: new Date().toISOString(),
        endDate: new Date().toISOString(),
        timezone: 'UTC',
      },
      limits: { daily: 0, monthly: 0, alertThresholds: { warning: 80, critical: 95 } },
      projections: { dailyProjection: 0, monthlyProjection: 0 },
    };
  }
}

/**
 * Get company cost quotas from backend
 */
async function getCompanyCostQuotas(companyId: string, env: Env): Promise<CostQuota | null> {
  try {
    const response = await fetch(`${env.API_LENS_BACKEND_URL}/companies/${companyId}/quotas`, {
      headers: {
        'Authorization': `Bearer ${env.API_LENS_BACKEND_TOKEN}`,
        'Content-Type': 'application/json',
      },
    });
    
    if (response.status === 404) {
      return null; // No quotas configured
    }
    
    if (!response.ok) {
      throw new Error(`Backend API error: ${response.status}`);
    }
    
    return await response.json();
    
  } catch (error) {
    console.error('Error fetching company quotas:', error);
    return null;
  }
}

/**
 * Generate cost headers for response
 * 
 * @param cost - The request cost
 * @param monthlyTotal - Current monthly total cost
 * @param costCalculation - Detailed cost calculation
 * @returns Headers object with cost information
 */
export function getCostHeaders(
  cost: number,
  monthlyTotal: number,
  costCalculation?: CostCalculation,
  quotas?: CostQuota
): Headers {
  const headers = new Headers();
  
  if (costCalculation) {
    headers.set('X-Cost-Input', costCalculation.inputCost.toFixed(6));
    headers.set('X-Cost-Output', costCalculation.outputCost.toFixed(6));
    headers.set('X-Cost-Total', costCalculation.totalCost.toFixed(6));
    headers.set('X-Cost-Currency', costCalculation.currency);
    headers.set('X-Cost-Tokens-Input', costCalculation.breakdown.inputTokens.toString());
    headers.set('X-Cost-Tokens-Output', costCalculation.breakdown.outputTokens.toString());
    headers.set('X-Cost-Rate-Input', costCalculation.breakdown.inputRate.toFixed(6));
    headers.set('X-Cost-Rate-Output', costCalculation.breakdown.outputRate.toFixed(6));
  } else {
    headers.set('X-Cost-Total', cost.toFixed(6));
    headers.set('X-Cost-Currency', 'USD');
  }
  
  headers.set('X-Cost-Monthly-Total', monthlyTotal.toFixed(6));
  
  if (quotas) {
    if (quotas.monthly > 0) {
      headers.set('X-Cost-Monthly-Limit', quotas.monthly.toFixed(2));
      headers.set('X-Cost-Monthly-Remaining', Math.max(0, quotas.monthly - monthlyTotal).toFixed(6));
    }
    
    if (quotas.daily > 0) {
      headers.set('X-Cost-Daily-Limit', quotas.daily.toFixed(2));
    }
  }
  
  return headers;
}

/**
 * Estimate cost for a request before execution
 */
export function estimateRequestCost(
  vendor: string,
  model: string,
  inputText: string,
  expectedOutputTokens: number = 150
): CostEstimate {
  const resolvedModel = resolveModelName(model);
  const pricing = getModelPricing(vendor, resolvedModel);
  
  if (!pricing) {
    return {
      estimatedInputTokens: 0,
      estimatedOutputTokens: 0,
      estimatedInputCost: 0,
      estimatedOutputCost: 0,
      estimatedTotalCost: 0,
      confidence: 0,
      model: resolvedModel,
      vendor,
    };
  }
  
  // Rough token estimation (4 characters per token average)
  const estimatedInputTokens = Math.ceil(inputText.length / 4);
  const estimatedOutputTokens = expectedOutputTokens;
  
  const estimatedInputCost = (estimatedInputTokens / 1000) * pricing.pricing.inputCostPer1kTokens;
  const estimatedOutputCost = (estimatedOutputTokens / 1000) * pricing.pricing.outputCostPer1kTokens;
  const estimatedTotalCost = estimatedInputCost + estimatedOutputCost;
  
  return {
    estimatedInputTokens,
    estimatedOutputTokens,
    estimatedInputCost: Math.round(estimatedInputCost * 1000000) / 1000000,
    estimatedOutputCost: Math.round(estimatedOutputCost * 1000000) / 1000000,
    estimatedTotalCost: Math.round(estimatedTotalCost * 1000000) / 1000000,
    confidence: 0.7, // Rough estimation
    model: resolvedModel,
    vendor,
  };
}

/**
 * Calculate daily projection based on current hourly usage
 */
function calculateDailyProjection(hourlyCost: number): number {
  const currentHour = new Date().getUTCHours();
  if (currentHour === 0) return hourlyCost * 24;
  
  const averageHourlyCost = hourlyCost / currentHour;
  return averageHourlyCost * 24;
}

/**
 * Calculate monthly projection based on current daily usage
 */
function calculateMonthlyProjection(dailyCost: number, now: Date): number {
  const dayOfMonth = now.getUTCDate();
  const daysInMonth = new Date(now.getUTCFullYear(), now.getUTCMonth() + 1, 0).getUTCDate();
  
  if (dayOfMonth === 1) return dailyCost * daysInMonth;
  
  const averageDailyCost = dailyCost / dayOfMonth;
  return averageDailyCost * daysInMonth;
}

/**
 * Format cost for display
 */
export function formatCost(cost: number, currency: string = 'USD'): string {
  return new Intl.NumberFormat('en-US', {
    style: 'currency',
    currency,
    minimumFractionDigits: 6,
    maximumFractionDigits: 6,
  }).format(cost);
}

/**
 * Get cost efficiency score for a model
 */
export function getCostEfficiencyScore(vendor: string, model: string): number {
  const pricing = getModelPricing(vendor, model);
  if (!pricing) return 0;
  
  const avgCost = (pricing.pricing.inputCostPer1kTokens + pricing.pricing.outputCostPer1kTokens) / 2;
  const contextLength = pricing.features?.contextLength || 1000;
  
  // Higher context length and lower cost = higher efficiency
  return Math.round((contextLength / 1000) / (avgCost * 1000));
}
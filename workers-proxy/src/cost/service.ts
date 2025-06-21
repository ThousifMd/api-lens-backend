/**
 * API Lens Workers Proxy - Cost Service
 * 
 * Main service for handling cost calculation, tracking, and quota enforcement
 */

import { Context } from 'hono';
import {
  CostCalculation,
  CostUsage,
  CostQuota,
  CostAlert,
  CostAlertType,
  CostSummary,
  CostMetrics,
  CostOptimization,
  UsageData,
} from './types';
import {
  calculateRequestCost,
  calculateDetailedCost,
  updateRealTimeCost,
  checkCostQuota,
  getCostHeaders,
  estimateRequestCost,
  formatCost,
  getCostEfficiencyScore,
} from './functions';
import { getModelPricing, findCheapestModel, getPricingSummary } from './pricing';
import { getAuthResult } from '../auth';
import { Env } from '../index';

export class CostService {
  private env: Env;
  
  constructor(env: Env) {
    this.env = env;
  }
  
  /**
   * Calculate cost for a completed request
   */
  async calculateCost(
    vendor: string,
    model: string,
    usage: UsageData
  ): Promise<CostCalculation> {
    return calculateDetailedCost(vendor, model, usage);
  }
  
  /**
   * Process cost for a request with tracking and quota checks
   */
  async processRequestCost(
    c: Context<{ Bindings: Env }>,
    vendor: string,
    model: string,
    usage: UsageData,
    preCheck: boolean = true
  ): Promise<{
    cost: CostCalculation;
    quotaStatus: {
      allowed: boolean;
      reason?: string;
    };
    headers: Headers;
  }> {
    const authResult = getAuthResult(c);
    if (!authResult) {
      throw new Error('Request not authenticated');
    }
    
    const companyId = authResult.company.id;
    
    // Calculate detailed cost
    const cost = await this.calculateCost(vendor, model, usage);
    
    // Check quota before processing (if preCheck is enabled)
    let quotaStatus = { allowed: true };
    if (preCheck) {
      const withinQuota = await checkCostQuota(companyId, cost.totalCost, this.env);
      if (!withinQuota) {
        quotaStatus = {
          allowed: false,
          reason: 'Cost quota exceeded',
        };
      }
    }
    
    // Update real-time cost tracking (fire and forget)
    if (quotaStatus.allowed) {
      updateRealTimeCost(companyId, cost.totalCost, this.env).catch(err => {
        console.error('Failed to update real-time cost:', err);
      });
      
      // Check for alerts
      this.checkCostAlerts(companyId, cost.totalCost).catch(err => {
        console.error('Failed to check cost alerts:', err);
      });
    }
    
    // Get current usage for headers
    const currentUsage = await this.getCurrentUsage(companyId);
    const quotas = await this.getCompanyQuotas(companyId);
    
    // Generate headers
    const headers = getCostHeaders(
      cost.totalCost,
      currentUsage.current.monthly,
      cost,
      quotas
    );
    
    return {
      cost,
      quotaStatus,
      headers,
    };
  }
  
  /**
   * Estimate cost before making a request
   */
  estimateCost(
    vendor: string,
    model: string,
    inputText: string,
    expectedOutputTokens?: number
  ): ReturnType<typeof estimateRequestCost> {
    return estimateRequestCost(vendor, model, inputText, expectedOutputTokens);
  }
  
  /**
   * Check if a request would exceed quotas
   */
  async checkQuota(
    companyId: string,
    estimatedCost: number
  ): Promise<boolean> {
    return checkCostQuota(companyId, estimatedCost, this.env);
  }
  
  /**
   * Get current cost usage for a company
   */
  async getCurrentUsage(companyId: string): Promise<CostUsage> {
    try {
      // This reuses the logic from functions.ts
      const { getCurrentCostUsage } = await import('./functions');
      return getCurrentCostUsage(companyId, this.env);
    } catch (error) {
      console.error('Error getting current usage:', error);
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
   * Get company cost quotas
   */
  async getCompanyQuotas(companyId: string): Promise<CostQuota | null> {
    try {
      const response = await fetch(`${this.env.API_LENS_BACKEND_URL}/companies/${companyId}/quotas`, {
        headers: {
          'Authorization': `Bearer ${this.env.API_LENS_BACKEND_TOKEN}`,
          'Content-Type': 'application/json',
        },
      });
      
      if (response.status === 404) {
        return null;
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
   * Get cost summary for a period
   */
  async getCostSummary(
    companyId: string,
    period: 'hour' | 'day' | 'month' | 'year',
    startDate?: string,
    endDate?: string
  ): Promise<CostSummary> {
    try {
      const response = await fetch(
        `${this.env.API_LENS_BACKEND_URL}/companies/${companyId}/cost-summary?period=${period}&start=${startDate}&end=${endDate}`,
        {
          headers: {
            'Authorization': `Bearer ${this.env.API_LENS_BACKEND_TOKEN}`,
            'Content-Type': 'application/json',
          },
        }
      );
      
      if (!response.ok) {
        throw new Error(`Backend API error: ${response.status}`);
      }
      
      return await response.json();
    } catch (error) {
      console.error('Error fetching cost summary:', error);
      
      // Return empty summary on error
      const now = new Date();
      return {
        period,
        startDate: startDate || now.toISOString(),
        endDate: endDate || now.toISOString(),
        totalCost: 0,
        totalRequests: 0,
        totalTokens: 0,
        averageCostPerRequest: 0,
        averageCostPerToken: 0,
        breakdown: {
          byVendor: {},
          byModel: {},
        },
      };
    }
  }
  
  /**
   * Get cost metrics and analytics
   */
  async getCostMetrics(companyId: string): Promise<CostMetrics> {
    try {
      const response = await fetch(`${this.env.API_LENS_BACKEND_URL}/companies/${companyId}/cost-metrics`, {
        headers: {
          'Authorization': `Bearer ${this.env.API_LENS_BACKEND_TOKEN}`,
          'Content-Type': 'application/json',
        },
      });
      
      if (!response.ok) {
        throw new Error(`Backend API error: ${response.status}`);
      }
      
      return await response.json();
    } catch (error) {
      console.error('Error fetching cost metrics:', error);
      
      return {
        totalRequests: 0,
        totalCost: 0,
        averageCostPerRequest: 0,
        averageCostPerToken: 0,
        costByVendor: {},
        costByModel: {},
        costTrends: {
          hourly: [],
          daily: [],
          monthly: [],
        },
      };
    }
  }
  
  /**
   * Get cost optimization recommendations
   */
  getCostOptimization(usage: CostMetrics): CostOptimization {
    const recommendations: CostOptimization['recommendations'] = [];
    const pricingSummary = getPricingSummary();
    
    // Find most used models and suggest cheaper alternatives
    const modelUsage = Object.entries(usage.costByModel)
      .sort(([, a], [, b]) => b - a)
      .slice(0, 5); // Top 5 models by cost
    
    for (const [model, cost] of modelUsage) {
      const currentPricing = pricingSummary.find(p => p.model === model);
      if (!currentPricing) continue;
      
      // Find cheaper alternatives with similar features
      const alternatives = pricingSummary
        .filter(p => 
          p.vendor !== currentPricing.vendor &&
          p.features.some(f => currentPricing.features.includes(f)) &&
          (p.inputCost + p.outputCost) / 2 < (currentPricing.inputCost + currentPricing.outputCost) / 2
        )
        .sort((a, b) => ((a.inputCost + a.outputCost) / 2) - ((b.inputCost + b.outputCost) / 2));
      
      if (alternatives.length > 0) {
        const alternative = alternatives[0];
        const currentAvgCost = (currentPricing.inputCost + currentPricing.outputCost) / 2;
        const altAvgCost = (alternative.inputCost + alternative.outputCost) / 2;
        const savingsRate = (currentAvgCost - altAvgCost) / currentAvgCost;
        const potentialSavings = cost * savingsRate;
        
        if (potentialSavings > 0.01) { // Only suggest if savings > $0.01
          recommendations.push({
            type: 'model_switch',
            currentModel: model,
            recommendedModel: alternative.model,
            potentialSavings,
            impactRating: potentialSavings > cost * 0.3 ? 'high' : potentialSavings > cost * 0.1 ? 'medium' : 'low',
            description: `Switch from ${model} to ${alternative.model} to save approximately ${formatCost(potentialSavings)} per month`,
          });
        }
      }
    }
    
    // Find most efficient models
    const efficientModels = pricingSummary
      .map(p => ({
        model: p.model,
        vendor: p.vendor,
        costEfficiencyScore: getCostEfficiencyScore(p.vendor, p.model),
        useCases: p.features,
      }))
      .filter(m => m.costEfficiencyScore > 0)
      .sort((a, b) => b.costEfficiencyScore - a.costEfficiencyScore)
      .slice(0, 10);
    
    // Calculate budget projections
    const currentMonthCost = usage.totalCost;
    const optimizedCost = recommendations.reduce((total, rec) => total - rec.potentialSavings, currentMonthCost);
    const savingsPotential = currentMonthCost - optimizedCost;
    
    return {
      recommendations,
      efficientModels,
      budgetProjections: {
        currentTrend: currentMonthCost,
        optimizedProjection: Math.max(0, optimizedCost),
        savingsPotential,
      },
    };
  }
  
  /**
   * Check for cost alerts and send notifications
   */
  private async checkCostAlerts(
    companyId: string,
    additionalCost: number
  ): Promise<void> {
    try {
      const [usage, quotas] = await Promise.all([
        this.getCurrentUsage(companyId),
        this.getCompanyQuotas(companyId),
      ]);
      
      if (!quotas) return;
      
      const newMonthlyCost = usage.current.monthly + additionalCost;
      const alerts: CostAlert[] = [];
      
      // Check monthly quota alerts
      if (quotas.monthly > 0) {
        const monthlyUsagePercent = (newMonthlyCost / quotas.monthly) * 100;
        
        if (monthlyUsagePercent >= quotas.alertThresholds.critical) {
          alerts.push({
            type: CostAlertType.CRITICAL,
            threshold: quotas.alertThresholds.critical,
            currentUsage: newMonthlyCost,
            quotaLimit: quotas.monthly,
            period: 'monthly',
            timestamp: new Date().toISOString(),
            companyId,
            message: `Critical: Monthly cost usage is at ${monthlyUsagePercent.toFixed(1)}% of quota`,
          });
        } else if (monthlyUsagePercent >= quotas.alertThresholds.warning) {
          alerts.push({
            type: CostAlertType.WARNING,
            threshold: quotas.alertThresholds.warning,
            currentUsage: newMonthlyCost,
            quotaLimit: quotas.monthly,
            period: 'monthly',
            timestamp: new Date().toISOString(),
            companyId,
            message: `Warning: Monthly cost usage is at ${monthlyUsagePercent.toFixed(1)}% of quota`,
          });
        }
        
        if (newMonthlyCost > quotas.monthly) {
          alerts.push({
            type: CostAlertType.QUOTA_EXCEEDED,
            threshold: 100,
            currentUsage: newMonthlyCost,
            quotaLimit: quotas.monthly,
            period: 'monthly',
            timestamp: new Date().toISOString(),
            companyId,
            message: `Quota exceeded: Monthly cost ${formatCost(newMonthlyCost)} exceeds limit ${formatCost(quotas.monthly)}`,
          });
        }
      }
      
      // Check daily quota alerts
      if (quotas.daily > 0) {
        const newDailyCost = usage.current.daily + additionalCost;
        const dailyUsagePercent = (newDailyCost / quotas.daily) * 100;
        
        if (dailyUsagePercent >= quotas.alertThresholds.critical) {
          alerts.push({
            type: CostAlertType.CRITICAL,
            threshold: quotas.alertThresholds.critical,
            currentUsage: newDailyCost,
            quotaLimit: quotas.daily,
            period: 'daily',
            timestamp: new Date().toISOString(),
            companyId,
            message: `Critical: Daily cost usage is at ${dailyUsagePercent.toFixed(1)}% of quota`,
          });
        }
      }
      
      // Send alerts to backend
      if (alerts.length > 0) {
        await this.sendCostAlerts(alerts);
      }
      
    } catch (error) {
      console.error('Error checking cost alerts:', error);
    }
  }
  
  /**
   * Send cost alerts to backend
   */
  private async sendCostAlerts(alerts: CostAlert[]): Promise<void> {
    try {
      await fetch(`${this.env.API_LENS_BACKEND_URL}/alerts/cost`, {
        method: 'POST',
        headers: {
          'Authorization': `Bearer ${this.env.API_LENS_BACKEND_TOKEN}`,
          'Content-Type': 'application/json',
        },
        body: JSON.stringify({ alerts }),
      });
    } catch (error) {
      console.error('Failed to send cost alerts:', error);
    }
  }
  
  /**
   * Format cost for display
   */
  formatCost(cost: number): string {
    return formatCost(cost);
  }
  
  /**
   * Get cheapest model recommendation
   */
  getCheapestModel(features: string[] = [], minContextLength: number = 0) {
    return findCheapestModel(features, minContextLength);
  }
}
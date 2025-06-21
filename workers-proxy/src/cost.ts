/**
 * API Lens Workers Proxy - Cost Calculation Integration
 * 
 * Main integration layer for the new modular cost calculation system
 */

import { Context } from 'hono';
import { Env } from './index';
import {
  CostService,
  calculateRequestCost,
  calculateDetailedCost,
  estimateRequestCost as newEstimateRequestCost,
  formatCost,
  getCostHeaders,
  CostCalculation,
  UsageData,
  CostQuota,
} from './cost';

// Legacy interface for backward compatibility
export interface CostInfo {
  inputTokens: number;
  outputTokens: number;
  totalTokens: number;
  cost: number;
  model: string;
  vendor: string;
}

/**
 * Calculate cost for a completed request (updated to use new system)
 */
export async function calculateCost(
  vendor: string,
  model: string | undefined,
  requestBody: any,
  responseBody: any
): Promise<CostInfo> {
  try {
    // Extract usage data from response
    const usage = extractUsageData(vendor, responseBody);
    
    // Use new cost calculation system
    const detailedCost = calculateDetailedCost(vendor, model || 'unknown', usage);
    
    return {
      inputTokens: usage.inputTokens,
      outputTokens: usage.outputTokens,
      totalTokens: usage.totalTokens,
      cost: detailedCost.totalCost,
      model: model || 'unknown',
      vendor,
    };
    
  } catch (error) {
    console.error('Error calculating cost:', error);
    
    // Fallback to estimation
    const estimated = estimateTokens(requestBody, responseBody);
    const estimatedCost = calculateRequestCost(vendor, model || 'unknown', {
      inputTokens: estimated.inputTokens,
      outputTokens: estimated.outputTokens,
      totalTokens: estimated.inputTokens + estimated.outputTokens,
      model: model || 'unknown',
    });
    
    return {
      inputTokens: estimated.inputTokens,
      outputTokens: estimated.outputTokens,
      totalTokens: estimated.inputTokens + estimated.outputTokens,
      cost: estimatedCost,
      model: model || 'unknown',
      vendor,
    };
  }
}

/**
 * Extract usage data from vendor response
 */
function extractUsageData(vendor: string, responseBody: any): UsageData {
  let inputTokens = 0;
  let outputTokens = 0;
  
  try {
    switch (vendor.toLowerCase()) {
      case 'openai':
        inputTokens = responseBody?.usage?.prompt_tokens || 0;
        outputTokens = responseBody?.usage?.completion_tokens || 0;
        break;
        
      case 'anthropic':
        inputTokens = responseBody?.usage?.input_tokens || 0;
        outputTokens = responseBody?.usage?.output_tokens || 0;
        break;
        
      case 'google':
        inputTokens = responseBody?.usageMetadata?.promptTokenCount || 0;
        outputTokens = responseBody?.usageMetadata?.candidatesTokenCount || 0;
        break;
        
      default:
        // Return zero usage for unknown vendors
        console.warn(`Unknown vendor for usage extraction: ${vendor}`);
    }
  } catch (error) {
    console.error('Error extracting usage data:', error);
  }
  
  return {
    inputTokens,
    outputTokens,
    totalTokens: inputTokens + outputTokens,
    model: responseBody?.model || 'unknown',
    requestId: responseBody?.id,
    finishReason: getFinishReason(responseBody, vendor),
  };
}

/**
 * Get finish reason from response
 */
function getFinishReason(responseBody: any, vendor: string): string | undefined {
  try {
    switch (vendor.toLowerCase()) {
      case 'openai':
        return responseBody?.choices?.[0]?.finish_reason;
      case 'anthropic':
        return responseBody?.stop_reason;
      case 'google':
        return responseBody?.candidates?.[0]?.finishReason;
      default:
        return undefined;
    }
  } catch {
    return undefined;
  }
}

/**
 * Estimate cost before making the request (legacy function)
 */
export function estimateRequestCost(
  vendor: string,
  model: string | undefined,
  requestBody: any
): number {
  try {
    // Extract input text for estimation
    let inputText = '';
    
    if (requestBody?.messages) {
      inputText = requestBody.messages
        .map((msg: any) => msg.content || '')
        .join(' ');
    } else if (requestBody?.prompt) {
      inputText = requestBody.prompt;
    } else if (requestBody?.contents) {
      inputText = requestBody.contents
        .map((content: any) => 
          content.parts?.map((part: any) => part.text || '').join(' ') || ''
        )
        .join(' ');
    }
    
    // Estimate output tokens
    const expectedOutput = estimateOutputTokens(requestBody);
    
    // Use new estimation system
    const estimate = newEstimateRequestCost(vendor, model || 'unknown', inputText, expectedOutput);
    return estimate.estimatedTotalCost;
    
  } catch (error) {
    console.error('Error estimating request cost:', error);
    return 0;
  }
}

/**
 * Process cost with full tracking and quota checking
 */
export async function processRequestCost(
  c: Context<{ Bindings: Env }>,
  vendor: string,
  model: string,
  usage: UsageData
): Promise<{
  cost: CostCalculation;
  allowed: boolean;
  headers: Record<string, string>;
}> {
  const costService = new CostService(c.env);
  
  try {
    const result = await costService.processRequestCost(c, vendor, model, usage);
    
    // Convert Headers to plain object
    const headers: Record<string, string> = {};
    for (const [key, value] of result.headers.entries()) {
      headers[key] = value;
    }
    
    return {
      cost: result.cost,
      allowed: result.quotaStatus.allowed,
      headers,
    };
    
  } catch (error) {
    console.error('Error processing request cost:', error);
    
    // Fallback calculation
    const cost = calculateDetailedCost(vendor, model, usage);
    
    return {
      cost,
      allowed: true, // Allow on error
      headers: {
        'X-Cost-Total': cost.totalCost.toFixed(6),
        'X-Cost-Currency': cost.currency,
      },
    };
  }
}

/**
 * Get current cost usage for a company
 */
export async function getCurrentCostUsage(
  companyId: string,
  env: Env
): Promise<{
  daily: number;
  monthly: number;
  yearly: number;
}> {
  const costService = new CostService(env);
  
  try {
    const usage = await costService.getCurrentUsage(companyId);
    return {
      daily: usage.current.daily,
      monthly: usage.current.monthly,
      yearly: usage.current.yearly,
    };
  } catch (error) {
    console.error('Error getting current cost usage:', error);
    return { daily: 0, monthly: 0, yearly: 0 };
  }
}

/**
 * Check if request would exceed cost quotas
 */
export async function checkCostQuota(
  companyId: string,
  estimatedCost: number,
  env: Env
): Promise<boolean> {
  const costService = new CostService(env);
  
  try {
    return await costService.checkQuota(companyId, estimatedCost);
  } catch (error) {
    console.error('Error checking cost quota:', error);
    return true; // Allow on error
  }
}

/**
 * Update real-time cost tracking
 */
export async function updateCostTracking(
  companyId: string,
  cost: number,
  env: Env
): Promise<void> {
  const { updateRealTimeCost } = await import('./cost/functions');
  
  try {
    await updateRealTimeCost(companyId, cost, env);
  } catch (error) {
    console.error('Error updating cost tracking:', error);
    // Don't throw - cost tracking failure shouldn't break the request
  }
}

/**
 * Create cost middleware for request processing
 */
export function createCostMiddleware() {
  return async function costMiddleware(
    c: Context<{ Bindings: Env }>,
    next: () => Promise<void>
  ) {
    // Add cost service to context
    const costService = new CostService(c.env);
    c.set('costService', costService);
    
    // Continue to next middleware
    await next();
    
    // After request, add cost headers if usage is available
    const usage = c.get('usage');
    const vendor = c.get('vendor');
    const model = c.get('model');
    
    if (usage && vendor && model) {
      try {
        const result = await processRequestCost(c, vendor, model, usage);
        
        // Add cost headers to response
        for (const [key, value] of Object.entries(result.headers)) {
          c.header(key, value);
        }
        
        // Store cost information in context
        c.set('requestCost', result.cost.totalCost);
        c.set('costBreakdown', result.cost);
        
      } catch (error) {
        console.error('Cost middleware error:', error);
      }
    }
  };
}

// Legacy helper functions (keep for backward compatibility)

/**
 * Estimate token usage when vendor doesn't provide exact counts
 */
function estimateTokens(requestBody: any, responseBody: any): {
  inputTokens: number;
  outputTokens: number;
} {
  let inputText = '';
  let outputText = '';
  
  try {
    // Extract input text
    if (requestBody?.messages) {
      inputText = requestBody.messages
        .map((msg: any) => msg.content || '')
        .join(' ');
    } else if (requestBody?.prompt) {
      inputText = requestBody.prompt;
    } else if (requestBody?.contents) {
      inputText = requestBody.contents
        .map((content: any) => 
          content.parts?.map((part: any) => part.text || '').join(' ') || ''
        )
        .join(' ');
    }
    
    // Extract output text
    if (responseBody?.choices) {
      outputText = responseBody.choices
        .map((choice: any) => choice.message?.content || choice.text || '')
        .join(' ');
    } else if (responseBody?.content) {
      outputText = responseBody.content
        .map((item: any) => item.text || '')
        .join(' ');
    } else if (responseBody?.candidates) {
      outputText = responseBody.candidates
        .map((candidate: any) => 
          candidate.content?.parts?.map((part: any) => part.text || '').join(' ') || ''
        )
        .join(' ');
    }
  } catch (error) {
    console.error('Error estimating tokens:', error);
  }
  
  // Rough estimation: 1 token ≈ 4 characters for English text
  const inputTokens = Math.ceil(inputText.length / 4);
  const outputTokens = Math.ceil(outputText.length / 4);
  
  return { inputTokens, outputTokens };
}

/**
 * Estimate output tokens from request parameters
 */
function estimateOutputTokens(requestBody: any): number {
  // Use max_tokens if specified
  if (requestBody?.max_tokens && typeof requestBody.max_tokens === 'number') {
    return requestBody.max_tokens;
  }
  
  // Use maxOutputTokens for Google AI
  if (requestBody?.generationConfig?.maxOutputTokens) {
    return requestBody.generationConfig.maxOutputTokens;
  }
  
  // Default estimation based on typical response sizes
  const model = requestBody?.model?.toLowerCase() || '';
  
  if (model.includes('gpt-4')) {
    return 500;
  } else if (model.includes('claude')) {
    return 400;
  } else if (model.includes('gemini')) {
    return 300;
  } else {
    return 200;
  }
}

// Re-export new system types and functions for convenience
export type {
  CostCalculation,
  CostBreakdown,
  UsageData,
  CostQuota,
  CostUsage,
  CostMetrics,
  CostSummary,
} from './cost';

export {
  CostService,
  formatCost,
  getCostHeaders,
} from './cost';
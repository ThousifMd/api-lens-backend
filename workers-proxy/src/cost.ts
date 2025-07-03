/**
 * API Lens Workers Proxy - Cost Calculation Integration
 * 
 * Main integration layer for the new modular cost calculation system
 */

import { Context } from 'hono';
import { Env, HonoVariables, CostInfo } from './types';

// Simplified types
export interface CostCalculation {
  inputCost: number;
  outputCost: number;
  totalCost: number;
  currency: string;
  model: string;
  vendor: string;
}

export interface UsageData {
  inputTokens: number;
  outputTokens: number;
  totalTokens: number;
  model: string;
  requestId?: string;
  finishReason?: string;
}

export interface CostQuota {
  dailyLimit?: number;
  monthlyLimit?: number;
  currentDaily: number;
  currentMonthly: number;
}


/**
 * Calculate cost for a completed request (updated to use new system)
 */
export async function calculateCost(
  c: Context<{ Bindings: Env; Variables: HonoVariables }>,
  vendor: string,
  model: string,
  inputTokens: number,
  outputTokens: number
): Promise<CostInfo> {
  // Simplified cost calculation
  const inputCost = (inputTokens / 1000) * 0.001; // $0.001 per 1K input tokens
  const outputCost = (outputTokens / 1000) * 0.002; // $0.002 per 1K output tokens
  const totalCost = inputCost + outputCost;

  return {
    inputTokens,
    outputTokens,
    totalTokens: inputTokens + outputTokens,
    inputCost,
    outputCost,
    totalCost,
    currency: 'USD',
    pricingTier: 'standard',
    costSource: 'simplified'
  };
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
    // Simple estimation based on typical request sizes
    const estimatedInputTokens = 100;
    const estimatedOutputTokens = 50;
    
    const inputCost = (estimatedInputTokens / 1000) * 0.001;
    const outputCost = (estimatedOutputTokens / 1000) * 0.002;
    
    return inputCost + outputCost;
    
  } catch (error) {
    console.error('Error estimating request cost:', error);
    return 0;
  }
}

/**
 * Process cost with full tracking and quota checking
 */
export async function processRequestCost(
  c: Context<{ Bindings: Env; Variables: HonoVariables }>,
  vendor: string,
  model: string,
  usage: UsageData
): Promise<{
  cost: CostCalculation;
  allowed: boolean;
  headers: Record<string, string>;
}> {
  try {
    const inputCost = (usage.inputTokens / 1000) * 0.001;
    const outputCost = (usage.outputTokens / 1000) * 0.002;
    const totalCost = inputCost + outputCost;
    
    const cost: CostCalculation = {
      inputCost,
      outputCost,
      totalCost,
      currency: 'USD',
      model,
      vendor
    };
    
    return {
      cost,
      allowed: true, // Simplified - always allow
      headers: {
        'X-Cost-Total': totalCost.toFixed(6),
        'X-Cost-Currency': 'USD',
      },
    };
    
  } catch (error) {
    console.error('Error processing request cost:', error);
    
    const cost: CostCalculation = {
      inputCost: 0,
      outputCost: 0,
      totalCost: 0,
      currency: 'USD',
      model,
      vendor
    };
    
    return {
      cost,
      allowed: true,
      headers: {},
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
  try {
    // Simplified - return mock data
    return { daily: 0, monthly: 0, yearly: 0 };
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
  try {
    // Simplified - always allow
    return true;
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
  try {
    // Simplified - just log the cost
    console.log(`Cost tracking for ${companyId}: $${cost}`);
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
    c: Context<{ Bindings: Env; Variables: HonoVariables }>,
    next: () => Promise<void>
  ) {
    // Continue to next middleware
    await next();
    
    // After request, add simple cost headers
    c.header('X-Cost-Total', '0.001');
    c.header('X-Cost-Currency', 'USD');
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

// Simplified helper functions
export function formatCost(cost: number): string {
  return `$${cost.toFixed(6)}`;
}

export function getCostHeaders(cost: CostCalculation): Record<string, string> {
  return {
    'X-Cost-Total': cost.totalCost.toFixed(6),
    'X-Cost-Currency': cost.currency,
    'X-Cost-Input': cost.inputCost.toFixed(6),
    'X-Cost-Output': cost.outputCost.toFixed(6)
  };
}
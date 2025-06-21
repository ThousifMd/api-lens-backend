/**
 * API Lens Workers Proxy - Vendor Pricing Configuration
 * 
 * Current pricing data for all supported vendors and models
 */

import { VendorPricing } from './types';

/**
 * Current vendor pricing data (updated as of December 2024)
 */
export const VENDOR_PRICING: VendorPricing[] = [
  // OpenAI Models
  {
    vendor: 'openai',
    model: 'gpt-4o',
    pricing: {
      inputCostPer1kTokens: 0.015,
      outputCostPer1kTokens: 0.060,
      currency: 'USD',
      effectiveDate: '2024-05-13',
    },
    features: {
      contextLength: 128000,
      supportedFeatures: ['chat', 'function_calling', 'vision', 'structured_output'],
      rateLimits: {
        requestsPerMinute: 10000,
        tokensPerMinute: 30000000,
      },
    },
  },
  {
    vendor: 'openai',
    model: 'gpt-4o-mini',
    pricing: {
      inputCostPer1kTokens: 0.00015,
      outputCostPer1kTokens: 0.0006,
      currency: 'USD',
      effectiveDate: '2024-07-18',
    },
    features: {
      contextLength: 128000,
      supportedFeatures: ['chat', 'function_calling', 'vision'],
      rateLimits: {
        requestsPerMinute: 10000,
        tokensPerMinute: 200000000,
      },
    },
  },
  {
    vendor: 'openai',
    model: 'gpt-4-turbo',
    pricing: {
      inputCostPer1kTokens: 0.01,
      outputCostPer1kTokens: 0.03,
      currency: 'USD',
      effectiveDate: '2024-04-09',
    },
    features: {
      contextLength: 128000,
      supportedFeatures: ['chat', 'function_calling', 'vision'],
    },
  },
  {
    vendor: 'openai',
    model: 'gpt-4',
    pricing: {
      inputCostPer1kTokens: 0.03,
      outputCostPer1kTokens: 0.06,
      currency: 'USD',
      effectiveDate: '2023-03-14',
    },
    features: {
      contextLength: 8192,
      supportedFeatures: ['chat', 'function_calling'],
    },
  },
  {
    vendor: 'openai',
    model: 'gpt-3.5-turbo',
    pricing: {
      inputCostPer1kTokens: 0.0015,
      outputCostPer1kTokens: 0.002,
      currency: 'USD',
      effectiveDate: '2023-06-13',
    },
    features: {
      contextLength: 16385,
      supportedFeatures: ['chat', 'function_calling'],
      rateLimits: {
        requestsPerMinute: 10000,
        tokensPerMinute: 1000000,
      },
    },
  },
  {
    vendor: 'openai',
    model: 'text-embedding-3-large',
    pricing: {
      inputCostPer1kTokens: 0.00013,
      outputCostPer1kTokens: 0,
      currency: 'USD',
      effectiveDate: '2024-01-25',
    },
    features: {
      contextLength: 8191,
      supportedFeatures: ['embeddings'],
    },
  },
  {
    vendor: 'openai',
    model: 'text-embedding-3-small',
    pricing: {
      inputCostPer1kTokens: 0.00002,
      outputCostPer1kTokens: 0,
      currency: 'USD',
      effectiveDate: '2024-01-25',
    },
    features: {
      contextLength: 8191,
      supportedFeatures: ['embeddings'],
    },
  },
  {
    vendor: 'openai',
    model: 'text-embedding-ada-002',
    pricing: {
      inputCostPer1kTokens: 0.0001,
      outputCostPer1kTokens: 0,
      currency: 'USD',
      effectiveDate: '2022-12-15',
    },
    features: {
      contextLength: 8191,
      supportedFeatures: ['embeddings'],
    },
  },

  // Anthropic Models
  {
    vendor: 'anthropic',
    model: 'claude-3-5-sonnet-20241022',
    pricing: {
      inputCostPer1kTokens: 0.003,
      outputCostPer1kTokens: 0.015,
      currency: 'USD',
      effectiveDate: '2024-10-22',
    },
    features: {
      contextLength: 200000,
      supportedFeatures: ['chat', 'vision', 'artifacts', 'computer_use'],
      rateLimits: {
        requestsPerMinute: 1000,
        tokensPerMinute: 40000,
      },
    },
  },
  {
    vendor: 'anthropic',
    model: 'claude-3-5-haiku-20241022',
    pricing: {
      inputCostPer1kTokens: 0.001,
      outputCostPer1kTokens: 0.005,
      currency: 'USD',
      effectiveDate: '2024-11-01',
    },
    features: {
      contextLength: 200000,
      supportedFeatures: ['chat'],
      rateLimits: {
        requestsPerMinute: 1000,
        tokensPerMinute: 50000,
      },
    },
  },
  {
    vendor: 'anthropic',
    model: 'claude-3-opus-20240229',
    pricing: {
      inputCostPer1kTokens: 0.015,
      outputCostPer1kTokens: 0.075,
      currency: 'USD',
      effectiveDate: '2024-02-29',
    },
    features: {
      contextLength: 200000,
      supportedFeatures: ['chat', 'vision'],
    },
  },
  {
    vendor: 'anthropic',
    model: 'claude-3-sonnet-20240229',
    pricing: {
      inputCostPer1kTokens: 0.003,
      outputCostPer1kTokens: 0.015,
      currency: 'USD',
      effectiveDate: '2024-02-29',
    },
    features: {
      contextLength: 200000,
      supportedFeatures: ['chat', 'vision'],
    },
  },
  {
    vendor: 'anthropic',
    model: 'claude-3-haiku-20240307',
    pricing: {
      inputCostPer1kTokens: 0.00025,
      outputCostPer1kTokens: 0.00125,
      currency: 'USD',
      effectiveDate: '2024-03-07',
    },
    features: {
      contextLength: 200000,
      supportedFeatures: ['chat', 'vision'],
    },
  },

  // Google AI Models
  {
    vendor: 'google',
    model: 'gemini-1.5-pro',
    pricing: {
      inputCostPer1kTokens: 0.00125,
      outputCostPer1kTokens: 0.005,
      currency: 'USD',
      effectiveDate: '2024-02-15',
    },
    features: {
      contextLength: 2097152,
      supportedFeatures: ['chat', 'vision', 'function_calling', 'code_execution'],
      rateLimits: {
        requestsPerMinute: 360,
        tokensPerMinute: 4000000,
      },
    },
  },
  {
    vendor: 'google',
    model: 'gemini-1.5-flash',
    pricing: {
      inputCostPer1kTokens: 0.000075,
      outputCostPer1kTokens: 0.0003,
      currency: 'USD',
      effectiveDate: '2024-05-14',
    },
    features: {
      contextLength: 1048576,
      supportedFeatures: ['chat', 'vision', 'function_calling'],
      rateLimits: {
        requestsPerMinute: 1000,
        tokensPerMinute: 4000000,
      },
    },
  },
  {
    vendor: 'google',
    model: 'gemini-1.0-pro',
    pricing: {
      inputCostPer1kTokens: 0.0005,
      outputCostPer1kTokens: 0.0015,
      currency: 'USD',
      effectiveDate: '2023-12-06',
    },
    features: {
      contextLength: 32768,
      supportedFeatures: ['chat', 'function_calling'],
    },
  },
  {
    vendor: 'google',
    model: 'text-embedding-004',
    pricing: {
      inputCostPer1kTokens: 0.00001,
      outputCostPer1kTokens: 0,
      currency: 'USD',
      effectiveDate: '2024-05-14',
    },
    features: {
      contextLength: 2048,
      supportedFeatures: ['embeddings'],
    },
  },

  // Cohere Models
  {
    vendor: 'cohere',
    model: 'command-r',
    pricing: {
      inputCostPer1kTokens: 0.0005,
      outputCostPer1kTokens: 0.0015,
      currency: 'USD',
      effectiveDate: '2024-03-11',
    },
    features: {
      contextLength: 128000,
      supportedFeatures: ['chat', 'retrieval_augmented_generation'],
    },
  },
  {
    vendor: 'cohere',
    model: 'command-r-plus',
    pricing: {
      inputCostPer1kTokens: 0.003,
      outputCostPer1kTokens: 0.015,
      currency: 'USD',
      effectiveDate: '2024-04-04',
    },
    features: {
      contextLength: 128000,
      supportedFeatures: ['chat', 'retrieval_augmented_generation', 'function_calling'],
    },
  },

  // Mistral Models
  {
    vendor: 'mistral',
    model: 'mistral-large-latest',
    pricing: {
      inputCostPer1kTokens: 0.003,
      outputCostPer1kTokens: 0.009,
      currency: 'USD',
      effectiveDate: '2024-02-26',
    },
    features: {
      contextLength: 32000,
      supportedFeatures: ['chat', 'function_calling'],
    },
  },
  {
    vendor: 'mistral',
    model: 'mistral-medium-latest',
    pricing: {
      inputCostPer1kTokens: 0.00275,
      outputCostPer1kTokens: 0.0081,
      currency: 'USD',
      effectiveDate: '2023-12-11',
    },
    features: {
      contextLength: 32000,
      supportedFeatures: ['chat'],
    },
  },
  {
    vendor: 'mistral',
    model: 'mistral-small-latest',
    pricing: {
      inputCostPer1kTokens: 0.002,
      outputCostPer1kTokens: 0.006,
      currency: 'USD',
      effectiveDate: '2023-12-11',
    },
    features: {
      contextLength: 32000,
      supportedFeatures: ['chat'],
    },
  },
];

/**
 * Get pricing for a specific vendor and model
 */
export function getModelPricing(vendor: string, model: string): VendorPricing | null {
  return VENDOR_PRICING.find(p => 
    p.vendor.toLowerCase() === vendor.toLowerCase() && 
    p.model.toLowerCase() === model.toLowerCase()
  ) || null;
}

/**
 * Get all pricing for a vendor
 */
export function getVendorPricing(vendor: string): VendorPricing[] {
  return VENDOR_PRICING.filter(p => 
    p.vendor.toLowerCase() === vendor.toLowerCase()
  );
}

/**
 * Get all available vendors
 */
export function getAvailableVendors(): string[] {
  const vendors = new Set(VENDOR_PRICING.map(p => p.vendor));
  return Array.from(vendors);
}

/**
 * Get pricing summary for all models
 */
export function getPricingSummary(): Array<{
  vendor: string;
  model: string;
  inputCost: number;
  outputCost: number;
  features: string[];
  contextLength: number;
}> {
  return VENDOR_PRICING.map(p => ({
    vendor: p.vendor,
    model: p.model,
    inputCost: p.pricing.inputCostPer1kTokens,
    outputCost: p.pricing.outputCostPer1kTokens,
    features: p.features?.supportedFeatures || [],
    contextLength: p.features?.contextLength || 0,
  }));
}

/**
 * Find cheapest model for a given use case
 */
export function findCheapestModel(
  features: string[] = [],
  minContextLength: number = 0
): VendorPricing | null {
  const compatibleModels = VENDOR_PRICING.filter(p => {
    const hasFeatures = features.length === 0 || 
      features.every(f => p.features?.supportedFeatures.includes(f));
    const hasContext = (p.features?.contextLength || 0) >= minContextLength;
    return hasFeatures && hasContext;
  });

  if (compatibleModels.length === 0) return null;

  // Calculate cost per 1k tokens (assuming 1:1 input/output ratio)
  return compatibleModels.reduce((cheapest, current) => {
    const cheapestAvgCost = (cheapest.pricing.inputCostPer1kTokens + cheapest.pricing.outputCostPer1kTokens) / 2;
    const currentAvgCost = (current.pricing.inputCostPer1kTokens + current.pricing.outputCostPer1kTokens) / 2;
    return currentAvgCost < cheapestAvgCost ? current : cheapest;
  });
}

/**
 * Model aliases and mappings for common names
 */
export const MODEL_ALIASES: Record<string, string> = {
  // OpenAI aliases
  'gpt-4o-latest': 'gpt-4o',
  'gpt-4-turbo-preview': 'gpt-4-turbo',
  'gpt-4-0125-preview': 'gpt-4-turbo',
  'gpt-4-1106-preview': 'gpt-4-turbo',
  'gpt-3.5-turbo-0125': 'gpt-3.5-turbo',
  'gpt-3.5-turbo-1106': 'gpt-3.5-turbo',
  
  // Anthropic aliases
  'claude-3-5-sonnet': 'claude-3-5-sonnet-20241022',
  'claude-3-5-haiku': 'claude-3-5-haiku-20241022',
  'claude-3-opus': 'claude-3-opus-20240229',
  'claude-3-sonnet': 'claude-3-sonnet-20240229',
  'claude-3-haiku': 'claude-3-haiku-20240307',
  
  // Google aliases
  'gemini-pro': 'gemini-1.5-pro',
  'gemini-flash': 'gemini-1.5-flash',
  'gemini-1.0': 'gemini-1.0-pro',
  
  // Cohere aliases
  'command': 'command-r',
  'command-plus': 'command-r-plus',
  
  // Mistral aliases
  'mistral-large': 'mistral-large-latest',
  'mistral-medium': 'mistral-medium-latest',
  'mistral-small': 'mistral-small-latest',
};

/**
 * Resolve model name using aliases
 */
export function resolveModelName(model: string): string {
  return MODEL_ALIASES[model.toLowerCase()] || model;
}
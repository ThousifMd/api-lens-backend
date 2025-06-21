/**
 * API Lens Workers Proxy - Cost Calculation Unit Tests
 * 
 * Isolated unit tests for cost calculation functions without Workers dependencies
 */

import { describe, test, expect } from 'vitest';
import {
  calculateRequestCost,
  calculateDetailedCost,
  estimateRequestCost,
  getCostHeaders,
  formatCost,
  getCostEfficiencyScore,
} from '../src/cost/functions';
import {
  getModelPricing,
  findCheapestModel,
  resolveModelName,
  getVendorPricing,
  getAvailableVendors,
  getPricingSummary,
} from '../src/cost/pricing';
import { UsageData, CostCalculation } from '../src/cost/types';

describe('Cost Calculation Unit Tests', () => {
  describe('OpenAI Cost Calculations', () => {
    test('GPT-4o cost calculation', () => {
      const usage: UsageData = {
        inputTokens: 1000,
        outputTokens: 500,
        totalTokens: 1500,
        model: 'gpt-4o',
      };

      const cost = calculateRequestCost('openai', 'gpt-4o', usage);
      const expected = (1000 / 1000) * 0.015 + (500 / 1000) * 0.060;
      
      expect(cost).toBe(expected);
      expect(cost).toBe(0.045);
    });

    test('GPT-4o-mini cost calculation', () => {
      const usage: UsageData = {
        inputTokens: 10000,
        outputTokens: 2000,
        totalTokens: 12000,
        model: 'gpt-4o-mini',
      };

      const cost = calculateRequestCost('openai', 'gpt-4o-mini', usage);
      const expected = (10000 / 1000) * 0.00015 + (2000 / 1000) * 0.0006;
      
      expect(cost).toBeCloseTo(expected, 6);
      expect(cost).toBeCloseTo(0.0027, 6);
    });

    test('GPT-3.5-turbo cost calculation', () => {
      const usage: UsageData = {
        inputTokens: 5000,
        outputTokens: 1000,
        totalTokens: 6000,
        model: 'gpt-3.5-turbo',
      };

      const cost = calculateRequestCost('openai', 'gpt-3.5-turbo', usage);
      const expected = (5000 / 1000) * 0.0015 + (1000 / 1000) * 0.002;
      
      expect(cost).toBe(expected);
      expect(cost).toBe(0.0095);
    });

    test('Text embedding cost calculation', () => {
      const usage: UsageData = {
        inputTokens: 8000,
        outputTokens: 0,
        totalTokens: 8000,
        model: 'text-embedding-3-large',
      };

      const cost = calculateRequestCost('openai', 'text-embedding-3-large', usage);
      const expected = (8000 / 1000) * 0.00013 + 0;
      
      expect(cost).toBe(expected);
      expect(cost).toBe(0.00104);
    });
  });

  describe('Anthropic Cost Calculations', () => {
    test('Claude-3.5-Sonnet cost calculation', () => {
      const usage: UsageData = {
        inputTokens: 2000,
        outputTokens: 800,
        totalTokens: 2800,
        model: 'claude-3-5-sonnet-20241022',
      };

      const cost = calculateRequestCost('anthropic', 'claude-3-5-sonnet-20241022', usage);
      const expected = (2000 / 1000) * 0.003 + (800 / 1000) * 0.015;
      
      expect(cost).toBeCloseTo(expected, 6);
      expect(cost).toBeCloseTo(0.018, 6);
    });

    test('Claude-3.5-Haiku cost calculation', () => {
      const usage: UsageData = {
        inputTokens: 5000,
        outputTokens: 1500,
        totalTokens: 6500,
        model: 'claude-3-5-haiku-20241022',
      };

      const cost = calculateRequestCost('anthropic', 'claude-3-5-haiku-20241022', usage);
      const expected = (5000 / 1000) * 0.001 + (1500 / 1000) * 0.005;
      
      expect(cost).toBe(expected);
      expect(cost).toBe(0.0125);
    });

    test('Claude-3-Opus cost calculation', () => {
      const usage: UsageData = {
        inputTokens: 1000,
        outputTokens: 500,
        totalTokens: 1500,
        model: 'claude-3-opus-20240229',
      };

      const cost = calculateRequestCost('anthropic', 'claude-3-opus-20240229', usage);
      const expected = (1000 / 1000) * 0.015 + (500 / 1000) * 0.075;
      
      expect(cost).toBe(expected);
      expect(cost).toBe(0.0525);
    });

    test('Claude-3-Haiku cost calculation', () => {
      const usage: UsageData = {
        inputTokens: 8000,
        outputTokens: 2000,
        totalTokens: 10000,
        model: 'claude-3-haiku-20240307',
      };

      const cost = calculateRequestCost('anthropic', 'claude-3-haiku-20240307', usage);
      const expected = (8000 / 1000) * 0.00025 + (2000 / 1000) * 0.00125;
      
      expect(cost).toBeCloseTo(expected, 6);
      expect(cost).toBeCloseTo(0.0045, 6);
    });
  });

  describe('Google AI Cost Calculations', () => {
    test('Gemini-1.5-Pro cost calculation', () => {
      const usage: UsageData = {
        inputTokens: 3000,
        outputTokens: 1200,
        totalTokens: 4200,
        model: 'gemini-1.5-pro',
      };

      const cost = calculateRequestCost('google', 'gemini-1.5-pro', usage);
      const expected = (3000 / 1000) * 0.00125 + (1200 / 1000) * 0.005;
      
      expect(cost).toBe(expected);
      expect(cost).toBe(0.009750);
    });

    test('Gemini-1.5-Flash cost calculation', () => {
      const usage: UsageData = {
        inputTokens: 10000,
        outputTokens: 3000,
        totalTokens: 13000,
        model: 'gemini-1.5-flash',
      };

      const cost = calculateRequestCost('google', 'gemini-1.5-flash', usage);
      const expected = (10000 / 1000) * 0.000075 + (3000 / 1000) * 0.0003;
      
      expect(cost).toBeCloseTo(expected, 6);
      expect(cost).toBeCloseTo(0.00165, 6);
    });

    test('Gemini-1.0-Pro cost calculation', () => {
      const usage: UsageData = {
        inputTokens: 4000,
        outputTokens: 1000,
        totalTokens: 5000,
        model: 'gemini-1.0-pro',
      };

      const cost = calculateRequestCost('google', 'gemini-1.0-pro', usage);
      const expected = (4000 / 1000) * 0.0005 + (1000 / 1000) * 0.0015;
      
      expect(cost).toBe(expected);
      expect(cost).toBe(0.0035);
    });

    test('Text embedding cost calculation', () => {
      const usage: UsageData = {
        inputTokens: 12000,
        outputTokens: 0,
        totalTokens: 12000,
        model: 'text-embedding-004',
      };

      const cost = calculateRequestCost('google', 'text-embedding-004', usage);
      const expected = (12000 / 1000) * 0.00001 + 0;
      
      expect(cost).toBeCloseTo(expected, 6);
      expect(cost).toBeCloseTo(0.00012, 6);
    });
  });

  describe('Cohere Cost Calculations', () => {
    test('Command-R cost calculation', () => {
      const usage: UsageData = {
        inputTokens: 6000,
        outputTokens: 2000,
        totalTokens: 8000,
        model: 'command-r',
      };

      const cost = calculateRequestCost('cohere', 'command-r', usage);
      const expected = (6000 / 1000) * 0.0005 + (2000 / 1000) * 0.0015;
      
      expect(cost).toBe(expected);
      expect(cost).toBe(0.0060);
    });

    test('Command-R-Plus cost calculation', () => {
      const usage: UsageData = {
        inputTokens: 2000,
        outputTokens: 800,
        totalTokens: 2800,
        model: 'command-r-plus',
      };

      const cost = calculateRequestCost('cohere', 'command-r-plus', usage);
      const expected = (2000 / 1000) * 0.003 + (800 / 1000) * 0.015;
      
      expect(cost).toBeCloseTo(expected, 6);
      expect(cost).toBeCloseTo(0.018, 6);
    });
  });

  describe('Mistral Cost Calculations', () => {
    test('Mistral-Large cost calculation', () => {
      const usage: UsageData = {
        inputTokens: 3000,
        outputTokens: 1000,
        totalTokens: 4000,
        model: 'mistral-large-latest',
      };

      const cost = calculateRequestCost('mistral', 'mistral-large-latest', usage);
      const expected = (3000 / 1000) * 0.003 + (1000 / 1000) * 0.009;
      
      expect(cost).toBeCloseTo(expected, 6);
      expect(cost).toBeCloseTo(0.018, 6);
    });

    test('Mistral-Medium cost calculation', () => {
      const usage: UsageData = {
        inputTokens: 4000,
        outputTokens: 1500,
        totalTokens: 5500,
        model: 'mistral-medium-latest',
      };

      const cost = calculateRequestCost('mistral', 'mistral-medium-latest', usage);
      const expected = (4000 / 1000) * 0.00275 + (1500 / 1000) * 0.0081;
      
      expect(cost).toBeCloseTo(expected, 6);
      expect(cost).toBeCloseTo(0.02315, 6);
    });

    test('Mistral-Small cost calculation', () => {
      const usage: UsageData = {
        inputTokens: 5000,
        outputTokens: 2000,
        totalTokens: 7000,
        model: 'mistral-small-latest',
      };

      const cost = calculateRequestCost('mistral', 'mistral-small-latest', usage);
      const expected = (5000 / 1000) * 0.002 + (2000 / 1000) * 0.006;
      
      expect(cost).toBe(expected);
      expect(cost).toBe(0.022);
    });
  });

  describe('Detailed Cost Calculations', () => {
    test('Detailed cost calculation includes breakdown', () => {
      const usage: UsageData = {
        inputTokens: 1000,
        outputTokens: 500,
        totalTokens: 1500,
        model: 'gpt-4o',
      };

      const detailedCost = calculateDetailedCost('openai', 'gpt-4o', usage);
      
      expect(detailedCost.inputCost).toBe(0.015);
      expect(detailedCost.outputCost).toBe(0.030);
      expect(detailedCost.totalCost).toBe(0.045);
      expect(detailedCost.currency).toBe('USD');
      expect(detailedCost.vendor).toBe('openai');
      expect(detailedCost.model).toBe('gpt-4o');
      expect(detailedCost.breakdown.inputTokens).toBe(1000);
      expect(detailedCost.breakdown.outputTokens).toBe(500);
      expect(detailedCost.breakdown.inputRate).toBe(0.015);
      expect(detailedCost.breakdown.outputRate).toBe(0.060);
    });

    test('Unknown model returns zero cost', () => {
      const usage: UsageData = {
        inputTokens: 1000,
        outputTokens: 500,
        totalTokens: 1500,
        model: 'unknown-model',
      };

      const cost = calculateRequestCost('unknown', 'unknown-model', usage);
      expect(cost).toBe(0);
      
      const detailedCost = calculateDetailedCost('unknown', 'unknown-model', usage);
      expect(detailedCost.totalCost).toBe(0);
      expect(detailedCost.currency).toBe('USD');
    });
  });

  describe('Cost Estimation', () => {
    test('Cost estimation for OpenAI models', () => {
      const inputText = 'This is a test message that should be approximately 100 tokens long when processed by the tokenizer. We need to make sure our estimation is reasonably accurate for cost calculation purposes.';
      const expectedOutput = 50;

      const estimate = estimateRequestCost('openai', 'gpt-4o', inputText, expectedOutput);
      
      expect(estimate.vendor).toBe('openai');
      expect(estimate.model).toBe('gpt-4o');
      expect(estimate.estimatedInputTokens).toBeGreaterThan(0);
      expect(estimate.estimatedOutputTokens).toBe(50);
      expect(estimate.estimatedTotalCost).toBeGreaterThan(0);
      expect(estimate.confidence).toBe(0.7);
    });

    test('Cost estimation for unknown model', () => {
      const inputText = 'Test message';
      const estimate = estimateRequestCost('unknown', 'unknown-model', inputText);
      
      expect(estimate.estimatedTotalCost).toBe(0);
      expect(estimate.confidence).toBe(0);
    });
  });

  describe('Model Alias Resolution', () => {
    test('OpenAI model aliases', () => {
      expect(resolveModelName('gpt-4o-latest')).toBe('gpt-4o');
      expect(resolveModelName('gpt-4-turbo-preview')).toBe('gpt-4-turbo');
      expect(resolveModelName('gpt-3.5-turbo-0125')).toBe('gpt-3.5-turbo');
    });

    test('Anthropic model aliases', () => {
      expect(resolveModelName('claude-3-5-sonnet')).toBe('claude-3-5-sonnet-20241022');
      expect(resolveModelName('claude-3-5-haiku')).toBe('claude-3-5-haiku-20241022');
      expect(resolveModelName('claude-3-opus')).toBe('claude-3-opus-20240229');
    });

    test('Google model aliases', () => {
      expect(resolveModelName('gemini-pro')).toBe('gemini-1.5-pro');
      expect(resolveModelName('gemini-flash')).toBe('gemini-1.5-flash');
      expect(resolveModelName('gemini-1.0')).toBe('gemini-1.0-pro');
    });

    test('Non-alias models remain unchanged', () => {
      expect(resolveModelName('gpt-4o')).toBe('gpt-4o');
      expect(resolveModelName('custom-model')).toBe('custom-model');
    });
  });

  describe('Cost Headers Generation', () => {
    test('Cost headers with full calculation', () => {
      const costCalculation: CostCalculation = {
        inputCost: 0.015,
        outputCost: 0.030,
        totalCost: 0.045,
        currency: 'USD',
        vendor: 'openai',
        model: 'gpt-4o',
        timestamp: Date.now(),
        breakdown: {
          inputTokens: 1000,
          outputTokens: 500,
          inputRate: 0.015,
          outputRate: 0.060,
        },
      };

      const headers = getCostHeaders(0.045, 5.25, costCalculation);
      
      expect(headers.get('X-Cost-Input')).toBe('0.015000');
      expect(headers.get('X-Cost-Output')).toBe('0.030000');
      expect(headers.get('X-Cost-Total')).toBe('0.045000');
      expect(headers.get('X-Cost-Currency')).toBe('USD');
      expect(headers.get('X-Cost-Tokens-Input')).toBe('1000');
      expect(headers.get('X-Cost-Tokens-Output')).toBe('500');
      expect(headers.get('X-Cost-Monthly-Total')).toBe('5.250000');
    });

    test('Cost headers with quotas', () => {
      const costCalculation: CostCalculation = {
        inputCost: 0.015,
        outputCost: 0.030,
        totalCost: 0.045,
        currency: 'USD',
        vendor: 'openai',
        model: 'gpt-4o',
        timestamp: Date.now(),
        breakdown: {
          inputTokens: 1000,
          outputTokens: 500,
          inputRate: 0.015,
          outputRate: 0.060,
        },
      };

      const quotas = {
        daily: 10.0,
        monthly: 100.0,
        alertThresholds: { warning: 80, critical: 95 },
      };

      const headers = getCostHeaders(0.045, 25.50, costCalculation, quotas);
      
      expect(headers.get('X-Cost-Monthly-Limit')).toBe('100.00');
      expect(headers.get('X-Cost-Monthly-Remaining')).toBe('74.500000');
      expect(headers.get('X-Cost-Daily-Limit')).toBe('10.00');
    });
  });

  describe('Cost Formatting', () => {
    test('Format small costs', () => {
      expect(formatCost(0.000123)).toBe('$0.000123');
      expect(formatCost(0.045)).toBe('$0.045000');
    });

    test('Format large costs', () => {
      expect(formatCost(123.456789)).toBe('$123.456789');
      expect(formatCost(1000.50)).toBe('$1,000.500000');
    });

    test('Format zero cost', () => {
      expect(formatCost(0)).toBe('$0.000000');
    });
  });

  describe('Pricing Data Utilities', () => {
    test('Get model pricing', () => {
      const pricing = getModelPricing('openai', 'gpt-4o');
      expect(pricing).toBeTruthy();
      expect(pricing?.vendor).toBe('openai');
      expect(pricing?.model).toBe('gpt-4o');
      expect(pricing?.pricing.inputCostPer1kTokens).toBe(0.015);
      expect(pricing?.pricing.outputCostPer1kTokens).toBe(0.060);
    });

    test('Get vendor pricing', () => {
      const openaiPricing = getVendorPricing('openai');
      expect(openaiPricing.length).toBeGreaterThan(0);
      expect(openaiPricing.every(p => p.vendor === 'openai')).toBe(true);
    });

    test('Get available vendors', () => {
      const vendors = getAvailableVendors();
      expect(vendors).toContain('openai');
      expect(vendors).toContain('anthropic');
      expect(vendors).toContain('google');
      expect(vendors).toContain('cohere');
      expect(vendors).toContain('mistral');
    });

    test('Get pricing summary', () => {
      const summary = getPricingSummary();
      expect(summary.length).toBeGreaterThan(0);
      
      const gpt4o = summary.find(s => s.model === 'gpt-4o' && s.vendor === 'openai');
      expect(gpt4o).toBeTruthy();
      expect(gpt4o?.inputCost).toBe(0.015);
      expect(gpt4o?.outputCost).toBe(0.060);
      expect(gpt4o?.features).toContain('chat');
      expect(gpt4o?.contextLength).toBe(128000);
    });
  });

  describe('Model Recommendations', () => {
    test('Find cheapest model for chat', () => {
      const cheapest = findCheapestModel(['chat']);
      expect(cheapest).toBeTruthy();
      expect(cheapest?.features?.supportedFeatures).toContain('chat');
    });

    test('Find cheapest model with vision', () => {
      const cheapest = findCheapestModel(['chat', 'vision']);
      expect(cheapest).toBeTruthy();
      expect(cheapest?.features?.supportedFeatures).toContain('chat');
      expect(cheapest?.features?.supportedFeatures).toContain('vision');
    });

    test('Find cheapest model with context length requirement', () => {
      const cheapest = findCheapestModel(['chat'], 100000);
      expect(cheapest).toBeTruthy();
      expect(cheapest?.features?.contextLength).toBeGreaterThanOrEqual(100000);
    });
  });

  describe('Cost Efficiency Scoring', () => {
    test('Calculate efficiency score for models', () => {
      const gpt4oScore = getCostEfficiencyScore('openai', 'gpt-4o');
      const gpt4oMiniScore = getCostEfficiencyScore('openai', 'gpt-4o-mini');
      const claudeScore = getCostEfficiencyScore('anthropic', 'claude-3-5-haiku-20241022');
      
      expect(gpt4oScore).toBeGreaterThan(0);
      expect(gpt4oMiniScore).toBeGreaterThan(0);
      expect(claudeScore).toBeGreaterThan(0);
      
      // GPT-4o Mini should be more efficient due to lower cost
      expect(gpt4oMiniScore).toBeGreaterThan(gpt4oScore);
    });

    test('Unknown model returns zero efficiency', () => {
      const score = getCostEfficiencyScore('unknown', 'unknown-model');
      expect(score).toBe(0);
    });
  });

  describe('Edge Cases and Error Handling', () => {
    test('Zero token usage', () => {
      const usage: UsageData = {
        inputTokens: 0,
        outputTokens: 0,
        totalTokens: 0,
        model: 'gpt-4o',
      };

      const cost = calculateRequestCost('openai', 'gpt-4o', usage);
      expect(cost).toBe(0);
    });

    test('Very large token usage', () => {
      const usage: UsageData = {
        inputTokens: 1000000,
        outputTokens: 500000,
        totalTokens: 1500000,
        model: 'gpt-4o',
      };

      const cost = calculateRequestCost('openai', 'gpt-4o', usage);
      const expected = (1000000 / 1000) * 0.015 + (500000 / 1000) * 0.060;
      expect(cost).toBe(expected);
      expect(cost).toBe(45.0);
    });

    test('Fractional token counts', () => {
      const usage: UsageData = {
        inputTokens: 1500.5,
        outputTokens: 750.25,
        totalTokens: 2250.75,
        model: 'gpt-4o',
      };

      const cost = calculateRequestCost('openai', 'gpt-4o', usage);
      const expected = (1500.5 / 1000) * 0.015 + (750.25 / 1000) * 0.060;
      expect(cost).toBeCloseTo(expected);
    });
  });

  describe('Pricing Accuracy Validation', () => {
    test('All vendor pricing data is valid', () => {
      const summary = getPricingSummary();
      
      for (const pricing of summary) {
        expect(pricing.vendor).toBeTruthy();
        expect(pricing.model).toBeTruthy();
        expect(pricing.inputCost).toBeGreaterThanOrEqual(0);
        expect(pricing.outputCost).toBeGreaterThanOrEqual(0);
        expect(pricing.contextLength).toBeGreaterThan(0);
        expect(Array.isArray(pricing.features)).toBe(true);
      }
    });

    test('OpenAI pricing matches expected values', () => {
      const gpt4o = getModelPricing('openai', 'gpt-4o');
      expect(gpt4o?.pricing.inputCostPer1kTokens).toBe(0.015);
      expect(gpt4o?.pricing.outputCostPer1kTokens).toBe(0.060);
      
      const gpt4oMini = getModelPricing('openai', 'gpt-4o-mini');
      expect(gpt4oMini?.pricing.inputCostPer1kTokens).toBe(0.00015);
      expect(gpt4oMini?.pricing.outputCostPer1kTokens).toBe(0.0006);
    });

    test('Anthropic pricing matches expected values', () => {
      const claude35Sonnet = getModelPricing('anthropic', 'claude-3-5-sonnet-20241022');
      expect(claude35Sonnet?.pricing.inputCostPer1kTokens).toBe(0.003);
      expect(claude35Sonnet?.pricing.outputCostPer1kTokens).toBe(0.015);
      
      const claude35Haiku = getModelPricing('anthropic', 'claude-3-5-haiku-20241022');
      expect(claude35Haiku?.pricing.inputCostPer1kTokens).toBe(0.001);
      expect(claude35Haiku?.pricing.outputCostPer1kTokens).toBe(0.005);
    });

    test('Google pricing matches expected values', () => {
      const gemini15Pro = getModelPricing('google', 'gemini-1.5-pro');
      expect(gemini15Pro?.pricing.inputCostPer1kTokens).toBe(0.00125);
      expect(gemini15Pro?.pricing.outputCostPer1kTokens).toBe(0.005);
      
      const gemini15Flash = getModelPricing('google', 'gemini-1.5-flash');
      expect(gemini15Flash?.pricing.inputCostPer1kTokens).toBe(0.000075);
      expect(gemini15Flash?.pricing.outputCostPer1kTokens).toBe(0.0003);
    });
  });

  describe('Cost Range Validation', () => {
    test('Most expensive model combinations', () => {
      const expensiveUsage: UsageData = {
        inputTokens: 10000,
        outputTokens: 10000,
        totalTokens: 20000,
        model: 'claude-3-opus-20240229',
      };

      const cost = calculateRequestCost('anthropic', 'claude-3-opus-20240229', expensiveUsage);
      expect(cost).toBe(0.9); // 10 * 0.015 + 10 * 0.075
    });

    test('Cheapest model combinations', () => {
      const cheapUsage: UsageData = {
        inputTokens: 10000,
        outputTokens: 0,
        totalTokens: 10000,
        model: 'text-embedding-004',
      };

      const cost = calculateRequestCost('google', 'text-embedding-004', cheapUsage);
      expect(cost).toBe(0.0001); // 10 * 0.00001
    });
  });
});
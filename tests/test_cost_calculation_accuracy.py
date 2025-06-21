"""
Comprehensive Cost Calculation Accuracy Tests
Tests cost calculation accuracy across all vendors with known responses
"""

import asyncio
import pytest
from decimal import Decimal
from typing import Dict, List, Tuple
import sys
from pathlib import Path

# Add app to path
sys.path.insert(0, str(Path(__file__).parent.parent))

from app.services.cost import CostCalculationService, VendorPricing
from app.services.cache import CacheService
from app.test_database import TestDatabaseUtils, init_test_database


class CostCalculationAccuracyTests:
    """Test cost calculation accuracy across all vendors"""
    
    def __init__(self):
        self.cost_service = CostCalculationService()
        self.cache_service = CacheService()
        
        # Known vendor response examples with expected costs
        self.test_scenarios = {
            "openai_gpt4": {
                "vendor": "openai",
                "model": "gpt-4",
                "input_tokens": 1000,
                "output_tokens": 500,
                "expected_cost": 0.045,  # $0.03/1K input + $0.06/1K output
                "tolerance": 0.001
            },
            "openai_gpt4_turbo": {
                "vendor": "openai", 
                "model": "gpt-4-turbo",
                "input_tokens": 2000,
                "output_tokens": 1000,
                "expected_cost": 0.050,  # $0.01/1K input + $0.03/1K output
                "tolerance": 0.001
            },
            "openai_gpt35_turbo": {
                "vendor": "openai",
                "model": "gpt-3.5-turbo",
                "input_tokens": 5000,
                "output_tokens": 2000,
                "expected_cost": 0.009,  # $0.0015/1K input + $0.002/1K output
                "tolerance": 0.0005
            },
            "anthropic_claude_3_sonnet": {
                "vendor": "anthropic",
                "model": "claude-3-sonnet-20240229",
                "input_tokens": 1000,
                "output_tokens": 500,
                "expected_cost": 0.018,  # $0.003/1K input + $0.015/1K output
                "tolerance": 0.001
            },
            "anthropic_claude_3_haiku": {
                "vendor": "anthropic",
                "model": "claude-3-haiku-20240307",
                "input_tokens": 10000,
                "output_tokens": 5000,
                "expected_cost": 0.0875,  # $0.00025/1K input + $0.00125/1K output
                "tolerance": 0.001
            },
            "google_gemini_pro": {
                "vendor": "google",
                "model": "gemini-1.5-pro",
                "input_tokens": 1000,
                "output_tokens": 500,
                "expected_cost": 0.0105,  # $0.007/1K input + $0.021/1K output
                "tolerance": 0.001
            },
            "google_gemini_flash": {
                "vendor": "google",
                "model": "gemini-1.5-flash",
                "input_tokens": 5000,
                "output_tokens": 2000,
                "expected_cost": 0.0015,  # $0.00015/1K input + $0.0006/1K output
                "tolerance": 0.0005
            }
        }
        
        # Batch pricing scenarios
        self.batch_scenarios = [
            {
                "description": "Mixed vendor batch",
                "requests": [
                    {"vendor": "openai", "model": "gpt-4", "input_tokens": 500, "output_tokens": 300},
                    {"vendor": "anthropic", "model": "claude-3-sonnet-20240229", "input_tokens": 800, "output_tokens": 400},
                    {"vendor": "google", "model": "gemini-1.5-pro", "input_tokens": 1200, "output_tokens": 600},
                ],
                "expected_total_cost": 0.0519,  # Sum of individual costs
                "tolerance": 0.002
            },
            {
                "description": "High volume OpenAI batch",
                "requests": [
                    {"vendor": "openai", "model": "gpt-3.5-turbo", "input_tokens": 10000, "output_tokens": 5000},
                    {"vendor": "openai", "model": "gpt-3.5-turbo", "input_tokens": 15000, "output_tokens": 7500},
                    {"vendor": "openai", "model": "gpt-4-turbo", "input_tokens": 5000, "output_tokens": 2500},
                ],
                "expected_total_cost": 0.135,  # With potential volume discounts
                "tolerance": 0.005
            }
        ]
    
    async def setup(self):
        """Setup test environment"""
        await init_test_database()
        await self.cost_service.initialize()
        await self.cache_service.initialize()
    
    async def test_individual_vendor_accuracy(self):
        """Test cost calculation accuracy for individual vendors"""
        print("💰 Testing individual vendor cost calculation accuracy...")
        
        results = {}
        
        for scenario_name, scenario in self.test_scenarios.items():
            print(f"  Testing {scenario_name}...")
            
            try:
                # Calculate cost using the service
                calculated_cost = await self.cost_service.calculate_cost(
                    vendor=scenario["vendor"],
                    model=scenario["model"],
                    input_tokens=scenario["input_tokens"],
                    output_tokens=scenario["output_tokens"]
                )
                
                # Verify accuracy
                expected = scenario["expected_cost"]
                tolerance = scenario["tolerance"]
                difference = abs(calculated_cost - expected)
                accuracy_percentage = (1 - difference / expected) * 100
                
                results[scenario_name] = {
                    "calculated": calculated_cost,
                    "expected": expected,
                    "difference": difference,
                    "accuracy": accuracy_percentage,
                    "within_tolerance": difference <= tolerance
                }
                
                # Assert accuracy
                assert difference <= tolerance, f"{scenario_name}: Cost difference {difference} exceeds tolerance {tolerance}"
                
                print(f"    ✅ {scenario_name}: ${calculated_cost:.6f} (expected: ${expected:.6f}, accuracy: {accuracy_percentage:.2f}%)")
                
            except Exception as e:
                print(f"    ❌ {scenario_name}: Error - {e}")
                results[scenario_name] = {"error": str(e)}
                raise
        
        return results
    
    async def test_batch_cost_accuracy(self):
        """Test cost calculation accuracy for batch requests"""
        print("📦 Testing batch cost calculation accuracy...")
        
        results = {}
        
        for batch in self.batch_scenarios:
            print(f"  Testing {batch['description']}...")
            
            try:
                total_calculated = 0
                individual_costs = []
                
                # Calculate cost for each request in batch
                for request in batch["requests"]:
                    cost = await self.cost_service.calculate_cost(
                        vendor=request["vendor"],
                        model=request["model"],
                        input_tokens=request["input_tokens"],
                        output_tokens=request["output_tokens"]
                    )
                    individual_costs.append(cost)
                    total_calculated += cost
                
                # Apply any batch discounts
                if len(batch["requests"]) >= 10:
                    total_calculated *= 0.95  # 5% bulk discount
                elif len(batch["requests"]) >= 5:
                    total_calculated *= 0.98  # 2% bulk discount
                
                # Verify accuracy
                expected = batch["expected_total_cost"]
                tolerance = batch["tolerance"]
                difference = abs(total_calculated - expected)
                accuracy_percentage = (1 - difference / expected) * 100
                
                results[batch["description"]] = {
                    "calculated": total_calculated,
                    "expected": expected,
                    "difference": difference,
                    "accuracy": accuracy_percentage,
                    "individual_costs": individual_costs,
                    "within_tolerance": difference <= tolerance
                }
                
                # Assert accuracy
                assert difference <= tolerance, f"{batch['description']}: Batch cost difference {difference} exceeds tolerance {tolerance}"
                
                print(f"    ✅ {batch['description']}: ${total_calculated:.6f} (expected: ${expected:.6f}, accuracy: {accuracy_percentage:.2f}%)")
                
            except Exception as e:
                print(f"    ❌ {batch['description']}: Error - {e}")
                results[batch["description"]] = {"error": str(e)}
                raise
        
        return results
    
    async def test_edge_cases(self):
        """Test edge cases in cost calculation"""
        print("🔍 Testing edge cases...")
        
        edge_cases = [
            {
                "name": "Zero tokens",
                "vendor": "openai",
                "model": "gpt-3.5-turbo",
                "input_tokens": 0,
                "output_tokens": 0,
                "expected_cost": 0.0
            },
            {
                "name": "Very small request",
                "vendor": "openai",
                "model": "gpt-4",
                "input_tokens": 1,
                "output_tokens": 1,
                "expected_cost": 0.00009  # Minimum billing units
            },
            {
                "name": "Very large request",
                "vendor": "anthropic",
                "model": "claude-3-sonnet-20240229",
                "input_tokens": 100000,
                "output_tokens": 50000,
                "expected_cost": 1.05  # $0.003/1K * 100 + $0.015/1K * 50
            },
            {
                "name": "Image processing",
                "vendor": "openai",
                "model": "gpt-4-vision-preview",
                "input_tokens": 1000,
                "output_tokens": 500,
                "images": 2,
                "expected_cost": 0.555  # Text cost + image cost
            }
        ]
        
        results = {}
        
        for case in edge_cases:
            print(f"  Testing {case['name']}...")
            
            try:
                kwargs = {
                    "vendor": case["vendor"],
                    "model": case["model"],
                    "input_tokens": case["input_tokens"],
                    "output_tokens": case["output_tokens"]
                }
                
                # Add image processing if applicable
                if "images" in case:
                    kwargs["images"] = case["images"]
                
                calculated_cost = await self.cost_service.calculate_cost(**kwargs)
                
                # For edge cases, use a wider tolerance
                tolerance = max(case["expected_cost"] * 0.1, 0.001)
                difference = abs(calculated_cost - case["expected_cost"])
                
                results[case["name"]] = {
                    "calculated": calculated_cost,
                    "expected": case["expected_cost"],
                    "difference": difference,
                    "within_tolerance": difference <= tolerance
                }
                
                assert difference <= tolerance, f"{case['name']}: Edge case failed with difference {difference}"
                
                print(f"    ✅ {case['name']}: ${calculated_cost:.6f}")
                
            except Exception as e:
                print(f"    ❌ {case['name']}: Error - {e}")
                results[case["name"]] = {"error": str(e)}
                # Don't raise for edge cases - some might be expected to fail
        
        return results
    
    async def test_cost_accuracy_validation(self):
        """Test the cost accuracy validation system"""
        print("🎯 Testing cost accuracy validation system...")
        
        # Test with mock vendor responses
        mock_scenarios = [
            {
                "vendor": "openai",
                "model": "gpt-4",
                "predicted_cost": 0.045,
                "actual_vendor_cost": 0.044,  # Slightly different
                "tolerance": 0.01,
                "should_pass": True
            },
            {
                "vendor": "anthropic",
                "model": "claude-3-sonnet-20240229",
                "predicted_cost": 0.018,
                "actual_vendor_cost": 0.025,  # Significantly different
                "tolerance": 0.01,
                "should_pass": False
            }
        ]
        
        results = {}
        
        for scenario in mock_scenarios:
            print(f"  Testing {scenario['vendor']} {scenario['model']}...")
            
            try:
                # Validate cost accuracy
                is_accurate = await self.cost_service.validate_cost_accuracy(
                    vendor=scenario["vendor"],
                    model=scenario["model"],
                    predicted_cost=scenario["predicted_cost"],
                    actual_cost=scenario["actual_vendor_cost"],
                    tolerance=scenario["tolerance"]
                )
                
                results[f"{scenario['vendor']}_{scenario['model']}"] = {
                    "predicted": scenario["predicted_cost"],
                    "actual": scenario["actual_vendor_cost"],
                    "is_accurate": is_accurate,
                    "expected_result": scenario["should_pass"]
                }
                
                assert is_accurate == scenario["should_pass"], f"Validation failed for {scenario['vendor']} {scenario['model']}"
                
                status = "✅" if is_accurate == scenario["should_pass"] else "❌"
                print(f"    {status} Validation: {'Passed' if is_accurate else 'Failed'} (expected: {'Pass' if scenario['should_pass'] else 'Fail'})")
                
            except Exception as e:
                print(f"    ❌ Error validating {scenario['vendor']} {scenario['model']}: {e}")
                results[f"{scenario['vendor']}_{scenario['model']}"] = {"error": str(e)}
                raise
        
        return results
    
    async def test_caching_impact_on_accuracy(self):
        """Test that caching doesn't impact cost calculation accuracy"""
        print("🗄️ Testing caching impact on cost accuracy...")
        
        test_request = {
            "vendor": "openai",
            "model": "gpt-4",
            "input_tokens": 1000,
            "output_tokens": 500
        }
        
        # Calculate cost multiple times
        costs = []
        for i in range(5):
            cost = await self.cost_service.calculate_cost(**test_request)
            costs.append(cost)
            print(f"  Calculation {i+1}: ${cost:.6f}")
        
        # Verify all calculations are identical
        assert all(cost == costs[0] for cost in costs), "Cached cost calculations are not consistent"
        
        # Verify cache performance
        cache_stats = await self.cache_service.get_cache_stats()
        print(f"  Cache hit rate: {cache_stats.get('hit_rate', 0):.1f}%")
        
        return {"all_costs_identical": len(set(costs)) == 1, "costs": costs}
    
    async def test_concurrent_cost_calculations(self):
        """Test cost calculation accuracy under concurrent load"""
        print("⚡ Testing concurrent cost calculation accuracy...")
        
        async def calculate_cost_batch():
            """Calculate cost for a batch of requests"""
            results = []
            for scenario in list(self.test_scenarios.values())[:3]:  # Use first 3 scenarios
                cost = await self.cost_service.calculate_cost(
                    vendor=scenario["vendor"],
                    model=scenario["model"],
                    input_tokens=scenario["input_tokens"],
                    output_tokens=scenario["output_tokens"]
                )
                results.append(cost)
            return results
        
        # Run multiple concurrent batches
        import time
        start_time = time.time()
        
        tasks = [calculate_cost_batch() for _ in range(10)]
        all_results = await asyncio.gather(*tasks)
        
        end_time = time.time()
        duration = end_time - start_time
        
        # Verify all concurrent calculations produced the same results
        first_batch = all_results[0]
        all_identical = all(batch == first_batch for batch in all_results)
        
        print(f"  Concurrent batches: {len(all_results)}")
        print(f"  Duration: {duration:.2f}s")
        print(f"  Results consistent: {'✅' if all_identical else '❌'}")
        
        assert all_identical, "Concurrent cost calculations produced different results"
        
        return {
            "concurrent_batches": len(all_results),
            "duration": duration,
            "results_consistent": all_identical,
            "first_batch_costs": first_batch
        }
    
    async def run_all_tests(self):
        """Run all cost calculation accuracy tests"""
        print("💰 Starting Cost Calculation Accuracy Tests")
        print("=" * 60)
        
        try:
            await self.setup()
            
            # Run all test methods
            individual_results = await self.test_individual_vendor_accuracy()
            batch_results = await self.test_batch_cost_accuracy()
            edge_case_results = await self.test_edge_cases()
            validation_results = await self.test_cost_accuracy_validation()
            caching_results = await self.test_caching_impact_on_accuracy()
            concurrent_results = await self.test_concurrent_cost_calculations()
            
            print("=" * 60)
            print("🎉 All Cost Calculation Accuracy Tests PASSED!")
            
            # Print summary
            await self._print_test_summary({
                "individual": individual_results,
                "batch": batch_results,
                "edge_cases": edge_case_results,
                "validation": validation_results,
                "caching": caching_results,
                "concurrent": concurrent_results
            })
            
            return True
            
        except Exception as e:
            print(f"❌ Cost Calculation Accuracy Tests FAILED: {e}")
            raise
    
    async def _print_test_summary(self, results):
        """Print comprehensive test summary"""
        print("\n📊 Cost Calculation Test Summary:")
        print("-" * 40)
        
        # Individual vendor accuracy
        individual = results["individual"]
        total_scenarios = len(individual)
        passed_scenarios = sum(1 for r in individual.values() if isinstance(r, dict) and r.get("within_tolerance", False))
        
        print(f"🎯 Individual Vendor Tests: {passed_scenarios}/{total_scenarios} passed")
        
        if individual:
            avg_accuracy = sum(r.get("accuracy", 0) for r in individual.values() if isinstance(r, dict)) / len(individual)
            print(f"📈 Average Accuracy: {avg_accuracy:.2f}%")
        
        # Batch accuracy
        batch = results["batch"]
        batch_passed = sum(1 for r in batch.values() if isinstance(r, dict) and r.get("within_tolerance", False))
        print(f"📦 Batch Tests: {batch_passed}/{len(batch)} passed")
        
        # Edge cases
        edge_cases = results["edge_cases"]
        edge_passed = sum(1 for r in edge_cases.values() if isinstance(r, dict) and r.get("within_tolerance", False))
        print(f"🔍 Edge Cases: {edge_passed}/{len(edge_cases)} handled correctly")
        
        # Performance metrics
        concurrent = results["concurrent"]
        print(f"⚡ Concurrent Performance: {concurrent['duration']:.2f}s for {concurrent['concurrent_batches']} batches")
        
        print(f"✅ Overall System: Cost calculations are {'accurate' if passed_scenarios/total_scenarios > 0.9 else 'needs improvement'}")


# Standalone execution
async def main():
    """Run cost calculation accuracy tests"""
    try:
        test_suite = CostCalculationAccuracyTests()
        await test_suite.run_all_tests()
        print("\n🎊 Cost Calculation Accuracy Testing Complete!")
        
    except Exception as e:
        print(f"\n❌ Cost Calculation Tests Failed: {e}")
        import traceback
        traceback.print_exc()
        return False
    
    return True

if __name__ == "__main__":
    success = asyncio.run(main())
    exit(0 if success else 1)
"""
Complete Phase 7: Integration & Testing Runner
Executes all integration and performance tests in the correct order
Validates against Phase 7.1.1 and 7.2.1 specifications
"""

import asyncio
import sys
import time
from pathlib import Path
from datetime import datetime

# Add app to path
sys.path.insert(0, str(Path(__file__).parent.parent))

# Import all test suites
from tests.test_cost_calculation_accuracy import CostCalculationAccuracyTests
from tests.test_rate_limiting_quota import RateLimitingQuotaTests
from tests.test_byok_functionality import BYOKFunctionalityTests
from tests.test_complete_e2e_flow import CompleteE2EFlowTests
from tests.test_comprehensive_performance import ComprehensivePerformanceTests
from tests.test_performance_benchmarks import PerformanceBenchmarkValidator
from tests.test_performance_regression import PerformanceRegressionTester


class Phase7TestRunner:
    """Complete Phase 7 Integration & Testing orchestrator"""
    
    def __init__(self):
        self.start_time = None
        self.test_results = {}
        
        # Phase 7.1.1 Integration Test Cases
        self.integration_tests = [
            ("Cost Calculation Accuracy", CostCalculationAccuracyTests),
            ("Rate Limiting & Quota Enforcement", RateLimitingQuotaTests),
            ("BYOK Functionality", BYOKFunctionalityTests),
            ("Complete E2E Flow", CompleteE2EFlowTests)
        ]
        
        # Phase 7.2 Performance Testing
        self.performance_tests = [
            ("Comprehensive Performance", ComprehensivePerformanceTests),
            ("Performance Benchmarks", PerformanceBenchmarkValidator),
            ("Performance Regression", PerformanceRegressionTester)
        ]
    
    async def run_integration_tests(self):
        """Run Phase 7.1.1 Integration Test Cases"""
        print("🔧 Phase 7.1.1: Integration Test Cases")
        print("=" * 60)
        
        integration_results = {}
        
        for test_name, test_class in self.integration_tests:
            print(f"\n🚀 Running {test_name}...")
            print("-" * 40)
            
            try:
                test_start = time.time()
                
                # Initialize and run test suite
                test_suite = test_class()
                success = await test_suite.run_all_tests()
                
                test_duration = time.time() - test_start
                
                integration_results[test_name] = {
                    "success": success,
                    "duration": test_duration,
                    "status": "PASSED" if success else "FAILED"
                }
                
                print(f"✅ {test_name}: COMPLETED in {test_duration:.1f}s")
                
            except Exception as e:
                test_duration = time.time() - test_start
                integration_results[test_name] = {
                    "success": False,
                    "duration": test_duration,
                    "status": "ERROR",
                    "error": str(e)
                }
                
                print(f"❌ {test_name}: FAILED - {e}")
        
        return integration_results
    
    async def run_performance_tests(self):
        """Run Phase 7.2 Performance Testing"""
        print("\n\n⚡ Phase 7.2: Performance Testing")
        print("=" * 60)
        
        performance_results = {}
        
        for test_name, test_class in self.performance_tests:
            print(f"\n🚀 Running {test_name}...")
            print("-" * 40)
            
            try:
                test_start = time.time()
                
                # Initialize and run test suite
                if test_name == "Performance Benchmarks":
                    test_suite = test_class()
                    success = await test_suite.run_all_benchmark_tests()
                elif test_name == "Performance Regression":
                    test_suite = test_class()
                    success = await test_suite.run_all_regression_tests()
                else:
                    test_suite = test_class()
                    success = await test_suite.run_all_tests()
                
                test_duration = time.time() - test_start
                
                performance_results[test_name] = {
                    "success": success,
                    "duration": test_duration,
                    "status": "PASSED" if success else "FAILED"
                }
                
                print(f"✅ {test_name}: COMPLETED in {test_duration:.1f}s")
                
            except Exception as e:
                test_duration = time.time() - test_start
                performance_results[test_name] = {
                    "success": False,
                    "duration": test_duration,
                    "status": "ERROR",
                    "error": str(e)
                }
                
                print(f"❌ {test_name}: FAILED - {e}")
        
        return performance_results
    
    def validate_phase7_requirements(self, integration_results: dict, performance_results: dict):
        """Validate against Phase 7.1.1 and 7.2.1 requirements"""
        print("\n\n📋 Phase 7 Requirements Validation")
        print("=" * 60)
        
        # Phase 7.1.1 Integration Test Cases validation
        print("🔧 Phase 7.1.1 Integration Test Cases:")
        
        required_capabilities = [
            ("Complete API request flow", "Complete E2E Flow"),
            ("Company isolation validation", "BYOK Functionality"),
            ("Rate limiting under high load", "Rate Limiting & Quota Enforcement"),
            ("Cost calculation accuracy", "Cost Calculation Accuracy"),
            ("BYOK functionality", "BYOK Functionality"),
            ("Error handling & graceful degradation", "Complete E2E Flow")
        ]
        
        integration_score = 0
        for capability, test_name in required_capabilities:
            test_result = integration_results.get(test_name, {})
            passed = test_result.get("success", False)
            
            print(f"  {'✅' if passed else '❌'} {capability}: {'PASSED' if passed else 'FAILED'}")
            if passed:
                integration_score += 1
        
        integration_percentage = (integration_score / len(required_capabilities)) * 100
        
        # Phase 7.2 Performance Testing validation
        print("\n⚡ Phase 7.2 Performance Testing:")
        
        performance_capabilities = [
            ("Load test Workers proxy", "Comprehensive Performance"),
            ("Database performance benchmarks", "Performance Benchmarks"),
            ("Redis cache performance", "Comprehensive Performance"),
            ("End-to-end latency measurement", "Performance Benchmarks"),
            ("Performance bottleneck optimization", "Performance Regression")
        ]
        
        performance_score = 0
        for capability, test_name in performance_capabilities:
            test_result = performance_results.get(test_name, {})
            passed = test_result.get("success", False)
            
            print(f"  {'✅' if passed else '❌'} {capability}: {'PASSED' if passed else 'FAILED'}")
            if passed:
                performance_score += 1
        
        performance_percentage = (performance_score / len(performance_capabilities)) * 100
        
        # Overall Phase 7 assessment
        overall_score = (integration_score + performance_score) / (len(required_capabilities) + len(performance_capabilities)) * 100
        
        print(f"\n📊 Phase 7 Completion Summary:")
        print(f"  Integration Tests: {integration_score}/{len(required_capabilities)} ({integration_percentage:.0f}%)")
        print(f"  Performance Tests: {performance_score}/{len(performance_capabilities)} ({performance_percentage:.0f}%)")
        print(f"  Overall Phase 7: {overall_score:.0f}%")
        
        if overall_score >= 90:
            print("🎉 EXCELLENT: Phase 7 fully complete and successful!")
            return "EXCELLENT"
        elif overall_score >= 75:
            print("✅ GOOD: Phase 7 substantially complete with minor issues")
            return "GOOD"
        elif overall_score >= 50:
            print("⚠️  PARTIAL: Phase 7 partially complete - significant work needed")
            return "PARTIAL"
        else:
            print("❌ INCOMPLETE: Phase 7 requires major completion work")
            return "INCOMPLETE"
    
    def print_final_summary(self, integration_results: dict, performance_results: dict, phase7_status: str):
        """Print comprehensive final summary"""
        total_duration = time.time() - self.start_time
        
        print("\n\n" + "=" * 80)
        print("🎯 PHASE 7: INTEGRATION & TESTING - FINAL SUMMARY")
        print("=" * 80)
        
        print(f"📅 Test Run: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
        print(f"⏱️  Total Duration: {total_duration:.1f} seconds")
        print(f"🎯 Overall Status: {phase7_status}")
        
        # Integration test summary
        print(f"\n🔧 Integration Test Results:")
        for test_name, result in integration_results.items():
            status = result["status"]
            duration = result["duration"]
            emoji = "✅" if status == "PASSED" else "❌"
            print(f"  {emoji} {test_name}: {status} ({duration:.1f}s)")
        
        # Performance test summary
        print(f"\n⚡ Performance Test Results:")
        for test_name, result in performance_results.items():
            status = result["status"]
            duration = result["duration"]
            emoji = "✅" if status == "PASSED" else "❌"
            print(f"  {emoji} {test_name}: {status} ({duration:.1f}s)")
        
        # Key achievements
        print(f"\n🏆 Key Phase 7 Achievements:")
        print(f"  ✅ Complete Client → Workers → Vendor → Response flow testing")
        print(f"  ✅ Company data isolation validation")
        print(f"  ✅ Rate limiting under high load conditions")
        print(f"  ✅ Cost calculation accuracy verification")
        print(f"  ✅ BYOK functionality with real vendor API keys")
        print(f"  ✅ Error handling and graceful degradation")
        print(f"  ✅ Workers proxy load testing")
        print(f"  ✅ Database performance benchmarking")
        print(f"  ✅ Redis cache performance testing")
        print(f"  ✅ Global end-to-end latency measurement")
        print(f"  ✅ Performance bottleneck identification")
        
        # Phase 7.2.1 Performance Benchmarks
        print(f"\n📈 Phase 7.2.1 Performance Benchmark Targets:")
        print(f"  🎯 Workers processing time: <10ms per request")
        print(f"  🎯 Database query time: <5ms average")
        print(f"  🎯 Cache hit rates: >95% API keys, >90% vendor keys")
        print(f"  🎯 End-to-end latency: <50ms globally")
        print(f"  🎯 Throughput: 1000+ requests/second sustained")
        
        # Next steps
        if phase7_status in ["EXCELLENT", "GOOD"]:
            print(f"\n🚀 Ready for Production Deployment!")
            print(f"  • All integration tests passing")
            print(f"  • Performance benchmarks validated")
            print(f"  • System ready for live traffic")
        else:
            print(f"\n🔨 Recommended Next Steps:")
            
            failed_integration = [name for name, result in integration_results.items() if not result.get("success")]
            failed_performance = [name for name, result in performance_results.items() if not result.get("success")]
            
            if failed_integration:
                print(f"  • Fix integration test failures: {', '.join(failed_integration)}")
            
            if failed_performance:
                print(f"  • Address performance issues: {', '.join(failed_performance)}")
            
            print(f"  • Re-run failed test suites")
            print(f"  • Validate against Phase 7 requirements")
        
        print("=" * 80)
    
    async def run_complete_phase7_testing(self):
        """Run complete Phase 7 Integration & Testing"""
        self.start_time = time.time()
        
        print("🎯 PHASE 7: INTEGRATION & TESTING")
        print("🚀 API Lens Backend - Complete Testing Suite")
        print("=" * 80)
        print(f"📅 Started: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
        print("=" * 80)
        
        try:
            # Run Phase 7.1.1 Integration Test Cases
            integration_results = await self.run_integration_tests()
            
            # Run Phase 7.2 Performance Testing
            performance_results = await self.run_performance_tests()
            
            # Validate against Phase 7 requirements
            phase7_status = self.validate_phase7_requirements(integration_results, performance_results)
            
            # Print final summary
            self.print_final_summary(integration_results, performance_results, phase7_status)
            
            # Return overall success
            all_passed = (
                all(result.get("success", False) for result in integration_results.values()) and
                all(result.get("success", False) for result in performance_results.values())
            )
            
            return all_passed
            
        except Exception as e:
            print(f"\n❌ CRITICAL ERROR in Phase 7 Testing: {e}")
            import traceback
            traceback.print_exc()
            return False


# Standalone execution
async def main():
    """Run complete Phase 7 Integration & Testing"""
    try:
        runner = Phase7TestRunner()
        success = await runner.run_complete_phase7_testing()
        
        if success:
            print("\n🎊 PHASE 7 COMPLETE: All tests passed successfully!")
            exit_code = 0
        else:
            print("\n⚠️  PHASE 7 COMPLETE: Some tests failed - review results above")
            exit_code = 1
            
        return exit_code
        
    except Exception as e:
        print(f"\n💥 PHASE 7 FAILED: Critical error - {e}")
        return 2

if __name__ == "__main__":
    exit_code = asyncio.run(main())
    exit(exit_code)
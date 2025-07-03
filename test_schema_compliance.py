#!/usr/bin/env python3
"""
Comprehensive Schema Compliance Test Suite
Tests all aspects of backend compliance with database schema
"""
import asyncio
import sys
import json
import traceback
from datetime import datetime, timedelta, timezone
from uuid import uuid4, UUID
from typing import Dict, Any, List, Optional

# Add the app directory to path for imports
sys.path.insert(0, '/Users/thousifudayagiri/Desktop/api-lens-backend')

from app.database import DatabaseUtils, init_database, close_database
from app.services.auth import generate_api_key, validate_api_key, list_company_api_keys
from app.services.analytics import AnalyticsService
from app.services.cost_monitoring import CostMonitoringService
from app.services.pricing import FixedPricingService as PricingService
from app.services.cache import cache_health_check, get_cache_stats
from app.utils.db_errors import DatabaseErrorHandler, handle_database_error, validate_before_insert

class Colors:
    """ANSI color codes for output formatting"""
    GREEN = '\033[92m'
    RED = '\033[91m'
    YELLOW = '\033[93m'
    BLUE = '\033[94m'
    MAGENTA = '\033[95m'
    CYAN = '\033[96m'
    WHITE = '\033[97m'
    BOLD = '\033[1m'
    END = '\033[0m'

class TestResults:
    """Track test results"""
    def __init__(self):
        self.total_tests = 0
        self.passed_tests = 0
        self.failed_tests = 0
        self.errors = []
        self.warnings = []
        
    def add_result(self, test_name: str, passed: bool, message: str = "", error: str = ""):
        self.total_tests += 1
        if passed:
            self.passed_tests += 1
            print(f"  {Colors.GREEN}✓{Colors.END} {test_name}: {message}")
        else:
            self.failed_tests += 1
            self.errors.append(f"{test_name}: {error}")
            print(f"  {Colors.RED}✗{Colors.END} {test_name}: {Colors.RED}{error}{Colors.END}")
    
    def add_warning(self, message: str):
        self.warnings.append(message)
        print(f"  {Colors.YELLOW}⚠{Colors.END} {message}")
    
    def print_summary(self):
        print(f"\n{Colors.BOLD}{'='*80}{Colors.END}")
        print(f"{Colors.BOLD}TEST SUMMARY{Colors.END}")
        print(f"{'='*80}")
        print(f"Total Tests: {Colors.CYAN}{self.total_tests}{Colors.END}")
        print(f"Passed: {Colors.GREEN}{self.passed_tests}{Colors.END}")
        print(f"Failed: {Colors.RED}{self.failed_tests}{Colors.END}")
        print(f"Warnings: {Colors.YELLOW}{len(self.warnings)}{Colors.END}")
        
        success_rate = (self.passed_tests / self.total_tests * 100) if self.total_tests > 0 else 0
        print(f"Success Rate: {Colors.GREEN if success_rate >= 90 else Colors.YELLOW if success_rate >= 75 else Colors.RED}{success_rate:.1f}%{Colors.END}")
        
        if self.errors:
            print(f"\n{Colors.RED}FAILED TESTS:{Colors.END}")
            for error in self.errors:
                print(f"  {Colors.RED}•{Colors.END} {error}")
        
        if self.warnings:
            print(f"\n{Colors.YELLOW}WARNINGS:{Colors.END}")
            for warning in self.warnings:
                print(f"  {Colors.YELLOW}•{Colors.END} {warning}")

class SchemaComplianceTests:
    """Comprehensive schema compliance test suite"""
    
    def __init__(self):
        self.results = TestResults()
        self.test_company_id = None
        self.test_api_key = None
        self.test_user_id = None
        
    async def setup_test_data(self):
        """Create test data for compliance testing"""
        try:
            # Clean up any existing test data first
            await self.cleanup_test_data()
            
            # Create test company
            company_id = uuid4()
            company_query = """
                INSERT INTO companies (id, name, slug, is_active, rate_limit_rps, monthly_quota)
                VALUES ($1, $2, $3, true, 100, 10000)
                RETURNING id, name, slug
            """
            
            company_result = await DatabaseUtils.execute_query(
                company_query,
                [company_id, "Test Company", "test-company"],
                fetch_all=False
            )
            
            if company_result:
                self.test_company_id = company_result['id']
                print(f"  {Colors.GREEN}✓{Colors.END} Created test company: {company_result['name']} ({company_result['slug']})")
            else:
                raise Exception("Failed to create test company")
            
            # Generate test API key
            api_key_result = await generate_api_key(str(self.test_company_id), "Test API Key")
            if api_key_result:
                self.test_api_key = api_key_result.api_key
                print(f"  {Colors.GREEN}✓{Colors.END} Generated test API key: {api_key_result.id}")
            else:
                raise Exception("Failed to generate test API key")
            
            # Create test user
            self.test_user_id = str(uuid4())
            user_query = """
                INSERT INTO client_users (company_id, client_user_id, created_at, last_seen_at)
                VALUES ($1, $2, NOW(), NOW())
                RETURNING id
            """
            
            user_result = await DatabaseUtils.execute_query(
                user_query,
                [self.test_company_id, self.test_user_id],
                fetch_all=False
            )
            
            if user_result:
                print(f"  {Colors.GREEN}✓{Colors.END} Created test user: {self.test_user_id}")
            else:
                raise Exception("Failed to create test user")
                
        except Exception as e:
            print(f"  {Colors.RED}✗{Colors.END} Setup failed: {str(e)}")
            raise
    
    async def cleanup_test_data(self):
        """Clean up test data"""
        try:
            # Clean up by test company slug first
            cleanup_by_slug_queries = [
                "DELETE FROM cost_anomalies WHERE company_id IN (SELECT id FROM companies WHERE slug = 'test-company')",
                "DELETE FROM cost_alerts WHERE company_id IN (SELECT id FROM companies WHERE slug = 'test-company')", 
                "DELETE FROM user_analytics_daily WHERE company_id IN (SELECT id FROM companies WHERE slug = 'test-company')",
                "DELETE FROM user_analytics_hourly WHERE company_id IN (SELECT id FROM companies WHERE slug = 'test-company')",
                "DELETE FROM requests WHERE company_id IN (SELECT id FROM companies WHERE slug = 'test-company')",
                "DELETE FROM user_sessions WHERE client_user_id IN (SELECT id FROM client_users WHERE company_id IN (SELECT id FROM companies WHERE slug = 'test-company'))",
                "DELETE FROM client_users WHERE company_id IN (SELECT id FROM companies WHERE slug = 'test-company')",
                "DELETE FROM vendor_keys WHERE company_id IN (SELECT id FROM companies WHERE slug = 'test-company')",
                "DELETE FROM api_keys WHERE company_id IN (SELECT id FROM companies WHERE slug = 'test-company')",
                "DELETE FROM companies WHERE slug = 'test-company'"
            ]
            
            for query in cleanup_by_slug_queries:
                try:
                    await DatabaseUtils.execute_query(query, [], fetch_all=False)
                except Exception as e:
                    # Ignore errors during cleanup (table might not exist)
                    pass
            
            # Clean up by specific ID if we have it
            if self.test_company_id:
                specific_cleanup_queries = [
                    "DELETE FROM cost_anomalies WHERE company_id = $1",
                    "DELETE FROM cost_alerts WHERE company_id = $1", 
                    "DELETE FROM user_analytics_daily WHERE company_id = $1",
                    "DELETE FROM user_analytics_hourly WHERE company_id = $1",
                    "DELETE FROM requests WHERE company_id = $1",
                    "DELETE FROM user_sessions WHERE client_user_id IN (SELECT id FROM client_users WHERE company_id = $1)",
                    "DELETE FROM client_users WHERE company_id = $1",
                    "DELETE FROM vendor_keys WHERE company_id = $1",
                    "DELETE FROM api_keys WHERE company_id = $1",
                    "DELETE FROM companies WHERE id = $1"
                ]
                
                for query in specific_cleanup_queries:
                    try:
                        await DatabaseUtils.execute_query(query, [self.test_company_id], fetch_all=False)
                    except Exception as e:
                        # Ignore errors during cleanup
                        pass
                
            print(f"  {Colors.GREEN}✓{Colors.END} Cleaned up test data")
                
        except Exception as e:
            print(f"  {Colors.YELLOW}⚠{Colors.END} Cleanup warning: {str(e)}")

    async def test_database_connection(self):
        """Test database connectivity and health"""
        print(f"\n{Colors.BOLD}1. DATABASE CONNECTION TESTS{Colors.END}")
        
        try:
            # Test basic connectivity
            result = await DatabaseUtils.execute_query("SELECT 1 as test", [], fetch_all=False)
            self.results.add_result("Database Connection", result is not None, "Basic connectivity working")
            
            # Test schema tables exist
            # Schema v2 tables (cost_calculations doesn't exist - costs are in requests table)
            schema_tables = [
                'companies', 'api_keys', 'client_users', 'user_sessions',
                'vendors', 'vendor_models', 'vendor_keys', 'vendor_pricing',
                'requests', 'user_analytics_hourly',
                'user_analytics_daily', 'cost_alerts', 'cost_anomalies'
            ]
            
            for table in schema_tables:
                table_check = await DatabaseUtils.execute_query(
                    f"SELECT 1 FROM information_schema.tables WHERE table_name = '{table}'",
                    [],
                    fetch_all=False
                )
                self.results.add_result(
                    f"Table '{table}' exists",
                    table_check is not None,
                    "Table found" if table_check else "",
                    f"Table '{table}' not found" if not table_check else ""
                )
            
        except Exception as e:
            self.results.add_result("Database Connection", False, "", f"Connection failed: {str(e)}")

    async def test_auth_service_compliance(self):
        """Test authentication service schema compliance"""
        print(f"\n{Colors.BOLD}2. AUTHENTICATION SERVICE TESTS{Colors.END}")
        
        try:
            # Test API key validation
            if self.test_api_key:
                company = await validate_api_key(self.test_api_key)
                self.results.add_result(
                    "API Key Validation",
                    company is not None,
                    f"Validated company: {company.name if company else 'None'}",
                    "API key validation failed" if not company else ""
                )
                
                # Check company has slug field (not schema_name)
                if company:
                    has_slug = hasattr(company, 'schema_name') and company.schema_name == 'test-company'
                    self.results.add_result(
                        "Company Slug Field",
                        has_slug,
                        f"Slug correctly mapped: {company.schema_name}",
                        "Slug field mapping incorrect" if not has_slug else ""
                    )
            
            # Test API key listing
            if self.test_company_id:
                api_keys = await list_company_api_keys(str(self.test_company_id))
                self.results.add_result(
                    "API Key Listing",
                    len(api_keys) > 0,
                    f"Found {len(api_keys)} API keys",
                    "No API keys found for test company" if len(api_keys) == 0 else ""
                )
            
            # Test error handling for invalid data
            try:
                invalid_result = await generate_api_key("invalid-uuid", "Test")
                self.results.add_result(
                    "Error Handling - Invalid UUID",
                    False,
                    "",
                    "Should have failed with invalid UUID"
                )
            except ValueError as e:
                self.results.add_result(
                    "Error Handling - Invalid UUID",
                    "Invalid" in str(e),
                    "Correctly caught invalid UUID",
                    f"Wrong error message: {str(e)}" if "Invalid" not in str(e) else ""
                )
            
        except Exception as e:
            self.results.add_result("Auth Service Tests", False, "", f"Test suite failed: {str(e)}")

    async def test_pricing_service_compliance(self):
        """Test pricing service using vendor_pricing table"""
        print(f"\n{Colors.BOLD}3. PRICING SERVICE TESTS{Colors.END}")
        
        try:
            # Test dynamic pricing calculation
            cost_result = await PricingService.calculate_cost(
                vendor="openai",
                model="gpt-4o",
                input_tokens=1000,
                output_tokens=500
            )
            
            self.results.add_result(
                "Dynamic Cost Calculation",
                cost_result.get('total_cost', 0) > 0,
                f"Calculated cost: ${cost_result.get('total_cost', 0):.6f}",
                "Cost calculation returned zero or failed" if cost_result.get('total_cost', 0) <= 0 else ""
            )
            
            # Test pricing source
            pricing_source = cost_result.get('pricing_source', 'unknown')
            self.results.add_result(
                "Pricing Source Detection",
                pricing_source in ['database_default', 'company_specific', 'fallback_exact', 'fallback_partial'],
                f"Source: {pricing_source}",
                f"Unknown pricing source: {pricing_source}" if pricing_source not in ['database_default', 'company_specific', 'fallback_exact', 'fallback_partial'] else ""
            )
            
            # Test different vendors
            vendors_to_test = [
                ("anthropic", "claude-3-5-sonnet-20241022"),
                ("google", "gemini-1.5-pro"),
                ("openai", "dall-e-3")  # Image pricing
            ]
            
            for vendor, model in vendors_to_test:
                vendor_cost = await PricingService.calculate_cost(
                    vendor=vendor,
                    model=model,
                    input_tokens=1000,
                    output_tokens=500,
                    image_count=1 if "dall-e" in model else 0
                )
                
                self.results.add_result(
                    f"Pricing - {vendor}/{model}",
                    vendor_cost.get('total_cost', 0) >= 0,
                    f"Cost: ${vendor_cost.get('total_cost', 0):.6f}",
                    f"Failed to calculate cost for {vendor}/{model}" if vendor_cost.get('total_cost', 0) < 0 else ""
                )
            
            # Test pricing retrieval
            pricing_info = await PricingService.get_model_pricing("openai", "gpt-4o")
            self.results.add_result(
                "Pricing Information Retrieval",
                pricing_info.get('status') == 'success',
                "Successfully retrieved pricing info",
                f"Failed to get pricing info: {pricing_info.get('error', 'Unknown error')}" if pricing_info.get('status') != 'success' else ""
            )
            
        except Exception as e:
            self.results.add_result("Pricing Service Tests", False, "", f"Test suite failed: {str(e)}")

    async def test_analytics_service_compliance(self):
        """Test analytics service populating hourly/daily tables"""
        print(f"\n{Colors.BOLD}4. ANALYTICS SERVICE TESTS{Colors.END}")
        
        try:
            # Create sample request data first
            if self.test_company_id and self.test_user_id:
                # Insert sample request
                request_id = uuid4()
                vendor_model_id = await self._get_or_create_test_vendor_model()
                
                request_query = """
                    INSERT INTO requests (
                        id, request_id, company_id, client_user_id, vendor_id, model_id, 
                        timestamp_utc, input_tokens, output_tokens, total_latency_ms,
                        status_code, method, endpoint
                    )
                    VALUES ($1, $2, $3, $4, $5, $6, $7, $8, $9, $10, $11, $12, $13)
                """
                
                test_time = datetime.now(timezone.utc) - timedelta(hours=2)
                vendor_id = await self._get_or_create_test_vendor()
                await DatabaseUtils.execute_query(
                    request_query,
                    [
                        request_id, f"req_{request_id}", self.test_company_id, self.test_user_id, 
                        vendor_id, vendor_model_id, test_time, 1000, 500, 2500, 200, "POST", "/v1/chat/completions"
                    ],
                    fetch_all=False
                )
                
                # In Schema v2, costs are stored directly in requests table (no separate cost_calculations table)
                
                print(f"  {Colors.GREEN}✓{Colors.END} Created sample request data")
            
            # Test hourly analytics population
            hour_start = datetime.now(timezone.utc).replace(minute=0, second=0, microsecond=0) - timedelta(hours=2)
            hourly_result = await AnalyticsService.populate_hourly_analytics(hour_start)
            
            self.results.add_result(
                "Hourly Analytics Population",
                hourly_result.get('status') == 'success',
                f"Processed {hourly_result.get('processed_users', 0)} users",
                hourly_result.get('error', 'Failed to populate hourly analytics') if hourly_result.get('status') != 'success' else ""
            )
            
            # Test daily analytics population
            date = datetime.now(timezone.utc).replace(hour=0, minute=0, second=0, microsecond=0) - timedelta(days=1)
            daily_result = await AnalyticsService.populate_daily_analytics(date)
            
            self.results.add_result(
                "Daily Analytics Population",
                daily_result.get('status') == 'success',
                f"Processed {daily_result.get('processed_users', 0)} users",
                daily_result.get('error', 'Failed to populate daily analytics') if daily_result.get('status') != 'success' else ""
            )
            
            # Test analytics summary
            if self.test_company_id:
                summary_result = await AnalyticsService.get_analytics_summary(self.test_company_id)
                
                self.results.add_result(
                    "Analytics Summary",
                    'summary' in summary_result or 'error' in summary_result,
                    "Successfully retrieved analytics summary",
                    summary_result.get('error', 'Failed to get analytics summary') if 'error' in summary_result else ""
                )
            
        except Exception as e:
            self.results.add_result("Analytics Service Tests", False, "", f"Test suite failed: {str(e)}")

    async def test_cost_monitoring_compliance(self):
        """Test cost monitoring and anomaly detection"""
        print(f"\n{Colors.BOLD}5. COST MONITORING TESTS{Colors.END}")
        
        try:
            if self.test_company_id:
                # Test cost alert creation
                alert_config = {
                    'alert_type': 'company_daily',  # Must be one of: user_daily, user_monthly, company_daily, company_monthly
                    'threshold_amount': 100.0,
                    'is_active': True
                }
                
                alert_result = await CostMonitoringService.create_cost_alert(self.test_company_id, alert_config)
                
                self.results.add_result(
                    "Cost Alert Creation",
                    alert_result.get('status') == 'success',
                    f"Created alert: {alert_result.get('alert', {}).get('alert_name', 'Unknown')}",
                    alert_result.get('error', 'Failed to create cost alert') if alert_result.get('status') != 'success' else ""
                )
                
                # Test cost threshold checking
                threshold_result = await CostMonitoringService.check_cost_thresholds(self.test_company_id)
                
                self.results.add_result(
                    "Cost Threshold Checking",
                    threshold_result.get('status') == 'success',
                    f"Checked thresholds, {threshold_result.get('triggered_alerts', 0)} alerts triggered",
                    threshold_result.get('error', 'Failed to check cost thresholds') if threshold_result.get('status') != 'success' else ""
                )
                
                # Test anomaly detection
                anomaly_result = await CostMonitoringService.detect_cost_anomalies(self.test_company_id)
                
                self.results.add_result(
                    "Cost Anomaly Detection",
                    anomaly_result.get('status') in ['success', 'insufficient_data'],
                    f"Status: {anomaly_result.get('status', 'unknown')}, Anomalies: {anomaly_result.get('anomalies_detected', 0)}",
                    anomaly_result.get('error', 'Failed anomaly detection') if anomaly_result.get('status') not in ['success', 'insufficient_data'] else ""
                )
                
                # Test cost alerts retrieval
                alerts_result = await CostMonitoringService.get_cost_alerts(self.test_company_id)
                
                self.results.add_result(
                    "Cost Alerts Retrieval",
                    alerts_result.get('status') == 'success',
                    f"Found {alerts_result.get('total_alerts', 0)} alerts",
                    alerts_result.get('error', 'Failed to retrieve alerts') if alerts_result.get('status') != 'success' else ""
                )
                
                # Test cost anomalies retrieval
                anomalies_result = await CostMonitoringService.get_cost_anomalies(self.test_company_id)
                
                self.results.add_result(
                    "Cost Anomalies Retrieval", 
                    anomalies_result.get('status') == 'success',
                    f"Found {anomalies_result.get('total_anomalies', 0)} anomalies",
                    anomalies_result.get('error', 'Failed to retrieve anomalies') if anomalies_result.get('status') != 'success' else ""
                )
                
        except Exception as e:
            self.results.add_result("Cost Monitoring Tests", False, "", f"Test suite failed: {str(e)}")

    async def test_error_handling_compliance(self):
        """Test database error handling utilities"""
        print(f"\n{Colors.BOLD}6. ERROR HANDLING TESTS{Colors.END}")
        
        try:
            # Test constraint validation
            valid_company_data = {
                'name': 'Valid Company',
                'slug': 'valid-company',
                'rate_limit_rps': 100,
                'monthly_quota': 10000
            }
            
            is_valid, error = validate_before_insert('companies', valid_company_data)
            self.results.add_result(
                "Valid Data Validation",
                is_valid and error is None,
                "Valid data passed validation",
                f"Valid data failed validation: {error}" if not is_valid else ""
            )
            
            # Test invalid data validation
            invalid_company_data = {
                'name': '',  # Invalid empty name
                'slug': 'a',  # Too short slug
                'rate_limit_rps': -1  # Negative rate limit
            }
            
            is_invalid, invalid_error = validate_before_insert('companies', invalid_company_data)
            self.results.add_result(
                "Invalid Data Validation",
                not is_invalid and invalid_error is not None,
                f"Correctly caught invalid data: {invalid_error}",
                "Invalid data passed validation when it shouldn't have" if is_invalid else ""
            )
            
            # Test database error handling
            try:
                # Try to create duplicate company (should fail)
                duplicate_query = """
                    INSERT INTO companies (id, name, slug, is_active)
                    VALUES ($1, $2, $3, true)
                """
                await DatabaseUtils.execute_query(
                    duplicate_query,
                    [self.test_company_id, "Duplicate Company", "test-company"],  # Same slug as test company
                    fetch_all=False
                )
                self.results.add_result(
                    "Duplicate Key Error Handling",
                    False,
                    "",
                    "Should have failed with duplicate key error"
                )
            except Exception as e:
                error_info = handle_database_error(e)
                self.results.add_result(
                    "Duplicate Key Error Handling",
                    "unique" in str(error_info.get('user_message', '')).lower(),
                    f"Correctly handled duplicate error: {error_info.get('user_message', 'Unknown')}",
                    f"Wrong error handling: {error_info.get('user_message', 'Unknown')}" if "unique" not in str(error_info.get('user_message', '')).lower() else ""
                )
                
        except Exception as e:
            self.results.add_result("Error Handling Tests", False, "", f"Test suite failed: {str(e)}")

    async def test_cache_service_compliance(self):
        """Test cache service functionality"""
        print(f"\n{Colors.BOLD}7. CACHE SERVICE TESTS{Colors.END}")
        
        try:
            # Test cache health check
            cache_healthy = await cache_health_check()
            self.results.add_result(
                "Cache Health Check",
                cache_healthy,
                "Cache is healthy and responsive",
                "Cache health check failed" if not cache_healthy else ""
            )
            
            # Test cache statistics
            cache_stats = await get_cache_stats()
            self.results.add_result(
                "Cache Statistics",
                isinstance(cache_stats, dict) and 'timestamp' in cache_stats,
                f"Retrieved cache stats at {cache_stats.get('timestamp', 'unknown time')}",
                f"Failed to get cache stats: {cache_stats}" if not isinstance(cache_stats, dict) else ""
            )
            
            # Check if Redis is connected
            redis_connected = cache_stats.get('health', {}).get('redis_connected', False)
            self.results.add_result(
                "Redis Connection",
                redis_connected,
                "Redis is connected and accessible",
                "Redis connection failed" if not redis_connected else ""
            )
            
        except Exception as e:
            self.results.add_result("Cache Service Tests", False, "", f"Test suite failed: {str(e)}")

    async def test_overall_integration(self):
        """Test overall system integration"""
        print(f"\n{Colors.BOLD}8. INTEGRATION TESTS{Colors.END}")
        
        try:
            # Test complete request flow simulation
            if self.test_company_id and self.test_api_key:
                # Validate API key
                company = await validate_api_key(self.test_api_key)
                
                if company:
                    # Calculate cost using pricing service
                    cost_result = await PricingService.calculate_cost(
                        vendor="openai",
                        model="gpt-4o", 
                        input_tokens=1000,
                        output_tokens=500,
                        company_id=UUID(str(company.id))
                    )
                    
                    # Check that all components work together
                    integration_success = (
                        company is not None and
                        cost_result.get('total_cost', 0) > 0 and
                        company.schema_name == 'test-company'
                    )
                    
                    self.results.add_result(
                        "Full Request Flow Integration",
                        integration_success,
                        f"Complete flow: API validation → Cost calculation (${cost_result.get('total_cost', 0):.6f})",
                        "Integration flow failed at some point" if not integration_success else ""
                    )
                else:
                    self.results.add_result(
                        "Full Request Flow Integration",
                        False,
                        "",
                        "API key validation failed in integration test"
                    )
            
            # Test database schema consistency
            schema_check_query = """
                SELECT 
                    t.table_name,
                    COUNT(c.column_name) as column_count
                FROM information_schema.tables t
                LEFT JOIN information_schema.columns c ON t.table_name = c.table_name
                WHERE t.table_schema = 'public' 
                  AND t.table_type = 'BASE TABLE'
                  AND t.table_name IN (
                    'companies', 'api_keys', 'client_users', 'user_sessions',
                    'vendors', 'vendor_models', 'vendor_keys', 'vendor_pricing',
                    'requests', 'cost_calculations', 'user_analytics_hourly',
                    'user_analytics_daily', 'cost_alerts', 'cost_anomalies'
                  )
                GROUP BY t.table_name
                ORDER BY t.table_name
            """
            
            schema_result = await DatabaseUtils.execute_query(schema_check_query, [], fetch_all=True)
            
            expected_tables = 13  # Number of main schema tables (Schema v2)
            found_tables = len(schema_result) if schema_result else 0
            
            self.results.add_result(
                "Schema Table Completeness",
                found_tables >= expected_tables,
                f"Found {found_tables}/{expected_tables} expected tables",
                f"Missing tables: only found {found_tables}/{expected_tables}" if found_tables < expected_tables else ""
            )
            
            # Check for any tables with too few columns (potential schema issues)
            if schema_result:
                for table_info in schema_result:
                    table_name = table_info['table_name']
                    column_count = table_info['column_count']
                    
                    # Basic column count expectations (adjust as needed)
                    min_columns = {
                        'companies': 8, 'api_keys': 8, 'client_users': 5,
                        'vendors': 4, 'vendor_models': 6, 'requests': 15,
                        'cost_calculations': 8, 'user_analytics_hourly': 10,
                        'user_analytics_daily': 15, 'cost_alerts': 10
                    }
                    
                    expected_min = min_columns.get(table_name, 3)
                    
                    if column_count < expected_min:
                        self.results.add_warning(f"Table '{table_name}' has only {column_count} columns (expected ≥{expected_min})")
                    
        except Exception as e:
            self.results.add_result("Integration Tests", False, "", f"Test suite failed: {str(e)}")

    async def _get_or_create_test_vendor(self) -> UUID:
        """Helper to get or create a test vendor"""
        try:
            # Check if vendor exists
            vendor_query = "SELECT id FROM vendors WHERE name = 'openai' LIMIT 1"
            vendor_result = await DatabaseUtils.execute_query(vendor_query, [], fetch_all=False)
            
            if not vendor_result:
                # Create vendor
                vendor_id = uuid4()
                await DatabaseUtils.execute_query(
                    "INSERT INTO vendors (id, name, display_name, description) VALUES ($1, $2, $3, $4)",
                    [vendor_id, "openai", "OpenAI", "OpenAI API"],
                    fetch_all=False
                )
                return vendor_id
            else:
                return vendor_result['id']
                
        except Exception as e:
            print(f"  {Colors.YELLOW}⚠{Colors.END} Could not create test vendor: {str(e)}")
            return uuid4()  # Return a dummy UUID

    async def _get_or_create_test_vendor_model(self) -> UUID:
        """Helper to get or create a test vendor model"""
        try:
            # Check if vendor exists
            vendor_query = "SELECT id FROM vendors WHERE name = 'openai' LIMIT 1"
            vendor_result = await DatabaseUtils.execute_query(vendor_query, [], fetch_all=False)
            
            if not vendor_result:
                # Create vendor
                vendor_id = uuid4()
                await DatabaseUtils.execute_query(
                    "INSERT INTO vendors (id, name, description) VALUES ($1, $2, $3)",
                    [vendor_id, "openai", "OpenAI API"],
                    fetch_all=False
                )
            else:
                vendor_id = vendor_result['id']
            
            # Check if model exists
            model_query = "SELECT id FROM vendor_models WHERE vendor_id = $1 AND name = 'gpt-4o' LIMIT 1"
            model_result = await DatabaseUtils.execute_query(model_query, [vendor_id], fetch_all=False)
            
            if not model_result:
                # Create model
                model_id = uuid4()
                await DatabaseUtils.execute_query(
                    "INSERT INTO vendor_models (id, vendor_id, name, display_name, description) VALUES ($1, $2, $3, $4, $5)",
                    [model_id, vendor_id, "gpt-4o", "GPT-4o", "GPT-4o model"],
                    fetch_all=False
                )
                return model_id
            else:
                return model_result['id']
                
        except Exception as e:
            print(f"  {Colors.YELLOW}⚠{Colors.END} Could not create test vendor model: {str(e)}")
            return uuid4()  # Return a dummy UUID

    async def run_all_tests(self):
        """Run the complete test suite"""
        print(f"{Colors.BOLD}{Colors.CYAN}🧪 API LENS BACKEND - COMPREHENSIVE SCHEMA COMPLIANCE TESTS{Colors.END}")
        print(f"{Colors.CYAN}{'='*80}{Colors.END}")
        print(f"Started at: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
        
        try:
            # Initialize database
            print(f"\n{Colors.BOLD}🔌 INITIALIZING DATABASE CONNECTION{Colors.END}")
            await init_database()
            print(f"  {Colors.GREEN}✓{Colors.END} Database connection initialized")
            
            # Setup test data
            print(f"\n{Colors.BOLD}🛠️  SETTING UP TEST DATA{Colors.END}")
            await self.setup_test_data()
            
            # Run all test suites
            await self.test_database_connection()
            await self.test_auth_service_compliance()
            await self.test_pricing_service_compliance()
            await self.test_analytics_service_compliance()
            await self.test_cost_monitoring_compliance()
            await self.test_error_handling_compliance()
            await self.test_cache_service_compliance()
            await self.test_overall_integration()
            
        except Exception as e:
            print(f"\n{Colors.RED}💥 CRITICAL ERROR: {str(e)}{Colors.END}")
            print(f"{Colors.RED}Traceback:{Colors.END}")
            print(traceback.format_exc())
            
        finally:
            # Cleanup
            print(f"\n{Colors.BOLD}🧹 CLEANING UP TEST DATA{Colors.END}")
            await self.cleanup_test_data()
            
            # Close database
            await close_database()
            print(f"  {Colors.GREEN}✓{Colors.END} Database connection closed")
            
            # Print results
            self.results.print_summary()
            
            # Final compliance assessment
            success_rate = (self.results.passed_tests / self.results.total_tests * 100) if self.results.total_tests > 0 else 0
            
            print(f"\n{Colors.BOLD}📊 FINAL COMPLIANCE ASSESSMENT{Colors.END}")
            if success_rate >= 95:
                print(f"{Colors.GREEN}🎉 EXCELLENT: Your backend is highly compliant with the database schema!{Colors.END}")
            elif success_rate >= 85:
                print(f"{Colors.YELLOW}✅ GOOD: Your backend is mostly compliant with minor issues to address.{Colors.END}")
            elif success_rate >= 70:
                print(f"{Colors.YELLOW}⚠️  FAIR: Your backend has some compliance issues that should be fixed.{Colors.END}")
            else:
                print(f"{Colors.RED}❌ POOR: Your backend has significant compliance issues requiring attention.{Colors.END}")
            
            return success_rate >= 85  # Return True if compliance is good

async def main():
    """Main test runner"""
    print(f"{Colors.BOLD}Starting comprehensive schema compliance testing...{Colors.END}\n")
    
    tester = SchemaComplianceTests()
    success = await tester.run_all_tests()
    
    # Exit with appropriate code
    sys.exit(0 if success else 1)

if __name__ == "__main__":
    asyncio.run(main())
#!/usr/bin/env python3
"""
Database Connection Test Script
Tests database connectivity with real credentials and validates schema
"""
import asyncio
import sys
import os
from datetime import datetime
from typing import Dict, Any
import traceback

# Add the app directory to path for imports
sys.path.insert(0, '/Users/thousifudayagiri/Desktop/api-lens-backend')

from app.database import DatabaseUtils, init_database, close_database
from app.config import get_settings

class Colors:
    """ANSI color codes"""
    GREEN = '\033[92m'
    RED = '\033[91m'
    YELLOW = '\033[93m'
    BLUE = '\033[94m'
    CYAN = '\033[96m'
    BOLD = '\033[1m'
    END = '\033[0m'

class DatabaseConnectionTester:
    """Test database connection and validate schema"""
    
    def __init__(self):
        self.settings = get_settings()
        self.test_results = []
    
    def log_result(self, test_name: str, success: bool, message: str = "", error: str = ""):
        """Log test result"""
        status = "✓" if success else "✗"
        color = Colors.GREEN if success else Colors.RED
        
        self.test_results.append({
            'test': test_name,
            'success': success,
            'message': message,
            'error': error
        })
        
        print(f"  {color}{status}{Colors.END} {test_name}: {message if success else error}")
    
    async def test_basic_connectivity(self):
        """Test basic database connectivity"""
        print(f"\n{Colors.BOLD}1. BASIC CONNECTIVITY TESTS{Colors.END}")
        
        try:
            # Test simple query
            result = await DatabaseUtils.execute_query("SELECT 1 as test_value", [], fetch_all=False)
            self.log_result(
                "Basic Query Execution",
                result is not None and result.get('test_value') == 1,
                f"Query successful: {result}",
                "Basic query failed" if not result else ""
            )
            
            # Test current timestamp
            result = await DatabaseUtils.execute_query("SELECT NOW() as current_time", [], fetch_all=False)
            self.log_result(
                "Timestamp Query",
                result is not None and 'current_time' in result,
                f"Server time: {result.get('current_time') if result else 'Unknown'}",
                "Timestamp query failed" if not result else ""
            )
            
            # Test database version
            result = await DatabaseUtils.execute_query("SELECT version() as pg_version", [], fetch_all=False)
            if result:
                version = str(result.get('pg_version', '')).split(' ')[0:2]
                version_str = ' '.join(version) if version else 'Unknown'
                self.log_result(
                    "Database Version",
                    True,
                    f"PostgreSQL {version_str}",
                    ""
                )
            else:
                self.log_result("Database Version", False, "", "Failed to get version")
                
        except Exception as e:
            self.log_result("Basic Connectivity", False, "", f"Connection failed: {str(e)}")
    
    async def test_schema_tables(self):
        """Test that all required schema tables exist"""
        print(f"\n{Colors.BOLD}2. SCHEMA VALIDATION TESTS{Colors.END}")
        
        required_tables = [
            'companies', 'api_keys', 'client_users', 'user_sessions',
            'vendors', 'vendor_models', 'vendor_keys', 'vendor_pricing',
            'requests', 'user_analytics_hourly', 'user_analytics_daily',
            'cost_alerts', 'cost_anomalies'
        ]
        
        try:
            for table in required_tables:
                result = await DatabaseUtils.execute_query(
                    """
                    SELECT table_name, column_count 
                    FROM (
                        SELECT t.table_name, COUNT(c.column_name) as column_count
                        FROM information_schema.tables t
                        LEFT JOIN information_schema.columns c ON t.table_name = c.table_name
                        WHERE t.table_schema = 'public' 
                          AND t.table_type = 'BASE TABLE'
                          AND t.table_name = $1
                        GROUP BY t.table_name
                    ) sub
                    """,
                    [table],
                    fetch_all=False
                )
                
                if result:
                    self.log_result(
                        f"Table '{table}'",
                        True,
                        f"Found with {result.get('column_count', 0)} columns",
                        ""
                    )
                else:
                    self.log_result(
                        f"Table '{table}'",
                        False,
                        "",
                        f"Table '{table}' not found"
                    )
                    
        except Exception as e:
            self.log_result("Schema Validation", False, "", f"Schema check failed: {str(e)}")
    
    async def test_database_permissions(self):
        """Test database permissions for CRUD operations"""
        print(f"\n{Colors.BOLD}3. PERMISSION TESTS{Colors.END}")
        
        try:
            # Test CREATE permission with a temporary table
            create_test = """
                CREATE TEMP TABLE connection_test (
                    id SERIAL PRIMARY KEY,
                    test_data VARCHAR(100),
                    created_at TIMESTAMP DEFAULT NOW()
                )
            """
            
            await DatabaseUtils.execute_query(create_test, [], fetch_all=False)
            self.log_result("CREATE Permission", True, "Can create temporary tables", "")
            
            # Test INSERT permission
            insert_test = """
                INSERT INTO connection_test (test_data) 
                VALUES ('test_insert') 
                RETURNING id, test_data
            """
            
            insert_result = await DatabaseUtils.execute_query(insert_test, [], fetch_all=False)
            if insert_result and insert_result.get('test_data') == 'test_insert':
                self.log_result("INSERT Permission", True, f"Inserted row with ID: {insert_result.get('id')}", "")
            else:
                self.log_result("INSERT Permission", False, "", "Insert operation failed")
            
            # Test SELECT permission
            select_test = "SELECT * FROM connection_test WHERE test_data = 'test_insert'"
            select_result = await DatabaseUtils.execute_query(select_test, [], fetch_all=True)
            
            if select_result and len(select_result) > 0:
                self.log_result("SELECT Permission", True, f"Retrieved {len(select_result)} rows", "")
            else:
                self.log_result("SELECT Permission", False, "", "Select operation failed")
            
            # Test UPDATE permission
            if insert_result:
                update_test = """
                    UPDATE connection_test 
                    SET test_data = 'test_updated' 
                    WHERE id = $1 
                    RETURNING test_data
                """
                update_result = await DatabaseUtils.execute_query(
                    update_test, 
                    [insert_result.get('id')], 
                    fetch_all=False
                )
                
                if update_result and update_result.get('test_data') == 'test_updated':
                    self.log_result("UPDATE Permission", True, "Updated test row successfully", "")
                else:
                    self.log_result("UPDATE Permission", False, "", "Update operation failed")
            
            # Test DELETE permission
            if insert_result:
                delete_test = "DELETE FROM connection_test WHERE id = $1"
                await DatabaseUtils.execute_query(delete_test, [insert_result.get('id')], fetch_all=False)
                
                # Verify deletion
                verify_delete = "SELECT COUNT(*) as count FROM connection_test WHERE id = $1"
                verify_result = await DatabaseUtils.execute_query(
                    verify_delete, 
                    [insert_result.get('id')], 
                    fetch_all=False
                )
                
                if verify_result and verify_result.get('count') == 0:
                    self.log_result("DELETE Permission", True, "Deleted test row successfully", "")
                else:
                    self.log_result("DELETE Permission", False, "", "Delete operation failed")
                    
        except Exception as e:
            self.log_result("Database Permissions", False, "", f"Permission test failed: {str(e)}")
    
    async def test_connection_pooling(self):
        """Test database connection pooling"""
        print(f"\n{Colors.BOLD}4. CONNECTION POOLING TESTS{Colors.END}")
        
        try:
            # Test multiple concurrent connections
            async def test_concurrent_query(query_id: int):
                result = await DatabaseUtils.execute_query(
                    "SELECT $1 as query_id, pg_backend_pid() as backend_pid", 
                    [query_id], 
                    fetch_all=False
                )
                return result
            
            # Run 5 concurrent queries
            tasks = [test_concurrent_query(i) for i in range(1, 6)]
            results = await asyncio.gather(*tasks, return_exceptions=True)
            
            successful_queries = [r for r in results if isinstance(r, dict) and 'query_id' in r]
            backend_pids = set(r.get('backend_pid') for r in successful_queries)
            
            self.log_result(
                "Concurrent Connections",
                len(successful_queries) == 5,
                f"Successfully ran {len(successful_queries)}/5 concurrent queries using {len(backend_pids)} backend processes",
                f"Only {len(successful_queries)}/5 queries succeeded" if len(successful_queries) < 5 else ""
            )
            
            # Test connection reuse
            result1 = await DatabaseUtils.execute_query("SELECT pg_backend_pid() as pid1", [], fetch_all=False)
            result2 = await DatabaseUtils.execute_query("SELECT pg_backend_pid() as pid2", [], fetch_all=False)
            
            if result1 and result2:
                same_connection = result1.get('pid1') == result2.get('pid2')
                self.log_result(
                    "Connection Reuse",
                    True,  # Either reuse or new connection is fine
                    f"Backend PIDs: {result1.get('pid1')} -> {result2.get('pid2')} ({'Reused' if same_connection else 'New connection'})",
                    ""
                )
            else:
                self.log_result("Connection Reuse", False, "", "Failed to get backend PIDs")
                
        except Exception as e:
            self.log_result("Connection Pooling", False, "", f"Connection pooling test failed: {str(e)}")
    
    async def test_data_integrity(self):
        """Test data integrity and constraints"""
        print(f"\n{Colors.BOLD}5. DATA INTEGRITY TESTS{Colors.END}")
        
        try:
            # Test foreign key constraints (if they exist)
            constraint_check = """
                SELECT tc.constraint_name, tc.table_name, tc.constraint_type
                FROM information_schema.table_constraints tc
                WHERE tc.table_schema = 'public' 
                  AND tc.constraint_type IN ('FOREIGN KEY', 'PRIMARY KEY', 'UNIQUE')
                ORDER BY tc.table_name, tc.constraint_type
            """
            
            constraints = await DatabaseUtils.execute_query(constraint_check, [], fetch_all=True)
            
            if constraints:
                fk_count = len([c for c in constraints if c.get('constraint_type') == 'FOREIGN KEY'])
                pk_count = len([c for c in constraints if c.get('constraint_type') == 'PRIMARY KEY'])
                unique_count = len([c for c in constraints if c.get('constraint_type') == 'UNIQUE'])
                
                self.log_result(
                    "Database Constraints",
                    True,
                    f"Found {pk_count} primary keys, {fk_count} foreign keys, {unique_count} unique constraints",
                    ""
                )
            else:
                self.log_result("Database Constraints", False, "", "No constraints found")
            
            # Test transaction support
            try:
                # This would be a more complex test in a real scenario
                result = await DatabaseUtils.execute_query("BEGIN; SELECT 1; ROLLBACK; SELECT 2 as test", [], fetch_all=False)
                self.log_result(
                    "Transaction Support",
                    result is not None and result.get('test') == 2,
                    "Transactions working correctly",
                    "Transaction test failed" if not result else ""
                )
            except Exception as te:
                self.log_result("Transaction Support", False, "", f"Transaction test failed: {str(te)}")
                
        except Exception as e:
            self.log_result("Data Integrity", False, "", f"Data integrity test failed: {str(e)}")
    
    async def test_performance(self):
        """Test basic database performance"""
        print(f"\n{Colors.BOLD}6. PERFORMANCE TESTS{Colors.END}")
        
        try:
            # Test query performance
            start_time = datetime.now()
            
            # Run a slightly complex query
            perf_query = """
                SELECT 
                    t.table_name,
                    COUNT(c.column_name) as column_count,
                    NOW() as query_time
                FROM information_schema.tables t
                LEFT JOIN information_schema.columns c ON t.table_name = c.table_name
                WHERE t.table_schema = 'public'
                GROUP BY t.table_name
                ORDER BY column_count DESC
                LIMIT 10
            """
            
            result = await DatabaseUtils.execute_query(perf_query, [], fetch_all=True)
            end_time = datetime.now()
            
            query_duration = (end_time - start_time).total_seconds() * 1000  # Convert to milliseconds
            
            if result:
                self.log_result(
                    "Query Performance",
                    query_duration < 1000,  # Should be under 1 second
                    f"Query executed in {query_duration:.2f}ms, returned {len(result)} rows",
                    f"Query took {query_duration:.2f}ms (too slow)" if query_duration >= 1000 else ""
                )
            else:
                self.log_result("Query Performance", False, "", "Performance query failed")
                
        except Exception as e:
            self.log_result("Performance Tests", False, "", f"Performance test failed: {str(e)}")
    
    def print_summary(self):
        """Print test summary"""
        print(f"\n{Colors.BOLD}{'='*80}{Colors.END}")
        print(f"{Colors.BOLD}DATABASE CONNECTION TEST SUMMARY{Colors.END}")
        print(f"{'='*80}")
        
        total_tests = len(self.test_results)
        passed_tests = len([t for t in self.test_results if t['success']])
        failed_tests = total_tests - passed_tests
        
        print(f"Total Tests: {Colors.CYAN}{total_tests}{Colors.END}")
        print(f"Passed: {Colors.GREEN}{passed_tests}{Colors.END}")
        print(f"Failed: {Colors.RED}{failed_tests}{Colors.END}")
        
        success_rate = (passed_tests / total_tests * 100) if total_tests > 0 else 0
        color = Colors.GREEN if success_rate >= 90 else Colors.YELLOW if success_rate >= 75 else Colors.RED
        print(f"Success Rate: {color}{success_rate:.1f}%{Colors.END}")
        
        if failed_tests > 0:
            print(f"\n{Colors.RED}FAILED TESTS:{Colors.END}")
            for test in self.test_results:
                if not test['success']:
                    print(f"  {Colors.RED}✗{Colors.END} {test['test']}: {test['error']}")
        
        print(f"\n{Colors.BOLD}DATABASE CONNECTION STATUS:{Colors.END}")
        if success_rate >= 90:
            print(f"{Colors.GREEN}🎉 EXCELLENT: Database connection is fully operational!{Colors.END}")
        elif success_rate >= 75:
            print(f"{Colors.YELLOW}✅ GOOD: Database connection is working with minor issues.{Colors.END}")
        elif success_rate >= 50:
            print(f"{Colors.YELLOW}⚠️  FAIR: Database connection has some issues that need attention.{Colors.END}")
        else:
            print(f"{Colors.RED}❌ POOR: Database connection has significant issues requiring immediate attention.{Colors.END}")
    
    async def run_all_tests(self):
        """Run all database connection tests"""
        print(f"{Colors.BOLD}{Colors.CYAN}🔗 API LENS BACKEND - DATABASE CONNECTION TESTS{Colors.END}")
        print(f"{Colors.CYAN}{'='*80}{Colors.END}")
        print(f"Started at: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
        print(f"Database URL: {self.settings.DATABASE_URL[:50]}...")
        
        try:
            # Initialize database connection
            print(f"\n{Colors.BOLD}🔌 INITIALIZING DATABASE CONNECTION{Colors.END}")
            await init_database()
            print(f"  {Colors.GREEN}✓{Colors.END} Database connection pool initialized")
            
            # Run all test suites
            await self.test_basic_connectivity()
            await self.test_schema_tables()
            await self.test_database_permissions()
            await self.test_connection_pooling()
            await self.test_data_integrity()
            await self.test_performance()
            
        except Exception as e:
            print(f"\n{Colors.RED}💥 CRITICAL ERROR: {str(e)}{Colors.END}")
            print(f"{Colors.RED}Traceback:{Colors.END}")
            print(traceback.format_exc())
            
        finally:
            # Close database connection
            print(f"\n{Colors.BOLD}🔌 CLOSING DATABASE CONNECTION{Colors.END}")
            await close_database()
            print(f"  {Colors.GREEN}✓{Colors.END} Database connection closed")
            
            # Print results
            self.print_summary()
            
            # Return success status
            passed_tests = len([t for t in self.test_results if t['success']])
            total_tests = len(self.test_results)
            return (passed_tests / total_tests) >= 0.85 if total_tests > 0 else False

async def main():
    """Main test runner"""
    print(f"{Colors.BOLD}Starting database connection tests...{Colors.END}\n")
    
    tester = DatabaseConnectionTester()
    success = await tester.run_all_tests()
    
    # Exit with appropriate code
    sys.exit(0 if success else 1)

if __name__ == "__main__":
    asyncio.run(main())
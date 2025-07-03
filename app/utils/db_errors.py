"""
Database Error Handling Utilities
Provides structured error handling for database constraint violations and common database errors
"""
import re
from typing import Dict, Any, Optional, Tuple
from enum import Enum
import asyncpg

class DBErrorType(Enum):
    """Database error types for structured error handling"""
    UNIQUE_VIOLATION = "unique_violation"
    FOREIGN_KEY_VIOLATION = "foreign_key_violation"
    NOT_NULL_VIOLATION = "not_null_violation"
    CHECK_VIOLATION = "check_violation"
    INVALID_TEXT_REPRESENTATION = "invalid_text_representation"
    CONNECTION_ERROR = "connection_error"
    TIMEOUT_ERROR = "timeout_error"
    PERMISSION_DENIED = "permission_denied"
    UNKNOWN_ERROR = "unknown_error"

class DBError:
    """Structured database error representation"""
    
    def __init__(self, error_type: DBErrorType, message: str, details: Optional[Dict[str, Any]] = None):
        self.error_type = error_type
        self.message = message
        self.details = details or {}
        
    def to_dict(self) -> Dict[str, Any]:
        return {
            "error_type": self.error_type.value,
            "message": self.message,
            "details": self.details
        }
    
    def __str__(self) -> str:
        return f"{self.error_type.value}: {self.message}"

class DatabaseErrorHandler:
    """Database error handler with intelligent error parsing"""
    
    # PostgreSQL error codes mapping
    PG_ERROR_CODES = {
        "23505": DBErrorType.UNIQUE_VIOLATION,
        "23503": DBErrorType.FOREIGN_KEY_VIOLATION, 
        "23502": DBErrorType.NOT_NULL_VIOLATION,
        "23514": DBErrorType.CHECK_VIOLATION,
        "22P02": DBErrorType.INVALID_TEXT_REPRESENTATION,
        "08000": DBErrorType.CONNECTION_ERROR,
        "08003": DBErrorType.CONNECTION_ERROR,
        "08006": DBErrorType.CONNECTION_ERROR,
        "57014": DBErrorType.TIMEOUT_ERROR,
        "42501": DBErrorType.PERMISSION_DENIED,
    }
    
    # Constraint name patterns for better error messages
    CONSTRAINT_PATTERNS = {
        r'companies_name_key': 'Company name must be unique',
        r'companies_slug_key': 'Company identifier (slug) must be unique',
        r'api_keys_key_hash_key': 'API key already exists',
        r'api_keys_company_id_fkey': 'Company not found',
        r'vendor_keys_company_id_fkey': 'Company not found',
        r'requests_company_id_fkey': 'Company not found',
        r'requests_api_key_id_fkey': 'API key not found',
        r'client_users_company_id_fkey': 'Company not found',
        r'user_sessions_user_id_fkey': 'User not found',
        r'cost_calculations_request_id_fkey': 'Request not found',
        r'hourly_analytics_company_id_fkey': 'Company not found',
        r'daily_analytics_company_id_fkey': 'Company not found',
    }
    
    @classmethod
    def parse_error(cls, error: Exception) -> DBError:
        """
        Parse database error and return structured error information
        
        Args:
            error: Raw database exception
            
        Returns:
            DBError: Structured error with type and details
        """
        
        # Handle asyncpg errors
        if isinstance(error, asyncpg.PostgresError):
            return cls._parse_postgres_error(error)
        
        # Handle connection-related errors
        if isinstance(error, (asyncpg.ConnectionDoesNotExistError, asyncpg.InterfaceError)):
            return DBError(
                DBErrorType.CONNECTION_ERROR,
                "Database connection failed",
                {"original_error": str(error)}
            )
        
        # Handle timeout errors
        if isinstance(error, (asyncpg.ServerTimeoutError, asyncpg.ConnectionTimeoutError)):
            return DBError(
                DBErrorType.TIMEOUT_ERROR,
                "Database operation timed out",
                {"original_error": str(error)}
            )
        
        # Default case for unknown errors
        return DBError(
            DBErrorType.UNKNOWN_ERROR,
            f"Database error: {str(error)}",
            {"error_type": type(error).__name__, "original_error": str(error)}
        )
    
    @classmethod
    def _parse_postgres_error(cls, error: asyncpg.PostgresError) -> DBError:
        """Parse PostgreSQL-specific errors"""
        
        sqlstate = getattr(error, 'sqlstate', None)
        constraint_name = getattr(error, 'constraint_name', None)
        table_name = getattr(error, 'table_name', None)
        column_name = getattr(error, 'column_name', None)
        detail = getattr(error, 'detail', '')
        
        # Map error code to type
        error_type = cls.PG_ERROR_CODES.get(sqlstate, DBErrorType.UNKNOWN_ERROR)
        
        # Generate user-friendly message
        message = cls._generate_user_message(error_type, constraint_name, table_name, column_name, detail)
        
        # Build error details
        details = {
            "sqlstate": sqlstate,
            "constraint_name": constraint_name,
            "table_name": table_name,
            "column_name": column_name,
            "detail": detail,
            "original_error": str(error)
        }
        
        return DBError(error_type, message, details)
    
    @classmethod
    def _generate_user_message(cls, error_type: DBErrorType, constraint_name: str, 
                              table_name: str, column_name: str, detail: str) -> str:
        """Generate user-friendly error messages"""
        
        # Check for specific constraint patterns
        if constraint_name:
            for pattern, message in cls.CONSTRAINT_PATTERNS.items():
                if re.search(pattern, constraint_name):
                    return message
        
        # Generic messages based on error type
        if error_type == DBErrorType.UNIQUE_VIOLATION:
            if column_name:
                return f"The {column_name} already exists and violates unique constraint"
            return "This record already exists and violates unique constraint"
        
        elif error_type == DBErrorType.FOREIGN_KEY_VIOLATION:
            if "is not present in table" in detail:
                referenced_table = cls._extract_referenced_table(detail)
                if referenced_table:
                    return f"Referenced {referenced_table} does not exist"
            return "Referenced record does not exist"
        
        elif error_type == DBErrorType.NOT_NULL_VIOLATION:
            if column_name:
                return f"The field '{column_name}' is required"
            return "Required field is missing"
        
        elif error_type == DBErrorType.CHECK_VIOLATION:
            return "Data validation failed - invalid value provided"
        
        elif error_type == DBErrorType.INVALID_TEXT_REPRESENTATION:
            return "Invalid data format provided"
        
        elif error_type == DBErrorType.CONNECTION_ERROR:
            return "Database connection failed"
        
        elif error_type == DBErrorType.TIMEOUT_ERROR:
            return "Database operation timed out"
        
        elif error_type == DBErrorType.PERMISSION_DENIED:
            return "Insufficient permissions for this operation"
        
        else:
            return "Database operation failed"
    
    @classmethod
    def _extract_referenced_table(cls, detail: str) -> Optional[str]:
        """Extract referenced table name from error detail"""
        match = re.search(r'is not present in table "(\w+)"', detail)
        if match:
            table_name = match.group(1)
            # Convert table names to more user-friendly terms
            table_mapping = {
                'companies': 'company',
                'api_keys': 'API key',
                'client_users': 'user',
                'vendors': 'vendor',
                'vendor_models': 'model'
            }
            return table_mapping.get(table_name, table_name)
        return None

class DatabaseConstraintValidator:
    """Validate data before database operations to prevent constraint violations"""
    
    @staticmethod
    def validate_company_data(data: Dict[str, Any]) -> Tuple[bool, Optional[str]]:
        """Validate company data before insertion/update"""
        
        # Check required fields
        required_fields = ['name', 'slug']
        for field in required_fields:
            if not data.get(field):
                return False, f"Field '{field}' is required"
        
        # Validate slug format (alphanumeric, underscores, hyphens)
        slug = data.get('slug', '')
        if not re.match(r'^[a-zA-Z0-9_-]+$', slug):
            return False, "Company identifier (slug) can only contain letters, numbers, underscores, and hyphens"
        
        # Check slug length
        if len(slug) < 2 or len(slug) > 50:
            return False, "Company identifier (slug) must be between 2 and 50 characters"
        
        # Validate rate limits
        rate_limit_rps = data.get('rate_limit_rps')
        if rate_limit_rps is not None and (rate_limit_rps < 0 or rate_limit_rps > 10000):
            return False, "Rate limit must be between 0 and 10000 requests per second"
        
        # Validate monthly quota
        monthly_quota = data.get('monthly_quota')
        if monthly_quota is not None and monthly_quota < 0:
            return False, "Monthly quota cannot be negative"
        
        return True, None
    
    @staticmethod
    def validate_api_key_data(data: Dict[str, Any]) -> Tuple[bool, Optional[str]]:
        """Validate API key data before insertion/update"""
        
        # Check required fields
        if not data.get('company_id'):
            return False, "Company ID is required"
        
        if not data.get('key_hash'):
            return False, "API key hash is required"
        
        # Validate name
        name = data.get('name', '')
        if not name or len(name.strip()) == 0:
            return False, "API key name is required"
        
        if len(name) > 100:
            return False, "API key name cannot exceed 100 characters"
        
        return True, None
    
    @staticmethod  
    def validate_user_data(data: Dict[str, Any]) -> Tuple[bool, Optional[str]]:
        """Validate user data before insertion/update"""
        
        # Check required fields
        if not data.get('company_id'):
            return False, "Company ID is required"
        
        if not data.get('user_id'):
            return False, "User ID is required"
        
        # Validate user_id format (no special validation rules yet)
        user_id = data.get('user_id', '')
        if len(user_id) > 255:
            return False, "User ID cannot exceed 255 characters"
        
        return True, None

# Utility functions for common error handling patterns

def handle_database_error(error: Exception) -> Dict[str, Any]:
    """
    Handle database errors and return structured response
    
    Args:
        error: Database exception
        
    Returns:
        Dictionary with error information suitable for API responses
    """
    db_error = DatabaseErrorHandler.parse_error(error)
    
    # Map internal error types to HTTP status codes
    status_code_mapping = {
        DBErrorType.UNIQUE_VIOLATION: 409,  # Conflict
        DBErrorType.FOREIGN_KEY_VIOLATION: 400,  # Bad Request
        DBErrorType.NOT_NULL_VIOLATION: 400,  # Bad Request
        DBErrorType.CHECK_VIOLATION: 400,  # Bad Request
        DBErrorType.INVALID_TEXT_REPRESENTATION: 400,  # Bad Request
        DBErrorType.CONNECTION_ERROR: 503,  # Service Unavailable
        DBErrorType.TIMEOUT_ERROR: 504,  # Gateway Timeout
        DBErrorType.PERMISSION_DENIED: 403,  # Forbidden
        DBErrorType.UNKNOWN_ERROR: 500,  # Internal Server Error
    }
    
    return {
        "error": db_error.to_dict(),
        "status_code": status_code_mapping.get(db_error.error_type, 500),
        "user_message": db_error.message
    }

def validate_before_insert(table_name: str, data: Dict[str, Any]) -> Tuple[bool, Optional[str]]:
    """
    Validate data before database insertion
    
    Args:
        table_name: Name of the target table
        data: Data to be inserted
        
    Returns:
        Tuple of (is_valid, error_message)
    """
    
    validator_mapping = {
        'companies': DatabaseConstraintValidator.validate_company_data,
        'api_keys': DatabaseConstraintValidator.validate_api_key_data,
        'client_users': DatabaseConstraintValidator.validate_user_data,
    }
    
    validator = validator_mapping.get(table_name)
    if validator:
        return validator(data)
    
    # Default validation (just check for required fields if any are defined)
    return True, None
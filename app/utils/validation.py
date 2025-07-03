"""
Input Validation Utilities
Provides comprehensive validation for all incoming API data
"""
import re
import uuid
from typing import Dict, Any, List, Optional, Union, Tuple
from datetime import datetime
from pydantic import BaseModel, ValidationError, validator
from enum import Enum

from ..utils.logger import get_logger

logger = get_logger(__name__)

class ValidationError(Exception):
    """Custom validation error"""
    pass

class ValidationLevel(Enum):
    """Validation strictness levels"""
    STRICT = "strict"
    MODERATE = "moderate"
    LENIENT = "lenient"

class InputValidator:
    """Comprehensive input validation service"""
    
    # Common regex patterns
    PATTERNS = {
        'email': re.compile(r'^[a-zA-Z0-9._%+-]+@[a-zA-Z0-9.-]+\.[a-zA-Z]{2,}$'),
        'slug': re.compile(r'^[a-z0-9-]{2,50}$'),
        'api_key': re.compile(r'^ak-[a-zA-Z0-9]{32,64}$'),
        'username': re.compile(r'^[a-zA-Z0-9_-]{2,50}$'),
        'company_name': re.compile(r'^[a-zA-Z0-9\s\.\-&]{2,100}$'),
        'model_name': re.compile(r'^[a-zA-Z0-9\-\.\_]{1,100}$'),
        'vendor_name': re.compile(r'^[a-zA-Z0-9]{2,50}$'),
        'ip_address': re.compile(r'^(?:(?:25[0-5]|2[0-4][0-9]|[01]?[0-9][0-9]?)\.){3}(?:25[0-5]|2[0-4][0-9]|[01]?[0-9][0-9]?)$'),
        'url': re.compile(r'^https?:\/\/[^\s/$.?#].[^\s]*$'),
        'timezone': re.compile(r'^[A-Za-z]+\/[A-Za-z_\/]+$')
    }
    
    # Field length limits
    LIMITS = {
        'name': (2, 100),
        'slug': (2, 50),
        'description': (0, 500),
        'user_agent': (0, 500),
        'referer': (0, 500),
        'error_message': (0, 1000),
        'error_code': (0, 50),
        'endpoint': (1, 200),
        'method': (3, 10),
        'country_code': (2, 3),
        'region': (0, 100),
        'city': (0, 100)
    }
    
    @staticmethod
    def validate_uuid(value: Any, field_name: str = "UUID") -> str:
        """
        Validate UUID format
        
        Args:
            value: Value to validate
            field_name: Field name for error messages
            
        Returns:
            String representation of valid UUID
            
        Raises:
            ValidationError: If UUID is invalid
        """
        if not value:
            raise ValidationError(f"{field_name} is required")
        
        try:
            # Convert to string if not already
            uuid_str = str(value)
            
            # Validate UUID format
            uuid_obj = uuid.UUID(uuid_str)
            
            return str(uuid_obj)
            
        except (ValueError, TypeError) as e:
            raise ValidationError(f"Invalid {field_name} format: {value}")
    
    @staticmethod
    def validate_string(
        value: Any, 
        field_name: str, 
        pattern: Optional[str] = None,
        min_length: int = 0,
        max_length: int = 1000,
        required: bool = True,
        allow_empty: bool = False
    ) -> Optional[str]:
        """
        Validate string field
        
        Args:
            value: Value to validate
            field_name: Field name for error messages
            pattern: Regex pattern name from PATTERNS dict
            min_length: Minimum length
            max_length: Maximum length
            required: Whether field is required
            allow_empty: Whether to allow empty strings
            
        Returns:
            Validated string or None
            
        Raises:
            ValidationError: If validation fails
        """
        if value is None or value == "":
            if required and not allow_empty:
                raise ValidationError(f"{field_name} is required")
            return None if value is None else ""
        
        # Convert to string
        str_value = str(value).strip()
        
        # Check length
        if len(str_value) < min_length:
            raise ValidationError(f"{field_name} must be at least {min_length} characters")
        
        if len(str_value) > max_length:
            raise ValidationError(f"{field_name} must be no more than {max_length} characters")
        
        # Check pattern if provided
        if pattern and pattern in InputValidator.PATTERNS:
            if not InputValidator.PATTERNS[pattern].match(str_value):
                raise ValidationError(f"{field_name} format is invalid")
        
        return str_value
    
    @staticmethod
    def validate_integer(
        value: Any,
        field_name: str,
        min_value: Optional[int] = None,
        max_value: Optional[int] = None,
        required: bool = True
    ) -> Optional[int]:
        """
        Validate integer field
        
        Args:
            value: Value to validate
            field_name: Field name for error messages
            min_value: Minimum allowed value
            max_value: Maximum allowed value
            required: Whether field is required
            
        Returns:
            Validated integer or None
            
        Raises:
            ValidationError: If validation fails
        """
        if value is None:
            if required:
                raise ValidationError(f"{field_name} is required")
            return None
        
        try:
            int_value = int(value)
        except (ValueError, TypeError):
            raise ValidationError(f"{field_name} must be a valid integer")
        
        if min_value is not None and int_value < min_value:
            raise ValidationError(f"{field_name} must be at least {min_value}")
        
        if max_value is not None and int_value > max_value:
            raise ValidationError(f"{field_name} must be no more than {max_value}")
        
        return int_value
    
    @staticmethod
    def validate_float(
        value: Any,
        field_name: str,
        min_value: Optional[float] = None,
        max_value: Optional[float] = None,
        required: bool = True
    ) -> Optional[float]:
        """
        Validate float field
        
        Args:
            value: Value to validate
            field_name: Field name for error messages
            min_value: Minimum allowed value
            max_value: Maximum allowed value
            required: Whether field is required
            
        Returns:
            Validated float or None
            
        Raises:
            ValidationError: If validation fails
        """
        if value is None:
            if required:
                raise ValidationError(f"{field_name} is required")
            return None
        
        try:
            float_value = float(value)
        except (ValueError, TypeError):
            raise ValidationError(f"{field_name} must be a valid number")
        
        if min_value is not None and float_value < min_value:
            raise ValidationError(f"{field_name} must be at least {min_value}")
        
        if max_value is not None and float_value > max_value:
            raise ValidationError(f"{field_name} must be no more than {max_value}")
        
        return float_value
    
    @staticmethod
    def validate_boolean(
        value: Any,
        field_name: str,
        required: bool = True
    ) -> Optional[bool]:
        """
        Validate boolean field
        
        Args:
            value: Value to validate
            field_name: Field name for error messages
            required: Whether field is required
            
        Returns:
            Validated boolean or None
            
        Raises:
            ValidationError: If validation fails
        """
        if value is None:
            if required:
                raise ValidationError(f"{field_name} is required")
            return None
        
        if isinstance(value, bool):
            return value
        
        # Handle string representations
        if isinstance(value, str):
            lower_value = value.lower()
            if lower_value in ('true', '1', 'yes', 'on'):
                return True
            elif lower_value in ('false', '0', 'no', 'off'):
                return False
        
        # Handle numeric representations
        try:
            numeric_value = float(value)
            return bool(numeric_value)
        except (ValueError, TypeError):
            pass
        
        raise ValidationError(f"{field_name} must be a valid boolean value")
    
    @staticmethod
    def validate_datetime(
        value: Any,
        field_name: str,
        required: bool = True
    ) -> Optional[datetime]:
        """
        Validate datetime field
        
        Args:
            value: Value to validate
            field_name: Field name for error messages
            required: Whether field is required
            
        Returns:
            Validated datetime or None
            
        Raises:
            ValidationError: If validation fails
        """
        if value is None:
            if required:
                raise ValidationError(f"{field_name} is required")
            return None
        
        if isinstance(value, datetime):
            return value
        
        # Try to parse string datetime
        if isinstance(value, str):
            try:
                # Try ISO format first
                return datetime.fromisoformat(value.replace('Z', '+00:00'))
            except ValueError:
                try:
                    # Try common format
                    return datetime.strptime(value, '%Y-%m-%d %H:%M:%S')
                except ValueError:
                    pass
        
        # Try timestamp (int or float)
        try:
            timestamp = float(value)
            # Handle milliseconds
            if timestamp > 1e10:
                timestamp = timestamp / 1000
            return datetime.fromtimestamp(timestamp)
        except (ValueError, TypeError, OSError):
            pass
        
        raise ValidationError(f"{field_name} must be a valid datetime")
    
    @staticmethod
    def validate_enum(
        value: Any,
        field_name: str,
        allowed_values: List[str],
        required: bool = True,
        case_sensitive: bool = False
    ) -> Optional[str]:
        """
        Validate enum/choice field
        
        Args:
            value: Value to validate
            field_name: Field name for error messages
            allowed_values: List of allowed values
            required: Whether field is required
            case_sensitive: Whether comparison is case sensitive
            
        Returns:
            Validated value or None
            
        Raises:
            ValidationError: If validation fails
        """
        if value is None:
            if required:
                raise ValidationError(f"{field_name} is required")
            return None
        
        str_value = str(value)
        
        # Check against allowed values
        if case_sensitive:
            if str_value in allowed_values:
                return str_value
        else:
            str_value_lower = str_value.lower()
            allowed_lower = [v.lower() for v in allowed_values]
            if str_value_lower in allowed_lower:
                # Return original casing from allowed_values
                index = allowed_lower.index(str_value_lower)
                return allowed_values[index]
        
        raise ValidationError(f"{field_name} must be one of: {', '.join(allowed_values)}")
    
    @staticmethod
    def validate_log_entry(log_data: Dict[str, Any]) -> Dict[str, Any]:
        """
        Validate optimized log entry data
        
        Args:
            log_data: Raw log entry data
            
        Returns:
            Validated and sanitized log data
            
        Raises:
            ValidationError: If validation fails
        """
        try:
            validated = {}
            
            # Required fields
            validated['requestId'] = InputValidator.validate_string(
                log_data.get('requestId'), 'requestId', 
                min_length=10, max_length=100, required=True
            )
            
            validated['companyId'] = InputValidator.validate_uuid(
                log_data.get('companyId'), 'companyId'
            )
            
            validated['timestamp'] = InputValidator.validate_integer(
                log_data.get('timestamp'), 'timestamp',
                min_value=1000000000000,  # Reasonable timestamp in ms
                max_value=9999999999999
            )
            
            validated['method'] = InputValidator.validate_enum(
                log_data.get('method'), 'method',
                ['GET', 'POST', 'PUT', 'PATCH', 'DELETE', 'OPTIONS', 'HEAD']
            )
            
            validated['endpoint'] = InputValidator.validate_string(
                log_data.get('endpoint'), 'endpoint',
                min_length=1, max_length=200, required=True
            )
            
            validated['vendor'] = InputValidator.validate_string(
                log_data.get('vendor'), 'vendor', pattern='vendor_name', required=True
            )
            
            validated['model'] = InputValidator.validate_string(
                log_data.get('model'), 'model', pattern='model_name', required=True
            )
            
            validated['inputTokens'] = InputValidator.validate_integer(
                log_data.get('inputTokens'), 'inputTokens',
                min_value=0, max_value=1000000
            )
            
            validated['outputTokens'] = InputValidator.validate_integer(
                log_data.get('outputTokens'), 'outputTokens',
                min_value=0, max_value=1000000
            )
            
            validated['totalLatency'] = InputValidator.validate_integer(
                log_data.get('totalLatency'), 'totalLatency',
                min_value=0, max_value=300000  # 5 minutes max
            )
            
            validated['vendorLatency'] = InputValidator.validate_integer(
                log_data.get('vendorLatency'), 'vendorLatency',
                min_value=0, max_value=300000
            )
            
            validated['statusCode'] = InputValidator.validate_integer(
                log_data.get('statusCode'), 'statusCode',
                min_value=100, max_value=599
            )
            
            validated['success'] = InputValidator.validate_boolean(
                log_data.get('success'), 'success', required=True
            )
            
            validated['cost'] = InputValidator.validate_float(
                log_data.get('cost'), 'cost',
                min_value=0.0, max_value=1000.0, required=True
            )
            
            # Optional fields
            validated['userId'] = InputValidator.validate_string(
                log_data.get('userId'), 'userId',
                min_length=1, max_length=100, required=False
            )
            
            validated['userAgent'] = InputValidator.validate_string(
                log_data.get('userAgent'), 'userAgent',
                max_length=500, required=False
            )
            
            validated['url'] = InputValidator.validate_string(
                log_data.get('url'), 'url',
                pattern='url', required=False
            )
            
            validated['errorMessage'] = InputValidator.validate_string(
                log_data.get('errorMessage'), 'errorMessage',
                max_length=1000, required=False
            )
            
            validated['errorCode'] = InputValidator.validate_string(
                log_data.get('errorCode'), 'errorCode',
                max_length=50, required=False
            )
            
            validated['country'] = InputValidator.validate_string(
                log_data.get('country'), 'country',
                max_length=3, required=False
            )
            
            validated['region'] = InputValidator.validate_string(
                log_data.get('region'), 'region',
                max_length=100, required=False
            )
            
            validated['ipAddress'] = InputValidator.validate_string(
                log_data.get('ipAddress'), 'ipAddress',
                pattern='ip_address', required=False
            )
            
            return validated
            
        except Exception as e:
            logger.error(f"Log entry validation failed: {str(e)}")
            raise ValidationError(f"Invalid log entry data: {str(e)}")
    
    @staticmethod
    def validate_company_data(company_data: Dict[str, Any]) -> Dict[str, Any]:
        """
        Validate company data
        
        Args:
            company_data: Raw company data
            
        Returns:
            Validated company data
            
        Raises:
            ValidationError: If validation fails
        """
        try:
            validated = {}
            
            validated['name'] = InputValidator.validate_string(
                company_data.get('name'), 'name',
                pattern='company_name', required=True
            )
            
            validated['slug'] = InputValidator.validate_string(
                company_data.get('slug'), 'slug',
                pattern='slug', required=True
            )
            
            validated['description'] = InputValidator.validate_string(
                company_data.get('description'), 'description',
                max_length=500, required=False
            )
            
            validated['rate_limit_rps'] = InputValidator.validate_integer(
                company_data.get('rate_limit_rps'), 'rate_limit_rps',
                min_value=1, max_value=10000, required=False
            )
            
            validated['monthly_quota'] = InputValidator.validate_integer(
                company_data.get('monthly_quota'), 'monthly_quota',
                min_value=0, max_value=1000000, required=False
            )
            
            validated['is_active'] = InputValidator.validate_boolean(
                company_data.get('is_active'), 'is_active', required=False
            )
            
            return validated
            
        except Exception as e:
            logger.error(f"Company data validation failed: {str(e)}")
            raise ValidationError(f"Invalid company data: {str(e)}")
    
    @staticmethod
    def sanitize_input(value: Any) -> Any:
        """
        Sanitize input to prevent XSS and injection attacks
        
        Args:
            value: Input value to sanitize
            
        Returns:
            Sanitized value
        """
        if isinstance(value, str):
            # Remove potentially dangerous characters
            value = re.sub(r'[<>"\']', '', value)
            # Remove control characters
            value = re.sub(r'[\x00-\x1f\x7f-\x9f]', '', value)
            # Trim whitespace
            value = value.strip()
        
        return value
    
    @staticmethod
    def validate_pagination(
        page: Any = 1,
        limit: Any = 20,
        max_limit: int = 1000
    ) -> Tuple[int, int]:
        """
        Validate pagination parameters
        
        Args:
            page: Page number
            limit: Items per page
            max_limit: Maximum allowed limit
            
        Returns:
            Tuple of (validated_page, validated_limit)
            
        Raises:
            ValidationError: If validation fails
        """
        validated_page = InputValidator.validate_integer(
            page, 'page', min_value=1, max_value=10000, required=False
        ) or 1
        
        validated_limit = InputValidator.validate_integer(
            limit, 'limit', min_value=1, max_value=max_limit, required=False
        ) or 20
        
        return validated_page, validated_limit

class RequestValidator:
    """Request-level validation for API endpoints"""
    
    @staticmethod
    def validate_headers(headers: Dict[str, str]) -> Dict[str, Any]:
        """Validate request headers"""
        validated = {}
        
        # Validate common headers
        if 'user-agent' in headers:
            validated['user_agent'] = InputValidator.validate_string(
                headers['user-agent'], 'user-agent',
                max_length=500, required=False
            )
        
        if 'referer' in headers or 'referrer' in headers:
            referer = headers.get('referer') or headers.get('referrer')
            validated['referer'] = InputValidator.validate_string(
                referer, 'referer', max_length=500, required=False
            )
        
        return validated
    
    @staticmethod
    def validate_query_params(params: Dict[str, Any]) -> Dict[str, Any]:
        """Validate query parameters"""
        validated = {}
        
        # Common query parameters
        if 'page' in params or 'limit' in params:
            page, limit = InputValidator.validate_pagination(
                params.get('page'), params.get('limit')
            )
            validated['page'] = page
            validated['limit'] = limit
        
        if 'sort' in params:
            validated['sort'] = InputValidator.validate_enum(
                params['sort'], 'sort',
                ['created_at', 'updated_at', 'name', 'cost', 'timestamp'],
                required=False
            )
        
        if 'order' in params:
            validated['order'] = InputValidator.validate_enum(
                params['order'], 'order',
                ['asc', 'desc'], required=False
            )
        
        return validated

# Export the main classes and functions
__all__ = [
    'InputValidator',
    'RequestValidator', 
    'ValidationError',
    'ValidationLevel'
]
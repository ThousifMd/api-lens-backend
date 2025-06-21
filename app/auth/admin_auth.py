"""
Admin Authentication - Secure authentication for administrative endpoints
Implements JWT-based authentication with role verification and audit logging
"""

import json
import logging
import time
from datetime import datetime, timedelta, timezone
from typing import Optional, Dict, Any
import jwt
from fastapi import HTTPException, Depends, Request
from fastapi.security import HTTPBearer, HTTPAuthorizationCredentials
import hashlib
import secrets

from ..config import get_settings
from ..utils.logger import get_logger
from ..database import DatabaseUtils

settings = get_settings()
logger = get_logger(__name__)

# Security configuration
security = HTTPBearer()
JWT_SECRET_KEY = settings.JWT_SECRET_KEY if hasattr(settings, 'JWT_SECRET_KEY') else secrets.token_urlsafe(32)
JWT_ALGORITHM = "HS256"
JWT_EXPIRATION_HOURS = 24

# Admin roles and permissions
class AdminRole:
    SUPER_ADMIN = "super_admin"      # Full system access
    SYSTEM_ADMIN = "system_admin"    # System management, no user data access
    SUPPORT_ADMIN = "support_admin"  # Read-only access for support
    BILLING_ADMIN = "billing_admin"  # Billing and usage data access

class AdminPermission:
    # Company management
    CREATE_COMPANY = "create_company"
    UPDATE_COMPANY = "update_company"
    DELETE_COMPANY = "delete_company"
    VIEW_COMPANY = "view_company"
    
    # System management
    UPDATE_PRICING = "update_pricing"
    VIEW_SYSTEM_HEALTH = "view_system_health"
    UPDATE_SYSTEM_CONFIG = "update_system_config"
    
    # Analytics and monitoring
    VIEW_SYSTEM_ANALYTICS = "view_system_analytics"
    VIEW_COMPANY_ANALYTICS = "view_company_analytics"
    
    # Security
    MANAGE_ADMIN_USERS = "manage_admin_users"
    VIEW_AUDIT_LOGS = "view_audit_logs"

# Role permissions mapping
ROLE_PERMISSIONS = {
    AdminRole.SUPER_ADMIN: [
        AdminPermission.CREATE_COMPANY,
        AdminPermission.UPDATE_COMPANY,
        AdminPermission.DELETE_COMPANY,
        AdminPermission.VIEW_COMPANY,
        AdminPermission.UPDATE_PRICING,
        AdminPermission.VIEW_SYSTEM_HEALTH,
        AdminPermission.UPDATE_SYSTEM_CONFIG,
        AdminPermission.VIEW_SYSTEM_ANALYTICS,
        AdminPermission.VIEW_COMPANY_ANALYTICS,
        AdminPermission.MANAGE_ADMIN_USERS,
        AdminPermission.VIEW_AUDIT_LOGS,
    ],
    AdminRole.SYSTEM_ADMIN: [
        AdminPermission.VIEW_COMPANY,
        AdminPermission.UPDATE_PRICING,
        AdminPermission.VIEW_SYSTEM_HEALTH,
        AdminPermission.UPDATE_SYSTEM_CONFIG,
        AdminPermission.VIEW_SYSTEM_ANALYTICS,
    ],
    AdminRole.SUPPORT_ADMIN: [
        AdminPermission.VIEW_COMPANY,
        AdminPermission.VIEW_SYSTEM_HEALTH,
        AdminPermission.VIEW_COMPANY_ANALYTICS,
    ],
    AdminRole.BILLING_ADMIN: [
        AdminPermission.VIEW_COMPANY,
        AdminPermission.UPDATE_PRICING,
        AdminPermission.VIEW_SYSTEM_ANALYTICS,
        AdminPermission.VIEW_COMPANY_ANALYTICS,
    ]
}

class AdminUser:
    """Admin user data model"""
    def __init__(self, user_id: str, username: str, email: str, role: str, 
                 permissions: list, is_active: bool = True):
        self.user_id = user_id
        self.username = username
        self.email = email
        self.role = role
        self.permissions = permissions
        self.is_active = is_active

class AdminTokenData:
    """Admin JWT token data"""
    def __init__(self, user_id: str, username: str, role: str, permissions: list, 
                 issued_at: int, expires_at: int):
        self.user_id = user_id
        self.username = username
        self.role = role
        self.permissions = permissions
        self.issued_at = issued_at
        self.expires_at = expires_at

async def create_admin_token(admin_user: AdminUser) -> str:
    """Create JWT token for admin user"""
    try:
        current_time = int(time.time())
        expiration_time = current_time + (JWT_EXPIRATION_HOURS * 3600)
        
        payload = {
            "user_id": admin_user.user_id,
            "username": admin_user.username,
            "email": admin_user.email,
            "role": admin_user.role,
            "permissions": admin_user.permissions,
            "iat": current_time,
            "exp": expiration_time,
            "type": "admin_access"
        }
        
        token = jwt.encode(payload, JWT_SECRET_KEY, algorithm=JWT_ALGORITHM)
        
        # Log token creation for audit
        await _log_admin_action(
            admin_user.user_id,
            "token_created",
            {"expires_at": expiration_time}
        )
        
        return token
        
    except Exception as e:
        logger.error(f"Failed to create admin token: {e}")
        raise HTTPException(status_code=500, detail="Failed to create authentication token")

async def verify_admin_token(credentials: HTTPAuthorizationCredentials = Depends(security)) -> AdminTokenData:
    """Verify and decode admin JWT token"""
    try:
        token = credentials.credentials
        
        # Decode JWT token
        payload = jwt.decode(token, JWT_SECRET_KEY, algorithms=[JWT_ALGORITHM])
        
        # Validate token type
        if payload.get("type") != "admin_access":
            raise HTTPException(status_code=401, detail="Invalid token type")
        
        # Extract token data
        user_id = payload.get("user_id")
        username = payload.get("username")
        role = payload.get("role")
        permissions = payload.get("permissions", [])
        issued_at = payload.get("iat")
        expires_at = payload.get("exp")
        
        if not user_id or not username or not role:
            raise HTTPException(status_code=401, detail="Invalid token payload")
        
        # Verify admin user is still active
        admin_user = await _get_admin_user(user_id)
        if not admin_user or not admin_user.is_active:
            raise HTTPException(status_code=401, detail="Admin user inactive or not found")
        
        # Create token data object
        token_data = AdminTokenData(
            user_id=user_id,
            username=username,
            role=role,
            permissions=permissions,
            issued_at=issued_at,
            expires_at=expires_at
        )
        
        return token_data
        
    except jwt.ExpiredSignatureError:
        raise HTTPException(status_code=401, detail="Token has expired")
    except jwt.InvalidTokenError:
        raise HTTPException(status_code=401, detail="Invalid authentication token")
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Failed to verify admin token: {e}")
        raise HTTPException(status_code=401, detail="Token verification failed")

def require_permission(permission: str):
    """Decorator to require specific permission for endpoint access"""
    def permission_dependency(token_data: AdminTokenData = Depends(verify_admin_token)) -> AdminTokenData:
        if permission not in token_data.permissions:
            raise HTTPException(
                status_code=403, 
                detail=f"Insufficient permissions. Required: {permission}"
            )
        return token_data
    
    return permission_dependency

def require_role(required_role: str):
    """Decorator to require specific role for endpoint access"""
    def role_dependency(token_data: AdminTokenData = Depends(verify_admin_token)) -> AdminTokenData:
        if token_data.role != required_role and token_data.role != AdminRole.SUPER_ADMIN:
            raise HTTPException(
                status_code=403, 
                detail=f"Insufficient role. Required: {required_role}"
            )
        return token_data
    
    return role_dependency

async def authenticate_admin(username: str, password: str) -> Optional[AdminUser]:
    """Authenticate admin user with username/password"""
    try:
        # Get admin user from database
        query = """
            SELECT id, username, email, password_hash, role, is_active, 
                   last_login_at, failed_login_attempts, locked_until
            FROM admin_users 
            WHERE username = :username AND is_active = true
        """
        
        user_data = await DatabaseUtils.execute_query(
            query, 
            {'username': username}, 
            fetch_one=True
        )
        
        if not user_data:
            # Log failed login attempt
            await _log_admin_action(
                None,
                "login_failed",
                {"username": username, "reason": "user_not_found"}
            )
            return None
        
        # Check if account is locked
        if user_data['locked_until'] and user_data['locked_until'] > datetime.now(timezone.utc):
            await _log_admin_action(
                user_data['id'],
                "login_failed",
                {"username": username, "reason": "account_locked"}
            )
            return None
        
        # Verify password
        if not _verify_password(password, user_data['password_hash']):
            # Increment failed attempts
            await _increment_failed_login_attempts(user_data['id'])
            await _log_admin_action(
                user_data['id'],
                "login_failed",
                {"username": username, "reason": "invalid_password"}
            )
            return None
        
        # Reset failed attempts on successful login
        await _reset_failed_login_attempts(user_data['id'])
        
        # Get user permissions based on role
        permissions = ROLE_PERMISSIONS.get(user_data['role'], [])
        
        # Create admin user object
        admin_user = AdminUser(
            user_id=user_data['id'],
            username=user_data['username'],
            email=user_data['email'],
            role=user_data['role'],
            permissions=permissions,
            is_active=user_data['is_active']
        )
        
        # Update last login
        await _update_last_login(user_data['id'])
        
        # Log successful login
        await _log_admin_action(
            user_data['id'],
            "login_success",
            {"username": username}
        )
        
        return admin_user
        
    except Exception as e:
        logger.error(f"Failed to authenticate admin user: {e}")
        return None

async def create_admin_user(username: str, email: str, password: str, role: str, 
                          created_by: str) -> AdminUser:
    """Create new admin user with proper validation"""
    try:
        # Validate role
        if role not in ROLE_PERMISSIONS:
            raise ValueError(f"Invalid role: {role}")
        
        # Hash password
        password_hash = _hash_password(password)
        
        # Generate user ID
        user_id = str(uuid.uuid4())
        current_time = datetime.now(timezone.utc)
        
        # Insert admin user
        query = """
            INSERT INTO admin_users (
                id, username, email, password_hash, role, is_active,
                created_by, created_at, updated_at
            ) VALUES (
                :id, :username, :email, :password_hash, :role, :is_active,
                :created_by, :created_at, :updated_at
            )
        """
        
        await DatabaseUtils.execute_query(query, {
            'id': user_id,
            'username': username,
            'email': email,
            'password_hash': password_hash,
            'role': role,
            'is_active': True,
            'created_by': created_by,
            'created_at': current_time,
            'updated_at': current_time
        })
        
        # Get permissions for role
        permissions = ROLE_PERMISSIONS.get(role, [])
        
        # Create admin user object
        admin_user = AdminUser(
            user_id=user_id,
            username=username,
            email=email,
            role=role,
            permissions=permissions,
            is_active=True
        )
        
        # Log admin user creation
        await _log_admin_action(
            created_by,
            "admin_user_created",
            {"new_user_id": user_id, "username": username, "role": role}
        )
        
        return admin_user
        
    except Exception as e:
        logger.error(f"Failed to create admin user: {e}")
        raise

# Helper functions

async def _get_admin_user(user_id: str) -> Optional[AdminUser]:
    """Get admin user by ID"""
    try:
        query = """
            SELECT id, username, email, role, is_active
            FROM admin_users 
            WHERE id = :user_id
        """
        
        user_data = await DatabaseUtils.execute_query(
            query, 
            {'user_id': user_id}, 
            fetch_one=True
        )
        
        if not user_data:
            return None
        
        permissions = ROLE_PERMISSIONS.get(user_data['role'], [])
        
        return AdminUser(
            user_id=user_data['id'],
            username=user_data['username'],
            email=user_data['email'],
            role=user_data['role'],
            permissions=permissions,
            is_active=user_data['is_active']
        )
        
    except Exception as e:
        logger.error(f"Failed to get admin user {user_id}: {e}")
        return None

def _hash_password(password: str) -> str:
    """Hash password using SHA-256 with salt"""
    salt = secrets.token_hex(16)
    password_hash = hashlib.sha256((password + salt).encode()).hexdigest()
    return f"{salt}${password_hash}"

def _verify_password(password: str, stored_hash: str) -> bool:
    """Verify password against stored hash"""
    try:
        salt, stored_password_hash = stored_hash.split('$', 1)
        password_hash = hashlib.sha256((password + salt).encode()).hexdigest()
        return password_hash == stored_password_hash
    except Exception:
        return False

async def _increment_failed_login_attempts(user_id: str):
    """Increment failed login attempts and lock account if needed"""
    try:
        query = """
            UPDATE admin_users 
            SET failed_login_attempts = failed_login_attempts + 1,
                locked_until = CASE 
                    WHEN failed_login_attempts >= 4 THEN CURRENT_TIMESTAMP + INTERVAL '1 hour'
                    ELSE locked_until 
                END
            WHERE id = :user_id
        """
        
        await DatabaseUtils.execute_query(query, {'user_id': user_id})
        
    except Exception as e:
        logger.error(f"Failed to increment failed login attempts: {e}")

async def _reset_failed_login_attempts(user_id: str):
    """Reset failed login attempts on successful login"""
    try:
        query = """
            UPDATE admin_users 
            SET failed_login_attempts = 0, locked_until = NULL
            WHERE id = :user_id
        """
        
        await DatabaseUtils.execute_query(query, {'user_id': user_id})
        
    except Exception as e:
        logger.error(f"Failed to reset failed login attempts: {e}")

async def _update_last_login(user_id: str):
    """Update last login timestamp"""
    try:
        query = """
            UPDATE admin_users 
            SET last_login_at = CURRENT_TIMESTAMP
            WHERE id = :user_id
        """
        
        await DatabaseUtils.execute_query(query, {'user_id': user_id})
        
    except Exception as e:
        logger.error(f"Failed to update last login: {e}")

async def _log_admin_action(user_id: Optional[str], action: str, details: Dict[str, Any]):
    """Log admin action for audit trail"""
    try:
        query = """
            INSERT INTO admin_audit_log (
                id, user_id, action, details, ip_address, user_agent, created_at
            ) VALUES (
                :id, :user_id, :action, :details, :ip_address, :user_agent, :created_at
            )
        """
        
        import uuid
        await DatabaseUtils.execute_query(query, {
            'id': str(uuid.uuid4()),
            'user_id': user_id,
            'action': action,
            'details': json.dumps(details),
            'ip_address': None,  # Would be extracted from request context
            'user_agent': None,  # Would be extracted from request context
            'created_at': datetime.now(timezone.utc)
        })
        
    except Exception as e:
        logger.error(f"Failed to log admin action: {e}")

# For development/testing - create default admin user
async def create_default_admin():
    """Create default admin user for development"""
    try:
        # Check if any admin users exist
        query = "SELECT COUNT(*) as count FROM admin_users"
        result = await DatabaseUtils.execute_query(query, {}, fetch_one=True)
        
        if result['count'] == 0:
            # Create default super admin
            admin_user = await create_admin_user(
                username="admin",
                email="admin@apilens.dev",
                password="admin123",  # Change in production!
                role=AdminRole.SUPER_ADMIN,
                created_by="system"
            )
            
            logger.info("Created default admin user: admin/admin123")
            return admin_user
        
    except Exception as e:
        logger.error(f"Failed to create default admin: {e}")
        return None
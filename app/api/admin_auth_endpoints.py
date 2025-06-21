"""
Admin Authentication Endpoints - Login, logout, and session management
Provides secure authentication endpoints for administrative access
"""

import logging
from datetime import datetime, timezone
from typing import Optional

from fastapi import APIRouter, HTTPException, Depends, Form, status
from fastapi.responses import JSONResponse
from pydantic import BaseModel, Field

from ..config import get_settings
from ..utils.logger import get_logger
from ..auth.admin_auth import (
    authenticate_admin, create_admin_token, verify_admin_token,
    AdminTokenData, AdminUser
)

settings = get_settings()
logger = get_logger(__name__)

# Create auth router
auth_router = APIRouter(
    prefix="/admin/auth",
    tags=["Admin Authentication"]
)

# ============================================================================
# PYDANTIC MODELS
# ============================================================================

class LoginRequest(BaseModel):
    """Request model for admin login"""
    username: str = Field(..., min_length=1, max_length=50)
    password: str = Field(..., min_length=1)
    remember_me: bool = Field(default=False)

class LoginResponse(BaseModel):
    """Response model for successful login"""
    access_token: str
    token_type: str = "bearer"
    expires_in: int  # seconds
    user_info: dict

class TokenRefreshRequest(BaseModel):
    """Request model for token refresh"""
    refresh_token: str

class ChangePasswordRequest(BaseModel):
    """Request model for password change"""
    current_password: str = Field(..., min_length=1)
    new_password: str = Field(..., min_length=8, max_length=128)
    confirm_password: str = Field(..., min_length=8, max_length=128)

# ============================================================================
# AUTHENTICATION ENDPOINTS
# ============================================================================

@auth_router.post("/login", response_model=LoginResponse)
async def admin_login(login_data: LoginRequest):
    """
    Authenticate admin user and return JWT access token
    """
    try:
        # Authenticate user
        admin_user = await authenticate_admin(login_data.username, login_data.password)
        
        if not admin_user:
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail="Invalid username or password",
                headers={"WWW-Authenticate": "Bearer"}
            )
        
        # Create access token
        access_token = await create_admin_token(admin_user)
        
        # Calculate token expiration (24 hours)
        expires_in = 24 * 3600  # 24 hours in seconds
        
        # Prepare user info for response (no sensitive data)
        user_info = {
            "user_id": admin_user.user_id,
            "username": admin_user.username,
            "email": admin_user.email,
            "role": admin_user.role,
            "permissions": admin_user.permissions,
            "is_active": admin_user.is_active
        }
        
        logger.info(f"Admin user {admin_user.username} logged in successfully")
        
        return LoginResponse(
            access_token=access_token,
            token_type="bearer",
            expires_in=expires_in,
            user_info=user_info
        )
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Login failed for {login_data.username}: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Authentication service error"
        )

@auth_router.post("/logout", status_code=204)
async def admin_logout(token_data: AdminTokenData = Depends(verify_admin_token)):
    """
    Logout admin user and invalidate token
    """
    try:
        # In production, you would add the token to a blacklist
        # or implement proper session management
        
        # Log the logout event
        from ..auth.admin_auth import _log_admin_action
        await _log_admin_action(
            token_data.user_id,
            "logout",
            {"username": token_data.username}
        )
        
        logger.info(f"Admin user {token_data.username} logged out")
        
    except Exception as e:
        logger.error(f"Logout failed for {token_data.username}: {e}")
        # Don't raise exception for logout - just log it

@auth_router.get("/me")
async def get_current_admin_user(token_data: AdminTokenData = Depends(verify_admin_token)):
    """
    Get current admin user information
    """
    try:
        return {
            "user_id": token_data.user_id,
            "username": token_data.username,
            "role": token_data.role,
            "permissions": token_data.permissions,
            "issued_at": datetime.fromtimestamp(token_data.issued_at, timezone.utc).isoformat(),
            "expires_at": datetime.fromtimestamp(token_data.expires_at, timezone.utc).isoformat()
        }
        
    except Exception as e:
        logger.error(f"Failed to get current user info: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to retrieve user information"
        )

@auth_router.post("/change-password", status_code=200)
async def change_admin_password(
    password_data: ChangePasswordRequest,
    token_data: AdminTokenData = Depends(verify_admin_token)
):
    """
    Change admin user password
    """
    try:
        # Validate new password confirmation
        if password_data.new_password != password_data.confirm_password:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="New password and confirmation do not match"
            )
        
        # Verify current password
        admin_user = await authenticate_admin(token_data.username, password_data.current_password)
        if not admin_user:
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail="Current password is incorrect"
            )
        
        # Hash new password and update
        from ..auth.admin_auth import _hash_password
        from ..database import DatabaseUtils
        
        new_password_hash = _hash_password(password_data.new_password)
        current_time = datetime.now(timezone.utc)
        
        query = """
            UPDATE admin_users 
            SET password_hash = :password_hash,
                password_changed_at = :changed_at,
                last_password_change = :changed_at,
                updated_at = :changed_at
            WHERE id = :user_id
        """
        
        await DatabaseUtils.execute_query(query, {
            'password_hash': new_password_hash,
            'changed_at': current_time,
            'user_id': token_data.user_id
        })
        
        # Log password change
        from ..auth.admin_auth import _log_admin_action
        await _log_admin_action(
            token_data.user_id,
            "password_changed",
            {"username": token_data.username}
        )
        
        logger.info(f"Admin user {token_data.username} changed password")
        
        return {"message": "Password changed successfully"}
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Password change failed for {token_data.username}: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to change password"
        )

@auth_router.get("/sessions")
async def get_admin_sessions(token_data: AdminTokenData = Depends(verify_admin_token)):
    """
    Get active sessions for current admin user
    """
    try:
        from ..database import DatabaseUtils
        
        query = """
            SELECT 
                id, ip_address, user_agent, created_at, last_activity_at,
                expires_at, is_active, device_fingerprint
            FROM admin_sessions
            WHERE user_id = :user_id AND is_active = true
            ORDER BY last_activity_at DESC
        """
        
        sessions = await DatabaseUtils.execute_query(
            query,
            {'user_id': token_data.user_id},
            fetch_all=True
        )
        
        return {
            "active_sessions": len(sessions),
            "sessions": [
                {
                    "session_id": session['id'],
                    "ip_address": str(session['ip_address']) if session['ip_address'] else None,
                    "user_agent": session['user_agent'],
                    "created_at": session['created_at'].isoformat(),
                    "last_activity": session['last_activity_at'].isoformat(),
                    "expires_at": session['expires_at'].isoformat(),
                    "is_current": True  # Would need to determine current session
                }
                for session in sessions
            ]
        }
        
    except Exception as e:
        logger.error(f"Failed to get sessions for {token_data.username}: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to retrieve sessions"
        )

@auth_router.delete("/sessions/{session_id}", status_code=204)
async def terminate_admin_session(
    session_id: str,
    token_data: AdminTokenData = Depends(verify_admin_token)
):
    """
    Terminate a specific admin session
    """
    try:
        from ..database import DatabaseUtils
        
        # Verify session belongs to current user
        verify_query = """
            SELECT id FROM admin_sessions
            WHERE id = :session_id AND user_id = :user_id AND is_active = true
        """
        
        session = await DatabaseUtils.execute_query(
            verify_query,
            {'session_id': session_id, 'user_id': token_data.user_id},
            fetch_one=True
        )
        
        if not session:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="Session not found or not owned by current user"
            )
        
        # Terminate session
        terminate_query = """
            UPDATE admin_sessions
            SET is_active = false,
                terminated_by = 'user',
                terminated_at = CURRENT_TIMESTAMP,
                termination_reason = 'User requested termination'
            WHERE id = :session_id
        """
        
        await DatabaseUtils.execute_query(terminate_query, {'session_id': session_id})
        
        # Log session termination
        from ..auth.admin_auth import _log_admin_action
        await _log_admin_action(
            token_data.user_id,
            "session_terminated",
            {"username": token_data.username, "session_id": session_id}
        )
        
        logger.info(f"Admin user {token_data.username} terminated session {session_id}")
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Failed to terminate session {session_id}: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to terminate session"
        )

@auth_router.get("/audit-log")
async def get_admin_audit_log(
    token_data: AdminTokenData = Depends(verify_admin_token),
    limit: int = 50,
    offset: int = 0
):
    """
    Get audit log for current admin user
    """
    try:
        from ..database import DatabaseUtils
        
        query = """
            SELECT 
                action, details, ip_address, user_agent, success,
                error_message, risk_level, created_at
            FROM admin_audit_log
            WHERE user_id = :user_id
            ORDER BY created_at DESC
            LIMIT :limit OFFSET :offset
        """
        
        audit_entries = await DatabaseUtils.execute_query(
            query,
            {'user_id': token_data.user_id, 'limit': limit, 'offset': offset},
            fetch_all=True
        )
        
        # Get total count
        count_query = """
            SELECT COUNT(*) as total
            FROM admin_audit_log
            WHERE user_id = :user_id
        """
        
        count_result = await DatabaseUtils.execute_query(
            count_query,
            {'user_id': token_data.user_id},
            fetch_one=True
        )
        
        return {
            "total_entries": count_result['total'],
            "entries": [
                {
                    "action": entry['action'],
                    "details": entry['details'],
                    "ip_address": str(entry['ip_address']) if entry['ip_address'] else None,
                    "user_agent": entry['user_agent'],
                    "success": entry['success'],
                    "error_message": entry['error_message'],
                    "risk_level": entry['risk_level'],
                    "timestamp": entry['created_at'].isoformat()
                }
                for entry in audit_entries
            ]
        }
        
    except Exception as e:
        logger.error(f"Failed to get audit log for {token_data.username}: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to retrieve audit log"
        )
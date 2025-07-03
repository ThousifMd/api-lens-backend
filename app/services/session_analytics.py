"""
Session Analytics Service - Populate and manage user session data
Creates session records from request data based on user activity patterns
"""
import asyncio
from datetime import datetime, timedelta, timezone
from typing import Dict, Any, List, Optional
from uuid import UUID
import hashlib

from ..database import DatabaseUtils
from ..utils.logger import get_logger
from ..utils.db_errors import handle_database_error

logger = get_logger(__name__)

class SessionAnalyticsService:
    """Service for managing user session data"""
    
    @staticmethod
    def generate_session_id(client_user_id: str, ip_address: str, user_id_header: str, timestamp: datetime) -> str:
        """
        Generate a deterministic session ID based on user, IP, and time window
        Groups requests by user+IP within 30-minute windows
        """
        # Round timestamp to 30-minute windows for session grouping
        window_start = timestamp.replace(minute=(timestamp.minute // 30) * 30, second=0, microsecond=0)
        
        # Create deterministic session ID
        session_data = f"{client_user_id}:{ip_address}:{user_id_header}:{window_start.isoformat()}"
        session_hash = hashlib.md5(session_data.encode()).hexdigest()
        return f"session_{session_hash[:16]}"
    
    @staticmethod
    async def populate_user_sessions() -> Dict[str, Any]:
        """
        Populate user_sessions table from existing request data
        Groups requests by user, IP, and time windows to create logical sessions
        
        Returns:
            Dictionary with processing results
        """
        try:
            # First, aggregate request data into logical sessions
            session_query = """
                WITH session_data AS (
                    SELECT 
                        company_id,
                        client_user_id,
                        ip_address,
                        user_id_header,
                        -- Group requests into 30-minute windows for sessions
                        date_trunc('minute', timestamp_utc - interval '30 minutes' * 
                            (extract(minute from timestamp_utc)::integer / 30)
                        ) + interval '30 minutes' * 
                            (extract(minute from timestamp_utc)::integer / 30) as session_window,
                        COUNT(*) as request_count,
                        SUM(total_cost) as total_cost,
                        MIN(timestamp_utc) as started_at,
                        MAX(timestamp_utc) as ended_at,
                        MAX(timestamp_utc) as last_activity
                    FROM requests 
                    WHERE client_user_id IS NOT NULL 
                    AND ip_address IS NOT NULL
                    AND user_id_header IS NOT NULL
                    GROUP BY company_id, client_user_id, ip_address, user_id_header, session_window
                ),
                session_ids AS (
                    SELECT *,
                        CONCAT('session_', 
                            substring(md5(
                                CONCAT(client_user_id::text, ':', ip_address::text, ':', 
                                       user_id_header, ':', session_window::text)
                            ), 1, 16)
                        ) as session_id
                    FROM session_data
                )
                INSERT INTO user_sessions (
                    client_user_id, session_id, ip_address, 
                    started_at_utc, started_at_local,
                    ended_at_utc, ended_at_local,
                    last_activity_at_utc, last_activity_at_local,
                    request_count, total_cost_usd, is_active
                )
                SELECT 
                    s.client_user_id,
                    s.session_id,
                    s.ip_address,
                    s.started_at as started_at_utc,
                    s.started_at as started_at_local,  -- Using UTC for now
                    s.ended_at as ended_at_utc,
                    s.ended_at as ended_at_local,     -- Using UTC for now
                    s.last_activity as last_activity_at_utc,
                    s.last_activity as last_activity_at_local,  -- Using UTC for now
                    s.request_count,
                    s.total_cost as total_cost_usd,
                    CASE 
                        WHEN s.last_activity > NOW() - INTERVAL '1 hour' THEN true 
                        ELSE false 
                    END as is_active
                FROM session_ids s
                ON CONFLICT (client_user_id, session_id) 
                DO UPDATE SET
                    ended_at_utc = EXCLUDED.ended_at_utc,
                    ended_at_local = EXCLUDED.ended_at_local,
                    last_activity_at_utc = EXCLUDED.last_activity_at_utc,
                    last_activity_at_local = EXCLUDED.last_activity_at_local,
                    request_count = EXCLUDED.request_count,
                    total_cost_usd = EXCLUDED.total_cost_usd,
                    is_active = EXCLUDED.is_active
            """
            
            await DatabaseUtils.execute_query(
                session_query,
                [],
                fetch_all=False
            )
            
            # Get count of created sessions
            count_query = """
                SELECT 
                    COUNT(*) as total_sessions,
                    COUNT(DISTINCT client_user_id) as unique_users,
                    COUNT(CASE WHEN is_active THEN 1 END) as active_sessions,
                    SUM(request_count) as total_requests,
                    SUM(total_cost_usd) as total_cost
                FROM user_sessions
            """
            
            result = await DatabaseUtils.execute_query(
                count_query,
                [],
                fetch_all=False
            )
            
            logger.info(f"Populated user sessions: {result['total_sessions']} sessions for {result['unique_users']} users")
            
            return {
                "status": "success",
                "total_sessions": result['total_sessions'] or 0,
                "unique_users": result['unique_users'] or 0,
                "active_sessions": result['active_sessions'] or 0,
                "total_requests": result['total_requests'] or 0,
                "total_cost": float(result['total_cost'] or 0),
                "timestamp": datetime.utcnow().isoformat()
            }
            
        except Exception as e:
            error_info = handle_database_error(e)
            logger.error(f"Failed to populate user sessions: {error_info['user_message']}")
            return {
                "status": "error",
                "error": error_info['user_message'],
                "timestamp": datetime.utcnow().isoformat()
            }
    
    @staticmethod
    async def get_session_summary(company_id: Optional[UUID] = None) -> Dict[str, Any]:
        """
        Get session analytics summary
        
        Args:
            company_id: Optional company filter
            
        Returns:
            Dictionary with session summary
        """
        try:
            where_clause = "WHERE company_id = $1" if company_id else ""
            params = [company_id] if company_id else []
            
            query = f"""
                SELECT 
                    COUNT(*) as total_sessions,
                    COUNT(DISTINCT client_user_id) as unique_users,
                    COUNT(CASE WHEN is_active THEN 1 END) as active_sessions,
                    AVG(request_count) as avg_requests_per_session,
                    AVG(total_cost_usd) as avg_cost_per_session,
                    AVG(EXTRACT(epoch FROM (ended_at_utc - started_at_utc))) as avg_session_duration_seconds,
                    COUNT(DISTINCT ip_address) as unique_ips
                FROM user_sessions
                {where_clause}
            """
            
            result = await DatabaseUtils.execute_query(
                query,
                params,
                fetch_all=False
            )
            
            if result:
                return {
                    "company_id": str(company_id) if company_id else "all",
                    "summary": {
                        "total_sessions": result['total_sessions'] or 0,
                        "unique_users": result['unique_users'] or 0,
                        "active_sessions": result['active_sessions'] or 0,
                        "avg_requests_per_session": float(result['avg_requests_per_session'] or 0),
                        "avg_cost_per_session": float(result['avg_cost_per_session'] or 0),
                        "avg_session_duration_seconds": float(result['avg_session_duration_seconds'] or 0),
                        "unique_ips": result['unique_ips'] or 0
                    },
                    "timestamp": datetime.utcnow().isoformat()
                }
            else:
                return {
                    "company_id": str(company_id) if company_id else "all",
                    "summary": None,
                    "message": "No session data found",
                    "timestamp": datetime.utcnow().isoformat()
                }
                
        except Exception as e:
            error_info = handle_database_error(e)
            logger.error(f"Failed to get session summary: {error_info['user_message']}")
            return {
                "company_id": str(company_id) if company_id else "all",
                "error": error_info['user_message'],
                "timestamp": datetime.utcnow().isoformat()
            }
    
    @staticmethod
    async def update_session_from_request(request_data: Dict[str, Any]) -> Optional[str]:
        """
        Update or create a session record from a new request
        Used for real-time session tracking
        
        Args:
            request_data: Dictionary containing request information
            
        Returns:
            Session ID if successful, None if failed
        """
        try:
            if not all(key in request_data for key in ['client_user_id', 'ip_address', 'user_id_header', 'timestamp_utc']):
                logger.warning("Missing required fields for session update")
                return None
            
            # Generate session ID
            session_id = SessionAnalyticsService.generate_session_id(
                str(request_data['client_user_id']),
                str(request_data['ip_address']),
                request_data['user_id_header'],
                request_data['timestamp_utc']
            )
            
            # Upsert session record
            upsert_query = """
                INSERT INTO user_sessions (
                    client_user_id, session_id, ip_address,
                    started_at_utc, started_at_local,
                    last_activity_at_utc, last_activity_at_local,
                    request_count, total_cost_usd, is_active
                )
                VALUES ($1, $2, $3, $4, $4, $4, $4, 1, $5, true)
                ON CONFLICT (client_user_id, session_id)
                DO UPDATE SET
                    last_activity_at_utc = $4,
                    last_activity_at_local = $4,
                    request_count = user_sessions.request_count + 1,
                    total_cost_usd = user_sessions.total_cost_usd + $5,
                    is_active = true
            """
            
            await DatabaseUtils.execute_query(
                upsert_query,
                [
                    request_data['client_user_id'],
                    session_id,
                    request_data['ip_address'],
                    request_data['timestamp_utc'],
                    request_data.get('total_cost', 0)
                ],
                fetch_all=False
            )
            
            return session_id
            
        except Exception as e:
            logger.error(f"Failed to update session from request: {e}")
            return None

# Background functions for session management

async def cleanup_inactive_sessions(hours_inactive: int = 24):
    """Mark sessions as inactive if no activity for specified hours"""
    try:
        cleanup_query = """
            UPDATE user_sessions 
            SET is_active = false
            WHERE is_active = true 
            AND last_activity_at_utc < NOW() - INTERVAL '%s hours'
        """ % hours_inactive
        
        result = await DatabaseUtils.execute_query(cleanup_query, [], fetch_all=False)
        logger.info(f"Marked inactive sessions (>{hours_inactive}h) as inactive")
        
    except Exception as e:
        logger.error(f"Failed to cleanup inactive sessions: {e}")

async def populate_sessions_from_requests():
    """Convenience function to populate all sessions from request data"""
    service = SessionAnalyticsService()
    return await service.populate_user_sessions()
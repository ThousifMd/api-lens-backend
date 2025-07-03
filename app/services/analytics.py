"""
Analytics Service - Populate and manage user analytics data
Handles aggregation of request data into hourly and daily analytics tables
"""
import asyncio
from datetime import datetime, timedelta, timezone
from typing import Dict, Any, List, Optional
from uuid import UUID

from ..database import DatabaseUtils
from ..utils.logger import get_logger
from ..utils.db_errors import handle_database_error

logger = get_logger(__name__)

class AnalyticsService:
    """Service for managing analytics data aggregation"""
    
    @staticmethod
    async def populate_hourly_analytics(hour_start: Optional[datetime] = None) -> Dict[str, Any]:
        """
        Populate hourly analytics table for a specific hour
        
        Args:
            hour_start: Start of the hour to process (defaults to current hour)
            
        Returns:
            Dictionary with processing results
        """
        if hour_start is None:
            # Default to current hour start
            now = datetime.now(timezone.utc)
            hour_start = now.replace(minute=0, second=0, microsecond=0)
        
        hour_end = hour_start + timedelta(hours=1)
        
        try:
            # Aggregate data from requests table
            query = """
                INSERT INTO user_analytics_hourly (
                    company_id, client_user_id, vendor_id, model_id,
                    hour_bucket_utc, hour_bucket_local, timezone_name,
                    request_count, success_count, error_count,
                    total_tokens, total_cost, avg_latency_ms, created_at
                )
                SELECT 
                    r.company_id,
                    r.client_user_id,
                    r.vendor_id,
                    r.model_id,
                    date_trunc('hour', r.timestamp_utc) as hour_bucket_utc,
                    date_trunc('hour', r.timestamp_utc) as hour_bucket_local,
                    'UTC' as timezone_name,
                    COUNT(*) as request_count,
                    SUM(CASE WHEN r.status_code < 400 THEN 1 ELSE 0 END) as success_count,
                    SUM(CASE WHEN r.status_code >= 400 THEN 1 ELSE 0 END) as error_count,
                    COALESCE(SUM(r.total_tokens), 0) as total_tokens,
                    COALESCE(SUM(r.total_cost), 0) as total_cost,
                    COALESCE(AVG(r.total_latency_ms), 0) as avg_latency_ms,
                    NOW() as created_at
                FROM requests r
                WHERE r.timestamp_utc >= $1 
                  AND r.timestamp_utc < $2
                  AND r.client_user_id IS NOT NULL
                  AND r.vendor_id IS NOT NULL
                  AND r.model_id IS NOT NULL
                GROUP BY r.company_id, r.client_user_id, r.vendor_id, r.model_id, date_trunc('hour', r.timestamp_utc)
                ON CONFLICT (company_id, client_user_id, vendor_id, model_id, hour_bucket_utc) 
                DO UPDATE SET
                    request_count = EXCLUDED.request_count,
                    success_count = EXCLUDED.success_count,
                    error_count = EXCLUDED.error_count,
                    total_tokens = EXCLUDED.total_tokens,
                    total_cost = EXCLUDED.total_cost,
                    avg_latency_ms = EXCLUDED.avg_latency_ms,
                    updated_at = NOW()
            """
            
            await DatabaseUtils.execute_query(
                query,
                [hour_start, hour_end],
                fetch_all=False
            )
            
            # Get count of processed records
            count_query = """
                SELECT COUNT(DISTINCT client_user_id) as processed_users
                FROM user_analytics_hourly 
                WHERE hour_bucket_utc = $1
            """
            
            result = await DatabaseUtils.execute_query(
                count_query,
                [hour_start],
                fetch_all=False
            )
            
            processed_count = result['processed_users'] if result else 0
            
            logger.info(f"Populated hourly analytics for {hour_start}: {processed_count} user records")
            
            return {
                "status": "success",
                "hour_start": hour_start.isoformat(),
                "hour_end": hour_end.isoformat(),
                "processed_users": processed_count,
                "timestamp": datetime.utcnow().isoformat()
            }
            
        except Exception as e:
            error_info = handle_database_error(e)
            logger.error(f"Failed to populate hourly analytics for {hour_start}: {error_info['user_message']}")
            return {
                "status": "error",
                "hour_start": hour_start.isoformat(),
                "error": error_info['user_message'],
                "timestamp": datetime.utcnow().isoformat()
            }
    
    @staticmethod
    async def populate_daily_analytics(date: Optional[datetime] = None) -> Dict[str, Any]:
        """
        Populate daily analytics table for a specific date
        
        Args:
            date: Date to process (defaults to yesterday)
            
        Returns:
            Dictionary with processing results
        """
        if date is None:
            # Default to yesterday
            yesterday = datetime.now(timezone.utc) - timedelta(days=1)
            date = yesterday.replace(hour=0, minute=0, second=0, microsecond=0)
        
        date_start = date.replace(hour=0, minute=0, second=0, microsecond=0)
        date_end = date_start + timedelta(days=1)
        
        try:
            # Aggregate data from hourly analytics
            query = """
                INSERT INTO user_analytics_daily (
                    company_id, client_user_id, date,
                    total_requests, total_tokens, total_cost,
                    model_usage, avg_latency_ms, error_rate,
                    active_hours, created_at
                )
                SELECT 
                    ha.company_id,
                    ha.client_user_id,
                    $1::date as date,
                    SUM(ha.request_count) as total_requests,
                    SUM(ha.total_tokens) as total_tokens,
                    SUM(ha.total_cost) as total_cost,
                    jsonb_object_agg(
                        CONCAT(v.name, '/', m.name), 
                        ha.request_count
                    ) as model_usage,
                    AVG(ha.avg_latency_ms) as avg_latency_ms,
                    CASE 
                        WHEN SUM(ha.request_count) = 0 THEN 0
                        ELSE ROUND((SUM(ha.error_count)::DECIMAL / SUM(ha.request_count)) * 100, 2)
                    END as error_rate,
                    COUNT(DISTINCT EXTRACT(hour FROM ha.hour_bucket_utc)) as active_hours,
                    NOW() as created_at
                FROM user_analytics_hourly ha
                JOIN vendors v ON ha.vendor_id = v.id
                JOIN vendor_models m ON ha.model_id = m.id
                WHERE ha.hour_bucket_utc >= $1::date
                  AND ha.hour_bucket_utc < $1::date + INTERVAL '1 day'
                GROUP BY ha.company_id, ha.client_user_id
                ON CONFLICT (company_id, client_user_id, date)
                DO UPDATE SET
                    total_requests = EXCLUDED.total_requests,
                    total_tokens = EXCLUDED.total_tokens,
                    total_cost = EXCLUDED.total_cost,
                    model_usage = EXCLUDED.model_usage,
                    avg_latency_ms = EXCLUDED.avg_latency_ms,
                    error_rate = EXCLUDED.error_rate,
                    active_hours = EXCLUDED.active_hours,
                    updated_at = NOW()
            """
            
            await DatabaseUtils.execute_query(
                query,
                [date_start],
                fetch_all=False
            )
            
            # Update rankings and percentiles
            await AnalyticsService._update_daily_rankings(date_start)
            
            # Get count of processed records
            count_query = """
                SELECT COUNT(*) as processed_users
                FROM user_analytics_daily 
                WHERE date = $1::date
            """
            
            result = await DatabaseUtils.execute_query(
                count_query,
                [date_start],
                fetch_all=False
            )
            
            processed_count = result['processed_users'] if result else 0
            
            logger.info(f"Populated daily analytics for {date_start.date()}: {processed_count} user records")
            
            return {
                "status": "success",
                "date": date_start.date().isoformat(),
                "processed_users": processed_count,
                "timestamp": datetime.utcnow().isoformat()
            }
            
        except Exception as e:
            error_info = handle_database_error(e)
            logger.error(f"Failed to populate daily analytics for {date_start.date()}: {error_info['user_message']}")
            return {
                "status": "error",
                "date": date_start.date().isoformat(),
                "error": error_info['user_message'],
                "timestamp": datetime.utcnow().isoformat()
            }
    
    @staticmethod
    async def _update_daily_rankings(date: datetime) -> None:
        """Update user rankings and percentiles for daily analytics"""
        try:
            # Update rankings by requests
            ranking_query = """
                WITH ranked_users AS (
                    SELECT 
                        company_id, client_user_id, date, total_requests, total_cost,
                        ROW_NUMBER() OVER (PARTITION BY company_id ORDER BY total_cost DESC) as rank_by_cost,
                        PERCENT_RANK() OVER (PARTITION BY company_id ORDER BY total_cost) as cost_percentile
                    FROM user_analytics_daily
                    WHERE date = $1::date
                )
                UPDATE user_analytics_daily da
                SET 
                    cost_rank_in_company = ru.rank_by_cost,
                    cost_percentile = ROUND((ru.cost_percentile * 100)::DECIMAL, 2),
                    updated_at = NOW()
                FROM ranked_users ru
                WHERE da.company_id = ru.company_id 
                  AND da.client_user_id = ru.client_user_id 
                  AND da.date = ru.date
            """
            
            await DatabaseUtils.execute_query(
                ranking_query,
                [date],
                fetch_all=False
            )
            
            logger.debug(f"Updated daily rankings for {date.date()}")
            
        except Exception as e:
            logger.error(f"Failed to update daily rankings for {date.date()}: {e}")
            raise
    
    @staticmethod
    async def populate_analytics_range(start_date: datetime, end_date: datetime) -> Dict[str, Any]:
        """
        Populate analytics for a date range
        
        Args:
            start_date: Start date (inclusive)
            end_date: End date (exclusive)
            
        Returns:
            Dictionary with processing results
        """
        results = {
            "status": "success",
            "start_date": start_date.date().isoformat(),
            "end_date": end_date.date().isoformat(),
            "processed_days": 0,
            "errors": [],
            "timestamp": datetime.utcnow().isoformat()
        }
        
        current_date = start_date
        processed_days = 0
        
        try:
            while current_date < end_date:
                # Process hourly analytics for each hour of the day
                for hour in range(24):
                    hour_start = current_date.replace(hour=hour, minute=0, second=0, microsecond=0)
                    hour_result = await AnalyticsService.populate_hourly_analytics(hour_start)
                    
                    if hour_result["status"] == "error":
                        results["errors"].append(f"Hour {hour_start}: {hour_result['error']}")
                
                # Process daily analytics
                daily_result = await AnalyticsService.populate_daily_analytics(current_date)
                
                if daily_result["status"] == "error":
                    results["errors"].append(f"Day {current_date.date()}: {daily_result['error']}")
                else:
                    processed_days += 1
                
                current_date += timedelta(days=1)
            
            results["processed_days"] = processed_days
            
            if results["errors"]:
                results["status"] = "partial_success"
            
            logger.info(f"Completed analytics population for range {start_date.date()} to {end_date.date()}: {processed_days} days processed")
            
        except Exception as e:
            error_info = handle_database_error(e)
            results["status"] = "error"
            results["error"] = error_info['user_message']
            logger.error(f"Failed to populate analytics range: {error_info['user_message']}")
        
        return results
    
    @staticmethod
    async def get_analytics_summary(company_id: UUID, date: Optional[datetime] = None) -> Dict[str, Any]:
        """
        Get analytics summary for a company
        
        Args:
            company_id: Company UUID
            date: Date to get summary for (defaults to yesterday)
            
        Returns:
            Dictionary with analytics summary
        """
        if date is None:
            date = (datetime.now(timezone.utc) - timedelta(days=1)).replace(hour=0, minute=0, second=0, microsecond=0)
        
        try:
            query = """
                SELECT 
                    COUNT(*) as total_users,
                    SUM(total_requests) as total_requests,
                    SUM(total_tokens) as total_tokens,
                    SUM(total_cost) as total_cost,
                    AVG(100 - error_rate) as avg_success_rate,
                    MAX(total_requests) as max_user_requests,
                    MIN(total_requests) as min_user_requests,
                    COUNT(DISTINCT model_usage) as distinct_models_used
                FROM user_analytics_daily
                WHERE company_id = $1 AND date = $2::date
            """
            
            result = await DatabaseUtils.execute_query(
                query,
                [company_id, date],
                fetch_all=False
            )
            
            if result:
                return {
                    "company_id": str(company_id),
                    "date": date.date().isoformat(),
                    "summary": {
                        "total_users": result['total_users'] or 0,
                        "total_requests": result['total_requests'] or 0,
                        "total_tokens": result['total_tokens'] or 0,
                        "total_cost": float(result['total_cost'] or 0),
                        "avg_success_rate": float(result['avg_success_rate'] or 0),
                        "max_user_requests": result['max_user_requests'] or 0,
                        "min_user_requests": result['min_user_requests'] or 0,
                        "distinct_models_used": result['distinct_models_used'] or 0
                    },
                    "timestamp": datetime.utcnow().isoformat()
                }
            else:
                return {
                    "company_id": str(company_id),
                    "date": date.date().isoformat(),
                    "summary": None,
                    "message": "No analytics data found for this date",
                    "timestamp": datetime.utcnow().isoformat()
                }
                
        except Exception as e:
            error_info = handle_database_error(e)
            logger.error(f"Failed to get analytics summary for company {company_id}: {error_info['user_message']}")
            return {
                "company_id": str(company_id),
                "date": date.date().isoformat(),
                "error": error_info['user_message'],
                "timestamp": datetime.utcnow().isoformat()
            }

# Background task functions for scheduled analytics processing

async def run_hourly_analytics_job():
    """Background job to populate hourly analytics"""
    try:
        # Process the previous hour
        now = datetime.now(timezone.utc)
        previous_hour = (now - timedelta(hours=1)).replace(minute=0, second=0, microsecond=0)
        
        result = await AnalyticsService.populate_hourly_analytics(previous_hour)
        
        if result["status"] == "success":
            logger.info(f"Hourly analytics job completed successfully: {result['processed_users']} users processed")
        else:
            logger.error(f"Hourly analytics job failed: {result.get('error', 'Unknown error')}")
            
    except Exception as e:
        logger.error(f"Hourly analytics job crashed: {e}")

async def run_daily_analytics_job():
    """Background job to populate daily analytics"""
    try:
        # Process yesterday
        yesterday = (datetime.now(timezone.utc) - timedelta(days=1)).replace(hour=0, minute=0, second=0, microsecond=0)
        
        result = await AnalyticsService.populate_daily_analytics(yesterday)
        
        if result["status"] == "success":
            logger.info(f"Daily analytics job completed successfully: {result['processed_users']} users processed")
        else:
            logger.error(f"Daily analytics job failed: {result.get('error', 'Unknown error')}")
            
    except Exception as e:
        logger.error(f"Daily analytics job crashed: {e}")

async def backfill_analytics(days_back: int = 7):
    """Backfill analytics data for the last N days"""
    try:
        end_date = datetime.now(timezone.utc).replace(hour=0, minute=0, second=0, microsecond=0)
        start_date = end_date - timedelta(days=days_back)
        
        logger.info(f"Starting analytics backfill for {days_back} days: {start_date.date()} to {end_date.date()}")
        
        result = await AnalyticsService.populate_analytics_range(start_date, end_date)
        
        if result["status"] in ["success", "partial_success"]:
            logger.info(f"Analytics backfill completed: {result['processed_days']} days processed")
            if result.get("errors"):
                logger.warning(f"Backfill had {len(result['errors'])} errors: {result['errors']}")
        else:
            logger.error(f"Analytics backfill failed: {result.get('error', 'Unknown error')}")
            
        return result
        
    except Exception as e:
        logger.error(f"Analytics backfill crashed: {e}")
        return {"status": "error", "error": str(e)}
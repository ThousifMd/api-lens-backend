"""
Optimized Analytics Service - Improved performance for analytics data aggregation
Uses batch processing, caching, and optimized queries
"""
import asyncio
from datetime import datetime, timedelta, timezone
from typing import Dict, Any, List, Optional, Tuple
from uuid import UUID
import time

from ..database import db_manager, DatabaseUtils
from ..utils.logger import get_logger
from ..utils.db_errors import handle_database_error
from .cache_service import cache_service

logger = get_logger(__name__)

class OptimizedAnalyticsService:
    """Optimized service for managing analytics data aggregation"""
    
    # Batch processing configuration
    BATCH_SIZE = 1000
    MAX_CONCURRENT_BATCHES = 5
    
    @staticmethod
    async def populate_hourly_analytics_batch(
        start_time: datetime, 
        end_time: datetime,
        batch_hours: int = 24
    ) -> Dict[str, Any]:
        """
        Populate hourly analytics for a time range using batch processing
        
        Args:
            start_time: Start of the time range
            end_time: End of the time range
            batch_hours: Number of hours to process in each batch
            
        Returns:
            Dictionary with processing results
        """
        results = {
            "status": "success",
            "start_time": start_time.isoformat(),
            "end_time": end_time.isoformat(),
            "total_hours_processed": 0,
            "total_records_processed": 0,
            "errors": [],
            "processing_time_ms": 0
        }
        
        start_process = time.time()
        
        try:
            # Create batches of hours to process
            current_time = start_time
            batches = []
            
            while current_time < end_time:
                batch_end = min(current_time + timedelta(hours=batch_hours), end_time)
                batches.append((current_time, batch_end))
                current_time = batch_end
            
            # Process batches with concurrency limit
            semaphore = asyncio.Semaphore(OptimizedAnalyticsService.MAX_CONCURRENT_BATCHES)
            
            async def process_batch(batch_start: datetime, batch_end: datetime) -> Tuple[int, int]:
                async with semaphore:
                    return await OptimizedAnalyticsService._process_hourly_batch(
                        batch_start, batch_end
                    )
            
            # Execute all batches concurrently
            batch_results = await asyncio.gather(
                *[process_batch(start, end) for start, end in batches],
                return_exceptions=True
            )
            
            # Aggregate results
            for i, result in enumerate(batch_results):
                if isinstance(result, Exception):
                    results["errors"].append(f"Batch {i}: {str(result)}")
                else:
                    hours_processed, records_processed = result
                    results["total_hours_processed"] += hours_processed
                    results["total_records_processed"] += records_processed
            
            # Refresh materialized views if available
            await OptimizedAnalyticsService._refresh_materialized_views()
            
        except Exception as e:
            results["status"] = "error"
            results["errors"].append(str(e))
            logger.error(f"Batch analytics processing failed: {e}")
        
        results["processing_time_ms"] = (time.time() - start_process) * 1000
        return results
    
    @staticmethod
    async def _process_hourly_batch(
        batch_start: datetime, 
        batch_end: datetime
    ) -> Tuple[int, int]:
        """Process a batch of hourly analytics"""
        
        async with db_manager.pool.acquire() as conn:
            # Use optimized function if available
            result = await conn.fetchrow("""
                SELECT * FROM populate_hourly_analytics_optimized($1, $2)
            """, batch_start, batch_end)
            
            if result:
                records = result['processed_records']
                hours = int((batch_end - batch_start).total_seconds() / 3600)
                return hours, records
            
            # Fallback to standard query
            hours_processed = 0
            records_processed = 0
            
            current_hour = batch_start
            while current_hour < batch_end:
                hour_end = current_hour + timedelta(hours=1)
                
                # Execute optimized aggregation query
                result = await conn.execute("""
                    WITH aggregated_data AS (
                        SELECT 
                            r.company_id,
                            r.client_user_id,
                            r.vendor_id,
                            r.model_id,
                            date_trunc('hour', r.timestamp_utc) as hour_bucket,
                            COUNT(*) as request_count,
                            COUNT(*) FILTER (WHERE r.status_code < 400) as success_count,
                            COUNT(*) FILTER (WHERE r.status_code >= 400) as error_count,
                            COALESCE(SUM(r.total_tokens), 0) as total_tokens,
                            COALESCE(SUM(r.total_cost), 0) as total_cost,
                            COALESCE(AVG(r.total_latency_ms), 0) as avg_latency_ms
                        FROM requests r
                        WHERE r.timestamp_utc >= $1 AND r.timestamp_utc < $2
                          AND r.client_user_id IS NOT NULL
                        GROUP BY 1, 2, 3, 4, 5
                    )
                    INSERT INTO user_analytics_hourly (
                        company_id, client_user_id, vendor_id, model_id,
                        hour_bucket_utc, hour_bucket_local, timezone_name,
                        request_count, success_count, error_count,
                        total_tokens, total_cost, avg_latency_ms
                    )
                    SELECT *, hour_bucket, 'UTC' FROM aggregated_data
                    ON CONFLICT (company_id, client_user_id, vendor_id, model_id, hour_bucket_utc) 
                    DO UPDATE SET
                        request_count = EXCLUDED.request_count,
                        success_count = EXCLUDED.success_count,
                        error_count = EXCLUDED.error_count,
                        total_tokens = EXCLUDED.total_tokens,
                        total_cost = EXCLUDED.total_cost,
                        avg_latency_ms = EXCLUDED.avg_latency_ms,
                        updated_at = NOW()
                """, current_hour, hour_end)
                
                # Extract row count from result
                if result:
                    count = int(result.split()[-1])
                    records_processed += count
                
                hours_processed += 1
                current_hour = hour_end
            
            return hours_processed, records_processed
    
    @staticmethod
    async def get_analytics_summary(
        company_id: UUID,
        start_date: datetime,
        end_date: datetime,
        use_cache: bool = True
    ) -> Dict[str, Any]:
        """
        Get analytics summary with caching support
        
        Args:
            company_id: Company ID
            start_date: Start date
            end_date: End date  
            use_cache: Whether to use cache
            
        Returns:
            Analytics summary data
        """
        
        # Generate cache key
        cache_key = await cache_service.cache_analytics_query(
            str(company_id),
            "summary",
            {"start": start_date.isoformat(), "end": end_date.isoformat()}
        )
        
        # Try cache first
        if use_cache and cache_service.connected:
            cached_data = await cache_service.get(cache_key)
            if cached_data:
                return cached_data
        
        # Query data
        async with db_manager.pool.acquire() as conn:
            # Try materialized view first
            summary = await conn.fetchrow("""
                SELECT 
                    COUNT(DISTINCT client_user_id) as unique_users,
                    COUNT(DISTINCT vendor_id) as unique_vendors,
                    COUNT(DISTINCT model_id) as unique_models,
                    SUM(request_count) as total_requests,
                    SUM(success_count) as total_success,
                    SUM(error_count) as total_errors,
                    SUM(total_tokens) as total_tokens,
                    SUM(total_cost) as total_cost,
                    AVG(avg_latency_ms) as avg_latency
                FROM user_analytics_hourly
                WHERE company_id = $1
                  AND hour_bucket_utc >= $2
                  AND hour_bucket_utc < $3
            """, company_id, start_date, end_date)
            
            if summary:
                result = dict(summary)
                result["start_date"] = start_date.isoformat()
                result["end_date"] = end_date.isoformat()
                result["company_id"] = str(company_id)
                
                # Cache the result
                if cache_service.connected:
                    await cache_service.set(
                        cache_key, 
                        result, 
                        ttl=cache_service.ttl_config['analytics_hourly']
                    )
                
                return result
        
        return {
            "error": "No data found",
            "company_id": str(company_id),
            "start_date": start_date.isoformat(),
            "end_date": end_date.isoformat()
        }
    
    @staticmethod
    async def get_top_users_by_cost(
        company_id: UUID,
        date: datetime,
        limit: int = 10,
        use_cache: bool = True
    ) -> List[Dict[str, Any]]:
        """Get top users by cost with caching"""
        
        cache_key = f"top_users:{company_id}:{date.date()}:{limit}"
        
        if use_cache and cache_service.connected:
            cached_data = await cache_service.get(cache_key)
            if cached_data:
                return cached_data
        
        async with db_manager.pool.acquire() as conn:
            # Try materialized view first
            results = await conn.fetch("""
                SELECT 
                    cu.user_id,
                    cu.display_name,
                    cr.total_cost,
                    cr.total_requests,
                    cr.cost_rank,
                    cr.cost_percentile
                FROM mv_daily_cost_rankings cr
                JOIN client_users cu ON cr.client_user_id = cu.id
                WHERE cr.company_id = $1 AND cr.date = $2
                ORDER BY cr.cost_rank
                LIMIT $3
            """, company_id, date.date(), limit)
            
            if not results:
                # Fallback to direct query
                results = await conn.fetch("""
                    WITH ranked AS (
                        SELECT 
                            da.client_user_id,
                            da.total_cost,
                            da.total_requests,
                            ROW_NUMBER() OVER (ORDER BY da.total_cost DESC) as rank
                        FROM user_analytics_daily da
                        WHERE da.company_id = $1 AND da.date = $2
                    )
                    SELECT 
                        cu.user_id,
                        cu.display_name,
                        r.total_cost,
                        r.total_requests,
                        r.rank as cost_rank
                    FROM ranked r
                    JOIN client_users cu ON r.client_user_id = cu.id
                    ORDER BY r.rank
                    LIMIT $3
                """, company_id, date.date(), limit)
            
            result_list = [dict(r) for r in results]
            
            # Cache the result
            if cache_service.connected:
                await cache_service.set(
                    cache_key,
                    result_list,
                    ttl=cache_service.ttl_config['analytics_daily']
                )
            
            return result_list
    
    @staticmethod
    async def _refresh_materialized_views():
        """Refresh materialized views if they exist"""
        try:
            async with db_manager.pool.acquire() as conn:
                await conn.execute("SELECT refresh_analytics_materialized_views()")
                logger.info("Refreshed analytics materialized views")
        except Exception as e:
            # Views might not exist, which is okay
            logger.debug(f"Could not refresh materialized views: {e}")

# Utility function for parallel processing
async def process_analytics_parallel(
    date_ranges: List[Tuple[datetime, datetime]],
    max_concurrent: int = 3
) -> Dict[str, Any]:
    """
    Process multiple date ranges in parallel
    
    Args:
        date_ranges: List of (start_date, end_date) tuples
        max_concurrent: Maximum concurrent processing tasks
        
    Returns:
        Aggregated results
    """
    semaphore = asyncio.Semaphore(max_concurrent)
    
    async def process_range(start: datetime, end: datetime) -> Dict[str, Any]:
        async with semaphore:
            return await OptimizedAnalyticsService.populate_hourly_analytics_batch(
                start, end
            )
    
    results = await asyncio.gather(
        *[process_range(start, end) for start, end in date_ranges],
        return_exceptions=True
    )
    
    # Aggregate results
    total_processed = 0
    total_errors = []
    
    for i, result in enumerate(results):
        if isinstance(result, Exception):
            total_errors.append(f"Range {i}: {str(result)}")
        elif isinstance(result, dict):
            total_processed += result.get("total_records_processed", 0)
            total_errors.extend(result.get("errors", []))
    
    return {
        "total_ranges": len(date_ranges),
        "total_records_processed": total_processed,
        "errors": total_errors
    }
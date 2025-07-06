"""
Database Connection Pool Monitoring Service
Provides monitoring and metrics for database connection pools
"""
import asyncio
from typing import Dict, Any, Optional, List
from datetime import datetime, timedelta
import logging
from dataclasses import dataclass, asdict
import time

from sqlalchemy.pool import Pool
from sqlalchemy.engine import Engine
from sqlalchemy import event
import asyncpg

logger = logging.getLogger(__name__)

@dataclass
class PoolMetrics:
    """Connection pool metrics"""
    timestamp: datetime
    pool_size: int
    active_connections: int
    idle_connections: int
    overflow: int
    max_overflow: int
    total_connections: int
    checked_out_connections: int
    queue_size: int
    wait_time_ms: float
    connection_errors: int
    timeout_errors: int
    
    @property
    def utilization_percent(self) -> float:
        """Calculate pool utilization percentage"""
        if self.pool_size == 0:
            return 0.0
        return round((self.active_connections / self.pool_size) * 100, 2)
    
    @property
    def is_pool_exhausted(self) -> bool:
        """Check if pool is exhausted"""
        return self.checked_out_connections >= (self.pool_size + self.overflow)

@dataclass 
class QueryMetrics:
    """Query execution metrics"""
    query_count: int = 0
    total_execution_time_ms: float = 0.0
    slow_query_count: int = 0
    failed_query_count: int = 0
    average_execution_time_ms: float = 0.0
    max_execution_time_ms: float = 0.0
    queries_per_second: float = 0.0

class DatabaseMonitor:
    """Monitor database connection pools and query performance"""
    
    def __init__(self):
        self.metrics_history: List[PoolMetrics] = []
        self.query_metrics = QueryMetrics()
        self.connection_wait_times: List[float] = []
        self.monitoring_interval = 60  # seconds
        self.slow_query_threshold_ms = 1000  # 1 second
        self.metrics_retention_hours = 24
        self._monitoring_task: Optional[asyncio.Task] = None
        self._start_time = time.time()
        
        # Connection pool event tracking
        self.connection_checkouts = 0
        self.connection_checkins = 0
        self.connection_errors = 0
        self.timeout_errors = 0
    
    def setup_sqlalchemy_monitoring(self, engine: Engine):
        """Setup SQLAlchemy pool event listeners"""
        
        @event.listens_for(engine.pool, "connect")
        def on_connect(dbapi_conn, connection_record):
            connection_record.info['connect_time'] = time.time()
            logger.debug("New database connection established")
        
        @event.listens_for(engine.pool, "checkout")
        def on_checkout(dbapi_conn, connection_record, connection_proxy):
            self.connection_checkouts += 1
            checkout_time = time.time()
            connection_record.info['checkout_time'] = checkout_time
            
            # Track wait time
            connect_time = connection_record.info.get('connect_time', checkout_time)
            wait_time = (checkout_time - connect_time) * 1000  # Convert to ms
            self.connection_wait_times.append(wait_time)
            
            # Keep only recent wait times (last 100)
            if len(self.connection_wait_times) > 100:
                self.connection_wait_times.pop(0)
        
        @event.listens_for(engine.pool, "checkin")
        def on_checkin(dbapi_conn, connection_record):
            self.connection_checkins += 1
            
            # Calculate connection usage time
            checkout_time = connection_record.info.get('checkout_time')
            if checkout_time:
                usage_time = (time.time() - checkout_time) * 1000
                if usage_time > self.slow_query_threshold_ms * 2:
                    logger.warning(f"Long connection usage detected: {usage_time:.2f}ms")
    
    async def get_pool_metrics(self, engine: Engine, asyncpg_pool: Optional[asyncpg.Pool] = None) -> PoolMetrics:
        """Get current connection pool metrics"""
        
        # SQLAlchemy pool metrics
        pool = engine.pool
        
        # Get pool statistics
        pool_size = pool.size() if hasattr(pool, 'size') else 0
        overflow = pool.overflow() if hasattr(pool, 'overflow') else 0
        total = pool_size + overflow
        checked_out = pool.checkedout() if hasattr(pool, 'checkedout') else 0
        
        # AsyncPG pool metrics (if available)
        asyncpg_metrics = {}
        if asyncpg_pool:
            asyncpg_metrics = {
                'asyncpg_size': asyncpg_pool._size,
                'asyncpg_free': len(asyncpg_pool._free),
                'asyncpg_used': asyncpg_pool._size - len(asyncpg_pool._free),
                'asyncpg_max_queries': asyncpg_pool._max_queries,
            }
        
        # Calculate average wait time
        avg_wait_time = 0.0
        if self.connection_wait_times:
            avg_wait_time = sum(self.connection_wait_times) / len(self.connection_wait_times)
        
        metrics = PoolMetrics(
            timestamp=datetime.utcnow(),
            pool_size=pool_size,
            active_connections=checked_out,
            idle_connections=pool_size - checked_out if pool_size > checked_out else 0,
            overflow=overflow,
            max_overflow=pool._max_overflow if hasattr(pool, '_max_overflow') else 0,
            total_connections=total,
            checked_out_connections=checked_out,
            queue_size=0,  # SQLAlchemy doesn't expose queue size directly
            wait_time_ms=avg_wait_time,
            connection_errors=self.connection_errors,
            timeout_errors=self.timeout_errors
        )
        
        # Store metrics
        self.metrics_history.append(metrics)
        self._cleanup_old_metrics()
        
        return metrics
    
    def track_query_execution(self, execution_time_ms: float, success: bool = True):
        """Track query execution metrics"""
        self.query_metrics.query_count += 1
        self.query_metrics.total_execution_time_ms += execution_time_ms
        
        if execution_time_ms > self.slow_query_threshold_ms:
            self.query_metrics.slow_query_count += 1
            logger.warning(f"Slow query detected: {execution_time_ms:.2f}ms")
        
        if not success:
            self.query_metrics.failed_query_count += 1
        
        # Update max execution time
        if execution_time_ms > self.query_metrics.max_execution_time_ms:
            self.query_metrics.max_execution_time_ms = execution_time_ms
        
        # Calculate averages
        if self.query_metrics.query_count > 0:
            self.query_metrics.average_execution_time_ms = (
                self.query_metrics.total_execution_time_ms / self.query_metrics.query_count
            )
            
            # Calculate queries per second
            elapsed_seconds = time.time() - self._start_time
            if elapsed_seconds > 0:
                self.query_metrics.queries_per_second = (
                    self.query_metrics.query_count / elapsed_seconds
                )
    
    def increment_connection_error(self, error_type: str = "general"):
        """Increment connection error counter"""
        if error_type == "timeout":
            self.timeout_errors += 1
        else:
            self.connection_errors += 1
    
    async def start_monitoring(self, engine: Engine, asyncpg_pool: Optional[asyncpg.Pool] = None):
        """Start periodic monitoring task"""
        if self._monitoring_task and not self._monitoring_task.done():
            return
        
        self._monitoring_task = asyncio.create_task(
            self._monitoring_loop(engine, asyncpg_pool)
        )
        logger.info("Database monitoring started")
    
    async def stop_monitoring(self):
        """Stop monitoring task"""
        if self._monitoring_task:
            self._monitoring_task.cancel()
            try:
                await self._monitoring_task
            except asyncio.CancelledError:
                pass
            logger.info("Database monitoring stopped")
    
    async def _monitoring_loop(self, engine: Engine, asyncpg_pool: Optional[asyncpg.Pool]):
        """Main monitoring loop"""
        while True:
            try:
                metrics = await self.get_pool_metrics(engine, asyncpg_pool)
                
                # Log warnings for high utilization
                if metrics.utilization_percent > 80:
                    logger.warning(f"High connection pool utilization: {metrics.utilization_percent}%")
                
                if metrics.is_pool_exhausted:
                    logger.error("Connection pool exhausted!")
                
                # Log periodic summary
                logger.info(
                    f"Pool metrics - Active: {metrics.active_connections}/{metrics.pool_size}, "
                    f"Utilization: {metrics.utilization_percent}%, "
                    f"Wait time: {metrics.wait_time_ms:.2f}ms"
                )
                
                await asyncio.sleep(self.monitoring_interval)
                
            except Exception as e:
                logger.error(f"Error in monitoring loop: {e}")
                await asyncio.sleep(self.monitoring_interval)
    
    def _cleanup_old_metrics(self):
        """Remove metrics older than retention period"""
        cutoff_time = datetime.utcnow() - timedelta(hours=self.metrics_retention_hours)
        self.metrics_history = [
            m for m in self.metrics_history 
            if m.timestamp > cutoff_time
        ]
    
    def get_metrics_summary(self) -> Dict[str, Any]:
        """Get comprehensive metrics summary"""
        if not self.metrics_history:
            return {
                "status": "No metrics available",
                "pool_metrics": None,
                "query_metrics": asdict(self.query_metrics)
            }
        
        latest_metrics = self.metrics_history[-1]
        
        # Calculate averages over last hour
        hour_ago = datetime.utcnow() - timedelta(hours=1)
        recent_metrics = [m for m in self.metrics_history if m.timestamp > hour_ago]
        
        avg_utilization = 0.0
        avg_wait_time = 0.0
        if recent_metrics:
            avg_utilization = sum(m.utilization_percent for m in recent_metrics) / len(recent_metrics)
            avg_wait_time = sum(m.wait_time_ms for m in recent_metrics) / len(recent_metrics)
        
        return {
            "current": {
                "timestamp": latest_metrics.timestamp.isoformat(),
                "pool_size": latest_metrics.pool_size,
                "active_connections": latest_metrics.active_connections,
                "utilization_percent": latest_metrics.utilization_percent,
                "is_exhausted": latest_metrics.is_pool_exhausted,
                "wait_time_ms": latest_metrics.wait_time_ms
            },
            "hourly_average": {
                "utilization_percent": round(avg_utilization, 2),
                "wait_time_ms": round(avg_wait_time, 2)
            },
            "connection_stats": {
                "total_checkouts": self.connection_checkouts,
                "total_checkins": self.connection_checkins,
                "connection_errors": self.connection_errors,
                "timeout_errors": self.timeout_errors
            },
            "query_metrics": asdict(self.query_metrics),
            "alerts": self._generate_alerts(latest_metrics)
        }
    
    def _generate_alerts(self, metrics: PoolMetrics) -> List[Dict[str, Any]]:
        """Generate alerts based on current metrics"""
        alerts = []
        
        if metrics.utilization_percent > 90:
            alerts.append({
                "level": "critical",
                "message": f"Connection pool utilization critical: {metrics.utilization_percent}%"
            })
        elif metrics.utilization_percent > 80:
            alerts.append({
                "level": "warning", 
                "message": f"Connection pool utilization high: {metrics.utilization_percent}%"
            })
        
        if metrics.wait_time_ms > 1000:
            alerts.append({
                "level": "warning",
                "message": f"High connection wait time: {metrics.wait_time_ms:.2f}ms"
            })
        
        if metrics.is_pool_exhausted:
            alerts.append({
                "level": "critical",
                "message": "Connection pool exhausted - no connections available"
            })
        
        error_rate = 0.0
        if self.query_metrics.query_count > 0:
            error_rate = (self.query_metrics.failed_query_count / self.query_metrics.query_count) * 100
        
        if error_rate > 5:
            alerts.append({
                "level": "warning",
                "message": f"High query error rate: {error_rate:.2f}%"
            })
        
        return alerts
    
    async def get_pool_recommendations(self) -> List[str]:
        """Get recommendations for pool configuration"""
        recommendations = []
        
        if not self.metrics_history:
            return ["No metrics available for recommendations"]
        
        # Analyze recent metrics
        hour_ago = datetime.utcnow() - timedelta(hours=1)
        recent_metrics = [m for m in self.metrics_history if m.timestamp > hour_ago]
        
        if recent_metrics:
            avg_utilization = sum(m.utilization_percent for m in recent_metrics) / len(recent_metrics)
            max_utilization = max(m.utilization_percent for m in recent_metrics)
            
            if avg_utilization > 70:
                recommendations.append(
                    f"Consider increasing pool size. Average utilization: {avg_utilization:.1f}%"
                )
            
            if max_utilization == 100:
                recommendations.append(
                    "Pool reached 100% utilization. Increase pool_size or max_overflow"
                )
            
            avg_wait = sum(m.wait_time_ms for m in recent_metrics) / len(recent_metrics)
            if avg_wait > 500:
                recommendations.append(
                    f"High average wait time ({avg_wait:.0f}ms). Consider increasing pool size"
                )
        
        if self.query_metrics.slow_query_count > 100:
            recommendations.append(
                f"High number of slow queries ({self.query_metrics.slow_query_count}). "
                "Review query optimization and indexes"
            )
        
        return recommendations

# Global monitor instance
db_monitor = DatabaseMonitor()
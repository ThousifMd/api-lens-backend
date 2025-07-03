"""
Cost Monitoring Service - Cost alerts and anomaly detection
Handles cost threshold monitoring, anomaly detection, and alerting
"""
import asyncio
from datetime import datetime, timedelta, timezone
from typing import Dict, Any, List, Optional, Tuple
from uuid import UUID, uuid4
from enum import Enum
import statistics

from ..database import DatabaseUtils
from ..utils.logger import get_logger
from ..utils.db_errors import handle_database_error

logger = get_logger(__name__)

class AlertType(Enum):
    """Types of cost alerts - must match database constraint"""
    USER_DAILY = "user_daily"
    USER_MONTHLY = "user_monthly"
    COMPANY_DAILY = "company_daily"
    COMPANY_MONTHLY = "company_monthly"

class AlertSeverity(Enum):
    """Alert severity levels"""
    LOW = "low"
    MEDIUM = "medium"
    HIGH = "high"
    CRITICAL = "critical"

class CostMonitoringService:
    """Service for cost monitoring, alerts, and anomaly detection"""
    
    @staticmethod
    async def create_cost_alert(company_id: UUID, alert_config: Dict[str, Any]) -> Dict[str, Any]:
        """
        Create a new cost alert configuration
        
        Args:
            company_id: Company UUID
            alert_config: Alert configuration dictionary
            
        Returns:
            Dictionary with created alert details
        """
        try:
            # Validate alert configuration
            is_valid, error_msg = CostMonitoringService._validate_alert_config(alert_config)
            if not is_valid:
                return {"status": "error", "error": error_msg}
            
            alert_id = uuid4()
            
            query = """
                INSERT INTO cost_alerts (
                    id, company_id, alert_type, threshold_usd,
                    notification_emails, webhook_url, is_active, created_at
                )
                VALUES ($1, $2, $3, $4, $5, $6, $7, NOW())
                RETURNING id, alert_type, threshold_usd, is_active, created_at
            """
            
            result = await DatabaseUtils.execute_query(
                query,
                [
                    alert_id,
                    company_id,
                    alert_config['alert_type'],
                    alert_config['threshold_amount'],
                    alert_config.get('notification_emails', []),
                    alert_config.get('webhook_url'),
                    alert_config.get('is_active', True)
                ],
                fetch_all=False
            )
            
            if result:
                logger.info(f"Created cost alert '{alert_config['alert_type']}' for company {company_id}")
                return {
                    "status": "success",
                    "alert": {
                        "id": str(result['id']),
                        "alert_type": result['alert_type'],
                        "threshold_amount": float(result['threshold_usd']),
                        "is_active": result['is_active'],
                        "created_at": result['created_at'].isoformat()
                    },
                    "timestamp": datetime.utcnow().isoformat()
                }
            else:
                return {"status": "error", "error": "Failed to create cost alert"}
                
        except Exception as e:
            error_info = handle_database_error(e)
            logger.error(f"Failed to create cost alert for company {company_id}: {error_info['user_message']}")
            return {"status": "error", "error": error_info['user_message']}
    
    @staticmethod
    async def check_cost_thresholds(company_id: Optional[UUID] = None) -> Dict[str, Any]:
        """
        Check cost thresholds and trigger alerts
        
        Args:
            company_id: Specific company to check (None for all companies)
            
        Returns:
            Dictionary with check results
        """
        try:
            # Get active alerts
            if company_id:
                alerts_query = """
                    SELECT id, company_id, alert_type, threshold_usd,
                           notification_emails, webhook_url
                    FROM cost_alerts
                    WHERE company_id = $1 AND is_active = true
                """
                alerts = await DatabaseUtils.execute_query(alerts_query, [company_id], fetch_all=True)
            else:
                alerts_query = """
                    SELECT id, company_id, alert_type, threshold_usd,
                           notification_emails, webhook_url
                    FROM cost_alerts
                    WHERE is_active = true
                """
                alerts = await DatabaseUtils.execute_query(alerts_query, [], fetch_all=True)
            
            triggered_alerts = []
            
            for alert in alerts:
                # Calculate current cost for the time window (default 24 hours)
                current_cost = await CostMonitoringService._calculate_cost_for_window(
                    alert['company_id'], 
                    24  # Default 24 hour window
                )
                
                # Check if threshold is exceeded (default greater than)
                threshold_exceeded = CostMonitoringService._check_threshold(
                    current_cost,
                    alert['threshold_usd'],
                    'greater_than'
                )
                
                if threshold_exceeded:
                    # Record the triggered alert
                    alert_record = await CostMonitoringService._record_triggered_alert(
                        alert, current_cost
                    )
                    
                    if alert_record:
                        triggered_alerts.append(alert_record)
            
            logger.info(f"Cost threshold check completed: {len(triggered_alerts)} alerts triggered")
            
            return {
                "status": "success",
                "checked_companies": len(set(alert['company_id'] for alert in alerts)),
                "triggered_alerts": len(triggered_alerts),
                "alerts": triggered_alerts,
                "timestamp": datetime.utcnow().isoformat()
            }
            
        except Exception as e:
            error_info = handle_database_error(e)
            logger.error(f"Failed to check cost thresholds: {error_info['user_message']}")
            return {"status": "error", "error": error_info['user_message']}
    
    @staticmethod
    async def detect_cost_anomalies(company_id: UUID, lookback_days: int = 7) -> Dict[str, Any]:
        """
        Detect cost anomalies using statistical analysis
        
        Args:
            company_id: Company UUID
            lookback_days: Number of days to analyze
            
        Returns:
            Dictionary with anomaly detection results
        """
        try:
            # Get historical cost data
            end_date = datetime.now(timezone.utc)
            start_date = end_date - timedelta(days=lookback_days)
            
            cost_query = """
                SELECT 
                    DATE(r.timestamp_utc) as date,
                    SUM(r.total_cost) as daily_cost
                FROM requests r
                WHERE r.company_id = $1 
                  AND r.timestamp_utc >= $2
                  AND r.timestamp_utc < $3
                GROUP BY DATE(r.timestamp_utc)
                ORDER BY date
            """
            
            cost_data = await DatabaseUtils.execute_query(
                cost_query,
                [company_id, start_date, end_date],
                fetch_all=True
            )
            
            if len(cost_data) < 3:
                return {
                    "status": "insufficient_data",
                    "message": "Not enough historical data for anomaly detection",
                    "company_id": str(company_id),
                    "timestamp": datetime.utcnow().isoformat()
                }
            
            # Perform anomaly detection
            daily_costs = [float(row['daily_cost']) for row in cost_data]
            anomalies = CostMonitoringService._detect_statistical_anomalies(daily_costs)
            
            anomaly_records = []
            
            # Record detected anomalies
            for i, is_anomaly in enumerate(anomalies):
                if is_anomaly:
                    date = cost_data[i]['date']
                    cost = daily_costs[i]
                    
                    # Calculate severity based on deviation
                    mean_cost = statistics.mean(daily_costs)
                    std_dev = statistics.stdev(daily_costs) if len(daily_costs) > 1 else 0
                    z_score = (cost - mean_cost) / std_dev if std_dev > 0 else 0
                    
                    severity = CostMonitoringService._calculate_anomaly_severity(abs(z_score))
                    
                    anomaly_record = await CostMonitoringService._record_cost_anomaly(
                        company_id, date, cost, mean_cost, z_score, severity
                    )
                    
                    if anomaly_record:
                        anomaly_records.append(anomaly_record)
            
            logger.info(f"Cost anomaly detection completed for company {company_id}: {len(anomaly_records)} anomalies detected")
            
            return {
                "status": "success",
                "company_id": str(company_id),
                "analysis_period": {
                    "start_date": start_date.date().isoformat(),
                    "end_date": end_date.date().isoformat(),
                    "days_analyzed": len(cost_data)
                },
                "anomalies_detected": len(anomaly_records),
                "anomalies": anomaly_records,
                "statistics": {
                    "mean_daily_cost": round(statistics.mean(daily_costs), 4),
                    "std_deviation": round(statistics.stdev(daily_costs) if len(daily_costs) > 1 else 0, 4),
                    "min_cost": round(min(daily_costs), 4),
                    "max_cost": round(max(daily_costs), 4)
                },
                "timestamp": datetime.utcnow().isoformat()
            }
            
        except Exception as e:
            error_info = handle_database_error(e)
            logger.error(f"Failed to detect cost anomalies for company {company_id}: {error_info['user_message']}")
            return {"status": "error", "error": error_info['user_message']}
    
    @staticmethod
    async def get_cost_alerts(company_id: UUID) -> Dict[str, Any]:
        """
        Get all cost alerts for a company
        
        Args:
            company_id: Company UUID
            
        Returns:
            Dictionary with cost alerts
        """
        try:
            query = """
                SELECT id, alert_type, threshold_usd, is_active, notification_emails, 
                       webhook_url, created_at, updated_at
                FROM cost_alerts
                WHERE company_id = $1
                ORDER BY created_at DESC
            """
            
            alerts = await DatabaseUtils.execute_query(query, [company_id], fetch_all=True)
            
            alert_list = []
            for alert in alerts:
                alert_list.append({
                    "id": str(alert['id']),
                    "alert_type": alert['alert_type'],
                    "threshold_amount": float(alert['threshold_usd']),
                    "is_active": alert['is_active'],
                    "notification_emails": alert['notification_emails'],
                    "webhook_url": alert['webhook_url'],
                    "created_at": alert['created_at'].isoformat(),
                    "updated_at": alert['updated_at'].isoformat() if alert['updated_at'] else None
                })
            
            return {
                "status": "success",
                "company_id": str(company_id),
                "alerts": alert_list,
                "total_alerts": len(alert_list),
                "active_alerts": len([a for a in alert_list if a['is_active']]),
                "timestamp": datetime.utcnow().isoformat()
            }
            
        except Exception as e:
            error_info = handle_database_error(e)
            logger.error(f"Failed to get cost alerts for company {company_id}: {error_info['user_message']}")
            return {"status": "error", "error": error_info['user_message']}
    
    @staticmethod
    async def get_cost_anomalies(company_id: UUID, days_back: int = 30) -> Dict[str, Any]:
        """
        Get detected cost anomalies for a company
        
        Args:
            company_id: Company UUID
            days_back: Number of days to look back
            
        Returns:
            Dictionary with cost anomalies
        """
        try:
            cutoff_date = datetime.now(timezone.utc) - timedelta(days=days_back)
            
            query = """
                SELECT id, detected_at, anomaly_type, expected_value, actual_value,
                       deviation_percentage, details
                FROM cost_anomalies
                WHERE company_id = $1 AND detected_at >= $2
                ORDER BY detected_at DESC
            """
            
            anomalies = await DatabaseUtils.execute_query(
                query, 
                [company_id, cutoff_date], 
                fetch_all=True
            )
            
            anomaly_list = []
            for anomaly in anomalies:
                anomaly_list.append({
                    "id": str(anomaly['id']),
                    "detected_at": anomaly['detected_at'].isoformat(),
                    "anomaly_type": anomaly['anomaly_type'],
                    "expected_value": float(anomaly['expected_value']),
                    "actual_value": float(anomaly['actual_value']),
                    "deviation_percentage": float(anomaly['deviation_percentage']),
                    "details": anomaly['details']
                })
            
            return {
                "status": "success",
                "company_id": str(company_id),
                "anomalies": anomaly_list,
                "total_anomalies": len(anomaly_list),
                "analysis_period_days": days_back,
                "timestamp": datetime.utcnow().isoformat()
            }
            
        except Exception as e:
            error_info = handle_database_error(e)
            logger.error(f"Failed to get cost anomalies for company {company_id}: {error_info['user_message']}")
            return {"status": "error", "error": error_info['user_message']}
    
    # Helper methods
    
    @staticmethod
    def _validate_alert_config(config: Dict[str, Any]) -> Tuple[bool, Optional[str]]:
        """Validate alert configuration"""
        required_fields = ['alert_type', 'threshold_amount']
        
        for field in required_fields:
            if field not in config:
                return False, f"Required field '{field}' is missing"
        
        if config['threshold_amount'] <= 0:
            return False, "Threshold amount must be positive"
        
        valid_alert_types = [e.value for e in AlertType]
        if config['alert_type'] not in valid_alert_types:
            return False, f"Invalid alert type. Must be one of: {valid_alert_types}"
        
        if config.get('time_window_hours', 1) <= 0:
            return False, "Time window hours must be positive"
        
        return True, None
    
    @staticmethod
    async def _calculate_cost_for_window(company_id: UUID, hours: int) -> float:
        """Calculate total cost for a time window"""
        try:
            cutoff_time = datetime.now(timezone.utc) - timedelta(hours=hours)
            
            query = """
                SELECT COALESCE(SUM(r.total_cost), 0) as total_cost
                FROM requests r
                WHERE r.company_id = $1 AND r.timestamp_utc >= $2
            """
            
            result = await DatabaseUtils.execute_query(
                query,
                [company_id, cutoff_time],
                fetch_all=False
            )
            
            return float(result['total_cost']) if result else 0.0
            
        except Exception as e:
            logger.error(f"Failed to calculate cost for window: {e}")
            return 0.0
    
    @staticmethod
    def _check_threshold(current_value: float, threshold: float, operator: str) -> bool:
        """Check if threshold is exceeded"""
        if operator == 'greater_than':
            return current_value > threshold
        elif operator == 'greater_than_or_equal':
            return current_value >= threshold
        elif operator == 'less_than':
            return current_value < threshold
        elif operator == 'less_than_or_equal':
            return current_value <= threshold
        else:
            return current_value > threshold  # Default to greater_than
    
    @staticmethod
    async def _record_triggered_alert(alert: Dict[str, Any], current_cost: float) -> Optional[Dict[str, Any]]:
        """Record a triggered alert"""
        try:
            query = """
                INSERT INTO triggered_alerts (
                    id, alert_id, company_id, triggered_at, threshold_amount,
                    actual_amount, alert_type, severity, message
                )
                VALUES ($1, $2, $3, NOW(), $4, $5, $6, $7, $8)
                RETURNING id, triggered_at
            """
            
            severity = CostMonitoringService._calculate_threshold_severity(
                current_cost, float(alert['threshold_usd'])
            )
            
            message = f"Cost alert '{alert['alert_type']}' triggered: ${current_cost:.4f} exceeded threshold of ${float(alert['threshold_usd']):.4f}"
            
            result = await DatabaseUtils.execute_query(
                query,
                [
                    uuid4(),
                    alert['id'],
                    alert['company_id'],
                    float(alert['threshold_usd']),
                    current_cost,
                    alert['alert_type'],
                    severity,
                    message
                ],
                fetch_all=False
            )
            
            if result:
                return {
                    "id": str(result['id']),
                    "alert_type": alert['alert_type'],
                    "threshold_amount": float(alert['threshold_usd']),
                    "actual_amount": current_cost,
                    "severity": severity,
                    "triggered_at": result['triggered_at'].isoformat(),
                    "message": message
                }
            
            return None
            
        except Exception as e:
            logger.error(f"Failed to record triggered alert: {e}")
            return None
    
    @staticmethod
    def _detect_statistical_anomalies(values: List[float], threshold: float = 2.0) -> List[bool]:
        """Detect anomalies using z-score method"""
        if len(values) < 3:
            return [False] * len(values)
        
        mean = statistics.mean(values)
        std_dev = statistics.stdev(values)
        
        if std_dev == 0:
            return [False] * len(values)
        
        anomalies = []
        for value in values:
            z_score = abs((value - mean) / std_dev)
            anomalies.append(z_score > threshold)
        
        return anomalies
    
    @staticmethod
    async def _record_cost_anomaly(company_id: UUID, date: datetime, actual_cost: float, 
                                  expected_cost: float, z_score: float, severity: str) -> Optional[Dict[str, Any]]:
        """Record a detected cost anomaly"""
        try:
            deviation_pct = ((actual_cost - expected_cost) / expected_cost * 100) if expected_cost > 0 else 0
            
            description = f"Cost anomaly detected: ${actual_cost:.4f} vs expected ${expected_cost:.4f} ({deviation_pct:+.1f}%)"
            
            query = """
                INSERT INTO cost_anomalies (
                    id, company_id, anomaly_date, actual_cost_usd, expected_cost_usd,
                    deviation_percentage, z_score, severity, description, detected_at
                )
                VALUES ($1, $2, $3, $4, $5, $6, $7, $8, $9, NOW())
                ON CONFLICT (company_id, anomaly_date) DO UPDATE SET
                    actual_cost_usd = EXCLUDED.actual_cost_usd,
                    expected_cost_usd = EXCLUDED.expected_cost_usd,
                    deviation_percentage = EXCLUDED.deviation_percentage,
                    z_score = EXCLUDED.z_score,
                    severity = EXCLUDED.severity,
                    description = EXCLUDED.description,
                    detected_at = NOW()
                RETURNING id, anomaly_date, detected_at
            """
            
            result = await DatabaseUtils.execute_query(
                query,
                [
                    uuid4(),
                    company_id,
                    date,
                    actual_cost,
                    expected_cost,
                    deviation_pct,
                    z_score,
                    severity,
                    description
                ],
                fetch_all=False
            )
            
            if result:
                return {
                    "id": str(result['id']),
                    "anomaly_date": result['anomaly_date'].isoformat(),
                    "actual_cost_usd": actual_cost,
                    "expected_cost_usd": expected_cost,
                    "deviation_percentage": round(deviation_pct, 2),
                    "z_score": round(z_score, 3),
                    "severity": severity,
                    "description": description,
                    "detected_at": result['detected_at'].isoformat()
                }
            
            return None
            
        except Exception as e:
            logger.error(f"Failed to record cost anomaly: {e}")
            return None
    
    @staticmethod
    def _calculate_threshold_severity(actual: float, threshold: float) -> str:
        """Calculate severity based on how much threshold is exceeded"""
        ratio = actual / threshold if threshold > 0 else 1
        
        if ratio >= 3.0:
            return AlertSeverity.CRITICAL.value
        elif ratio >= 2.0:
            return AlertSeverity.HIGH.value
        elif ratio >= 1.5:
            return AlertSeverity.MEDIUM.value
        else:
            return AlertSeverity.LOW.value
    
    @staticmethod
    def _calculate_anomaly_severity(z_score: float) -> str:
        """Calculate anomaly severity based on z-score"""
        if z_score >= 4.0:
            return AlertSeverity.CRITICAL.value
        elif z_score >= 3.0:
            return AlertSeverity.HIGH.value
        elif z_score >= 2.5:
            return AlertSeverity.MEDIUM.value
        else:
            return AlertSeverity.LOW.value

# Background job functions

async def run_cost_monitoring_job():
    """Background job for cost monitoring"""
    try:
        logger.info("Starting cost monitoring job")
        
        # Check cost thresholds
        threshold_results = await CostMonitoringService.check_cost_thresholds()
        
        if threshold_results["status"] == "success":
            logger.info(f"Cost threshold monitoring completed: {threshold_results['triggered_alerts']} alerts triggered")
        else:
            logger.error(f"Cost threshold monitoring failed: {threshold_results.get('error', 'Unknown error')}")
        
        return threshold_results
        
    except Exception as e:
        logger.error(f"Cost monitoring job crashed: {e}")
        return {"status": "error", "error": str(e)}

async def run_anomaly_detection_job():
    """Background job for anomaly detection"""
    try:
        logger.info("Starting cost anomaly detection job")
        
        # Get all active companies
        companies_query = "SELECT id FROM companies WHERE is_active = true"
        companies = await DatabaseUtils.execute_query(companies_query, [], fetch_all=True)
        
        results = []
        
        for company in companies:
            company_id = company['id']
            result = await CostMonitoringService.detect_cost_anomalies(company_id)
            results.append(result)
        
        total_anomalies = sum(r.get('anomalies_detected', 0) for r in results if r.get('status') == 'success')
        
        logger.info(f"Anomaly detection job completed: {total_anomalies} anomalies detected across {len(companies)} companies")
        
        return {
            "status": "success",
            "companies_processed": len(companies),
            "total_anomalies_detected": total_anomalies,
            "results": results,
            "timestamp": datetime.utcnow().isoformat()
        }
        
    except Exception as e:
        logger.error(f"Anomaly detection job crashed: {e}")
        return {"status": "error", "error": str(e)}
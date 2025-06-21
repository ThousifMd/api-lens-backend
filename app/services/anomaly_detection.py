"""
Anomaly Detection Service - Advanced statistical and ML-based anomaly detection
Implements multiple algorithms for detecting usage anomalies and optimization opportunities
"""

import asyncio
import json
import logging
import time
import statistics
from datetime import datetime, timedelta, timezone
from typing import Optional, Dict, Any, List, Union, Tuple
from decimal import Decimal
from collections import defaultdict, deque
import numpy as np
from scipy import stats
import hashlib

from ..config import get_settings
from ..utils.logger import get_logger
from ..database import DatabaseUtils
from .monitoring import (
    AnomalyType, AlertSeverity, Anomaly, monitoring_service
)

settings = get_settings()
logger = get_logger(__name__)

# Anomaly detection constants
ANOMALY_WINDOW_HOURS = 168  # 7 days for baseline
MIN_BASELINE_POINTS = 20    # Minimum data points for baseline
CONFIDENCE_THRESHOLD = 0.8  # Minimum confidence for anomaly reporting
SEASONAL_PATTERN_DAYS = 7   # Days to consider for seasonal patterns

async def _get_historical_usage_data(company_id: str, start_time: datetime, end_time: datetime) -> Dict[str, List[float]]:
    """Get historical usage data for baseline calculation"""
    try:
        query = """
            SELECT 
                DATE_TRUNC('hour', calculation_timestamp) as hour,
                COUNT(*) as request_count,
                SUM(total_cost) as total_cost,
                AVG(EXTRACT(EPOCH FROM (response_received_at - request_sent_at)) * 1000) as avg_response_time,
                COUNT(CASE WHEN status_code >= 400 THEN 1 END) as error_count,
                COUNT(*) as total_requests
            FROM cost_calculations 
            WHERE company_id = :company_id 
                AND calculation_timestamp BETWEEN :start_time AND :end_time
            GROUP BY DATE_TRUNC('hour', calculation_timestamp)
            ORDER BY hour
        """
        
        results = await DatabaseUtils.execute_query(
            query, 
            {'company_id': company_id, 'start_time': start_time, 'end_time': end_time}, 
            fetch_all=True
        )
        
        # Organize data by metric type
        historical_data = {
            'requests': [],
            'costs': [],
            'response_times': [],
            'error_rates': [],
            'timestamps': []
        }
        
        for row in results:
            historical_data['requests'].append(row['request_count'])
            historical_data['costs'].append(float(row['total_cost']))
            historical_data['response_times'].append(row['avg_response_time'] or 0)
            
            error_rate = (row['error_count'] / row['total_requests'] * 100) if row['total_requests'] > 0 else 0
            historical_data['error_rates'].append(error_rate)
            historical_data['timestamps'].append(row['hour'])
        
        return historical_data
        
    except Exception as e:
        logger.error(f"Failed to get historical usage data: {e}")
        return {'requests': [], 'costs': [], 'response_times': [], 'error_rates': [], 'timestamps': []}

async def _get_recent_usage_data(company_id: str, current_time: datetime) -> Dict[str, float]:
    """Get recent usage data for comparison"""
    try:
        # Get data from the last hour
        start_time = current_time - timedelta(hours=1)
        
        query = """
            SELECT 
                COUNT(*) as request_count,
                SUM(total_cost) as total_cost,
                AVG(EXTRACT(EPOCH FROM (response_received_at - request_sent_at)) * 1000) as avg_response_time,
                COUNT(CASE WHEN status_code >= 400 THEN 1 END) as error_count
            FROM cost_calculations 
            WHERE company_id = :company_id 
                AND calculation_timestamp >= :start_time
        """
        
        result = await DatabaseUtils.execute_query(
            query, 
            {'company_id': company_id, 'start_time': start_time}, 
            fetch_one=True
        )
        
        if not result:
            return {'requests': 0, 'cost': 0, 'response_time': 0, 'error_rate': 0}
        
        error_rate = (result['error_count'] / result['request_count'] * 100) if result['request_count'] > 0 else 0
        
        return {
            'requests': result['request_count'],
            'cost': float(result['total_cost'] or 0),
            'response_time': result['avg_response_time'] or 0,
            'error_rate': error_rate
        }
        
    except Exception as e:
        logger.error(f"Failed to get recent usage data: {e}")
        return {'requests': 0, 'cost': 0, 'response_time': 0, 'error_rate': 0}

async def _detect_request_anomalies(company_id: str, historical_data: Dict, recent_data: Dict, current_time: datetime) -> List[Anomaly]:
    """Detect request volume anomalies"""
    anomalies = []
    
    try:
        requests_history = historical_data.get('requests', [])
        current_requests = recent_data.get('requests', 0)
        
        if len(requests_history) < MIN_BASELINE_POINTS:
            return anomalies
        
        # Calculate statistical baseline
        mean_requests = statistics.mean(requests_history)
        std_requests = statistics.stdev(requests_history) if len(requests_history) > 1 else 0
        
        if std_requests == 0:
            return anomalies  # No variation to detect anomalies
        
        # Calculate z-score
        z_score = (current_requests - mean_requests) / std_requests
        
        # Detect sudden spike
        if z_score > monitoring_service._anomaly_thresholds[AnomalyType.SUDDEN_SPIKE]:
            anomaly = Anomaly(
                anomaly_id=_generate_anomaly_id(company_id, AnomalyType.SUDDEN_SPIKE, current_time),
                company_id=company_id,
                anomaly_type=AnomalyType.SUDDEN_SPIKE,
                severity=_calculate_anomaly_severity(abs(z_score)),
                detected_at=current_time,
                metric_name="request_volume",
                current_value=current_requests,
                expected_value=mean_requests,
                deviation_percentage=((current_requests - mean_requests) / mean_requests * 100),
                description=f"Request volume spike detected: {current_requests} requests vs expected {mean_requests:.1f}",
                recommendation="Monitor system capacity and consider scaling resources",
                affected_period=(current_time - timedelta(hours=1), current_time),
                confidence_score=min(abs(z_score) / 5.0, 1.0),  # Normalize confidence
                is_ongoing=True,
                impact_assessment="High request volume may impact system performance"
            )
            anomalies.append(anomaly)
        
        # Detect sudden drop
        elif z_score < -monitoring_service._anomaly_thresholds[AnomalyType.SUDDEN_DROP]:
            anomaly = Anomaly(
                anomaly_id=_generate_anomaly_id(company_id, AnomalyType.SUDDEN_DROP, current_time),
                company_id=company_id,
                anomaly_type=AnomalyType.SUDDEN_DROP,
                severity=_calculate_anomaly_severity(abs(z_score)),
                detected_at=current_time,
                metric_name="request_volume",
                current_value=current_requests,
                expected_value=mean_requests,
                deviation_percentage=((current_requests - mean_requests) / mean_requests * 100),
                description=f"Request volume drop detected: {current_requests} requests vs expected {mean_requests:.1f}",
                recommendation="Check for service issues or client-side problems",
                affected_period=(current_time - timedelta(hours=1), current_time),
                confidence_score=min(abs(z_score) / 5.0, 1.0),
                is_ongoing=True,
                impact_assessment="Sudden drop may indicate service disruption"
            )
            anomalies.append(anomaly)
        
        return anomalies
        
    except Exception as e:
        logger.error(f"Failed to detect request anomalies: {e}")
        return []

async def _detect_cost_anomalies(company_id: str, historical_data: Dict, recent_data: Dict, current_time: datetime) -> List[Anomaly]:
    """Detect cost anomalies"""
    anomalies = []
    
    try:
        costs_history = historical_data.get('costs', [])
        current_cost = recent_data.get('cost', 0)
        
        if len(costs_history) < MIN_BASELINE_POINTS or current_cost == 0:
            return anomalies
        
        # Filter out zero costs for better baseline
        non_zero_costs = [c for c in costs_history if c > 0]
        if len(non_zero_costs) < MIN_BASELINE_POINTS:
            return anomalies
        
        mean_cost = statistics.mean(non_zero_costs)
        std_cost = statistics.stdev(non_zero_costs) if len(non_zero_costs) > 1 else 0
        
        if std_cost == 0:
            return anomalies
        
        z_score = (current_cost - mean_cost) / std_cost
        
        # Detect cost anomalies (both high and low)
        if abs(z_score) > monitoring_service._anomaly_thresholds[AnomalyType.COST_ANOMALY]:
            severity = AlertSeverity.WARNING if abs(z_score) < 3.0 else AlertSeverity.CRITICAL
            
            anomaly_type = AnomalyType.COST_ANOMALY
            description = f"Cost anomaly detected: ${current_cost:.2f} vs expected ${mean_cost:.2f}"
            
            if z_score > 0:
                recommendation = "Review usage patterns and consider cost optimization measures"
                impact = "Higher than expected costs may impact budget"
            else:
                recommendation = "Verify if reduced usage is intentional or indicates service issues"
                impact = "Lower costs may indicate reduced service utilization"
            
            anomaly = Anomaly(
                anomaly_id=_generate_anomaly_id(company_id, anomaly_type, current_time),
                company_id=company_id,
                anomaly_type=anomaly_type,
                severity=severity,
                detected_at=current_time,
                metric_name="cost_per_hour",
                current_value=current_cost,
                expected_value=mean_cost,
                deviation_percentage=((current_cost - mean_cost) / mean_cost * 100),
                description=description,
                recommendation=recommendation,
                affected_period=(current_time - timedelta(hours=1), current_time),
                confidence_score=min(abs(z_score) / 4.0, 1.0),
                is_ongoing=True,
                impact_assessment=impact
            )
            anomalies.append(anomaly)
        
        return anomalies
        
    except Exception as e:
        logger.error(f"Failed to detect cost anomalies: {e}")
        return []

async def _detect_performance_anomalies(company_id: str, historical_data: Dict, recent_data: Dict, current_time: datetime) -> List[Anomaly]:
    """Detect performance anomalies"""
    anomalies = []
    
    try:
        # Response time anomalies
        response_times_history = historical_data.get('response_times', [])
        current_response_time = recent_data.get('response_time', 0)
        
        if len(response_times_history) >= MIN_BASELINE_POINTS and current_response_time > 0:
            # Filter out zero response times
            non_zero_times = [rt for rt in response_times_history if rt > 0]
            
            if len(non_zero_times) >= MIN_BASELINE_POINTS:
                mean_time = statistics.mean(non_zero_times)
                std_time = statistics.stdev(non_zero_times) if len(non_zero_times) > 1 else 0
                
                if std_time > 0:
                    z_score = (current_response_time - mean_time) / std_time
                    
                    # Detect slow response times
                    if z_score > 2.0:  # Performance degradation threshold
                        anomaly = Anomaly(
                            anomaly_id=_generate_anomaly_id(company_id, AnomalyType.UNUSUAL_PATTERN, current_time),
                            company_id=company_id,
                            anomaly_type=AnomalyType.UNUSUAL_PATTERN,
                            severity=AlertSeverity.WARNING if z_score < 3.0 else AlertSeverity.CRITICAL,
                            detected_at=current_time,
                            metric_name="response_time",
                            current_value=current_response_time,
                            expected_value=mean_time,
                            deviation_percentage=((current_response_time - mean_time) / mean_time * 100),
                            description=f"Performance degradation detected: {current_response_time:.1f}ms vs expected {mean_time:.1f}ms",
                            recommendation="Check system resources and network connectivity",
                            affected_period=(current_time - timedelta(hours=1), current_time),
                            confidence_score=min(z_score / 4.0, 1.0),
                            is_ongoing=True,
                            impact_assessment="Slower response times may impact user experience"
                        )
                        anomalies.append(anomaly)
        
        # Error rate anomalies
        error_rates_history = historical_data.get('error_rates', [])
        current_error_rate = recent_data.get('error_rate', 0)
        
        if len(error_rates_history) >= MIN_BASELINE_POINTS:
            mean_error_rate = statistics.mean(error_rates_history)
            std_error_rate = statistics.stdev(error_rates_history) if len(error_rates_history) > 1 else 0
            
            # If standard deviation is very low, use a minimum threshold
            if std_error_rate < 1.0:
                std_error_rate = 1.0
            
            z_score = (current_error_rate - mean_error_rate) / std_error_rate
            
            # Detect error surges
            if z_score > monitoring_service._anomaly_thresholds[AnomalyType.ERROR_SURGE]:
                anomaly = Anomaly(
                    anomaly_id=_generate_anomaly_id(company_id, AnomalyType.ERROR_SURGE, current_time),
                    company_id=company_id,
                    anomaly_type=AnomalyType.ERROR_SURGE,
                    severity=AlertSeverity.CRITICAL,
                    detected_at=current_time,
                    metric_name="error_rate",
                    current_value=current_error_rate,
                    expected_value=mean_error_rate,
                    deviation_percentage=((current_error_rate - mean_error_rate) / max(mean_error_rate, 0.1) * 100),
                    description=f"Error rate surge detected: {current_error_rate:.1f}% vs expected {mean_error_rate:.1f}%",
                    recommendation="Investigate system errors and check service health",
                    affected_period=(current_time - timedelta(hours=1), current_time),
                    confidence_score=min(z_score / 3.0, 1.0),
                    is_ongoing=True,
                    impact_assessment="High error rates indicate service reliability issues"
                )
                anomalies.append(anomaly)
        
        return anomalies
        
    except Exception as e:
        logger.error(f"Failed to detect performance anomalies: {e}")
        return []

async def _detect_pattern_anomalies(company_id: str, historical_data: Dict, recent_data: Dict, current_time: datetime) -> List[Anomaly]:
    """Detect unusual patterns in usage"""
    anomalies = []
    
    try:
        requests_history = historical_data.get('requests', [])
        timestamps_history = historical_data.get('timestamps', [])
        
        if len(requests_history) < SEASONAL_PATTERN_DAYS * 24:  # Need at least 7 days of hourly data
            return anomalies
        
        # Analyze hourly patterns
        hourly_patterns = defaultdict(list)
        for i, timestamp in enumerate(timestamps_history):
            hour = timestamp.hour
            hourly_patterns[hour].append(requests_history[i])
        
        # Check if current hour's usage deviates from typical pattern
        current_hour = current_time.hour
        current_requests = recent_data.get('requests', 0)
        
        if current_hour in hourly_patterns and len(hourly_patterns[current_hour]) >= 7:
            typical_requests = hourly_patterns[current_hour]
            mean_requests = statistics.mean(typical_requests)
            std_requests = statistics.stdev(typical_requests) if len(typical_requests) > 1 else 0
            
            if std_requests > 0:
                z_score = (current_requests - mean_requests) / std_requests
                
                # Detect unusual patterns
                if abs(z_score) > 2.5:  # Pattern deviation threshold
                    anomaly = Anomaly(
                        anomaly_id=_generate_anomaly_id(company_id, AnomalyType.UNUSUAL_PATTERN, current_time),
                        company_id=company_id,
                        anomaly_type=AnomalyType.UNUSUAL_PATTERN,
                        severity=AlertSeverity.INFO if abs(z_score) < 3.0 else AlertSeverity.WARNING,
                        detected_at=current_time,
                        metric_name="hourly_pattern",
                        current_value=current_requests,
                        expected_value=mean_requests,
                        deviation_percentage=((current_requests - mean_requests) / mean_requests * 100),
                        description=f"Unusual usage pattern at {current_hour}:00 - {current_requests} requests vs typical {mean_requests:.1f}",
                        recommendation="Review if usage pattern change is expected or investigate potential issues",
                        affected_period=(current_time - timedelta(hours=1), current_time),
                        confidence_score=min(abs(z_score) / 4.0, 1.0),
                        is_ongoing=True,
                        impact_assessment="Usage pattern deviation from normal behavior"
                    )
                    anomalies.append(anomaly)
        
        return anomalies
        
    except Exception as e:
        logger.error(f"Failed to detect pattern anomalies: {e}")
        return []

async def _send_anomaly_alerts(company_id: str, anomalies: List[Anomaly]) -> None:
    """Send alerts for detected anomalies"""
    try:
        for anomaly in anomalies:
            # Log the anomaly
            logger.warning(f"ANOMALY DETECTED for {company_id}: {anomaly.description}")
            
            # Store anomaly in database
            await _store_anomaly(anomaly)
            
            # In production, integrate with alerting systems (email, Slack, PagerDuty, etc.)
            if anomaly.severity in [AlertSeverity.CRITICAL, AlertSeverity.EMERGENCY]:
                # Send immediate alerts for critical issues
                await _send_critical_anomaly_notification(anomaly)
        
    except Exception as e:
        logger.error(f"Failed to send anomaly alerts: {e}")

async def _store_anomaly(anomaly: Anomaly) -> None:
    """Store anomaly in database"""
    try:
        query = """
            INSERT INTO usage_anomalies (
                anomaly_id, company_id, anomaly_type, severity, metric_name,
                current_value, expected_value, deviation_percentage,
                description, recommendation, confidence_score,
                detected_at, affected_period_start, affected_period_end,
                is_ongoing, impact_assessment
            ) VALUES (
                :anomaly_id, :company_id, :anomaly_type, :severity, :metric_name,
                :current_value, :expected_value, :deviation_percentage,
                :description, :recommendation, :confidence_score,
                :detected_at, :affected_period_start, :affected_period_end,
                :is_ongoing, :impact_assessment
            )
        """
        
        await DatabaseUtils.execute_query(query, {
            'anomaly_id': anomaly.anomaly_id,
            'company_id': anomaly.company_id,
            'anomaly_type': anomaly.anomaly_type.value,
            'severity': anomaly.severity.value,
            'metric_name': anomaly.metric_name,
            'current_value': anomaly.current_value,
            'expected_value': anomaly.expected_value,
            'deviation_percentage': anomaly.deviation_percentage,
            'description': anomaly.description,
            'recommendation': anomaly.recommendation,
            'confidence_score': anomaly.confidence_score,
            'detected_at': anomaly.detected_at,
            'affected_period_start': anomaly.affected_period[0],
            'affected_period_end': anomaly.affected_period[1],
            'is_ongoing': anomaly.is_ongoing,
            'impact_assessment': anomaly.impact_assessment
        })
        
    except Exception as e:
        logger.error(f"Failed to store anomaly: {e}")

async def _send_critical_anomaly_notification(anomaly: Anomaly) -> None:
    """Send immediate notification for critical anomalies"""
    try:
        # In production, this would integrate with notification systems
        notification_data = {
            'company_id': anomaly.company_id,
            'anomaly_type': anomaly.anomaly_type.value,
            'severity': anomaly.severity.value,
            'description': anomaly.description,
            'recommendation': anomaly.recommendation,
            'detected_at': anomaly.detected_at.isoformat(),
            'confidence_score': anomaly.confidence_score
        }
        
        # Store notification for processing by external systems
        redis_client = await monitoring_service._get_redis_client()
        notification_key = f"critical_notifications:{anomaly.company_id}:{int(time.time())}"
        await redis_client.setex(notification_key, 3600, json.dumps(notification_data, default=str))
        
        logger.critical(f"CRITICAL ANOMALY: {anomaly.description} (Confidence: {anomaly.confidence_score:.2f})")
        
    except Exception as e:
        logger.error(f"Failed to send critical anomaly notification: {e}")

def _generate_anomaly_id(company_id: str, anomaly_type: AnomalyType, timestamp: datetime) -> str:
    """Generate unique anomaly ID"""
    data = f"{company_id}_{anomaly_type.value}_{timestamp.isoformat()}"
    return hashlib.sha256(data.encode()).hexdigest()[:16]

def _calculate_anomaly_severity(z_score: float) -> AlertSeverity:
    """Calculate anomaly severity based on z-score"""
    abs_z = abs(z_score)
    
    if abs_z >= 4.0:
        return AlertSeverity.EMERGENCY
    elif abs_z >= 3.0:
        return AlertSeverity.CRITICAL
    elif abs_z >= 2.0:
        return AlertSeverity.WARNING
    else:
        return AlertSeverity.INFO
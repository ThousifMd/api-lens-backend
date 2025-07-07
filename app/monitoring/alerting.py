"""
Alerting System
Monitors metrics and sends alerts via various channels
"""

import asyncio
import json
from typing import Dict, Any, List, Optional, Callable
from datetime import datetime, timedelta
from enum import Enum
import httpx
import smtplib
from email.mime.text import MIMEText
from email.mime.multipart import MIMEMultipart

from ..config import get_settings
from ..utils.logger import get_logger
from ..database import DatabaseUtils
from .metrics import ERROR_COUNT, RATE_LIMIT_EXCEEDED

settings = get_settings()
logger = get_logger(__name__)

class AlertSeverity(Enum):
    """Alert severity levels"""
    INFO = "info"
    WARNING = "warning"
    ERROR = "error"
    CRITICAL = "critical"

class AlertChannel(Enum):
    """Alert delivery channels"""
    EMAIL = "email"
    SLACK = "slack"
    WEBHOOK = "webhook"
    PAGERDUTY = "pagerduty"
    OPSGENIE = "opsgenie"

class AlertRule:
    """Defines an alert rule"""
    def __init__(
        self,
        name: str,
        condition: Callable[[], bool],
        message: str,
        severity: AlertSeverity,
        channels: List[AlertChannel],
        cooldown_minutes: int = 15
    ):
        self.name = name
        self.condition = condition
        self.message = message
        self.severity = severity
        self.channels = channels
        self.cooldown_minutes = cooldown_minutes
        self.last_alert_time: Optional[datetime] = None

class AlertingService:
    """Service for monitoring and alerting"""
    
    def __init__(self):
        self.rules: List[AlertRule] = []
        self.alert_handlers: Dict[AlertChannel, Callable] = {
            AlertChannel.EMAIL: self._send_email_alert,
            AlertChannel.SLACK: self._send_slack_alert,
            AlertChannel.WEBHOOK: self._send_webhook_alert,
            AlertChannel.PAGERDUTY: self._send_pagerduty_alert,
            AlertChannel.OPSGENIE: self._send_opsgenie_alert
        }
        self._setup_default_rules()
    
    def _setup_default_rules(self):
        """Set up default alerting rules"""
        
        # High error rate alert
        self.add_rule(
            name="high_error_rate",
            condition=lambda: self._check_error_rate(threshold=0.05, window_minutes=5),
            message="Error rate exceeded 5% in the last 5 minutes",
            severity=AlertSeverity.ERROR,
            channels=[AlertChannel.SLACK, AlertChannel.EMAIL]
        )
        
        # Database connection issues
        self.add_rule(
            name="database_connection_failure",
            condition=lambda: self._check_database_health(),
            message="Database connection issues detected",
            severity=AlertSeverity.CRITICAL,
            channels=[AlertChannel.PAGERDUTY, AlertChannel.SLACK]
        )
        
        # Rate limit abuse
        self.add_rule(
            name="rate_limit_abuse",
            condition=lambda: self._check_rate_limit_abuse(threshold=100, window_minutes=5),
            message="Excessive rate limit violations detected",
            severity=AlertSeverity.WARNING,
            channels=[AlertChannel.SLACK]
        )
        
        # High latency
        self.add_rule(
            name="high_latency",
            condition=lambda: self._check_latency(threshold_ms=5000, percentile=95),
            message="95th percentile latency exceeded 5 seconds",
            severity=AlertSeverity.WARNING,
            channels=[AlertChannel.SLACK]
        )
        
        # Low disk space
        self.add_rule(
            name="low_disk_space",
            condition=lambda: self._check_disk_space(threshold_percent=90),
            message="Disk usage exceeded 90%",
            severity=AlertSeverity.ERROR,
            channels=[AlertChannel.EMAIL, AlertChannel.SLACK]
        )
        
        # High memory usage
        self.add_rule(
            name="high_memory_usage",
            condition=lambda: self._check_memory_usage(threshold_percent=85),
            message="Memory usage exceeded 85%",
            severity=AlertSeverity.WARNING,
            channels=[AlertChannel.SLACK]
        )
    
    def add_rule(self, **kwargs):
        """Add a new alert rule"""
        rule = AlertRule(**kwargs)
        self.rules.append(rule)
        logger.info(f"Added alert rule: {rule.name}")
    
    async def check_alerts(self):
        """Check all alert rules and send alerts if needed"""
        for rule in self.rules:
            try:
                # Check if we're in cooldown period
                if rule.last_alert_time:
                    cooldown_end = rule.last_alert_time + timedelta(minutes=rule.cooldown_minutes)
                    if datetime.utcnow() < cooldown_end:
                        continue
                
                # Check if condition is met
                if await asyncio.to_thread(rule.condition):
                    await self._send_alert(rule)
                    rule.last_alert_time = datetime.utcnow()
                    
            except Exception as e:
                logger.error(f"Error checking alert rule {rule.name}: {e}")
    
    async def _send_alert(self, rule: AlertRule):
        """Send alert through configured channels"""
        alert_data = {
            "rule_name": rule.name,
            "message": rule.message,
            "severity": rule.severity.value,
            "timestamp": datetime.utcnow().isoformat(),
            "environment": settings.ENVIRONMENT,
            "service": "api-lens-backend"
        }
        
        # Log alert to database
        await self._log_alert(alert_data)
        
        # Send through each channel
        for channel in rule.channels:
            handler = self.alert_handlers.get(channel)
            if handler:
                try:
                    await handler(alert_data)
                except Exception as e:
                    logger.error(f"Failed to send alert via {channel.value}: {e}")
    
    async def _log_alert(self, alert_data: Dict[str, Any]):
        """Log alert to database"""
        try:
            query = """
                INSERT INTO alerts (
                    rule_name, message, severity, timestamp, 
                    environment, channel, sent_at
                ) VALUES ($1, $2, $3, $4, $5, $6, $7)
            """
            await DatabaseUtils.execute_query(query, [
                alert_data["rule_name"],
                alert_data["message"],
                alert_data["severity"],
                alert_data["timestamp"],
                alert_data["environment"],
                "multiple",
                datetime.utcnow()
            ])
        except Exception as e:
            logger.error(f"Failed to log alert to database: {e}")
    
    # Alert delivery methods
    
    async def _send_email_alert(self, alert_data: Dict[str, Any]):
        """Send alert via email"""
        if not getattr(settings, 'ALERT_EMAIL_ENABLED', False):
            return
            
        smtp_host = getattr(settings, 'SMTP_HOST', 'localhost')
        smtp_port = getattr(settings, 'SMTP_PORT', 587)
        smtp_user = getattr(settings, 'SMTP_USER', '')
        smtp_pass = getattr(settings, 'SMTP_PASS', '')
        from_email = getattr(settings, 'ALERT_FROM_EMAIL', 'alerts@apilens.dev')
        to_emails = getattr(settings, 'ALERT_TO_EMAILS', [])
        
        if not to_emails:
            return
        
        # Create email
        msg = MIMEMultipart()
        msg['From'] = from_email
        msg['To'] = ', '.join(to_emails)
        msg['Subject'] = f"[{alert_data['severity'].upper()}] API Lens Alert: {alert_data['rule_name']}"
        
        body = f"""
        Alert: {alert_data['message']}
        
        Details:
        - Rule: {alert_data['rule_name']}
        - Severity: {alert_data['severity']}
        - Time: {alert_data['timestamp']}
        - Environment: {alert_data['environment']}
        - Service: {alert_data['service']}
        """
        
        msg.attach(MIMEText(body, 'plain'))
        
        # Send email
        try:
            with smtplib.SMTP(smtp_host, smtp_port) as server:
                if smtp_user and smtp_pass:
                    server.starttls()
                    server.login(smtp_user, smtp_pass)
                server.send_message(msg)
                logger.info(f"Email alert sent for {alert_data['rule_name']}")
        except Exception as e:
            logger.error(f"Failed to send email alert: {e}")
    
    async def _send_slack_alert(self, alert_data: Dict[str, Any]):
        """Send alert via Slack webhook"""
        webhook_url = getattr(settings, 'SLACK_WEBHOOK_URL', '')
        if not webhook_url:
            return
        
        # Format message for Slack
        color_map = {
            AlertSeverity.INFO: "#36a64f",
            AlertSeverity.WARNING: "#ff9800",
            AlertSeverity.ERROR: "#f44336",
            AlertSeverity.CRITICAL: "#d32f2f"
        }
        
        slack_message = {
            "attachments": [{
                "color": color_map.get(AlertSeverity(alert_data['severity']), "#808080"),
                "title": f"{alert_data['severity'].upper()}: {alert_data['rule_name']}",
                "text": alert_data['message'],
                "fields": [
                    {"title": "Environment", "value": alert_data['environment'], "short": True},
                    {"title": "Service", "value": alert_data['service'], "short": True},
                    {"title": "Time", "value": alert_data['timestamp'], "short": False}
                ],
                "footer": "API Lens Alerting",
                "ts": int(datetime.utcnow().timestamp())
            }]
        }
        
        async with httpx.AsyncClient() as client:
            response = await client.post(webhook_url, json=slack_message)
            if response.status_code == 200:
                logger.info(f"Slack alert sent for {alert_data['rule_name']}")
            else:
                logger.error(f"Failed to send Slack alert: {response.status_code}")
    
    async def _send_webhook_alert(self, alert_data: Dict[str, Any]):
        """Send alert via generic webhook"""
        webhook_url = getattr(settings, 'ALERT_WEBHOOK_URL', '')
        if not webhook_url:
            return
        
        async with httpx.AsyncClient() as client:
            response = await client.post(
                webhook_url,
                json=alert_data,
                headers={"Content-Type": "application/json"}
            )
            if response.status_code in [200, 201, 202, 204]:
                logger.info(f"Webhook alert sent for {alert_data['rule_name']}")
            else:
                logger.error(f"Failed to send webhook alert: {response.status_code}")
    
    async def _send_pagerduty_alert(self, alert_data: Dict[str, Any]):
        """Send alert via PagerDuty"""
        integration_key = getattr(settings, 'PAGERDUTY_INTEGRATION_KEY', '')
        if not integration_key:
            return
        
        severity_map = {
            AlertSeverity.INFO: "info",
            AlertSeverity.WARNING: "warning",
            AlertSeverity.ERROR: "error",
            AlertSeverity.CRITICAL: "critical"
        }
        
        pagerduty_event = {
            "routing_key": integration_key,
            "event_action": "trigger",
            "payload": {
                "summary": alert_data['message'],
                "severity": severity_map.get(AlertSeverity(alert_data['severity']), "error"),
                "source": alert_data['service'],
                "custom_details": {
                    "rule": alert_data['rule_name'],
                    "environment": alert_data['environment'],
                    "timestamp": alert_data['timestamp']
                }
            }
        }
        
        async with httpx.AsyncClient() as client:
            response = await client.post(
                "https://events.pagerduty.com/v2/enqueue",
                json=pagerduty_event
            )
            if response.status_code == 202:
                logger.info(f"PagerDuty alert sent for {alert_data['rule_name']}")
            else:
                logger.error(f"Failed to send PagerDuty alert: {response.status_code}")
    
    async def _send_opsgenie_alert(self, alert_data: Dict[str, Any]):
        """Send alert via OpsGenie"""
        api_key = getattr(settings, 'OPSGENIE_API_KEY', '')
        if not api_key:
            return
        
        priority_map = {
            AlertSeverity.INFO: "P5",
            AlertSeverity.WARNING: "P3",
            AlertSeverity.ERROR: "P2",
            AlertSeverity.CRITICAL: "P1"
        }
        
        opsgenie_alert = {
            "message": alert_data['message'],
            "alias": f"{alert_data['rule_name']}_{alert_data['timestamp']}",
            "description": f"Alert from {alert_data['service']} in {alert_data['environment']}",
            "priority": priority_map.get(AlertSeverity(alert_data['severity']), "P3"),
            "tags": [alert_data['environment'], alert_data['service'], alert_data['rule_name']]
        }
        
        async with httpx.AsyncClient() as client:
            response = await client.post(
                "https://api.opsgenie.com/v2/alerts",
                json=opsgenie_alert,
                headers={
                    "Authorization": f"GenieKey {api_key}",
                    "Content-Type": "application/json"
                }
            )
            if response.status_code in [200, 201, 202]:
                logger.info(f"OpsGenie alert sent for {alert_data['rule_name']}")
            else:
                logger.error(f"Failed to send OpsGenie alert: {response.status_code}")
    
    # Alert condition check methods
    
    def _check_error_rate(self, threshold: float, window_minutes: int) -> bool:
        """Check if error rate exceeds threshold"""
        # This would query metrics to check error rate
        # For now, return False to avoid false alerts
        return False
    
    def _check_database_health(self) -> bool:
        """Check database health"""
        # This would check database connection pool metrics
        return False
    
    def _check_rate_limit_abuse(self, threshold: int, window_minutes: int) -> bool:
        """Check for rate limit abuse"""
        # This would check rate limit violation metrics
        return False
    
    def _check_latency(self, threshold_ms: int, percentile: int) -> bool:
        """Check latency percentiles"""
        # This would check latency metrics
        return False
    
    def _check_disk_space(self, threshold_percent: int) -> bool:
        """Check disk space usage"""
        try:
            import psutil
            disk = psutil.disk_usage('/')
            return disk.percent > threshold_percent
        except:
            return False
    
    def _check_memory_usage(self, threshold_percent: int) -> bool:
        """Check memory usage"""
        try:
            import psutil
            memory = psutil.virtual_memory()
            return memory.percent > threshold_percent
        except:
            return False

# Global alerting service instance
alerting_service = AlertingService()

async def monitor_alerts():
    """Background task to continuously monitor alerts"""
    while True:
        try:
            await alerting_service.check_alerts()
            await asyncio.sleep(60)  # Check every minute
        except Exception as e:
            logger.error(f"Error in alert monitoring: {e}")
            await asyncio.sleep(60)
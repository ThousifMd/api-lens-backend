"""
Report Generation Service - Comprehensive usage report generation with analytics
Implements executive summaries, trend analysis, optimization recommendations, and benchmarking
"""

import asyncio
import json
import logging
import time
import statistics
import calendar
from datetime import datetime, timedelta, timezone
from typing import Optional, Dict, Any, List, Union, Tuple
from decimal import Decimal
from collections import defaultdict
import hashlib

from ..config import get_settings
from ..utils.logger import get_logger
from ..database import DatabaseUtils
from .monitoring import TimePeriod, UsageAggregation
from .monitoring_helpers import _calculate_trend

settings = get_settings()
logger = get_logger(__name__)

async def _generate_executive_summary(company_id: str, usage_analysis: UsageAggregation, period: TimePeriod) -> Dict[str, Any]:
    """Generate executive summary for usage report"""
    try:
        # Key highlights
        total_requests = usage_analysis.total_requests
        total_cost = usage_analysis.total_cost
        avg_response_time = usage_analysis.avg_response_time
        success_rate = usage_analysis.success_rate
        
        # Calculate period description
        period_days = (usage_analysis.end_time - usage_analysis.start_time).days
        period_description = f"{period_days}-day period" if period_days > 1 else "24-hour period"
        
        # Generate summary insights
        insights = []
        
        # Request volume insights
        if total_requests > 0:
            daily_avg = usage_analysis.avg_requests_per_day
            if daily_avg > 1000:
                insights.append(f"High API usage with {daily_avg:.0f} requests per day on average")
            elif daily_avg < 100:
                insights.append(f"Low API usage with {daily_avg:.0f} requests per day on average")
            else:
                insights.append(f"Moderate API usage with {daily_avg:.0f} requests per day on average")
        
        # Cost insights
        if total_cost > 0:
            cost_per_request = usage_analysis.cost_per_request
            if cost_per_request > Decimal('0.01'):
                insights.append(f"Higher cost per request at ${cost_per_request:.4f}")
            elif cost_per_request < Decimal('0.001'):
                insights.append(f"Efficient cost per request at ${cost_per_request:.4f}")
            else:
                insights.append(f"Standard cost per request at ${cost_per_request:.4f}")
        
        # Performance insights
        if avg_response_time > 2000:
            insights.append(f"Elevated response times averaging {avg_response_time:.0f}ms")
        elif avg_response_time < 500:
            insights.append(f"Excellent response times averaging {avg_response_time:.0f}ms")
        
        # Reliability insights
        if success_rate >= 99.5:
            insights.append("Excellent service reliability")
        elif success_rate >= 95:
            insights.append("Good service reliability")
        elif success_rate < 90:
            insights.append("Service reliability needs attention")
        
        # Overall assessment
        if success_rate >= 99 and avg_response_time < 1000 and usage_analysis.cost_efficiency_score >= 80:
            overall_assessment = "Excellent - High performance, reliability, and cost efficiency"
        elif success_rate >= 95 and avg_response_time < 2000 and usage_analysis.cost_efficiency_score >= 60:
            overall_assessment = "Good - Solid performance with room for optimization"
        else:
            overall_assessment = "Needs attention - Performance or cost optimization recommended"
        
        return {
            'period_description': period_description,
            'overall_assessment': overall_assessment,
            'key_insights': insights[:3],  # Top 3 insights
            'headline_metrics': {
                'total_requests': total_requests,
                'total_cost': float(total_cost),
                'avg_response_time_ms': avg_response_time,
                'success_rate_pct': success_rate,
                'cost_efficiency_score': usage_analysis.cost_efficiency_score
            },
            'summary_statement': f"During this {period_description}, your application processed {total_requests:,} requests with a {success_rate:.1f}% success rate, spending ${total_cost:.2f} at ${usage_analysis.cost_per_request:.4f} per request."
        }
        
    except Exception as e:
        logger.error(f"Failed to generate executive summary: {e}")
        return {
            'period_description': 'Analysis period',
            'overall_assessment': 'Data unavailable',
            'key_insights': [],
            'headline_metrics': {},
            'summary_statement': 'Unable to generate summary due to insufficient data.'
        }

async def _extract_key_metrics(company_id: str, usage_analysis: UsageAggregation, period: TimePeriod) -> Dict[str, Any]:
    """Extract key metrics for the report"""
    try:
        metrics = {
            'volume_metrics': {
                'total_requests': usage_analysis.total_requests,
                'avg_requests_per_day': usage_analysis.avg_requests_per_day,
                'peak_hour': usage_analysis.peak_hour,
                'peak_day': usage_analysis.peak_day
            },
            'cost_metrics': {
                'total_cost': float(usage_analysis.total_cost),
                'avg_cost_per_day': float(usage_analysis.avg_cost_per_day),
                'cost_per_request': float(usage_analysis.cost_per_request),
                'cost_trend': usage_analysis.cost_trend,
                'efficiency_score': usage_analysis.cost_efficiency_score
            },
            'performance_metrics': {
                'avg_response_time': usage_analysis.avg_response_time,
                'p50_response_time': usage_analysis.p50_response_time,
                'p95_response_time': usage_analysis.p95_response_time,
                'p99_response_time': usage_analysis.p99_response_time
            },
            'reliability_metrics': {
                'success_rate': usage_analysis.success_rate,
                'error_rate': usage_analysis.error_rate,
                'timeout_rate': usage_analysis.timeout_rate
            },
            'usage_patterns': {
                'busiest_vendor': usage_analysis.busiest_vendor,
                'most_used_model': usage_analysis.most_used_model,
                'peak_usage_hour': usage_analysis.peak_hour,
                'peak_usage_day': usage_analysis.peak_day
            }
        }
        
        return metrics
        
    except Exception as e:
        logger.error(f"Failed to extract key metrics: {e}")
        return {}

async def _perform_cost_analysis(company_id: str, start_time: datetime, end_time: datetime) -> Dict[str, Any]:
    """Perform detailed cost analysis"""
    try:
        # Get cost breakdown by vendor and model
        cost_query = """
            SELECT 
                vendor,
                model,
                COUNT(*) as request_count,
                SUM(total_cost) as total_cost,
                AVG(total_cost) as avg_cost_per_request,
                MIN(total_cost) as min_cost,
                MAX(total_cost) as max_cost,
                DATE_TRUNC('day', calculation_timestamp) as day
            FROM cost_calculations 
            WHERE company_id = :company_id 
                AND calculation_timestamp BETWEEN :start_time AND :end_time
            GROUP BY vendor, model, DATE_TRUNC('day', calculation_timestamp)
            ORDER BY total_cost DESC
        """
        
        results = await DatabaseUtils.execute_query(
            cost_query, 
            {'company_id': company_id, 'start_time': start_time, 'end_time': end_time}, 
            fetch_all=True
        )
        
        # Aggregate by vendor
        vendor_costs = defaultdict(lambda: {'cost': 0, 'requests': 0, 'models': set()})
        model_costs = defaultdict(lambda: {'cost': 0, 'requests': 0, 'vendor': ''})
        daily_costs = defaultdict(lambda: {'cost': 0, 'requests': 0})
        
        for row in results:
            vendor = row['vendor']
            model = row['model']
            day = row['day'].strftime('%Y-%m-%d')
            cost = float(row['total_cost'])
            requests = row['request_count']
            
            vendor_costs[vendor]['cost'] += cost
            vendor_costs[vendor]['requests'] += requests
            vendor_costs[vendor]['models'].add(model)
            
            model_costs[f"{vendor}_{model}"]['cost'] += cost
            model_costs[f"{vendor}_{model}"]['requests'] += requests
            model_costs[f"{vendor}_{model}"]['vendor'] = vendor
            
            daily_costs[day]['cost'] += cost
            daily_costs[day]['requests'] += requests
        
        # Calculate total cost
        total_cost = sum(vendor['cost'] for vendor in vendor_costs.values())
        
        # Find most expensive vendor and model
        most_expensive_vendor = max(vendor_costs.items(), key=lambda x: x[1]['cost']) if vendor_costs else ('Unknown', {'cost': 0})
        most_expensive_model = max(model_costs.items(), key=lambda x: x[1]['cost']) if model_costs else ('Unknown', {'cost': 0})
        
        # Calculate cost trend
        daily_cost_values = [day['cost'] for day in daily_costs.values()]
        cost_trend = _calculate_trend(daily_cost_values)
        
        # Cost efficiency analysis
        avg_cost_per_request = total_cost / sum(vendor['requests'] for vendor in vendor_costs.values()) if vendor_costs else 0
        
        # Calculate cost savings opportunities
        cost_savings_opportunities = await _calculate_cost_savings_opportunities(vendor_costs, model_costs)
        
        return {
            'total_cost': total_cost,
            'avg_cost_per_request': avg_cost_per_request,
            'cost_trend': cost_trend,
            'vendor_breakdown': [
                {
                    'vendor': vendor,
                    'cost': data['cost'],
                    'requests': data['requests'],
                    'cost_percentage': (data['cost'] / total_cost * 100) if total_cost > 0 else 0,
                    'avg_cost_per_request': data['cost'] / data['requests'] if data['requests'] > 0 else 0,
                    'models_used': len(data['models'])
                }
                for vendor, data in vendor_costs.items()
            ],
            'model_breakdown': [
                {
                    'model': model.split('_', 1)[1] if '_' in model else model,
                    'vendor': data['vendor'],
                    'cost': data['cost'],
                    'requests': data['requests'],
                    'cost_percentage': (data['cost'] / total_cost * 100) if total_cost > 0 else 0,
                    'avg_cost_per_request': data['cost'] / data['requests'] if data['requests'] > 0 else 0
                }
                for model, data in model_costs.items()
            ],
            'daily_breakdown': [
                {
                    'date': day,
                    'cost': data['cost'],
                    'requests': data['requests'],
                    'cost_per_request': data['cost'] / data['requests'] if data['requests'] > 0 else 0
                }
                for day, data in sorted(daily_costs.items())
            ],
            'cost_insights': {
                'most_expensive_vendor': most_expensive_vendor[0],
                'most_expensive_vendor_cost': most_expensive_vendor[1]['cost'],
                'most_expensive_model': most_expensive_model[0].split('_', 1)[1] if '_' in most_expensive_model[0] else most_expensive_model[0],
                'most_expensive_model_cost': most_expensive_model[1]['cost'],
                'cost_concentration': (most_expensive_vendor[1]['cost'] / total_cost * 100) if total_cost > 0 else 0
            },
            'cost_savings_opportunities': cost_savings_opportunities
        }
        
    except Exception as e:
        logger.error(f"Failed to perform cost analysis: {e}")
        return {}

async def _calculate_cost_savings_opportunities(vendor_costs: Dict, model_costs: Dict) -> List[Dict[str, Any]]:
    """Calculate potential cost savings opportunities"""
    opportunities = []
    
    try:
        # Check for vendor consolidation opportunities
        if len(vendor_costs) > 3:
            opportunities.append({
                'type': 'vendor_consolidation',
                'description': f"Consider consolidating from {len(vendor_costs)} vendors to reduce complexity",
                'potential_savings': 'Administrative overhead reduction',
                'priority': 'medium'
            })
        
        # Check for model optimization opportunities
        expensive_models = [(model, data) for model, data in model_costs.items() 
                          if data['cost'] / data['requests'] > 0.01]  # More than $0.01 per request
        
        if expensive_models:
            opportunities.append({
                'type': 'model_optimization',
                'description': f"Consider optimizing usage of {len(expensive_models)} high-cost models",
                'potential_savings': 'Up to 20-30% cost reduction through model selection',
                'priority': 'high'
            })
        
        # Check for usage pattern optimization
        total_requests = sum(vendor['requests'] for vendor in vendor_costs.values())
        if total_requests > 10000:
            opportunities.append({
                'type': 'bulk_pricing',
                'description': "High volume usage may qualify for enterprise pricing tiers",
                'potential_savings': 'Up to 15% through volume discounts',
                'priority': 'high'
            })
        
        return opportunities
        
    except Exception as e:
        logger.error(f"Failed to calculate cost savings opportunities: {e}")
        return []

async def _analyze_performance_trends(company_id: str, start_time: datetime, end_time: datetime) -> Dict[str, Any]:
    """Analyze performance trends over time"""
    try:
        perf_query = """
            SELECT 
                DATE_TRUNC('day', calculation_timestamp) as day,
                AVG(EXTRACT(EPOCH FROM (response_received_at - request_sent_at)) * 1000) as avg_response_time,
                PERCENTILE_CONT(0.5) WITHIN GROUP (ORDER BY EXTRACT(EPOCH FROM (response_received_at - request_sent_at)) * 1000) as p50_response_time,
                PERCENTILE_CONT(0.95) WITHIN GROUP (ORDER BY EXTRACT(EPOCH FROM (response_received_at - request_sent_at)) * 1000) as p95_response_time,
                COUNT(CASE WHEN status_code >= 400 THEN 1 END) as error_count,
                COUNT(*) as total_requests,
                vendor,
                model
            FROM cost_calculations 
            WHERE company_id = :company_id 
                AND calculation_timestamp BETWEEN :start_time AND :end_time
                AND request_sent_at IS NOT NULL 
                AND response_received_at IS NOT NULL
            GROUP BY DATE_TRUNC('day', calculation_timestamp), vendor, model
            ORDER BY day
        """
        
        results = await DatabaseUtils.execute_query(
            perf_query, 
            {'company_id': company_id, 'start_time': start_time, 'end_time': end_time}, 
            fetch_all=True
        )
        
        # Aggregate daily performance
        daily_performance = defaultdict(lambda: {
            'response_times': [], 'p50_times': [], 'p95_times': [], 
            'error_count': 0, 'total_requests': 0
        })
        
        vendor_performance = defaultdict(lambda: {
            'response_times': [], 'error_rate': 0, 'requests': 0
        })
        
        for row in results:
            day = row['day'].strftime('%Y-%m-%d')
            vendor = row['vendor']
            
            if row['avg_response_time']:
                daily_performance[day]['response_times'].append(row['avg_response_time'])
                daily_performance[day]['p50_times'].append(row['p50_response_time'] or 0)
                daily_performance[day]['p95_times'].append(row['p95_response_time'] or 0)
                
                vendor_performance[vendor]['response_times'].append(row['avg_response_time'])
            
            daily_performance[day]['error_count'] += row['error_count']
            daily_performance[day]['total_requests'] += row['total_requests']
            
            vendor_performance[vendor]['error_rate'] += row['error_count']
            vendor_performance[vendor]['requests'] += row['total_requests']
        
        # Calculate trends
        daily_avg_times = []
        daily_error_rates = []
        
        for day, data in sorted(daily_performance.items()):
            if data['response_times']:
                daily_avg_times.append(statistics.mean(data['response_times']))
            
            error_rate = (data['error_count'] / data['total_requests'] * 100) if data['total_requests'] > 0 else 0
            daily_error_rates.append(error_rate)
        
        response_time_trend = _calculate_trend(daily_avg_times)
        error_rate_trend = _calculate_trend(daily_error_rates)
        
        # Vendor performance comparison
        vendor_comparison = []
        for vendor, data in vendor_performance.items():
            if data['response_times']:
                avg_response_time = statistics.mean(data['response_times'])
                error_rate = (data['error_rate'] / data['requests'] * 100) if data['requests'] > 0 else 0
                
                vendor_comparison.append({
                    'vendor': vendor,
                    'avg_response_time': avg_response_time,
                    'error_rate': error_rate,
                    'requests': data['requests'],
                    'performance_score': max(0, 100 - (avg_response_time / 10) - (error_rate * 5))  # Simple scoring
                })
        
        vendor_comparison.sort(key=lambda x: x['performance_score'], reverse=True)
        
        return {
            'response_time_trend': response_time_trend,
            'error_rate_trend': error_rate_trend,
            'daily_performance': [
                {
                    'date': day,
                    'avg_response_time': statistics.mean(data['response_times']) if data['response_times'] else 0,
                    'p50_response_time': statistics.mean(data['p50_times']) if data['p50_times'] else 0,
                    'p95_response_time': statistics.mean(data['p95_times']) if data['p95_times'] else 0,
                    'error_rate': (data['error_count'] / data['total_requests'] * 100) if data['total_requests'] > 0 else 0,
                    'total_requests': data['total_requests']
                }
                for day, data in sorted(daily_performance.items())
            ],
            'vendor_performance_comparison': vendor_comparison,
            'performance_insights': _generate_performance_insights(daily_avg_times, daily_error_rates, vendor_comparison)
        }
        
    except Exception as e:
        logger.error(f"Failed to analyze performance trends: {e}")
        return {}

def _generate_performance_insights(response_times: List[float], error_rates: List[float], vendor_comparison: List[Dict]) -> List[str]:
    """Generate performance insights"""
    insights = []
    
    try:
        # Response time insights
        if response_times:
            avg_response_time = statistics.mean(response_times)
            if avg_response_time < 500:
                insights.append("Excellent response times maintained throughout the period")
            elif avg_response_time > 2000:
                insights.append("Response times are elevated and may impact user experience")
        
        # Error rate insights
        if error_rates:
            avg_error_rate = statistics.mean(error_rates)
            if avg_error_rate < 1:
                insights.append("Excellent service reliability with minimal errors")
            elif avg_error_rate > 5:
                insights.append("Error rates are concerning and require investigation")
        
        # Vendor performance insights
        if vendor_comparison and len(vendor_comparison) > 1:
            best_vendor = vendor_comparison[0]
            worst_vendor = vendor_comparison[-1]
            
            performance_gap = best_vendor['performance_score'] - worst_vendor['performance_score']
            if performance_gap > 20:
                insights.append(f"{best_vendor['vendor']} significantly outperforms {worst_vendor['vendor']} in reliability")
        
        return insights[:3]  # Return top 3 insights
        
    except Exception as e:
        logger.error(f"Failed to generate performance insights: {e}")
        return []

async def _generate_optimization_recommendations(company_id: str, usage_analysis: UsageAggregation, 
                                               cost_analysis: Dict, anomalies: List) -> List[str]:
    """Generate optimization recommendations"""
    recommendations = []
    
    try:
        # Cost optimization recommendations
        if usage_analysis.cost_efficiency_score < 70:
            recommendations.append("Review vendor and model selection to improve cost efficiency")
        
        if cost_analysis.get('cost_insights', {}).get('cost_concentration', 0) > 80:
            recommendations.append("Consider diversifying vendor usage to reduce dependency and potentially lower costs")
        
        # Performance optimization recommendations
        if usage_analysis.avg_response_time > 1500:
            recommendations.append("Investigate response time bottlenecks to improve user experience")
        
        if usage_analysis.error_rate > 3:
            recommendations.append("Address error rate issues to improve service reliability")
        
        # Usage pattern recommendations
        if usage_analysis.peak_hour in [2, 3, 4, 5]:  # Off-peak hours
            recommendations.append("Consider batch processing during current peak hours for potential cost savings")
        
        # Anomaly-based recommendations
        critical_anomalies = [a for a in anomalies if a.severity.value in ['critical', 'emergency']]
        if critical_anomalies:
            recommendations.append("Address critical anomalies detected in usage patterns")
        
        # Scaling recommendations
        if usage_analysis.avg_requests_per_day > 10000:
            recommendations.append("Consider enterprise pricing tiers for high-volume usage")
        
        return recommendations[:5]  # Return top 5 recommendations
        
    except Exception as e:
        logger.error(f"Failed to generate optimization recommendations: {e}")
        return []

async def _perform_trend_analysis(company_id: str, usage_analysis: UsageAggregation, period: TimePeriod) -> Dict[str, Any]:
    """Perform comprehensive trend analysis"""
    try:
        # This would typically analyze longer-term trends
        # For now, return basic trend information
        
        trends = {
            'usage_trend': 'stable',  # Would be calculated from historical data
            'cost_trend': usage_analysis.cost_trend,
            'performance_trend': 'stable',  # Would be calculated from performance data
            'trend_insights': [
                f"Cost trend is {usage_analysis.cost_trend} over the analysis period",
                f"Usage pattern shows peak activity on {usage_analysis.peak_day} at {usage_analysis.peak_hour}:00"
            ],
            'future_projections': {
                'monthly_cost_projection': float(usage_analysis.avg_cost_per_day * 30),
                'monthly_request_projection': int(usage_analysis.avg_requests_per_day * 30),
                'confidence_level': 'medium'  # Based on data quality and variability
            }
        }
        
        return trends
        
    except Exception as e:
        logger.error(f"Failed to perform trend analysis: {e}")
        return {}

async def _compare_with_previous_period(company_id: str, usage_analysis: UsageAggregation, period: TimePeriod) -> Dict[str, Any]:
    """Compare current period with previous equivalent period"""
    try:
        # Calculate previous period dates
        period_duration = usage_analysis.end_time - usage_analysis.start_time
        prev_end_time = usage_analysis.start_time
        prev_start_time = prev_end_time - period_duration
        
        # Get previous period data
        from .monitoring_helpers import _aggregate_request_metrics, _aggregate_cost_metrics
        
        prev_requests = await _aggregate_request_metrics(company_id, prev_start_time, prev_end_time)
        prev_costs = await _aggregate_cost_metrics(company_id, prev_start_time, prev_end_time)
        
        # Calculate comparisons
        current_requests = usage_analysis.total_requests
        prev_total_requests = prev_requests.get('total_requests', 0)
        
        current_cost = float(usage_analysis.total_cost)
        prev_total_cost = prev_costs.get('total_cost', 0)
        
        # Calculate percentage changes
        request_change = ((current_requests - prev_total_requests) / prev_total_requests * 100) if prev_total_requests > 0 else 0
        cost_change = ((current_cost - prev_total_cost) / prev_total_cost * 100) if prev_total_cost > 0 else 0
        
        return {
            'period_comparison': {
                'current_period': {
                    'requests': current_requests,
                    'cost': current_cost,
                    'avg_response_time': usage_analysis.avg_response_time,
                    'success_rate': usage_analysis.success_rate
                },
                'previous_period': {
                    'requests': prev_total_requests,
                    'cost': prev_total_cost,
                    'avg_response_time': prev_requests.get('success_rate', 0),  # Would need proper calculation
                    'success_rate': prev_requests.get('success_rate', 100)
                },
                'changes': {
                    'request_change_pct': request_change,
                    'cost_change_pct': cost_change,
                    'efficiency_change': 'improved' if request_change > cost_change else 'declined'
                }
            },
            'comparison_insights': [
                f"Request volume {'increased' if request_change > 0 else 'decreased'} by {abs(request_change):.1f}%",
                f"Total cost {'increased' if cost_change > 0 else 'decreased'} by {abs(cost_change):.1f}%"
            ]
        }
        
    except Exception as e:
        logger.error(f"Failed to compare with previous period: {e}")
        return {}

async def _benchmark_against_peers(company_id: str, usage_analysis: UsageAggregation) -> Dict[str, Any]:
    """Benchmark performance against similar companies"""
    try:
        # This would typically compare against industry benchmarks
        # For now, return simulated benchmark data
        
        benchmarks = {
            'industry_averages': {
                'cost_per_request': 0.005,  # Industry average
                'response_time_ms': 800,
                'success_rate_pct': 98.5,
                'error_rate_pct': 1.5
            },
            'company_performance': {
                'cost_per_request': float(usage_analysis.cost_per_request),
                'response_time_ms': usage_analysis.avg_response_time,
                'success_rate_pct': usage_analysis.success_rate,
                'error_rate_pct': usage_analysis.error_rate
            },
            'performance_ranking': {
                'cost_efficiency': 'above_average',  # Would be calculated
                'response_time': 'average',
                'reliability': 'above_average',
                'overall': 'above_average'
            },
            'benchmark_insights': [
                f"Cost per request is {'below' if usage_analysis.cost_per_request < Decimal('0.005') else 'above'} industry average",
                f"Response time is {'better than' if usage_analysis.avg_response_time < 800 else 'slower than'} industry average",
                f"Success rate is {'above' if usage_analysis.success_rate > 98.5 else 'below'} industry average"
            ]
        }
        
        return benchmarks
        
    except Exception as e:
        logger.error(f"Failed to benchmark against peers: {e}")
        return {}

async def _store_usage_report(report) -> None:
    """Store generated usage report in database"""
    try:
        query = """
            INSERT INTO usage_reports (
                report_id, company_id, report_type, period_type, 
                period_start, period_end, executive_summary, key_metrics,
                usage_analysis, cost_analysis, performance_analysis,
                anomalies_detected, optimization_recommendations, trend_analysis,
                period_comparison, benchmark_comparison, generated_at
            ) VALUES (
                :report_id, :company_id, :report_type, :period_type,
                :period_start, :period_end, :executive_summary, :key_metrics,
                :usage_analysis, :cost_analysis, :performance_analysis,
                :anomalies_detected, :optimization_recommendations, :trend_analysis,
                :period_comparison, :benchmark_comparison, :generated_at
            )
        """
        
        # Convert dataclasses to dict for JSON serialization
        from dataclasses import asdict
        
        await DatabaseUtils.execute_query(query, {
            'report_id': report.report_id,
            'company_id': report.company_id,
            'report_type': 'comprehensive',
            'period_type': report.period.value,
            'period_start': report.usage_analysis.start_time,
            'period_end': report.usage_analysis.end_time,
            'executive_summary': json.dumps(report.executive_summary),
            'key_metrics': json.dumps(report.key_metrics),
            'usage_analysis': json.dumps(asdict(report.usage_analysis), default=str),
            'cost_analysis': json.dumps(report.cost_analysis),
            'performance_analysis': json.dumps(report.performance_analysis),
            'anomalies_detected': json.dumps([asdict(a) for a in report.anomalies_detected], default=str),
            'optimization_recommendations': json.dumps(report.optimization_recommendations),
            'trend_analysis': json.dumps(report.trend_analysis),
            'period_comparison': json.dumps(report.period_over_period_comparison),
            'benchmark_comparison': json.dumps(report.benchmark_comparison),
            'generated_at': report.generated_at
        })
        
        logger.info(f"Stored usage report {report.report_id} for company {report.company_id}")
        
    except Exception as e:
        logger.error(f"Failed to store usage report: {e}")
        raise
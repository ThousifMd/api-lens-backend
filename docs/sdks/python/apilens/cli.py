"""
API Lens Python SDK - Command Line Interface

A simple CLI for common API Lens operations.
"""

import sys
import argparse
import json
import os
from typing import Optional
from datetime import datetime, timedelta

from .client import Client
from .exceptions import APILensError


def get_client(api_key: Optional[str] = None, base_url: Optional[str] = None) -> Client:
    """Get configured API Lens client"""
    api_key = api_key or os.getenv("API_LENS_API_KEY")
    if not api_key:
        print("Error: API key required. Set API_LENS_API_KEY environment variable or use --api-key")
        sys.exit(1)
    
    return Client(api_key=api_key, base_url=base_url)


def cmd_auth(args):
    """Verify authentication"""
    try:
        client = get_client(args.api_key, args.base_url)
        
        # Try to get company info to verify auth
        company = client.get_company()
        print(f"✅ Authentication successful!")
        print(f"Company: {company.name}")
        print(f"Tier: {company.tier}")
        print(f"Active: {company.is_active}")
        
    except APILensError as e:
        print(f"❌ Authentication failed: {e}")
        sys.exit(1)


def cmd_company(args):
    """Show company information"""
    try:
        client = get_client(args.api_key, args.base_url)
        company = client.get_company()
        
        if args.json:
            print(json.dumps(company.dict(), indent=2, default=str))
        else:
            print(f"Company Information:")
            print(f"  Name: {company.name}")
            print(f"  ID: {company.id}")
            print(f"  Tier: {company.tier}")
            print(f"  Active: {company.is_active}")
            print(f"  Contact: {company.contact_email or 'Not set'}")
            print(f"  Current Month Requests: {company.current_month_requests:,}")
            print(f"  Current Month Cost: ${company.current_month_cost:.2f}")
            if company.monthly_request_limit:
                print(f"  Monthly Request Limit: {company.monthly_request_limit:,}")
            if company.monthly_budget_limit:
                print(f"  Monthly Budget Limit: ${company.monthly_budget_limit:.2f}")
            
    except APILensError as e:
        print(f"❌ Error: {e}")
        sys.exit(1)


def cmd_usage(args):
    """Show usage analytics"""
    try:
        client = get_client(args.api_key, args.base_url)
        
        # Get usage for specified period
        usage = client.analytics.get_usage(
            period=args.period,
            group_by=args.group_by
        )
        
        if args.json:
            print(json.dumps(usage.dict(), indent=2, default=str))
        else:
            print(f"Usage Analytics ({args.period}):")
            print(f"  Total Requests: {usage.total_requests:,}")
            print(f"  Total Tokens: {usage.total_tokens:,}")
            print(f"  Total Cost: ${usage.total_cost:.2f}")
            print(f"  Avg Requests/Day: {usage.average_requests_per_day:.1f}")
            print(f"  Avg Cost/Request: ${usage.average_cost_per_request:.4f}")
            print(f"  Peak Requests/Hour: {usage.peak_requests_per_hour:,}")
            
            if usage.vendor_breakdown:
                print(f"\\nVendor Breakdown:")
                for vendor in usage.vendor_breakdown:
                    print(f"  {vendor.vendor.upper()}:")
                    print(f"    Requests: {vendor.requests:,}")
                    print(f"    Tokens: {vendor.tokens:,}")
                    print(f"    Cost: ${vendor.cost:.2f}")
            
    except APILensError as e:
        print(f"❌ Error: {e}")
        sys.exit(1)


def cmd_costs(args):
    """Show cost analytics"""
    try:
        client = get_client(args.api_key, args.base_url)
        
        costs = client.analytics.get_costs(period=args.period)
        
        if args.json:
            print(json.dumps(costs.dict(), indent=2, default=str))
        else:
            print(f"Cost Analytics ({args.period}):")
            print(f"  Total Cost: ${costs.total_cost:.2f}")
            print(f"  Avg Cost/Request: ${costs.average_cost_per_request:.4f}")
            print(f"  Cost Trend: {costs.cost_trend_percentage:+.1f}%")
            print(f"  Projected Monthly: ${costs.projected_monthly_cost:.2f}")
            print(f"  Efficiency Score: {costs.cost_efficiency_score:.1f}/100")
            
            if costs.vendor_costs:
                print(f"\\nVendor Costs:")
                for vendor in costs.vendor_costs:
                    print(f"  {vendor.vendor.upper()}: ${vendor.total_cost:.2f} ({vendor.cost_percentage:.1f}%)")
            
    except APILensError as e:
        print(f"❌ Error: {e}")
        sys.exit(1)


def cmd_keys(args):
    """Manage API keys"""
    try:
        client = get_client(args.api_key, args.base_url)
        
        if args.action == "list":
            keys = client.api_keys.list()
            
            if args.json:
                print(json.dumps([key.dict() for key in keys], indent=2, default=str))
            else:
                print(f"API Keys ({len(keys)} total):")
                for key in keys:
                    status = "✅ Active" if key.is_active else "❌ Inactive"
                    last_used = key.last_used_at.strftime("%Y-%m-%d %H:%M") if key.last_used_at else "Never"
                    print(f"  {key.name} ({key.key_preview}) - {status}")
                    print(f"    Created: {key.created_at.strftime('%Y-%m-%d %H:%M')}")
                    print(f"    Last Used: {last_used}")
                    print(f"    Usage Count: {key.usage_count:,}")
        
        elif args.action == "create":
            if not args.name:
                print("❌ Error: --name is required for creating API keys")
                sys.exit(1)
            
            key = client.api_keys.create(args.name)
            print(f"✅ API key created successfully!")
            print(f"Name: {key.name}")
            print(f"Key: {key.secret_key}")
            print("⚠️  Save this key securely - it won't be shown again!")
        
        elif args.action == "revoke":
            if not args.key_id:
                print("❌ Error: --key-id is required for revoking API keys")
                sys.exit(1)
            
            client.api_keys.revoke(args.key_id)
            print(f"✅ API key {args.key_id} revoked successfully")
            
    except APILensError as e:
        print(f"❌ Error: {e}")
        sys.exit(1)


def cmd_recommendations(args):
    """Show cost optimization recommendations"""
    try:
        client = get_client(args.api_key, args.base_url)
        
        recommendations = client.analytics.get_recommendations(min_savings=args.min_savings)
        
        if args.json:
            print(json.dumps([rec.dict() for rec in recommendations], indent=2, default=str))
        else:
            if not recommendations:
                print(f"No recommendations found with minimum savings of ${args.min_savings}")
                return
                
            total_savings = sum(rec.potential_savings for rec in recommendations)
            print(f"Cost Optimization Recommendations:")
            print(f"Total Potential Savings: ${total_savings:.2f}")
            print(f"")
            
            for i, rec in enumerate(recommendations, 1):
                print(f"{i}. {rec.title}")
                print(f"   Category: {rec.category}")
                print(f"   Impact: {rec.impact_level}")
                print(f"   Savings: ${rec.potential_savings:.2f} ({rec.savings_percentage:.1f}%)")
                print(f"   Confidence: {rec.confidence_score:.1f}")
                print(f"   Effort: {rec.implementation_effort}")
                print(f"   Description: {rec.description}")
                
                if rec.actionable_steps:
                    print(f"   Steps:")
                    for step in rec.actionable_steps:
                        print(f"     • {step}")
                print()
                
    except APILensError as e:
        print(f"❌ Error: {e}")
        sys.exit(1)


def main():
    """Main CLI entry point"""
    parser = argparse.ArgumentParser(
        description="API Lens CLI - Manage your AI API usage and costs",
        formatter_class=argparse.RawDescriptionHelpFormatter
    )
    
    # Global options
    parser.add_argument("--api-key", help="API Lens API key (or set API_LENS_API_KEY env var)")
    parser.add_argument("--base-url", default="https://api.apilens.dev", help="API base URL")
    parser.add_argument("--json", action="store_true", help="Output as JSON")
    
    subparsers = parser.add_subparsers(dest="command", help="Available commands")
    
    # Auth command
    auth_parser = subparsers.add_parser("auth", help="Verify authentication")
    auth_parser.set_defaults(func=cmd_auth)
    
    # Company command
    company_parser = subparsers.add_parser("company", help="Show company information")
    company_parser.set_defaults(func=cmd_company)
    
    # Usage command
    usage_parser = subparsers.add_parser("usage", help="Show usage analytics")
    usage_parser.add_argument("--period", default="7d", help="Time period (1d, 7d, 30d, 90d)")
    usage_parser.add_argument("--group-by", default="day", help="Group by (hour, day, week)")
    usage_parser.set_defaults(func=cmd_usage)
    
    # Costs command
    costs_parser = subparsers.add_parser("costs", help="Show cost analytics")
    costs_parser.add_argument("--period", default="7d", help="Time period (1d, 7d, 30d, 90d)")
    costs_parser.set_defaults(func=cmd_costs)
    
    # Keys command
    keys_parser = subparsers.add_parser("keys", help="Manage API keys")
    keys_parser.add_argument("action", choices=["list", "create", "revoke"], help="Action to perform")
    keys_parser.add_argument("--name", help="Name for new API key")
    keys_parser.add_argument("--key-id", help="Key ID to revoke")
    keys_parser.set_defaults(func=cmd_keys)
    
    # Recommendations command
    rec_parser = subparsers.add_parser("recommendations", help="Show cost optimization recommendations")
    rec_parser.add_argument("--min-savings", type=float, default=10.0, help="Minimum savings amount")
    rec_parser.set_defaults(func=cmd_recommendations)
    
    # Parse arguments
    args = parser.parse_args()
    
    if not args.command:
        parser.print_help()
        sys.exit(1)
    
    # Execute command
    args.func(args)


if __name__ == "__main__":
    main()
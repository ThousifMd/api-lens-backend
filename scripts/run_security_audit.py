#!/usr/bin/env python3
"""
Security Audit Runner - Complete security assessment for API Lens backend
Runs all security tests and generates comprehensive reports
"""

import asyncio
import json
import sys
import time
from datetime import datetime
from pathlib import Path
from typing import Dict, List

# Add the parent directory to the Python path
sys.path.insert(0, str(Path(__file__).parent.parent))

from tests.test_security_audit import run_complete_security_audit
from tests.test_penetration_testing import run_penetration_tests


class SecurityAuditRunner:
    """Orchestrates comprehensive security testing"""
    
    def __init__(self):
        self.results = {
            "audit_timestamp": datetime.now().isoformat(),
            "security_audit": None,
            "penetration_tests": None,
            "overall_assessment": None
        }
    
    async def run_complete_assessment(self):
        """Run complete security assessment"""
        print("🔒 API Lens Security Assessment Starting...")
        print("=" * 80)
        
        start_time = time.time()
        
        try:
            # Run security audit
            print("\n🛡️  PHASE 1: Running comprehensive security audit...")
            audit_results = await run_complete_security_audit()
            self.results["security_audit"] = {
                "summary": audit_results.get_summary(),
                "results": audit_results.results,
                "vulnerabilities": audit_results.vulnerabilities
            }
            
            print(f"✅ Security audit completed - {audit_results.get_summary()['security_score']:.1f}% score")
            
            # Run penetration tests
            print("\n🏴‍☠️  PHASE 2: Running penetration testing...")
            pentest_results = await run_penetration_tests()
            self.results["penetration_tests"] = {
                "summary": pentest_results.get_summary(),
                "successful_attacks": pentest_results.successful_attacks,
                "attack_attempts": pentest_results.attack_attempts
            }
            
            print(f"✅ Penetration testing completed - {pentest_results.get_summary()['attack_success_rate']:.1f}% attack success rate")
            
            # Generate overall assessment
            self.generate_overall_assessment()
            
            # Generate reports
            await self.generate_reports()
            
            elapsed_time = time.time() - start_time
            print(f"\n⏱️  Total assessment time: {elapsed_time:.2f} seconds")
            
            return self.results
            
        except Exception as e:
            print(f"❌ Error during security assessment: {e}")
            raise
    
    def generate_overall_assessment(self):
        """Generate overall security assessment"""
        audit_summary = self.results["security_audit"]["summary"]
        pentest_summary = self.results["penetration_tests"]["summary"]
        
        # Calculate overall security score
        security_score = audit_summary["security_score"]
        attack_resistance = 100 - pentest_summary["attack_success_rate"]
        overall_score = (security_score + attack_resistance) / 2
        
        # Determine risk level
        if overall_score >= 90:
            risk_level = "LOW"
            risk_color = "🟢"
        elif overall_score >= 75:
            risk_level = "MEDIUM"
            risk_color = "🟡"
        elif overall_score >= 60:
            risk_level = "HIGH"
            risk_color = "🟠"
        else:
            risk_level = "CRITICAL"
            risk_color = "🔴"
        
        # Generate recommendations
        recommendations = self.generate_recommendations()
        
        self.results["overall_assessment"] = {
            "overall_security_score": round(overall_score, 1),
            "risk_level": risk_level,
            "risk_color": risk_color,
            "critical_issues": audit_summary["vulnerabilities_found"] + pentest_summary["critical_breaches"],
            "high_priority_issues": len([v for v in self.results["security_audit"]["vulnerabilities"] if v["level"] == "high"]) + pentest_summary["high_severity_breaches"],
            "recommendations": recommendations,
            "compliance_status": self.assess_compliance()
        }
    
    def generate_recommendations(self) -> List[Dict]:
        """Generate security recommendations based on findings"""
        recommendations = []
        
        audit_results = self.results["security_audit"]["results"]
        vulnerabilities = self.results["security_audit"]["vulnerabilities"]
        successful_attacks = self.results["penetration_tests"]["successful_attacks"]
        
        # Check for specific vulnerabilities and generate recommendations
        
        # API Key Security
        if not audit_results.get("api_key_entropy", {}).get("passed", True):
            recommendations.append({
                "priority": "HIGH",
                "category": "Authentication",
                "issue": "API key generation has insufficient entropy",
                "recommendation": "Implement cryptographically secure random number generation with at least 256 bits of entropy",
                "implementation": "Use secrets.token_urlsafe() or os.urandom() for key generation"
            })
        
        # SQL Injection
        sql_injection_failed = any("sql_injection" in result for result, data in audit_results.items() if not data.get("passed", True))
        if sql_injection_failed or any("sql" in attack["attack"].lower() for attack in successful_attacks):
            recommendations.append({
                "priority": "CRITICAL",
                "category": "Input Validation",
                "issue": "SQL injection vulnerabilities detected",
                "recommendation": "Implement parameterized queries and input validation for all database operations",
                "implementation": "Use SQLAlchemy with bound parameters, validate all user inputs"
            })
        
        # Encryption Issues
        encryption_failed = any("encryption" in result for result, data in audit_results.items() if not data.get("passed", True))
        if encryption_failed or any("encryption" in attack["attack"].lower() for attack in successful_attacks):
            recommendations.append({
                "priority": "HIGH",
                "category": "Encryption",
                "issue": "Encryption implementation vulnerabilities",
                "recommendation": "Review encryption implementation, ensure proper key derivation and AES-256-GCM usage",
                "implementation": "Use industry-standard libraries like cryptography, implement proper key rotation"
            })
        
        # Brute Force Protection
        if any("brute_force" in attack["attack"].lower() for attack in successful_attacks):
            recommendations.append({
                "priority": "HIGH",
                "category": "Rate Limiting",
                "issue": "Insufficient brute force protection",
                "recommendation": "Implement rate limiting, account lockouts, and CAPTCHA for repeated failures",
                "implementation": "Use Redis for rate limiting, implement exponential backoff"
            })
        
        # Data Isolation
        isolation_failed = any("isolation" in result for result, data in audit_results.items() if not data.get("passed", True))
        if isolation_failed:
            recommendations.append({
                "priority": "CRITICAL",
                "category": "Data Security",
                "issue": "Data isolation between companies may be compromised",
                "recommendation": "Review schema-based isolation implementation, ensure proper access controls",
                "implementation": "Audit all database queries for proper schema prefixing, implement additional access controls"
            })
        
        # JWT Security
        jwt_failed = any("jwt" in result.lower() for result, data in audit_results.items() if not data.get("passed", True))
        if jwt_failed:
            recommendations.append({
                "priority": "MEDIUM",
                "category": "Authentication",
                "issue": "JWT implementation security issues",
                "recommendation": "Review JWT secret key strength and token validation logic",
                "implementation": "Use strong random JWT secrets, implement proper token expiration and refresh"
            })
        
        # General recommendations based on overall score
        overall_score = self.results["overall_assessment"]["overall_security_score"]
        if overall_score < 80:
            recommendations.append({
                "priority": "HIGH",
                "category": "General",
                "issue": f"Overall security score is {overall_score}% - below recommended 80%",
                "recommendation": "Implement a comprehensive security improvement plan",
                "implementation": "Address all high and critical issues, conduct regular security reviews"
            })
        
        return recommendations
    
    def assess_compliance(self) -> Dict:
        """Assess compliance with security standards"""
        overall_score = self.results["overall_assessment"]["overall_security_score"]
        critical_issues = self.results["overall_assessment"]["critical_issues"]
        
        compliance_status = {
            "SOC2": "FAIL" if critical_issues > 0 or overall_score < 85 else "PASS",
            "GDPR": "FAIL" if critical_issues > 0 or overall_score < 80 else "PASS",
            "HIPAA": "FAIL" if critical_issues > 0 or overall_score < 90 else "PASS",
            "PCI_DSS": "FAIL" if critical_issues > 0 or overall_score < 85 else "PASS"
        }
        
        return compliance_status
    
    async def generate_reports(self):
        """Generate security reports"""
        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        
        # Save comprehensive JSON report
        json_report_path = f"security_assessment_{timestamp}.json"
        with open(json_report_path, "w") as f:
            json.dump(self.results, f, indent=2)
        
        # Generate executive summary
        await self.generate_executive_summary(f"security_executive_summary_{timestamp}.md")
        
        # Generate technical report
        await self.generate_technical_report(f"security_technical_report_{timestamp}.md")
        
        print(f"\n📊 Reports generated:")
        print(f"  📄 JSON Report: {json_report_path}")
        print(f"  📋 Executive Summary: security_executive_summary_{timestamp}.md")
        print(f"  🔧 Technical Report: security_technical_report_{timestamp}.md")
    
    async def generate_executive_summary(self, filename: str):
        """Generate executive summary report"""
        assessment = self.results["overall_assessment"]
        
        content = f"""# API Lens Security Assessment - Executive Summary
        
**Assessment Date:** {self.results["audit_timestamp"]}
**Overall Security Score:** {assessment["overall_security_score"]}%
**Risk Level:** {assessment["risk_color"]} {assessment["risk_level"]}

## Executive Overview

This security assessment evaluated the API Lens backend system across multiple security domains including authentication, encryption, data isolation, and vulnerability resistance.

### Key Findings

- **Security Score:** {assessment["overall_security_score"]}% overall security rating
- **Critical Issues:** {assessment["critical_issues"]} critical security vulnerabilities identified
- **High Priority Issues:** {assessment["high_priority_issues"]} high-priority security concerns
- **Attack Resistance:** {100 - self.results["penetration_tests"]["summary"]["attack_success_rate"]:.1f}% of attacks were successfully blocked

### Risk Assessment

**Current Risk Level: {assessment["risk_level"]}**

### Compliance Status

"""
        
        for standard, status in assessment["compliance_status"].items():
            status_icon = "✅" if status == "PASS" else "❌"
            content += f"- **{standard}:** {status_icon} {status}\n"
        
        content += """
### Priority Recommendations

"""
        
        high_priority_recommendations = [r for r in assessment["recommendations"] if r["priority"] in ["CRITICAL", "HIGH"]]
        for i, rec in enumerate(high_priority_recommendations[:5], 1):
            content += f"{i}. **{rec['category']}:** {rec['issue']}\n   - {rec['recommendation']}\n\n"
        
        content += f"""
### Next Steps

1. **Immediate Action Required:** Address all {assessment["critical_issues"]} critical issues
2. **Security Improvements:** Implement high-priority recommendations
3. **Ongoing Monitoring:** Establish continuous security monitoring
4. **Regular Assessments:** Schedule quarterly security reviews

---
*This report was generated by the API Lens automated security assessment system.*
"""
        
        with open(filename, "w") as f:
            f.write(content)
    
    async def generate_technical_report(self, filename: str):
        """Generate detailed technical report"""
        audit_results = self.results["security_audit"]["results"]
        pentest_results = self.results["penetration_tests"]["attack_attempts"]
        
        content = f"""# API Lens Security Assessment - Technical Report

**Assessment Date:** {self.results["audit_timestamp"]}

## Security Audit Results

### Test Summary
- **Total Tests:** {self.results["security_audit"]["summary"]["total_tests"]}
- **Passed:** {self.results["security_audit"]["summary"]["passed"]}
- **Failed:** {self.results["security_audit"]["summary"]["failed"]}

### Detailed Results

"""
        
        for test_name, result in audit_results.items():
            status = "✅ PASS" if result["passed"] else "❌ FAIL"
            content += f"#### {test_name}\n**Status:** {status}\n**Details:** {result['details']}\n\n"
        
        content += """## Penetration Testing Results

### Attack Summary
"""
        
        pentest_summary = self.results["penetration_tests"]["summary"]
        content += f"""- **Total Attacks:** {pentest_summary["total_attacks"]}
- **Successful:** {pentest_summary["successful_attacks"]}
- **Blocked:** {pentest_summary["blocked_attacks"]}
- **Success Rate:** {pentest_summary["attack_success_rate"]:.1f}%

### Attack Details

"""
        
        for attack_name, details in pentest_results.items():
            status = "💥 SUCCESS" if details["success"] else "🛡️ BLOCKED"
            content += f"#### {attack_name}\n**Status:** {status}\n**Severity:** {details['severity'].upper()}\n**Details:** {details['details']}\n\n"
        
        content += """## Recommendations

### Implementation Guide

"""
        
        for rec in self.results["overall_assessment"]["recommendations"]:
            content += f"""#### {rec['category']}: {rec['issue']}
**Priority:** {rec['priority']}
**Recommendation:** {rec['recommendation']}
**Implementation:** {rec['implementation']}

"""
        
        with open(filename, "w") as f:
            f.write(content)


async def main():
    """Main function to run security assessment"""
    runner = SecurityAuditRunner()
    
    try:
        results = await runner.run_complete_assessment()
        
        # Print final summary
        print("\n" + "=" * 80)
        print("🔒 SECURITY ASSESSMENT COMPLETE")
        print("=" * 80)
        
        assessment = results["overall_assessment"]
        print(f"Overall Security Score: {assessment['overall_security_score']}%")
        print(f"Risk Level: {assessment['risk_color']} {assessment['risk_level']}")
        print(f"Critical Issues: {assessment['critical_issues']}")
        print(f"High Priority Issues: {assessment['high_priority_issues']}")
        
        if assessment["critical_issues"] > 0:
            print("\n🚨 CRITICAL SECURITY ISSUES FOUND - IMMEDIATE ACTION REQUIRED!")
            return 2
        elif assessment["overall_security_score"] < 75:
            print("\n⚠️  SECURITY SCORE BELOW ACCEPTABLE THRESHOLD - IMPROVEMENTS NEEDED!")
            return 1
        else:
            print("\n✅ SECURITY ASSESSMENT PASSED - SYSTEM SHOWS GOOD SECURITY POSTURE!")
            return 0
    
    except Exception as e:
        print(f"❌ Security assessment failed: {e}")
        return 3


if __name__ == "__main__":
    exit(asyncio.run(main()))
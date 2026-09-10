"""Security Governance - Priority 31.

This module implements security-focused governance for autonomous testing,
ensuring that security risks are properly assessed and managed.

Priority 31: Universal Autonomous Test Governance + Risk Intelligence
"""

from __future__ import annotations

import logging
from dataclasses import dataclass, field
from datetime import datetime
from enum import Enum
from typing import Any, Dict, List, Optional
from uuid import uuid4

logger = logging.getLogger(__name__)


class SecurityRiskLevel(Enum):
    """Security risk levels."""
    NONE = "none"
    LOW = "low"
    MEDIUM = "medium"
    HIGH = "high"
    CRITICAL = "critical"


class SecurityVulnerabilityType(Enum):
    """Types of security vulnerabilities."""
    XSS = "xss"
    CSRF = "csrf"
    SQL_INJECTION = "sql_injection"
    AUTHENTICATION = "authentication"
    AUTHORIZATION = "authorization"
    DATA_EXPOSURE = "data_exposure"
    INSECURE_COMMUNICATION = "insecure_communication"
    INPUT_VALIDATION = "input_validation"
    SESSION_MANAGEMENT = "session_management"
    CRYPTOGRAPHY = "cryptography"
    CONFIGURATION = "configuration"
    OTHER = "other"


class SecurityComplianceStatus(Enum):
    """Security compliance status."""
    COMPLIANT = "compliant"
    NON_COMPLIANT = "non_compliant"
    PARTIALLY_COMPLIANT = "partially_compliant"
    UNKNOWN = "unknown"


@dataclass
class SecurityVulnerability:
    """A security vulnerability found during testing."""
    vulnerability_id: str
    vulnerability_type: SecurityVulnerabilityType
    risk_level: SecurityRiskLevel
    description: str
    location: str
    evidence: Dict[str, Any]
    remediation: str
    timestamp: datetime = field(default_factory=datetime.now)
    
    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary."""
        return {
            "vulnerability_id": self.vulnerability_id,
            "vulnerability_type": self.vulnerability_type.value,
            "risk_level": self.risk_level.value,
            "description": self.description,
            "location": self.location,
            "evidence": self.evidence,
            "remediation": self.remediation,
            "timestamp": self.timestamp.isoformat(),
        }


@dataclass
class SecurityComplianceCheck:
    """A security compliance check."""
    check_id: str
    check_name: str
    description: str
    status: SecurityComplianceStatus
    requirements: List[str]
    evidence: Dict[str, Any]
    violations: List[str] = field(default_factory=list)
    timestamp: datetime = field(default_factory=datetime.now)
    
    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary."""
        return {
            "check_id": self.check_id,
            "check_name": self.check_name,
            "description": self.description,
            "status": self.status.value,
            "requirements": self.requirements,
            "evidence": self.evidence,
            "violations": self.violations,
            "timestamp": self.timestamp.isoformat(),
        }


@dataclass
class SecurityRiskAssessment:
    """A comprehensive security risk assessment."""
    assessment_id: str
    target_url: str
    overall_risk_level: SecurityRiskLevel
    vulnerabilities: List[SecurityVulnerability]
    compliance_checks: List[SecurityComplianceCheck]
    security_score: float  # 0.0 to 1.0
    recommendations: List[str]
    requires_human_review: bool
    timestamp: datetime = field(default_factory=datetime.now)
    
    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary."""
        return {
            "assessment_id": self.assessment_id,
            "target_url": self.target_url,
            "overall_risk_level": self.overall_risk_level.value,
            "vulnerabilities": [v.to_dict() for v in self.vulnerabilities],
            "compliance_checks": [c.to_dict() for c in self.compliance_checks],
            "security_score": self.security_score,
            "recommendations": self.recommendations,
            "requires_human_review": self.requires_human_review,
            "timestamp": self.timestamp.isoformat(),
        }


class SecurityGovernance:
    """Security governance for autonomous testing.
    
    This class:
    - Assesses security risks in applications
    - Identifies security vulnerabilities
    - Performs compliance checks
    - Generates security recommendations
    - Determines if human review is needed for security issues
    """
    
    def __init__(self):
        """Initialize security governance."""
        self.assessments: Dict[str, SecurityRiskAssessment] = {}
        self.vulnerabilities: Dict[str, SecurityVulnerability] = {}
        self.compliance_checks: Dict[str, SecurityComplianceCheck] = {}
        
        # Security standards and requirements
        self.security_standards = self._initialize_security_standards()
        
        logger.info("[SECURITY GOVERNANCE] Initialized")
    
    def _initialize_security_standards(self) -> Dict[str, List[str]]:
        """Initialize security standards and requirements.
        
        Returns:
            Dictionary of security standards and their requirements
        """
        return {
            "OWASP_TOP_10": [
                "Injection protection",
                "Broken authentication",
                "Sensitive data exposure",
                "XML external entities",
                "Broken access control",
                "Security misconfiguration",
                "Cross-site scripting",
                "Insecure deserialization",
                "Using components with known vulnerabilities",
                "Insufficient logging and monitoring",
            ],
            "HTTPS": [
                "All communications use HTTPS",
                "Valid SSL/TLS certificates",
                "Secure cipher suites",
                "HSTS headers",
            ],
            "AUTHENTICATION": [
                "Strong password policies",
                "Multi-factor authentication",
                "Secure session management",
                "Proper logout functionality",
            ],
            "AUTHORIZATION": [
                "Role-based access control",
                "Least privilege principle",
                "Proper authorization checks",
                "No privilege escalation",
            ],
        }
    
    def assess_security_risk(
        self,
        target_url: str,
        application_state: Dict[str, Any],
        test_results: List[Dict[str, Any]],
    ) -> SecurityRiskAssessment:
        """Assess comprehensive security risk.
        
        Args:
            target_url: Target URL
            application_state: Application state
            test_results: Test results
            
        Returns:
            Security risk assessment
        """
        logger.info(f"[SECURITY GOVERNANCE] Assessing security risk for: {target_url}")
        
        assessment_id = f"SEC-{uuid4().hex[:8]}"
        
        # Identify vulnerabilities
        vulnerabilities = self._identify_vulnerabilities(
            target_url,
            application_state,
            test_results,
        )
        
        # Perform compliance checks
        compliance_checks = self._perform_compliance_checks(
            target_url,
            application_state,
        )
        
        # Calculate overall risk level
        overall_risk_level = self._calculate_overall_risk(vulnerabilities, compliance_checks)
        
        # Calculate security score
        security_score = self._calculate_security_score(vulnerabilities, compliance_checks)
        
        # Generate recommendations
        recommendations = self._generate_recommendations(
            vulnerabilities,
            compliance_checks,
        )
        
        # Determine if human review is needed
        requires_human_review = self._requires_human_review(overall_risk_level, vulnerabilities)
        
        # Create assessment
        assessment = SecurityRiskAssessment(
            assessment_id=assessment_id,
            target_url=target_url,
            overall_risk_level=overall_risk_level,
            vulnerabilities=vulnerabilities,
            compliance_checks=compliance_checks,
            security_score=security_score,
            recommendations=recommendations,
            requires_human_review=requires_human_review,
        )
        
        self.assessments[assessment_id] = assessment
        
        # Store vulnerabilities and compliance checks
        for vuln in vulnerabilities:
            self.vulnerabilities[vuln.vulnerability_id] = vuln
        for check in compliance_checks:
            self.compliance_checks[check.check_id] = check
        
        logger.info(
            f"[SECURITY GOVERNANCE] Security assessment complete: "
            f"risk={overall_risk_level.value}, score={security_score:.2f}, "
            f"vulnerabilities={len(vulnerabilities)}"
        )
        
        return assessment
    
    def _identify_vulnerabilities(
        self,
        target_url: str,
        application_state: Dict[str, Any],
        test_results: List[Dict[str, Any]],
    ) -> List[SecurityVulnerability]:
        """Identify security vulnerabilities.
        
        Args:
            target_url: Target URL
            application_state: Application state
            test_results: Test results
            
        Returns:
            List of vulnerabilities
        """
        vulnerabilities = []
        
        # Check for common security issues
        # This is a simplified implementation - in production, this would use
        # comprehensive security scanning tools
        
        # Check for HTTP instead of HTTPS
        if target_url.startswith("http://"):
            vulnerabilities.append(SecurityVulnerability(
                vulnerability_id=f"VULN-{uuid4().hex[:8]}",
                vulnerability_type=SecurityVulnerabilityType.INSECURE_COMMUNICATION,
                risk_level=SecurityRiskLevel.HIGH,
                description="Application uses HTTP instead of HTTPS",
                location=target_url,
                evidence={"url": target_url},
                remediation="Configure the application to use HTTPS with valid SSL/TLS certificates",
            ))
        
        # Check for potential XSS vulnerabilities in test results
        for result in test_results:
            if "error" in result and "script" in str(result.get("error", "")).lower():
                vulnerabilities.append(SecurityVulnerability(
                    vulnerability_id=f"VULN-{uuid4().hex[:8]}",
                    vulnerability_type=SecurityVulnerabilityType.XSS,
                    risk_level=SecurityRiskLevel.HIGH,
                    description="Potential XSS vulnerability detected",
                    location=result.get("test_id", "unknown"),
                    evidence=result,
                    remediation="Implement proper input validation and output encoding",
                ))
        
        # Check for authentication issues
        if application_state.get("requires_auth", False):
            auth_implementation = application_state.get("auth_implementation", {})
            if not auth_implementation.get("multi_factor_enabled", False):
                vulnerabilities.append(SecurityVulnerability(
                    vulnerability_id=f"VULN-{uuid4().hex[:8]}",
                    vulnerability_type=SecurityVulnerabilityType.AUTHENTICATION,
                    risk_level=SecurityRiskLevel.MEDIUM,
                    description="Multi-factor authentication not enabled",
                    location="authentication system",
                    evidence=auth_implementation,
                    remediation="Implement multi-factor authentication for enhanced security",
                ))
        
        return vulnerabilities
    
    def _perform_compliance_checks(
        self,
        target_url: str,
        application_state: Dict[str, Any],
    ) -> List[SecurityComplianceCheck]:
        """Perform security compliance checks.
        
        Args:
            target_url: Target URL
            application_state: Application state
            
        Returns:
            List of compliance checks
        """
        compliance_checks = []
        
        # Check HTTPS compliance
        https_check = SecurityComplianceCheck(
            check_id=f"CHECK-{uuid4().hex[:8]}",
            check_name="HTTPS Compliance",
            description="Verify application uses HTTPS for all communications",
            status=SecurityComplianceStatus.COMPLIANT if target_url.startswith("https://") else SecurityComplianceStatus.NON_COMPLIANT,
            requirements=self.security_standards["HTTPS"],
            evidence={"url": target_url},
            violations=["Application uses HTTP instead of HTTPS"] if not target_url.startswith("https://") else [],
        )
        compliance_checks.append(https_check)
        
        # Check authentication compliance
        auth_check = SecurityComplianceCheck(
            check_id=f"CHECK-{uuid4().hex[:8]}",
            check_name="Authentication Compliance",
            description="Verify authentication meets security standards",
            status=SecurityComplianceStatus.PARTIALLY_COMPLIANT,
            requirements=self.security_standards["AUTHENTICATION"],
            evidence=application_state.get("auth_implementation", {}),
            violations=["Multi-factor authentication not enabled"] if not application_state.get("auth_implementation", {}).get("multi_factor_enabled", False) else [],
        )
        compliance_checks.append(auth_check)
        
        # Check authorization compliance
        authz_check = SecurityComplianceCheck(
            check_id=f"CHECK-{uuid4().hex[:8]}",
            check_name="Authorization Compliance",
            description="Verify authorization meets security standards",
            status=SecurityComplianceStatus.UNKNOWN,
            requirements=self.security_standards["AUTHORIZATION"],
            evidence=application_state.get("authorization_implementation", {}),
        )
        compliance_checks.append(authz_check)
        
        return compliance_checks
    
    def _calculate_overall_risk(
        self,
        vulnerabilities: List[SecurityVulnerability],
        compliance_checks: List[SecurityComplianceCheck],
    ) -> SecurityRiskLevel:
        """Calculate overall security risk level.
        
        Args:
            vulnerabilities: List of vulnerabilities
            compliance_checks: List of compliance checks
            
        Returns:
            Overall risk level
        """
        # Count critical and high risk vulnerabilities
        critical_count = sum(1 for v in vulnerabilities if v.risk_level == SecurityRiskLevel.CRITICAL)
        high_count = sum(1 for v in vulnerabilities if v.risk_level == SecurityRiskLevel.HIGH)
        
        # Count non-compliant checks
        non_compliant_count = sum(1 for c in compliance_checks if c.status == SecurityComplianceStatus.NON_COMPLIANT)
        
        # Determine overall risk
        if critical_count > 0:
            return SecurityRiskLevel.CRITICAL
        elif high_count > 0 or non_compliant_count > 0:
            return SecurityRiskLevel.HIGH
        elif len(vulnerabilities) > 0:
            return SecurityRiskLevel.MEDIUM
        else:
            return SecurityRiskLevel.LOW
    
    def _calculate_security_score(
        self,
        vulnerabilities: List[SecurityVulnerability],
        compliance_checks: List[SecurityComplianceCheck],
    ) -> float:
        """Calculate security score (0.0 to 1.0).
        
        Args:
            vulnerabilities: List of vulnerabilities
            compliance_checks: List of compliance checks
            
        Returns:
            Security score
        """
        # Start with perfect score
        score = 1.0
        
        # Deduct for vulnerabilities
        for vuln in vulnerabilities:
            if vuln.risk_level == SecurityRiskLevel.CRITICAL:
                score -= 0.4
            elif vuln.risk_level == SecurityRiskLevel.HIGH:
                score -= 0.2
            elif vuln.risk_level == SecurityRiskLevel.MEDIUM:
                score -= 0.1
            elif vuln.risk_level == SecurityRiskLevel.LOW:
                score -= 0.05
        
        # Deduct for non-compliant checks
        for check in compliance_checks:
            if check.status == SecurityComplianceStatus.NON_COMPLIANT:
                score -= 0.15
            elif check.status == SecurityComplianceStatus.PARTIALLY_COMPLIANT:
                score -= 0.05
        
        # Ensure score is between 0 and 1
        return max(0.0, min(1.0, score))
    
    def _generate_recommendations(
        self,
        vulnerabilities: List[SecurityVulnerability],
        compliance_checks: List[SecurityComplianceCheck],
    ) -> List[str]:
        """Generate security recommendations.
        
        Args:
            vulnerabilities: List of vulnerabilities
            compliance_checks: List of compliance checks
            
        Returns:
            List of recommendations
        """
        recommendations = []
        
        # Add remediation for each vulnerability
        for vuln in vulnerabilities:
            recommendations.append(vuln.remediation)
        
        # Add recommendations for non-compliant checks
        for check in compliance_checks:
            if check.status == SecurityComplianceStatus.NON_COMPLIANT:
                recommendations.append(f"Address compliance issues in {check.check_name}")
            elif check.status == SecurityComplianceStatus.PARTIALLY_COMPLIANT:
                recommendations.append(f"Improve compliance in {check.check_name}")
        
        return recommendations
    
    def _requires_human_review(
        self,
        overall_risk_level: SecurityRiskLevel,
        vulnerabilities: List[SecurityVulnerability],
    ) -> bool:
        """Determine if human review is required.
        
        Args:
            overall_risk_level: Overall risk level
            vulnerabilities: List of vulnerabilities
            
        Returns:
            True if human review is required
        """
        # Critical or high risk requires human review
        if overall_risk_level in [SecurityRiskLevel.CRITICAL, SecurityRiskLevel.HIGH]:
            return True
        
        # More than 3 vulnerabilities requires human review
        if len(vulnerabilities) > 3:
            return True
        
        return False
    
    def get_status(self) -> Dict[str, Any]:
        """Get security governance status.
        
        Returns:
            Status dictionary
        """
        return {
            "assessments": len(self.assessments),
            "vulnerabilities": len(self.vulnerabilities),
            "compliance_checks": len(self.compliance_checks),
            "critical_vulnerabilities": sum(1 for v in self.vulnerabilities.values() if v.risk_level == SecurityRiskLevel.CRITICAL),
            "high_vulnerabilities": sum(1 for v in self.vulnerabilities.values() if v.risk_level == SecurityRiskLevel.HIGH),
        }

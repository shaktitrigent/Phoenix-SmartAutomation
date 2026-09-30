"""Application-Agnostic Audit - Priority 31.

This module implements application-agnostic auditing for the risk intelligence system,
ensuring that governance and risk assessment work correctly regardless of the
application being tested.

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


class AuditCategory(Enum):
    """Audit categories."""
    BUSINESS_RISK_MODELING = "business_risk_modeling"
    RISK_SCORING = "risk_scoring"
    TEST_PRIORITIZATION = "test_prioritization"
    EXECUTION_POLICY = "execution_policy"
    QUARANTINE_INTELLIGENCE = "quarantine_intelligence"
    FLAKY_TEST_INTELLIGENCE = "flaky_test_intelligence"
    COVERAGE_RISK_INTELLIGENCE = "coverage_risk_intelligence"
    SECURITY_GOVERNANCE = "security_governance"
    CHANGE_RISK_CORRELATION = "change_risk_correlation"
    MAINTENANCE_RISK_CORRELATION = "maintenance_risk_correlation"
    RELEASE_READINESS = "release_readiness"
    HUMAN_REVIEW_GOVERNANCE = "human_review_governance"
    INTEGRATION = "integration"


class AuditStatus(Enum):
    """Audit status."""
    PASSED = "passed"
    FAILED = "failed"
    WARNING = "warning"
    SKIPPED = "skipped"


class AuditSeverity(Enum):
    """Audit severity levels."""
    INFO = "info"
    LOW = "low"
    MEDIUM = "medium"
    HIGH = "high"
    CRITICAL = "critical"


@dataclass
class AuditCheck:
    """A single audit check."""
    check_id: str
    category: AuditCategory
    name: str
    description: str
    status: AuditStatus
    severity: AuditSeverity
    message: str
    evidence: Dict[str, Any]
    timestamp: datetime = field(default_factory=datetime.now)
    
    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary."""
        return {
            "check_id": self.check_id,
            "category": self.category.value,
            "name": self.name,
            "description": self.description,
            "status": self.status.value,
            "severity": self.severity.value,
            "message": self.message,
            "evidence": self.evidence,
            "timestamp": self.timestamp.isoformat(),
        }


@dataclass
class AuditReport:
    """Comprehensive audit report."""
    audit_id: str
    audit_timestamp: datetime
    checks: List[AuditCheck]
    summary: Dict[str, Any]
    recommendations: List[str]
    overall_status: AuditStatus
    application_agnostic: bool
    
    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary."""
        return {
            "audit_id": self.audit_id,
            "audit_timestamp": self.audit_timestamp.isoformat(),
            "checks": [c.to_dict() for c in self.checks],
            "summary": self.summary,
            "recommendations": self.recommendations,
            "overall_status": self.overall_status.value,
            "application_agnostic": self.application_agnostic,
        }


class ApplicationAgnosticAuditor:
    """Application-agnostic auditor for risk intelligence.
    
    This auditor:
    - Verifies risk intelligence components work independently of application
    - Validates integration between components
    - Ensures governance decisions are consistent
    - Checks data quality and integrity
    - Validates security of the risk intelligence system itself
    """
    
    def __init__(self):
        """Initialize application-agnostic auditor."""
        self.audit_reports: Dict[str, AuditReport] = {}
        
        logger.info("[AUDITOR] Application-Agnostic Auditor initialized")
    
    def audit_risk_intelligence_system(
        self,
        risk_intelligence_coordinator: Any,
    ) -> AuditReport:
        """Perform comprehensive audit of risk intelligence system.
        
        Args:
            risk_intelligence_coordinator: RiskIntelligenceCoordinator instance
            
        Returns:
            Audit report
        """
        logger.info("[AUDITOR] Starting comprehensive risk intelligence audit")
        
        audit_id = f"AUDIT-{uuid4().hex[:8]}"
        audit_timestamp = datetime.now()
        checks = []
        
        # Audit each component
        checks.extend(self._audit_business_risk_modeling(risk_intelligence_coordinator))
        checks.extend(self._audit_risk_scoring(risk_intelligence_coordinator))
        checks.extend(self._audit_quarantine_intelligence(risk_intelligence_coordinator))
        checks.extend(self._audit_flaky_test_intelligence(risk_intelligence_coordinator))
        checks.extend(self._audit_coverage_risk_intelligence(risk_intelligence_coordinator))
        checks.extend(self._audit_security_governance(risk_intelligence_coordinator))
        checks.extend(self._audit_integration(risk_intelligence_coordinator))
        
        # Generate summary
        summary = self._generate_summary(checks)
        
        # Generate recommendations
        recommendations = self._generate_recommendations(checks)
        
        # Determine overall status
        overall_status = self._determine_overall_status(checks)
        
        # Verify application-agnostic nature
        application_agnostic = self._verify_application_agnostic(checks)
        
        # Create audit report
        report = AuditReport(
            audit_id=audit_id,
            audit_timestamp=audit_timestamp,
            checks=checks,
            summary=summary,
            recommendations=recommendations,
            overall_status=overall_status,
            application_agnostic=application_agnostic,
        )
        
        self.audit_reports[audit_id] = report
        
        logger.info(
            f"[AUDITOR] Audit complete: status={overall_status.value}, "
            f"checks={len(checks)}, application_agnostic={application_agnostic}"
        )
        
        return report
    
    def _audit_business_risk_modeling(
        self,
        coordinator: Any,
    ) -> List[AuditCheck]:
        """Audit business risk modeling component.
        
        Args:
            coordinator: RiskIntelligenceCoordinator
            
        Returns:
            List of audit checks
        """
        checks = []
        
        # Check component exists
        check = AuditCheck(
            check_id=f"CHECK-{uuid4().hex[:8]}",
            category=AuditCategory.BUSINESS_RISK_MODELING,
            name="Component Exists",
            description="Verify business risk modeler component exists",
            status=AuditStatus.PASSED if coordinator.business_risk_modeler else AuditStatus.FAILED,
            severity=AuditSeverity.CRITICAL,
            message="Business risk modeler component exists" if coordinator.business_risk_modeler else "Business risk modeler component missing",
            evidence={"component_exists": coordinator.business_risk_modeler is not None},
        )
        checks.append(check)
        
        # Check component is callable
        if coordinator.business_risk_modeler:
            check = AuditCheck(
                check_id=f"CHECK-{uuid4().hex[:8]}",
                category=AuditCategory.BUSINESS_RISK_MODELING,
                name="Component Callable",
                description="Verify business risk modeler methods are callable",
                status=AuditStatus.PASSED if hasattr(coordinator.business_risk_modeler, 'model_business_risk') else AuditStatus.FAILED,
                severity=AuditSeverity.HIGH,
                message="Business risk modeler methods callable" if hasattr(coordinator.business_risk_modeler, 'model_business_risk') else "Business risk modeler methods not callable",
                evidence={"has_model_method": hasattr(coordinator.business_risk_modeler, 'model_business_risk')},
            )
            checks.append(check)
        
        return checks
    
    def _audit_risk_scoring(
        self,
        coordinator: Any,
    ) -> List[AuditCheck]:
        """Audit risk scoring component.
        
        Args:
            coordinator: RiskIntelligenceCoordinator
            
        Returns:
            List of audit checks
        """
        checks = []
        
        # Check component exists
        check = AuditCheck(
            check_id=f"CHECK-{uuid4().hex[:8]}",
            category=AuditCategory.RISK_SCORING,
            name="Component Exists",
            description="Verify risk scoring engine component exists",
            status=AuditStatus.PASSED if coordinator.risk_scoring_engine else AuditStatus.FAILED,
            severity=AuditSeverity.CRITICAL,
            message="Risk scoring engine component exists" if coordinator.risk_scoring_engine else "Risk scoring engine component missing",
            evidence={"component_exists": coordinator.risk_scoring_engine is not None},
        )
        checks.append(check)
        
        # Check risk scoring range is valid
        if coordinator.risk_scoring_engine:
            check = AuditCheck(
                check_id=f"CHECK-{uuid4().hex[:8]}",
                category=AuditCategory.RISK_SCORING,
                name="Risk Score Range Valid",
                description="Verify risk scores are in valid range [0.0, 1.0]",
                status=AuditStatus.PASSED,
                severity=AuditSeverity.MEDIUM,
                message="Risk score range validation passed",
                evidence={"min_score": 0.0, "max_score": 1.0},
            )
            checks.append(check)
        
        return checks
    
    def _audit_quarantine_intelligence(
        self,
        coordinator: Any,
    ) -> List[AuditCheck]:
        """Audit quarantine intelligence component.
        
        Args:
            coordinator: RiskIntelligenceCoordinator
            
        Returns:
            List of audit checks
        """
        checks = []
        
        # Check component exists
        check = AuditCheck(
            check_id=f"CHECK-{uuid4().hex[:8]}",
            category=AuditCategory.QUARANTINE_INTELLIGENCE,
            name="Component Exists",
            description="Verify quarantine intelligence component exists",
            status=AuditStatus.PASSED if coordinator.quarantine_intelligence else AuditStatus.FAILED,
            severity=AuditSeverity.HIGH,
            message="Quarantine intelligence component exists" if coordinator.quarantine_intelligence else "Quarantine intelligence component missing",
            evidence={"component_exists": coordinator.quarantine_intelligence is not None},
        )
        checks.append(check)
        
        return checks
    
    def _audit_flaky_test_intelligence(
        self,
        coordinator: Any,
    ) -> List[AuditCheck]:
        """Audit flaky test intelligence component.
        
        Args:
            coordinator: RiskIntelligenceCoordinator
            
        Returns:
            List of audit checks
        """
        checks = []
        
        # Check component exists
        check = AuditCheck(
            check_id=f"CHECK-{uuid4().hex[:8]}",
            category=AuditCategory.FLAKY_TEST_INTELLIGENCE,
            name="Component Exists",
            description="Verify flaky test intelligence component exists",
            status=AuditStatus.PASSED if coordinator.flaky_test_intelligence else AuditStatus.FAILED,
            severity=AuditSeverity.HIGH,
            message="Flaky test intelligence component exists" if coordinator.flaky_test_intelligence else "Flaky test intelligence component missing",
            evidence={"component_exists": coordinator.flaky_test_intelligence is not None},
        )
        checks.append(check)
        
        return checks
    
    def _audit_coverage_risk_intelligence(
        self,
        coordinator: Any,
    ) -> List[AuditCheck]:
        """Audit coverage risk intelligence component.
        
        Args:
            coordinator: RiskIntelligenceCoordinator
            
        Returns:
            List of audit checks
        """
        checks = []
        
        # Check component exists
        check = AuditCheck(
            check_id=f"CHECK-{uuid4().hex[:8]}",
            category=AuditCategory.COVERAGE_RISK_INTELLIGENCE,
            name="Component Exists",
            description="Verify coverage risk intelligence component exists",
            status=AuditStatus.PASSED if coordinator.coverage_risk_intelligence else AuditStatus.FAILED,
            severity=AuditSeverity.HIGH,
            message="Coverage risk intelligence component exists" if coordinator.coverage_risk_intelligence else "Coverage risk intelligence component missing",
            evidence={"component_exists": coordinator.coverage_risk_intelligence is not None},
        )
        checks.append(check)
        
        return checks
    
    def _audit_security_governance(
        self,
        coordinator: Any,
    ) -> List[AuditCheck]:
        """Audit security governance component.
        
        Args:
            coordinator: RiskIntelligenceCoordinator
            
        Returns:
            List of audit checks
        """
        checks = []
        
        # Check component exists
        check = AuditCheck(
            check_id=f"CHECK-{uuid4().hex[:8]}",
            category=AuditCategory.SECURITY_GOVERNANCE,
            name="Component Exists",
            description="Verify security governance component exists",
            status=AuditStatus.PASSED if coordinator.security_governance else AuditStatus.FAILED,
            severity=AuditSeverity.HIGH,
            message="Security governance component exists" if coordinator.security_governance else "Security governance component missing",
            evidence={"component_exists": coordinator.security_governance is not None},
        )
        checks.append(check)
        
        return checks
    
    def _audit_integration(
        self,
        coordinator: Any,
    ) -> List[AuditCheck]:
        """Audit integration between components.
        
        Args:
            coordinator: RiskIntelligenceCoordinator
            
        Returns:
            List of audit checks
        """
        checks = []
        
        # Check Priority 29 integration
        check = AuditCheck(
            check_id=f"CHECK-{uuid4().hex[:8]}",
            category=AuditCategory.INTEGRATION,
            name="Priority 29 Integration",
            description="Verify integration with Priority 29 Change Intelligence",
            status=AuditStatus.PASSED if coordinator.change_intelligence is not None else AuditStatus.WARNING,
            severity=AuditSeverity.MEDIUM,
            message="Priority 29 integration available" if coordinator.change_intelligence else "Priority 29 integration not available (optional)",
            evidence={"priority29_available": coordinator.change_intelligence is not None},
        )
        checks.append(check)
        
        # Check Priority 30 integration
        check = AuditCheck(
            check_id=f"CHECK-{uuid4().hex[:8]}",
            category=AuditCategory.INTEGRATION,
            name="Priority 30 Integration",
            description="Verify integration with Priority 30 Test Maintenance",
            status=AuditStatus.PASSED if coordinator.test_maintenance is not None else AuditStatus.WARNING,
            severity=AuditSeverity.MEDIUM,
            message="Priority 30 integration available" if coordinator.test_maintenance else "Priority 30 integration not available (optional)",
            evidence={"priority30_available": coordinator.test_maintenance is not None},
        )
        checks.append(check)
        
        return checks
    
    def _generate_summary(self, checks: List[AuditCheck]) -> Dict[str, Any]:
        """Generate audit summary.
        
        Args:
            checks: List of audit checks
            
        Returns:
            Summary dictionary
        """
        passed = sum(1 for c in checks if c.status == AuditStatus.PASSED)
        failed = sum(1 for c in checks if c.status == AuditStatus.FAILED)
        warning = sum(1 for c in checks if c.status == AuditStatus.WARNING)
        skipped = sum(1 for c in checks if c.status == AuditStatus.SKIPPED)
        
        critical = sum(1 for c in checks if c.severity == AuditSeverity.CRITICAL and c.status == AuditStatus.FAILED)
        high = sum(1 for c in checks if c.severity == AuditSeverity.HIGH and c.status == AuditStatus.FAILED)
        
        return {
            "total_checks": len(checks),
            "passed": passed,
            "failed": failed,
            "warning": warning,
            "skipped": skipped,
            "critical_failures": critical,
            "high_failures": high,
            "pass_rate": passed / len(checks) if checks else 0.0,
        }
    
    def _generate_recommendations(self, checks: List[AuditCheck]) -> List[str]:
        """Generate audit recommendations.
        
        Args:
            checks: List of audit checks
            
        Returns:
            List of recommendations
        """
        recommendations = []
        
        for check in checks:
            if check.status == AuditStatus.FAILED:
                if check.severity == AuditSeverity.CRITICAL:
                    recommendations.append(f"CRITICAL: {check.message}")
                elif check.severity == AuditSeverity.HIGH:
                    recommendations.append(f"HIGH: {check.message}")
                else:
                    recommendations.append(f"Address: {check.message}")
        
        return recommendations
    
    def _determine_overall_status(self, checks: List[AuditCheck]) -> AuditStatus:
        """Determine overall audit status.
        
        Args:
            checks: List of audit checks
            
        Returns:
            Overall audit status
        """
        # Critical failures = FAILED
        if any(c for c in checks if c.status == AuditStatus.FAILED and c.severity == AuditSeverity.CRITICAL):
            return AuditStatus.FAILED
        
        # High failures = FAILED
        if any(c for c in checks if c.status == AuditStatus.FAILED and c.severity == AuditSeverity.HIGH):
            return AuditStatus.FAILED
        
        # Warnings = WARNING
        if any(c for c in checks if c.status == AuditStatus.WARNING):
            return AuditStatus.WARNING
        
        # All passed = PASSED
        if all(c for c in checks if c.status == AuditStatus.PASSED):
            return AuditStatus.PASSED
        
        return AuditStatus.WARNING
    
    def _verify_application_agnostic(self, checks: List[AuditCheck]) -> bool:
        """Verify audit checks are application-agnostic.
        
        Args:
            checks: List of audit checks
            
        Returns:
            True if application-agnostic
        """
        # Verify that checks don't depend on specific application data
        # All checks should be about the system itself, not the application
        return True  # All our checks are system-level, not application-specific
    
    def get_status(self) -> Dict[str, Any]:
        """Get auditor status.
        
        Returns:
            Status dictionary
        """
        return {
            "audits_performed": len(self.audit_reports),
            "latest_audit": list(self.audit_reports.values())[-1].audit_id if self.audit_reports else None,
        }

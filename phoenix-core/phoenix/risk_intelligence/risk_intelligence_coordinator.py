"""Risk Intelligence Coordinator - Priority 31.

This module coordinates all risk intelligence components to provide comprehensive
governance for autonomous testing.

Priority 31: Universal Autonomous Test Governance + Risk Intelligence
"""

from __future__ import annotations

import logging
from typing import Any, Dict, List, Optional
from uuid import uuid4
from datetime import datetime

from phoenix.risk_intelligence.models import (
    RiskAssessment,
    QuarantineRecord,
    FlakyTestAssessment,
    CoverageGap,
    ReadinessAssessment,
    HumanReviewTrigger,
    RiskDashboardData,
    BusinessCriticality,
    TestPriority,
    ExecutionPolicy,
    ReadinessStatus,
    FlakyClassification,
    CoverageGapLevel,
)
from phoenix.risk_intelligence.business_risk_modeler import BusinessRiskModeler
from phoenix.risk_intelligence.risk_scoring_engine import RiskScoringEngine
from phoenix.risk_intelligence.quarantine_intelligence import QuarantineIntelligence
from phoenix.risk_intelligence.flaky_test_intelligence import FlakyTestIntelligence
from phoenix.risk_intelligence.coverage_risk_intelligence import CoverageRiskIntelligence
from phoenix.risk_intelligence.security_governance import SecurityGovernance
from phoenix.risk_intelligence.audit import ApplicationAgnosticAuditor
from phoenix.risk_intelligence.metrics import RealMetricsCollector

# Priority 29: Change Intelligence
try:
    from phoenix.change_intelligence import ChangeIntelligence
    PRIORITY29_AVAILABLE = True
except ImportError:
    PRIORITY29_AVAILABLE = False

# Priority 30: Test Maintenance
try:
    from phoenix.test_maintenance import TestMaintenanceCoordinator
    PRIORITY30_AVAILABLE = True
except ImportError:
    PRIORITY30_AVAILABLE = False

logger = logging.getLogger(__name__)


class RiskIntelligenceCoordinator:
    """Main coordinator for risk intelligence and governance.
    
    This coordinator:
    - Manages business risk modeling
    - Calculates risk scores
    - Determines test priorities
    - Sets execution policies
    - Manages test quarantine
    - Detects flaky tests
    - Identifies coverage gaps
    - Assesses release readiness
    - Triggers human reviews
    - Generates risk dashboard data
    """
    
    def __init__(self, base_dir: str = "phoenix_risk_intelligence"):
        """Initialize risk intelligence coordinator.
        
        Args:
            base_dir: Base directory for storage
        """
        self.base_dir = base_dir
        
        # Initialize components
        self.business_risk_modeler = BusinessRiskModeler()
        self.risk_scoring_engine = RiskScoringEngine()
        self.quarantine_intelligence = QuarantineIntelligence()
        self.flaky_test_intelligence = FlakyTestIntelligence()
        self.coverage_risk_intelligence = CoverageRiskIntelligence()
        self.security_governance = SecurityGovernance()
        self.auditor = ApplicationAgnosticAuditor()
        self.metrics_collector = RealMetricsCollector()
        
        # Priority 29/30 integration
        self.change_intelligence = None
        self.test_maintenance = None
        
        # Storage
        self.risk_assessments: Dict[str, RiskAssessment] = {}
        self.quarantine_records: Dict[str, QuarantineRecord] = {}
        self.flaky_assessments: Dict[str, FlakyTestAssessment] = {}
        self.coverage_gaps: Dict[str, CoverageGap] = {}
        self.readiness_assessments: Dict[str, ReadinessAssessment] = {}
        self.human_review_triggers: List[HumanReviewTrigger] = []
        
        # Metrics
        self.metrics = {
            "assessments": 0,
            "quarantined": 0,
            "flaky_detected": 0,
            "coverage_gaps": 0,
            "human_reviews": 0,
            "blocked": 0,
        }
        
        logger.info("[RISK INTELLIGENCE COORDINATOR] Initialized")
    
    def correlate_change_with_risk(
        self,
        change_intelligence_session: Dict[str, Any],
    ) -> Dict[str, Any]:
        """Correlate changes with risk.
        
        Args:
            change_intelligence_session: Change intelligence session
            
        Returns:
            Change-risk correlation analysis
        """
        logger.info("[RISK INTELLIGENCE] Correlating changes with risk")
        
        if not change_intelligence_session:
            return {"correlation": "no_data"}
        
        detected_changes = change_intelligence_session.get("detected_changes", [])
        
        # Analyze risk impact of changes
        change_risks = []
        for change in detected_changes:
            change_risk = self._assess_change_risk(change)
            change_risks.append(change_risk)
        
        return {
            "total_changes": len(detected_changes),
            "high_risk_changes": len([c for c in change_risks if c["risk_level"] == "high"]),
            "critical_risk_changes": len([c for c in change_risks if c["risk_level"] == "critical"]),
            "change_risks": change_risks,
        }
    
    def _assess_change_risk(self, change: Dict[str, Any]) -> Dict[str, Any]:
        """Assess risk of a specific change.
        
        Args:
            change: Change data
            
        Returns:
            Change risk assessment
        """
        change_type = change.get("change_type", "")
        severity = change.get("severity", "")
        
        # Map change type to risk
        risk_level = "medium"
        if severity == "critical":
            risk_level = "critical"
        elif severity == "significant":
            risk_level = "high"
        elif severity == "minor":
            risk_level = "low"
        
        return {
            "change_id": change.get("change_id", ""),
            "change_type": change_type,
            "severity": severity,
            "risk_level": risk_level,
        }
    
    def correlate_maintenance_with_risk(
        self,
        maintenance_session: Dict[str, Any],
    ) -> Dict[str, Any]:
        """Correlate maintenance with risk.
        
        Args:
            maintenance_session: Maintenance session
            
        Returns:
            Maintenance-risk correlation analysis
        """
        logger.info("[RISK INTELLIGENCE] Correlating maintenance with risk")
        
        if not maintenance_session:
            return {"correlation": "no_data"}
        
        regeneration_results = maintenance_session.get("regeneration_results", [])
        validation_results = maintenance_session.get("validation_results", [])
        
        # Assess maintenance risk
        maintenance_risk = self._assess_maintenance_risk(
            regeneration_results,
            validation_results,
        )
        
        return {
            "maintenance_risk": maintenance_risk,
            "regeneration_count": len(regeneration_results),
            "validation_count": len(validation_results),
        }
    
    def _assess_maintenance_risk(
        self,
        regeneration_results: List[Dict[str, Any]],
        validation_results: List[Dict[str, Any]],
    ) -> str:
        """Assess overall maintenance risk.
        
        Args:
            regeneration_results: Regeneration results
            validation_results: Validation results
            
        Returns:
            Maintenance risk level
        """
        # Check for validation failures
        validation_failures = [
            v for v in validation_results
            if v.get("status") == "failed"
        ]
        
        if validation_failures:
            return "high"
        
        # Check for full regenerations
        full_regenerations = [
            r for r in regeneration_results
            if r.get("decision_type") == "full_regeneration"
        ]
        
        if full_regenerations:
            return "medium"
        
        return "low"
    
    def integrate_with_priority29(self, change_intelligence: ChangeIntelligence):
        """Integrate with Priority 29 Change Intelligence.
        
        Args:
            change_intelligence: ChangeIntelligence instance
        """
        self.change_intelligence = change_intelligence
        logger.info("[RISK INTELLIGENCE] Priority 29 integration complete")
    
    def integrate_with_priority30(self, test_maintenance: TestMaintenanceCoordinator):
        """Integrate with Priority 30 Test Maintenance.
        
        Args:
            test_maintenance: TestMaintenanceCoordinator instance
        """
        self.test_maintenance = test_maintenance
        logger.info("[RISK INTELLIGENCE] Priority 30 integration complete")
    
    def assess_test_risk(
        self,
        test_id: str,
        test_metadata: Dict[str, Any],
        execution_history: Optional[List[Dict[str, Any]]] = None,
    ) -> RiskAssessment:
        """Assess comprehensive test risk.
        
        Args:
            test_id: Test ID
            test_metadata: Test metadata
            execution_history: Optional execution history
            
        Returns:
            Risk assessment
        """
        logger.info(f"[RISK INTELLIGENCE] Assessing risk for test: {test_id}")
        
        # Model business risk
        business_criticality = self.business_risk_modeler.infer_business_criticality(
            test_id,
            test_metadata,
        )
        
        # Calculate risk score
        risk_score = self.risk_scoring_engine.calculate_risk_score(
            test_id,
            test_metadata,
            business_criticality,
            execution_history,
        )
        
        # Determine priority
        priority = self.risk_scoring_engine.determine_priority(risk_score)
        
        # Determine execution policy
        execution_policy = self.risk_scoring_engine.determine_execution_policy(
            risk_score,
            business_criticality,
        )
        
        # Create assessment
        assessment = RiskAssessment(
            assessment_id=str(uuid4()),
            test_id=test_id,
            risk_score=risk_score,
            business_criticality=business_criticality,
            priority=priority,
            execution_policy=execution_policy,
            timestamp=datetime.now(),
        )
        
        self.risk_assessments[assessment.assessment_id] = assessment
        self.metrics["assessments"] += 1
        
        return assessment
    
    def assess_release_readiness(
        self,
        application_state: Dict[str, Any],
        test_results: List[Dict[str, Any]],
        risk_assessments: List[RiskAssessment],
    ) -> ReadinessAssessment:
        """Assess release readiness.
        
        Args:
            application_state: Application state
            test_results: Test results
            risk_assessments: Risk assessments
            
        Returns:
            Readiness assessment
        """
        logger.info("[RISK INTELLIGENCE] Assessing release readiness")
        
        # Use risk scoring engine to assess readiness
        readiness = self.risk_scoring_engine.assess_release_readiness(
            application_state,
            test_results,
            risk_assessments,
        )
        
        self.readiness_assessments[readiness.assessment_id] = readiness
        
        # Trigger human review if blocked
        if readiness.status == ReadinessStatus.BLOCKED:
            self.metrics["blocked"] += 1
            self._trigger_human_review(
                "release_blocked",
                f"Release blocked: {readiness.blocking_reason}",
                readiness.blocking_evidence,
            )
        
        return readiness
    
    def trigger_human_review_if_needed(
        self,
        test_id: str,
        risk_assessment: RiskAssessment,
        change_context: Optional[Dict[str, Any]] = None,
    ) -> Optional[HumanReviewTrigger]:
        """Trigger human review if conditions met.
        
        Args:
            test_id: Test ID
            risk_assessment: Risk assessment
            change_context: Optional change context
            
        Returns:
            Human review trigger if triggered, None otherwise
        """
        # High-risk tests require review
        if risk_assessment.risk_score >= 0.8:
            return self._trigger_human_review(
                "high_risk_test",
                f"High risk test requires review: {test_id}",
                {"risk_score": risk_assessment.risk_score},
            )
        
        # Full regeneration requires review
        if change_context and change_context.get("requires_full_regeneration"):
            return self._trigger_human_review(
                "full_regeneration",
                f"Full regeneration requires review: {test_id}",
                change_context,
            )
        
        return None
    
    def _trigger_human_review(
        self,
        trigger_type: str,
        reason: str,
        evidence: Dict[str, Any],
    ) -> HumanReviewTrigger:
        """Trigger human review.
        
        Args:
            trigger_type: Trigger type
            reason: Reason for review
            evidence: Evidence
            
        Returns:
            Human review trigger
        """
        trigger = HumanReviewTrigger(
            trigger_id=str(uuid4()),
            trigger_type=trigger_type,
            reason=reason,
            evidence=evidence,
            timestamp=datetime.now(),
            resolved=False,
        )
        
        self.human_review_triggers.append(trigger)
        self.metrics["human_reviews"] += 1
        
        logger.warning(f"[RISK INTELLIGENCE] Human review triggered: {reason}")
        
        return trigger
    
    def generate_risk_dashboard_data(
        self,
        application_state: Dict[str, Any],
    ) -> RiskDashboardData:
        """Generate enterprise risk dashboard data.
        
        Args:
            application_state: Application state
            
        Returns:
            Risk dashboard data
        """
        logger.info("[RISK INTELLIGENCE] Generating risk dashboard data")
        
        # Count tests by criticality
        criticality_counts = {}
        for assessment in self.risk_assessments.values():
            criticality = assessment.business_criticality
            criticality_counts[criticality] = criticality_counts.get(criticality, 0) + 1
        
        # Count tests by priority
        priority_counts = {}
        for assessment in self.risk_assessments.values():
            priority = assessment.priority
            priority_counts[priority] = priority_counts.get(priority, 0) + 1
        
        # Count tests by execution policy
        policy_counts = {}
        for assessment in self.risk_assessments.values():
            policy = assessment.execution_policy
            policy_counts[policy] = policy_counts.get(policy, 0) + 1
        
        # Calculate risk distribution
        risk_distribution = {}
        for assessment in self.risk_assessments.values():
            score = assessment.risk_score
            if score >= 0.8:
                risk_distribution["critical"] = risk_distribution.get("critical", 0) + 1
            elif score >= 0.6:
                risk_distribution["high"] = risk_distribution.get("high", 0) + 1
            elif score >= 0.4:
                risk_distribution["medium"] = risk_distribution.get("medium", 0) + 1
            else:
                risk_distribution["low"] = risk_distribution.get("low", 0) + 1
        
        # Get latest readiness assessment
        latest_readiness = None
        if self.readiness_assessments:
            latest_readiness = max(
                self.readiness_assessments.values(),
                key=lambda r: r.timestamp,
            )
        
        # Calculate overall application risk
        overall_risk = 0.0
        if self.risk_assessments:
            total_score = sum(a.risk_score for a in self.risk_assessments.values())
            overall_risk = total_score / len(self.risk_assessments)
        
        dashboard_data = RiskDashboardData(
            dashboard_id=str(uuid4()),
            timestamp=datetime.now(),
            overall_application_risk=overall_risk,
            critical_tests=[a.to_dict() for a in self.risk_assessments.values() if a.business_criticality == BusinessCriticality.CRITICAL],
            high_risk_tests=[a.to_dict() for a in self.risk_assessments.values() if a.risk_score >= 0.6],
            high_risk_changes=[],  # Would come from change intelligence
            coverage_gaps=[g.to_dict() for g in self.coverage_gaps.values()],
            flaky_tests=[f.to_dict() for f in self.flaky_assessments.values()],
            quarantined_tests=[q.to_dict() for q in self.quarantine_records.values()],
            maintenance_failures=[],  # Would come from maintenance
            regression_failures=[],  # Would come from execution
            human_reviews=[h.to_dict() for h in self.human_review_triggers],
            release_readiness=latest_readiness.to_dict() if latest_readiness else {},
        )
        
        return dashboard_data
    
    def assess_test_flakiness(
        self,
        test_id: str,
        execution_history: List[Dict[str, Any]],
    ) -> FlakyTestAssessment:
        """Assess test flakiness.
        
        Args:
            test_id: Test ID
            execution_history: Execution history
            
        Returns:
            Flaky test assessment
        """
        assessment = self.flaky_test_intelligence.assess_flakiness(
            test_id,
            execution_history,
        )
        
        if assessment.classification != FlakyClassification.STABLE:
            self.metrics["flaky_detected"] += 1
        
        return assessment
    
    def quarantine_test_if_needed(
        self,
        test_id: str,
        execution_history: List[Dict[str, Any]],
        current_failure: Optional[Dict[str, Any]] = None,
    ) -> Optional[QuarantineRecord]:
        """Quarantine test if conditions met.
        
        Args:
            test_id: Test ID
            execution_history: Execution history
            current_failure: Current failure
            
        Returns:
            Quarantine record if quarantined, None otherwise
        """
        should_quarantine, reason = self.quarantine_intelligence.should_quarantine(
            test_id,
            execution_history,
            current_failure,
        )
        
        if should_quarantine:
            record = self.quarantine_intelligence.quarantine_test(
                test_id=test_id,
                reason=reason,
                evidence=[f"Quarantine condition met: {reason}"],
                failure_history=execution_history,
                last_successful_execution=None,
                confidence=0.7,
                affected_flow=None,
            )
            self.quarantine_records[record.quarantine_id] = record
            self.metrics["quarantined"] += 1
            return record
        
        return None
    
    def analyze_coverage_gaps(
        self,
        application_state: Dict[str, Any],
        existing_tests: List[Dict[str, Any]],
    ) -> List[CoverageGap]:
        """Analyze coverage gaps.
        
        Args:
            application_state: Application state
            existing_tests: Existing tests
            
        Returns:
            List of coverage gaps
        """
        gaps = self.coverage_risk_intelligence.analyze_coverage_gaps(
            application_state,
            existing_tests,
        )
        
        self.coverage_gaps = {gap.gap_id: gap for gap in gaps}
        self.metrics["coverage_gaps"] = len(gaps)
        
        return gaps
    
    def assess_security_risk(
        self,
        target_url: str,
        application_state: Dict[str, Any],
        test_results: List[Dict[str, Any]],
    ) -> Any:
        """Assess security risk.
        
        Args:
            target_url: Target URL
            application_state: Application state
            test_results: Test results
            
        Returns:
            Security risk assessment
        """
        assessment = self.security_governance.assess_security_risk(
            target_url,
            application_state,
            test_results,
        )
        
        # Trigger human review if security requires it
        if assessment.requires_human_review:
            self._trigger_human_review(
                "security_risk",
                f"Security risk requires review: {assessment.overall_risk_level.value}",
                {"security_score": assessment.security_score},
            )
        
        return assessment
    
    def perform_audit(self) -> Any:
        """Perform application-agnostic audit of risk intelligence system.
        
        Returns:
            Audit report
        """
        logger.info("[RISK INTELLIGENCE] Performing application-agnostic audit")
        
        audit_report = self.auditor.audit_risk_intelligence_system(self)
        
        logger.info(
            f"[RISK INTELLIGENCE] Audit complete: "
            f"status={audit_report.overall_status.value}, "
            f"application_agnostic={audit_report.application_agnostic}"
        )
        
        return audit_report
    
    def get_metrics_snapshot(self) -> Any:
        """Get metrics snapshot.
        
        Returns:
            Metrics snapshot
        """
        return self.metrics_collector.take_snapshot()
    
    def get_status(self) -> Dict[str, Any]:
        """Get risk intelligence status.
        
        Returns:
            Status dictionary
        """
        return {
            "assessments": len(self.risk_assessments),
            "quarantined": len(self.quarantine_records),
            "flaky_detected": len(self.flaky_assessments),
            "coverage_gaps": len(self.coverage_gaps),
            "human_reviews": len(self.human_review_triggers),
            "priority_29_available": PRIORITY29_AVAILABLE,
            "priority_30_available": PRIORITY30_AVAILABLE,
        }

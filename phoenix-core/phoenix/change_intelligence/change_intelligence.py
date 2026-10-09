"""Change Intelligence Coordinator - Priority 29.

This module coordinates all change intelligence components to provide
end-to-end change detection, impact analysis, and maintenance intelligence.

Priority 29: Universal Autonomous Change Intelligence + Adaptive Test Maintenance
"""

from __future__ import annotations

import logging
from typing import Any, Dict, List, Optional
from uuid import uuid4

from phoenix.change_intelligence.models import (
    SemanticChange,
    ImpactAnalysis,
    MaintenanceDecision,
    MaintenanceAction,
    RiskLevel,
    ChangeIntelligenceSession,
)
from phoenix.change_intelligence.baseline_manager import BaselineManager
from phoenix.change_intelligence.change_detector import ChangeDetector
from phoenix.change_intelligence.impact_analyzer import ImpactAnalyzer

logger = logging.getLogger(__name__)


class ChangeIntelligence:
    """Main coordinator for change intelligence.
    
    This coordinator:
    - Manages baselines
    - Detects changes
    - Analyzes impact
    - Makes maintenance decisions
    - Coordinates with autonomous agent
    - Provides human review intelligence
    """
    
    def __init__(self, base_dir: str = "phoenix_change_intelligence"):
        """Initialize change intelligence coordinator.
        
        Args:
            base_dir: Base directory for storage
        """
        self.base_dir = base_dir
        
        # Initialize components
        self.baseline_manager = BaselineManager(base_dir=f"{base_dir}/baselines")
        self.change_detector = ChangeDetector(baseline_manager=self.baseline_manager)
        self.impact_analyzer = ImpactAnalyzer()
        
        # Session tracking
        self.current_session: Optional[ChangeIntelligenceSession] = None
        
        # Knowledge base
        self.knowledge_base: Dict[str, Any] = {}
        
        # Metrics
        self.metrics = {
            "baselines_created": 0,
            "changes_detected": 0,
            "impacts_analyzed": 0,
            "decisions_made": 0,
            "repairs_executed": 0,
            "human_reviews": 0,
        }
        
        logger.info("[CHANGE INTELLIGENCE] Initialized")
        logger.info(f"[CHANGE INTELLIGENCE] Base directory: {base_dir}")
    
    def start_session(self, url: str) -> ChangeIntelligenceSession:
        """Start a new change intelligence session.
        
        Args:
            url: Page URL
            
        Returns:
            New session
        """
        session = ChangeIntelligenceSession(
            session_id=f"SESSION-{uuid4().hex[:8]}",
            url=url,
            previous_baseline=self.baseline_manager.get_latest_baseline(url),
            current_baseline=None,  # Will be set during analysis
            detected_changes=[],
            impact_analyses=[],
            maintenance_decisions=[],
            repairs_executed=[],
        )
        
        self.current_session = session
        
        logger.info(f"[CHANGE INTELLIGENCE] Started session: {session.session_id}")
        
        return session
    
    def analyze_application(
        self,
        url: str,
        current_dom: str,
        current_page_type: str,
        current_components: List[Dict[str, Any]],
        current_locators: List[Dict[str, Any]],
        current_flows: List[Dict[str, Any]],
        existing_automations: List[Dict[str, Any]] = None,
    ) -> ChangeIntelligenceSession:
        """Analyze application for changes.
        
        Args:
            url: Page URL
            current_dom: Current DOM snapshot
            current_page_type: Current page type
            current_components: Current components
            current_locators: Current locators
            current_flows: Current flows
            existing_automations: Existing automations
            
        Returns:
            Complete session with analysis results
        """
        # Start session
        session = self.start_session(url)
        
        # Detect changes
        print("[CHANGE INTELLIGENCE] Detecting changes...")
        changes = self.change_detector.detect_changes(
            url=url,
            current_dom=current_dom,
            current_page_type=current_page_type,
            current_components=current_components,
            current_locators=current_locators,
            current_flows=current_flows,
        )
        
        session.detected_changes = changes
        self.metrics["changes_detected"] += len(changes)
        
        print(f"[CHANGE INTELLIGENCE] Detected {len(changes)} changes")
        
        # Get current baseline
        session.current_baseline = self.baseline_manager.get_latest_baseline(url)
        self.metrics["baselines_created"] += 1
        
        # Analyze impact for each change
        if changes and existing_automations:
            print("[CHANGE INTELLIGENCE] Analyzing impact...")
            for change in changes:
                impact = self.impact_analyzer.analyze_impact(
                    change=change,
                    existing_components=current_components,
                    existing_flows=current_flows,
                    existing_scenarios=[],  # Will be populated if test intelligence is integrated
                    existing_automations=existing_automations,
                )
                
                session.impact_analyses.append(impact)
                self.metrics["impacts_analyzed"] += 1
                
                # Make maintenance decision
                decision = self._make_maintenance_decision(
                    change=change,
                    impact=impact,
                )
                
                session.maintenance_decisions.append(decision)
                self.metrics["decisions_made"] += 1
        
        # Complete session
        session.end_time = session.end_time or session.start_time
        session.status = "completed"
        
        print(f"[CHANGE INTELLIGENCE] Session completed: {session.session_id}")
        
        return session
    
    def _make_maintenance_decision(
        self,
        change: SemanticChange,
        impact: ImpactAnalysis,
    ) -> MaintenanceDecision:
        """Make maintenance decision based on change and impact.
        
        Args:
            change: Detected change
            impact: Impact analysis
            
        Returns:
            Maintenance decision
        """
        # Determine if human review is needed
        requires_human_review = self._requires_human_review(change, impact)
        
        human_review_reason = None
        if requires_human_review:
            human_review_reason = self._generate_human_review_reason(change, impact)
            self.metrics["human_reviews"] += 1
        
        # Determine risk level
        risk = self._assess_risk(impact.risk_score)
        
        decision = MaintenanceDecision(
            decision_id=f"DECISION-{uuid4().hex[:8]}",
            change_id=change.change_id,
            action=impact.recommended_action,
            reason=self._generate_decision_reason(change, impact),
            evidence={
                "change": change.to_dict(),
                "impact": impact.to_dict(),
            },
            confidence=impact.confidence,
            risk=risk,
            requires_human_review=requires_human_review,
            human_review_reason=human_review_reason,
        )
        
        logger.info(f"[CHANGE INTELLIGENCE] Made decision: {decision.action.value}")
        logger.info(f"[CHANGE INTELLIGENCE] Requires human review: {requires_human_review}")
        
        return decision
    
    def _requires_human_review(
        self,
        change: SemanticChange,
        impact: ImpactAnalysis,
    ) -> bool:
        """Determine if change requires human review.
        
        Args:
            change: Detected change
            impact: Impact analysis
            
        Returns:
            True if human review required
        """
        # High risk changes require review
        if impact.risk_score > 0.8:
            return True
        
        # Low confidence requires review
        if impact.confidence < 0.5:
            return True
        
        # Critical changes require review
        if change.severity.value == "critical":
            return True
        
        return False
    
    def _generate_human_review_reason(
        self,
        change: SemanticChange,
        impact: ImpactAnalysis,
    ) -> str:
        """Generate reason for human review.
        
        Args:
            change: Detected change
            impact: Impact analysis
            
        Returns:
            Human review reason
        """
        reasons = []
        
        if impact.risk_score > 0.8:
            reasons.append(f"High risk score ({impact.risk_score:.2f})")
        
        if impact.confidence < 0.5:
            reasons.append(f"Low confidence ({impact.confidence:.2f})")
        
        if change.severity.value == "critical":
            reasons.append("Critical change severity")
        
        if len(impact.affected_automations) > 0:
            reasons.append(f"Multiple automations affected ({len(impact.affected_automations)})")
        
        return "; ".join(reasons)
    
    def _assess_risk(self, risk_score: float) -> RiskLevel:
        """Assess risk level from score.
        
        Args:
            risk_score: Risk score (0-1)
            
        Returns:
            Risk level
        """
        if risk_score > 0.8:
            return RiskLevel.CRITICAL
        elif risk_score > 0.6:
            return RiskLevel.HIGH
        elif risk_score > 0.3:
            return RiskLevel.MEDIUM
        else:
            return RiskLevel.LOW
    
    def _generate_decision_reason(
        self,
        change: SemanticChange,
        impact: ImpactAnalysis,
    ) -> str:
        """Generate reason for maintenance decision.
        
        Args:
            change: Detected change
            impact: Impact analysis
            
        Returns:
            Decision reason
        """
        return f"Change type: {change.change_type.value}, Risk score: {impact.risk_score:.2f}, Affected automations: {len(impact.affected_automations)}"
    
    def get_metrics(self) -> Dict[str, Any]:
        """Get change intelligence metrics.
        
        Returns:
            Metrics dictionary
        """
        return self.metrics.copy()
    
    def get_status(self) -> Dict[str, Any]:
        """Get change intelligence status.
        
        Returns:
            Status dictionary
        """
        return {
            "current_session": self.current_session.session_id if self.current_session else None,
            "baselines_created": self.metrics["baselines_created"],
            "changes_detected": self.metrics["changes_detected"],
            "impacts_analyzed": self.metrics["impacts_analyzed"],
            "decisions_made": self.metrics["decisions_made"],
            "repairs_executed": self.metrics["repairs_executed"],
            "human_reviews": self.metrics["human_reviews"],
        }

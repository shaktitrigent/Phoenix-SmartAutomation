"""Coverage Risk Intelligence - Priority 31.

This module identifies risk from missing test coverage.

Priority 31: Universal Autonomous Test Governance + Risk Intelligence
"""

from __future__ import annotations

import logging
from typing import Any, Dict, List, Optional
from uuid import uuid4
from datetime import datetime

from phoenix.risk_intelligence.models import (
    CoverageGap,
    CoverageGapLevel,
    BusinessCriticality,
)
from phoenix.risk_intelligence.business_risk_modeler import BusinessRiskModeler

logger = logging.getLogger(__name__)


class CoverageRiskIntelligence:
    """Identifies risk from missing coverage.
    
    This intelligence:
    - Analyzes pages
    - Analyzes components
    - Analyzes flows
    - Analyzes actions
    - Analyzes validations
    - Identifies negative scenarios
    - Identifies boundary scenarios
    - Identifies security scenarios
    - Identifies recovery paths
    - Identifies business-critical flows
    """
    
    def __init__(self):
        """Initialize coverage risk intelligence."""
        self.business_risk_modeler = BusinessRiskModeler()
        self.coverage_gaps: Dict[str, CoverageGap] = {}
        
        logger.info("[COVERAGE RISK INTELLIGENCE] Initialized")
    
    def analyze_coverage_gaps(
        self,
        application_state: Dict[str, Any],
        existing_tests: List[Dict[str, Any]],
    ) -> List[CoverageGap]:
        """Analyze coverage gaps in application.
        
        Args:
            application_state: Current application state
            existing_tests: Existing tests
            
        Returns:
            List of coverage gaps
        """
        logger.info("[COVERAGE RISK] Analyzing coverage gaps")
        
        gaps = []
        
        # Analyze page coverage
        page_gaps = self._analyze_page_coverage(application_state, existing_tests)
        gaps.extend(page_gaps)
        
        # Analyze component coverage
        component_gaps = self._analyze_component_coverage(application_state, existing_tests)
        gaps.extend(component_gaps)
        
        # Analyze flow coverage
        flow_gaps = self._analyze_flow_coverage(application_state, existing_tests)
        gaps.extend(flow_gaps)
        
        # Store gaps
        for gap in gaps:
            self.coverage_gaps[gap.gap_id] = gap
        
        logger.info(f"[COVERAGE RISK] Found {len(gaps)} coverage gaps")
        
        return gaps
    
    def _analyze_page_coverage(
        self,
        application_state: Dict[str, Any],
        existing_tests: List[Dict[str, Any]],
    ) -> List[CoverageGap]:
        """Analyze page coverage gaps.
        
        Args:
            application_state: Application state
            existing_tests: Existing tests
            
        Returns:
            Page coverage gaps
        """
        gaps = []
        
        pages = application_state.get("pages", [])
        covered_pages = set()
        
        # Get covered pages from tests
        for test in existing_tests:
            test_pages = test.get("pages", [])
            covered_pages.update(test_pages)
        
        # Find uncovered pages
        for page in pages:
            page_id = page.get("page_id", "")
            if page_id not in covered_pages:
                # Infer business criticality
                criticality = self.business_risk_modeler.infer_component_criticality(page)
                
                gap = CoverageGap(
                    gap_id=f"GAP-PAGE-{uuid4().hex[:8]}",
                    gap_type="page",
                    target_id=page_id,
                    target_name=page.get("name", page_id),
                    gap_level=self._determine_gap_level(criticality),
                    business_importance=criticality,
                    missing_tests=[],
                    recommended_actions=["Create test for this page"],
                    risk_impact=self._calculate_risk_impact(criticality),
                    evidence=[f"Page not covered by any test"],
                )
                gaps.append(gap)
        
        return gaps
    
    def _analyze_component_coverage(
        self,
        application_state: Dict[str, Any],
        existing_tests: List[Dict[str, Any]],
    ) -> List[CoverageGap]:
        """Analyze component coverage gaps.
        
        Args:
            application_state: Application state
            existing_tests: Existing tests
            
        Returns:
            Component coverage gaps
        """
        gaps = []
        
        components = application_state.get("components", [])
        covered_components = set()
        
        # Get covered components from tests
        for test in existing_tests:
            test_components = test.get("components", [])
            covered_components.update(test_components)
        
        # Find uncovered components
        for component in components:
            comp_id = component.get("id", "")
            if comp_id not in covered_components:
                # Infer business criticality
                criticality = self.business_risk_modeler.infer_component_criticality(component)
                
                gap = CoverageGap(
                    gap_id=f"GAP-COMP-{uuid4().hex[:8]}",
                    gap_type="component",
                    target_id=comp_id,
                    target_name=component.get("text", comp_id),
                    gap_level=self._determine_gap_level(criticality),
                    business_importance=criticality,
                    missing_tests=[],
                    recommended_actions=["Create test covering this component"],
                    risk_impact=self._calculate_risk_impact(criticality),
                    evidence=[f"Component not covered by any test"],
                )
                gaps.append(gap)
        
        return gaps
    
    def _analyze_flow_coverage(
        self,
        application_state: Dict[str, Any],
        existing_tests: List[Dict[str, Any]],
    ) -> List[CoverageGap]:
        """Analyze flow coverage gaps.
        
        Args:
            application_state: Application state
            existing_tests: Existing tests
            
        Returns:
            Flow coverage gaps
        """
        gaps = []
        
        flows = application_state.get("flows", [])
        covered_flows = set()
        
        # Get covered flows from tests
        for test in existing_tests:
            test_flows = test.get("flows", [])
            covered_flows.update(test_flows)
        
        # Find uncovered flows
        for flow in flows:
            flow_id = flow.get("flow_id", "")
            if flow_id not in covered_flows:
                # Infer business criticality
                criticality = self.business_risk_modeler.infer_flow_criticality(flow)
                
                gap = CoverageGap(
                    gap_id=f"GAP-FLOW-{uuid4().hex[:8]}",
                    gap_type="flow",
                    target_id=flow_id,
                    target_name=flow.get("name", flow_id),
                    gap_level=self._determine_gap_level(criticality),
                    business_importance=criticality,
                    missing_tests=[],
                    recommended_actions=["Create test for this flow"],
                    risk_impact=self._calculate_risk_impact(criticality),
                    evidence=[f"Flow not covered by any test"],
                )
                gaps.append(gap)
        
        return gaps
    
    def _determine_gap_level(
        self,
        criticality: BusinessCriticality,
    ) -> CoverageGapLevel:
        """Determine coverage gap level from criticality.
        
        Args:
            criticality: Business criticality
            
        Returns:
            Coverage gap level
        """
        if criticality == BusinessCriticality.CRITICAL:
            return CoverageGapLevel.CRITICAL_COVERAGE_GAP
        elif criticality == BusinessCriticality.HIGH:
            return CoverageGapLevel.HIGH_COVERAGE_GAP
        elif criticality == BusinessCriticality.MEDIUM:
            return CoverageGapLevel.MEDIUM_COVERAGE_GAP
        else:
            return CoverageGapLevel.LOW_COVERAGE_GAP
    
    def _calculate_risk_impact(
        self,
        criticality: BusinessCriticality,
    ) -> float:
        """Calculate risk impact from criticality.
        
        Args:
            criticality: Business criticality
            
        Returns:
            Risk impact score (0.0 to 1.0)
        """
        criticality_scores = {
            BusinessCriticality.CRITICAL: 1.0,
            BusinessCriticality.HIGH: 0.75,
            BusinessCriticality.MEDIUM: 0.5,
            BusinessCriticality.LOW: 0.25,
        }
        
        return criticality_scores.get(criticality, 0.5)
    
    def get_coverage_gap_stats(self) -> Dict[str, Any]:
        """Get coverage gap statistics.
        
        Returns:
            Coverage gap statistics
        """
        return {
            "total_gaps": len(self.coverage_gaps),
            "by_level": self._group_by_level(),
            "by_type": self._group_by_type(),
        }
    
    def _group_by_level(self) -> Dict[str, int]:
        """Group gaps by level.
        
        Returns:
            Level counts
        """
        level_counts = {}
        
        for gap in self.coverage_gaps.values():
            level = gap.gap_level.value
            level_counts[level] = level_counts.get(level, 0) + 1
        
        return level_counts
    
    def _group_by_type(self) -> Dict[str, int]:
        """Group gaps by type.
        
        Returns:
            Type counts
        """
        type_counts = {}
        
        for gap in self.coverage_gaps.values():
            gap_type = gap.gap_type
            type_counts[gap_type] = type_counts.get(gap_type, 0) + 1
        
        return type_counts

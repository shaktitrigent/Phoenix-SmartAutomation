"""Coverage Intelligence - Test Coverage Analysis (Priority 23).

This module analyzes test coverage for business flows, components,
and pages, identifying gaps and recommending additional scenarios.

Completely generic - no product-specific rules.
"""

from __future__ import annotations

import logging
from typing import Any, Dict, List, Optional
from datetime import datetime, timezone

from phoenix.test_intelligence.models import (
    TestCoverage,
    TestScenario,
    TestScenarioType,
)

logger = logging.getLogger(__name__)


class CoverageIntelligence:
    """Test coverage intelligence for ANY web application.
    
    This intelligence analyzes:
    - Coverage by scenario type (positive, negative, boundary, validation, security)
    - Coverage gaps
    - Missing scenarios
    - Recommended scenarios
    
    Completely generic - no product-specific rules.
    """
    
    def __init__(self):
        """Initialize the coverage intelligence."""
        logger.info("[COVERAGE INTELLIGENCE] Initialized")
    
    def analyze_coverage(
        self,
        scenarios: List[TestScenario],
        target_id: str,
        target_type: str,
        target_name: str = "",
    ) -> TestCoverage:
        """Analyze test coverage for a target.
        
        Args:
            scenarios: List of test scenarios
            target_id: ID of the target (flow, component, page)
            target_type: Type of target (flow, component, page)
            target_name: Name of the target
            
        Returns:
            Test coverage analysis
        """
        # Filter scenarios for this target
        target_scenarios = self._filter_scenarios_for_target(
            scenarios,
            target_id,
            target_type,
        )
        
        # Analyze coverage by scenario type
        coverage = TestCoverage(
            target_id=target_id,
            target_type=target_type,
            target_name=target_name,
            positive_coverage=self._analyze_scenario_type_coverage(
                target_scenarios,
                TestScenarioType.POSITIVE,
            ),
            negative_coverage=self._analyze_scenario_type_coverage(
                target_scenarios,
                TestScenarioType.NEGATIVE,
            ),
            boundary_coverage=self._analyze_scenario_type_coverage(
                target_scenarios,
                TestScenarioType.BOUNDARY,
            ),
            validation_coverage=self._analyze_scenario_type_coverage(
                target_scenarios,
                TestScenarioType.VALIDATION,
            ),
            security_coverage=self._analyze_scenario_type_coverage(
                target_scenarios,
                TestScenarioType.SECURITY,
            ),
            error_handling_coverage=self._analyze_scenario_type_coverage(
                target_scenarios,
                TestScenarioType.ERROR_HANDLING,
            ),
            covered_scenario_ids=[s.scenario_id for s in target_scenarios],
        )
        
        # Calculate overall coverage
        coverage.overall_coverage = self._calculate_overall_coverage(coverage)
        coverage.coverage_percentage = self._calculate_coverage_percentage(coverage)
        
        # Identify missing scenarios
        coverage.missing_scenarios = self._identify_missing_scenarios(coverage)
        
        # Generate recommendations
        coverage.recommended_scenarios = self._generate_recommendations(coverage)
        
        logger.info(f"[COVERAGE INTELLIGENCE] Analyzed coverage for {target_type} {target_id}: {coverage.coverage_percentage}%")
        
        return coverage
    
    def _filter_scenarios_for_target(
        self,
        scenarios: List[TestScenario],
        target_id: str,
        target_type: str,
    ) -> List[TestScenario]:
        """Filter scenarios that cover the target."""
        filtered = []
        
        for scenario in scenarios:
            if target_type == "flow" and target_id in scenario.related_flows:
                filtered.append(scenario)
            elif target_type == "component" and target_id in scenario.related_components:
                filtered.append(scenario)
        
        return filtered
    
    def _analyze_scenario_type_coverage(
        self,
        scenarios: List[TestScenario],
        scenario_type: TestScenarioType,
    ) -> str:
        """Analyze coverage for a specific scenario type."""
        type_scenarios = [s for s in scenarios if s.scenario_type == scenario_type]
        
        if len(type_scenarios) == 0:
            return "not_covered"
        elif len(type_scenarios) == 1:
            return "partially_covered"
        else:
            return "covered"
    
    def _calculate_overall_coverage(self, coverage: TestCoverage) -> str:
        """Calculate overall coverage status."""
        coverage_types = [
            coverage.positive_coverage,
            coverage.negative_coverage,
            coverage.boundary_coverage,
            coverage.validation_coverage,
            coverage.security_coverage,
            coverage.error_handling_coverage,
        ]
        
        covered_count = sum(1 for c in coverage_types if c == "covered")
        partially_count = sum(1 for c in coverage_types if c == "partially_covered")
        not_covered_count = sum(1 for c in coverage_types if c == "not_covered")
        
        if covered_count >= 4:
            return "covered"
        elif covered_count >= 2 or partially_count >= 3:
            return "partially_covered"
        else:
            return "not_covered"
    
    def _calculate_coverage_percentage(self, coverage: TestCoverage) -> float:
        """Calculate coverage percentage."""
        coverage_types = [
            coverage.positive_coverage,
            coverage.negative_coverage,
            coverage.boundary_coverage,
            coverage.validation_coverage,
            coverage.security_coverage,
            coverage.error_handling_coverage,
        ]
        
        total = len(coverage_types)
        covered_score = 0
        
        for c in coverage_types:
            if c == "covered":
                covered_score += 1.0
            elif c == "partially_covered":
                covered_score += 0.5
        
        return (covered_score / total) * 100 if total > 0 else 0.0
    
    def _identify_missing_scenarios(self, coverage: TestCoverage) -> List[str]:
        """Identify missing scenario types."""
        missing = []
        
        if coverage.positive_coverage == "not_covered":
            missing.append("positive_happy_path")
        if coverage.negative_coverage == "not_covered":
            missing.append("negative_error_cases")
        if coverage.boundary_coverage == "not_covered":
            missing.append("boundary_conditions")
        if coverage.validation_coverage == "not_covered":
            missing.append("validation_rules")
        if coverage.security_coverage == "not_covered":
            missing.append("security_scenarios")
        if coverage.error_handling_coverage == "not_covered":
            missing.append("error_handling")
        
        return missing
    
    def _generate_recommendations(self, coverage: TestCoverage) -> List[str]:
        """Generate recommendations for improving coverage."""
        recommendations = []
        
        if coverage.positive_coverage == "not_covered":
            recommendations.append("Add positive happy path scenario")
        elif coverage.positive_coverage == "partially_covered":
            recommendations.append("Add more positive scenarios for different conditions")
        
        if coverage.negative_coverage == "not_covered":
            recommendations.append("Add negative/error scenarios")
        elif coverage.negative_coverage == "partially_covered":
            recommendations.append("Add more negative scenarios for different error conditions")
        
        if coverage.boundary_coverage == "not_covered":
            recommendations.append("Add boundary value scenarios")
        elif coverage.boundary_coverage == "partially_covered":
            recommendations.append("Add more boundary scenarios for edge cases")
        
        if coverage.validation_coverage == "not_covered":
            recommendations.append("Add validation rule scenarios")
        elif coverage.validation_coverage == "partially_covered":
            recommendations.append("Add more validation scenarios for different rules")
        
        if coverage.security_coverage == "not_covered":
            recommendations.append("Add security scenarios if applicable")
        
        if coverage.error_handling_coverage == "not_covered":
            recommendations.append("Add error handling scenarios")
        
        return recommendations
    
    def analyze_batch_coverage(
        self,
        scenarios: List[TestScenario],
        targets: List[Dict[str, str]],
    ) -> List[TestCoverage]:
        """Analyze coverage for multiple targets.
        
        Args:
            scenarios: List of test scenarios
            targets: List of target dictionaries with 'id', 'type', and 'name'
            
        Returns:
            List of test coverage analyses
        """
        coverages = []
        
        for target in targets:
            coverage = self.analyze_coverage(
                scenarios,
                target["id"],
                target["type"],
                target.get("name", ""),
            )
            coverages.append(coverage)
        
        return coverages
    
    def get_coverage_summary(self, coverages: List[TestCoverage]) -> Dict[str, Any]:
        """Get a summary of coverage across all targets.
        
        Args:
            coverages: List of test coverage analyses
            
        Returns:
            Coverage summary
        """
        total_targets = len(coverages)
        if total_targets == 0:
            return {}
        
        fully_covered = sum(1 for c in coverages if c.overall_coverage == "covered")
        partially_covered = sum(1 for c in coverages if c.overall_coverage == "partially_covered")
        not_covered = sum(1 for c in coverages if c.overall_coverage == "not_covered")
        
        avg_coverage = sum(c.coverage_percentage for c in coverages) / total_targets
        
        all_missing = []
        for coverage in coverages:
            all_missing.extend(coverage.missing_scenarios)
        
        # Count missing scenario types
        missing_counts = {}
        for missing in all_missing:
            missing_counts[missing] = missing_counts.get(missing, 0) + 1
        
        return {
            "total_targets": total_targets,
            "fully_covered": fully_covered,
            "partially_covered": partially_covered,
            "not_covered": not_covered,
            "average_coverage_percentage": avg_coverage,
            "missing_scenario_counts": missing_counts,
        }

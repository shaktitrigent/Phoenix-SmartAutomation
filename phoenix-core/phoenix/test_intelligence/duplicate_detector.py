"""Duplicate Detector - Semantic Duplicate Test Detection (Priority 23).

This module detects duplicate or semantically equivalent test scenarios
to prevent redundant test generation.

Completely generic - no product-specific rules.
"""

from __future__ import annotations

import logging
from typing import Any, Dict, List, Optional, Set
from datetime import datetime, timezone
import difflib

from phoenix.test_intelligence.models import (
    TestScenario,
    QualityIssue,
    QualityIssueType,
)

logger = logging.getLogger(__name__)


class DuplicateDetector:
    """Semantic duplicate detector for test scenarios.
    
    This detector identifies:
    - Exact duplicates
    - Semantic duplicates (same intent, different wording)
    - Near-duplicates (minor variations)
    
    Uses semantic analysis, not just string comparison.
    
    Completely generic - no product-specific rules.
    """
    
    def __init__(self, similarity_threshold: float = 0.85):
        """Initialize the duplicate detector.
        
        Args:
            similarity_threshold: Threshold for considering scenarios as duplicates (0-1)
        """
        self.similarity_threshold = similarity_threshold
        logger.info(f"[DUPLICATE DETECTOR] Initialized with threshold {similarity_threshold}")
    
    def detect_duplicates(
        self,
        scenarios: List[TestScenario],
    ) -> tuple[List[TestScenario], List[Dict[str, Any]]]:
        """Detect and remove duplicate scenarios.
        
        Args:
            scenarios: List of test scenarios to check
            
        Returns:
            Tuple of (deduplicated scenarios, duplicate info)
        """
        logger.info(f"[DUPLICATE DETECTOR] Checking {len(scenarios)} scenarios for duplicates")
        
        deduplicated = []
        duplicate_info = []
        seen_scenarios: List[TestScenario] = []
        
        for scenario in scenarios:
            is_duplicate = False
            duplicate_of = None
            similarity = 0.0
            
            # Check against already seen scenarios
            for seen in seen_scenarios:
                similarity = self._calculate_semantic_similarity(scenario, seen)
                
                if similarity >= self.similarity_threshold:
                    is_duplicate = True
                    duplicate_of = seen.scenario_id
                    break
            
            if is_duplicate:
                # Mark as duplicate
                scenario.is_duplicate = True
                scenario.duplicate_of = duplicate_of
                
                duplicate_info.append({
                    "scenario_id": scenario.scenario_id,
                    "duplicate_of": duplicate_of,
                    "similarity": similarity,
                    "title": scenario.title,
                })
                
                logger.info(f"[DUPLICATE DETECTOR] Found duplicate: {scenario.scenario_id} -> {duplicate_of} ({similarity:.2f})")
            else:
                # Keep scenario
                deduplicated.append(scenario)
                seen_scenarios.append(scenario)
        
        logger.info(f"[DUPLICATE DETECTOR] Removed {len(duplicate_info)} duplicates, kept {len(deduplicated)}")
        
        return deduplicated, duplicate_info
    
    def _calculate_semantic_similarity(
        self,
        scenario1: TestScenario,
        scenario2: TestScenario,
    ) -> float:
        """Calculate semantic similarity between two scenarios.
        
        Uses multiple factors:
        - Title similarity
        - Purpose similarity
        - Steps similarity
        - Component overlap
        - Flow overlap
        - Scenario type match
        
        Returns:
            Similarity score (0-1)
        """
        similarities = []
        
        # Title similarity (weighted higher)
        title_sim = self._string_similarity(scenario1.title, scenario2.title)
        similarities.append(("title", title_sim, 0.3))
        
        # Purpose similarity
        purpose_sim = self._string_similarity(scenario1.purpose, scenario2.purpose)
        similarities.append(("purpose", purpose_sim, 0.25))
        
        # Steps similarity
        steps_sim = self._steps_similarity(scenario1.steps, scenario2.steps)
        similarities.append(("steps", steps_sim, 0.2))
        
        # Component overlap
        component_overlap = self._set_overlap_similarity(
            scenario1.related_components,
            scenario2.related_components,
        )
        similarities.append(("components", component_overlap, 0.1))
        
        # Flow overlap
        flow_overlap = self._set_overlap_similarity(
            scenario1.related_flows,
            scenario2.related_flows,
        )
        similarities.append(("flows", flow_overlap, 0.1))
        
        # Scenario type match
        type_match = 1.0 if scenario1.scenario_type == scenario2.scenario_type else 0.5
        similarities.append(("type", type_match, 0.05))
        
        # Calculate weighted average
        total_weight = sum(weight for _, _, weight in similarities)
        weighted_sum = sum(sim * weight for _, sim, weight in similarities)
        
        return weighted_sum / total_weight if total_weight > 0 else 0.0
    
    def _string_similarity(self, str1: str, str2: str) -> float:
        """Calculate string similarity using difflib."""
        if not str1 or not str2:
            return 0.0
        
        # Normalize strings
        str1_normalized = self._normalize_string(str1)
        str2_normalized = self._normalize_string(str2)
        
        # Use sequence matcher
        matcher = difflib.SequenceMatcher(None, str1_normalized, str2_normalized)
        return matcher.ratio()
    
    def _normalize_string(self, s: str) -> str:
        """Normalize string for comparison."""
        # Convert to lowercase
        s = s.lower()
        # Remove extra whitespace
        s = " ".join(s.split())
        # Remove common stop words for test scenarios
        stop_words = ["verify", "test", "check", "ensure", "that", "the", "a", "an"]
        words = s.split()
        words = [w for w in words if w not in stop_words]
        return " ".join(words)
    
    def _steps_similarity(self, steps1: List[str], steps2: List[str]) -> float:
        """Calculate similarity between step lists."""
        if not steps1 or not steps2:
            return 0.0
        
        # Compare step counts
        if len(steps1) != len(steps2):
            return 0.5  # Partial match if different lengths
        
        # Compare each step
        step_similarities = []
        for step1, step2 in zip(steps1, steps2):
            step_sim = self._string_similarity(step1, step2)
            step_similarities.append(step_sim)
        
        return sum(step_similarities) / len(step_similarities)
    
    def _set_overlap_similarity(self, set1: List[str], set2: List[str]) -> float:
        """Calculate overlap similarity between two sets."""
        if not set1 or not set2:
            return 0.0
        
        set1_set = set(set1)
        set2_set = set(set2)
        
        if not set1_set or not set2_set:
            return 0.0
        
        # Jaccard similarity
        intersection = len(set1_set & set2_set)
        union = len(set1_set | set2_set)
        
        return intersection / union if union > 0 else 0.0
    
    def find_quality_issues(
        self,
        scenarios: List[TestScenario],
    ) -> List[QualityIssue]:
        """Find quality issues related to duplicates.
        
        Args:
            scenarios: List of test scenarios
            
        Returns:
            List of quality issues
        """
        issues = []
        
        # Check for duplicates
        _, duplicate_info = self.detect_duplicates(scenarios)
        
        for dup_info in duplicate_info:
            issue = QualityIssue(
                issue_type=QualityIssueType.DUPLICATE_SCENARIO,
                severity="medium",
                description=f"Scenario is a duplicate of {dup_info['duplicate_of']}",
                affected_field="scenario",
                recommendation="Remove this duplicate scenario or merge with the original",
                evidence=[
                    f"Similarity: {dup_info['similarity']:.2f}",
                    f"Duplicate of: {dup_info['duplicate_of']}",
                ],
            )
            issues.append(issue)
        
        return issues
    
    def get_duplicate_groups(
        self,
        scenarios: List[TestScenario],
    ) -> List[List[TestScenario]]:
        """Group scenarios by similarity.
        
        Args:
            scenarios: List of test scenarios
            
        Returns:
            List of scenario groups (each group contains similar scenarios)
        """
        groups = []
        ungrouped = scenarios.copy()
        
        while ungrouped:
            # Start a new group with the first ungrouped scenario
            current = ungrouped.pop(0)
            group = [current]
            
            # Find similar scenarios
            i = 0
            while i < len(ungrouped):
                scenario = ungrouped[i]
                similarity = self._calculate_semantic_similarity(current, scenario)
                
                if similarity >= self.similarity_threshold:
                    group.append(scenario)
                    ungrouped.pop(i)
                else:
                    i += 1
            
            if len(group) > 1:
                groups.append(group)
        
        return groups

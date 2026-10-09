"""Enterprise Execution Reporter - Comprehensive execution reporting.

This module implements enterprise execution reporting with comprehensive
metrics and recommendations.

Priority 25: Universal Autonomous Execution Intelligence
"""

from __future__ import annotations

import logging
import uuid
from typing import Any, Dict, List, Optional
from datetime import datetime, timezone

from phoenix.execution_intelligence.models import EnterpriseExecutionReport

logger = logging.getLogger(__name__)


class EnterpriseExecutionReporter:
    """Enterprise execution reporter for comprehensive reporting.
    
    Generates reports with:
    - Executive summary
    - Test statistics
    - Step statistics
    - Locator statistics
    - Healing statistics
    - Runtime statistics
    - Intelligence statistics
    - Regression detection
    - Runtime learning
    - Recommendations
    """
    
    def __init__(self):
        logger.info("EnterpriseExecutionReporter initialized")
    
    def generate_report(
        self,
        execution_id: str,
        automation_id: str,
        test_name: str,
        project_name: str,
        status: str,
        pre_validation: Optional[Any] = None,
        execution_result: Optional[Dict[str, Any]] = None,
        action_evidence: Optional[List[Any]] = None,
        healing_sessions: Optional[List[Any]] = None,
    ) -> EnterpriseExecutionReport:
        """Generate enterprise execution report.
        
        Args:
            execution_id: Execution identifier
            automation_id: Automation identifier
            test_name: Test name
            project_name: Project name
            status: Overall status
            pre_validation: Pre-execution validation
            execution_result: Execution result data
            action_evidence: Action execution evidence
            healing_sessions: Healing session data
            
        Returns:
            EnterpriseExecutionReport with comprehensive metrics
        """
        report_id = f"REPORT-{uuid.uuid4().hex[:8].upper()}"
        
        # Extract statistics from execution result
        execution_result = execution_result or {}
        
        # Calculate statistics
        test_stats = self._calculate_test_statistics(status, execution_result)
        step_stats = self._calculate_step_statistics(action_evidence)
        locator_stats = self._calculate_locator_statistics(action_evidence)
        healing_stats = self._calculate_healing_statistics(healing_sessions)
        runtime_stats = self._calculate_runtime_statistics(execution_result)
        intelligence_stats = self._calculate_intelligence_statistics(execution_result)
        
        # Generate recommendations
        recommendations = self._generate_recommendations(
            status, test_stats, step_stats, healing_stats
        )
        
        report = EnterpriseExecutionReport(
            report_id=report_id,
            execution_id=execution_id,
            project_name=project_name,
            test_name=test_name,
            status=status,
            total_duration_ms=runtime_stats.get("execution_time_ms", 0),
            recovery_status="RECOVERED" if healing_stats.get("healing_recoveries", healing_stats["recoveries"]) > 0 else "NONE",
            
            # Test Statistics
            total_tests=test_stats["total"],
            passed_tests=test_stats["passed"],
            failed_tests=test_stats["failed"],
            recovered_tests=test_stats["recovered"],
            skipped_tests=test_stats["skipped"],
            
            # Step Statistics
            total_actions=step_stats["total"],
            successful_actions=step_stats["successful"],
            failed_actions=step_stats["failed"],
            healed_actions=step_stats["healed"],
            
            # Locator Statistics
            total_locators=locator_stats["total"],
            successful_locators=locator_stats["successful"],
            failed_locators=locator_stats["failed"],
            average_locator_confidence=locator_stats["avg_confidence"],
            
            # Healing Statistics
            healing_attempts=healing_stats["attempts"],
            healing_recoveries=healing_stats.get("healing_recoveries", healing_stats["recoveries"]),
            healing_failures=healing_stats["failures"],
            healing_success_rate=healing_stats["success_rate"],
            
            # Runtime Statistics
            execution_time_ms=runtime_stats.get("execution_time_ms", 0),
            time_saved_ms=runtime_stats.get("time_saved_ms", 0),
            dom_reuse_count=runtime_stats.get("dom_reuse", 0),
            locator_reuse_count=runtime_stats.get("locator_reuse", 0),
            mcp_calls_saved=runtime_stats.get("mcp_calls_saved", 0),
            
            # Intelligence Statistics
            semantic_confidence=intelligence_stats.get("semantic", 0),
            flow_confidence=intelligence_stats.get("flow", 0),
            execution_confidence=intelligence_stats.get("execution", 0),
            healing_confidence=intelligence_stats.get("healing", 0),
            
            # Recommendations
            recommendations=recommendations,
            
            # Evidence
            execution_evidence={
                "pre_validation": pre_validation.dict() if pre_validation else None,
                "execution_result": execution_result,
            },
        )
        
        logger.info(
            f"[REPORTER] Generated report {report_id} for execution {execution_id}"
        )
        
        return report
    
    def _calculate_test_statistics(
        self,
        status: str,
        execution_result: Dict[str, Any],
    ) -> Dict[str, int]:
        """Calculate test statistics."""
        total = 1
        passed = 1 if status == "PASSED" else 0
        failed = 1 if status == "FAILED" else 0
        recovered = 1 if status == "RECOVERED" else 0
        skipped = 0
        
        return {
            "total": total,
            "passed": passed,
            "failed": failed,
            "recovered": recovered,
            "skipped": skipped,
        }
    
    def _calculate_step_statistics(
        self,
        action_evidence: Optional[List[Any]],
    ) -> Dict[str, int]:
        """Calculate step statistics."""
        if not action_evidence:
            return {"total": 0, "successful": 0, "failed": 0, "healed": 0}
        
        total = len(action_evidence)
        successful = len([a for a in action_evidence if a.result == "success"])
        failed = len([a for a in action_evidence if a.result == "failure"])
        healed = len([a for a in action_evidence if a.result == "recovered"])
        
        return {
            "total": total,
            "successful": successful,
            "failed": failed,
            "healed": healed,
        }
    
    def _calculate_locator_statistics(
        self,
        action_evidence: Optional[List[Any]],
    ) -> Dict[str, Any]:
        """Calculate locator statistics."""
        if not action_evidence:
            return {"total": 0, "successful": 0, "failed": 0, "avg_confidence": 0.0}
        
        total = len([a for a in action_evidence if a.locator])
        successful = len([a for a in action_evidence if a.locator and a.result == "success"])
        failed = len([a for a in action_evidence if a.locator and a.result == "failure"])
        
        confidences = [a.locator_confidence for a in action_evidence if a.locator_confidence > 0]
        avg_confidence = sum(confidences) / len(confidences) if confidences else 0.0
        
        return {
            "total": total,
            "successful": successful,
            "failed": failed,
            "avg_confidence": avg_confidence * 100,
        }
    
    def _calculate_healing_statistics(
        self,
        healing_sessions: Optional[List[Any]],
    ) -> Dict[str, Any]:
        """Calculate healing statistics."""
        if not healing_sessions:
            return {"attempts": 0, "recoveries": 0, "failures": 0, "success_rate": 0.0}
        
        attempts = sum(len(s.attempts) for s in healing_sessions)
        recoveries = len([s for s in healing_sessions if s.final_result == "RECOVERED"])
        failures = len([s for s in healing_sessions if s.final_result == "FAILED"])
        
        success_rate = (recoveries / len(healing_sessions)) * 100 if healing_sessions else 0.0
        
        return {
            "attempts": attempts,
            "recoveries": recoveries,
            "failures": failures,
            "success_rate": success_rate,
            "healing_recoveries": recoveries,  # Add for model compatibility
        }
    
    def _calculate_runtime_statistics(
        self,
        execution_result: Dict[str, Any],
    ) -> Dict[str, Any]:
        """Calculate runtime statistics."""
        return {
            "execution_time_ms": execution_result.get("duration_ms", 0),
            "time_saved_ms": execution_result.get("time_saved_ms", 0),
            "dom_reuse": execution_result.get("dom_reuse", 0),
            "locator_reuse": execution_result.get("locator_reuse", 0),
            "mcp_calls_saved": execution_result.get("mcp_calls_saved", 0),
        }
    
    def _calculate_intelligence_statistics(
        self,
        execution_result: Dict[str, Any],
    ) -> Dict[str, float]:
        """Calculate intelligence statistics."""
        return {
            "semantic": execution_result.get("semantic_confidence", 0.0),
            "flow": execution_result.get("flow_confidence", 0.0),
            "execution": execution_result.get("execution_confidence", 0.0),
            "healing": execution_result.get("healing_confidence", 0.0),
        }
    
    def _generate_recommendations(
        self,
        status: str,
        test_stats: Dict[str, int],
        step_stats: Dict[str, int],
        healing_stats: Dict[str, Any],
    ) -> List[str]:
        """Generate recommendations based on execution results."""
        recommendations = []
        
        if status == "FAILED":
            recommendations.append("Review failure classification and root cause")
        
        if healing_stats["success_rate"] < 0.7:
            recommendations.append("Healing success rate low - review healing strategies")
        
        if step_stats["failed"] > 0:
            recommendations.append(f"Review {step_stats['failed']} failed step(s)")
        
        if test_stats["recovered"] > 0:
            recommendations.append("Test recovered - validate healing effectiveness")
        
        if not recommendations:
            recommendations.append("Execution successful - no action needed")
        
        return recommendations

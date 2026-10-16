"""Business Risk Modeling - Priority 31.

This module implements generic business risk modeling that infers business importance
from semantic signals without application-specific knowledge.

Priority 31: Universal Autonomous Test Governance + Risk Intelligence
"""

from __future__ import annotations

import logging
import re
from typing import Any, Dict, List, Optional
from enum import Enum

from phoenix.risk_intelligence.models import BusinessCriticality

logger = logging.getLogger(__name__)


class BusinessSignal(Enum):
    """Semantic business signals for risk assessment."""
    AUTHENTICATION = "authentication"
    PAYMENT = "payment"
    ACCOUNT_MANAGEMENT = "account_management"
    DATA_CREATION = "data_creation"
    DATA_DELETION = "data_deletion"
    DATA_MODIFICATION = "data_modification"
    PERMISSIONS = "permissions"
    CONFIGURATION = "configuration"
    SEARCH = "search"
    REPORTING = "reporting"
    FILE_UPLOAD = "file_upload"
    WORKFLOW_APPROVAL = "workflow_approval"
    STATE_TRANSITION = "state_transition"
    EXPORT = "export"
    IMPORT = "import"
    INTEGRATION = "integration"
    NOTIFICATION = "notification"
    AUDIT = "audit"


class BusinessRiskModeler:
    """Infers business importance from semantic signals.
    
    This modeler:
    - Analyzes component semantics
    - Analyzes flow semantics
    - Identifies business signals
    - Infers business criticality
    - Maintains application-agnostic rules
    """
    
    def __init__(self):
        """Initialize business risk modeler."""
        # Semantic signal patterns (application-agnostic)
        self.critical_patterns = [
            r"login|signin|auth|password|credential",
            r"payment|checkout|purchase|billing|invoice",
            r"delete|remove|destroy",
            r"permission|role|access|privilege",
            r"admin|administrator|root",
            r"security|encrypt|decrypt",
            r"config|setting|preference",
        ]
        
        self.high_patterns = [
            r"create|add|new|insert",
            r"update|edit|modify|change",
            r"upload|import",
            r"approval|review|workflow",
            r"export|download",
            r"account|profile|user",
        ]
        
        self.medium_patterns = [
            r"search|find|filter|query",
            r"view|display|show|list",
            r"report|dashboard|analytics",
            r"notification|message|alert",
        ]
        
        self.low_patterns = [
            r"help|faq|support",
            r"about|contact",
            r"feedback|comment",
        ]
        
        # Signal to criticality mapping
        self.signal_criticality = {
            BusinessSignal.AUTHENTICATION: BusinessCriticality.CRITICAL,
            BusinessSignal.PAYMENT: BusinessCriticality.CRITICAL,
            BusinessSignal.ACCOUNT_MANAGEMENT: BusinessCriticality.HIGH,
            BusinessSignal.DATA_DELETION: BusinessCriticality.CRITICAL,
            BusinessSignal.DATA_MODIFICATION: BusinessCriticality.HIGH,
            BusinessSignal.PERMISSIONS: BusinessCriticality.CRITICAL,
            BusinessSignal.CONFIGURATION: BusinessCriticality.HIGH,
            BusinessSignal.DATA_CREATION: BusinessCriticality.MEDIUM,
            BusinessSignal.FILE_UPLOAD: BusinessCriticality.HIGH,
            BusinessSignal.WORKFLOW_APPROVAL: BusinessCriticality.HIGH,
            BusinessSignal.STATE_TRANSITION: BusinessCriticality.HIGH,
            BusinessSignal.EXPORT: BusinessCriticality.MEDIUM,
            BusinessSignal.IMPORT: BusinessCriticality.HIGH,
            BusinessSignal.INTEGRATION: BusinessCriticality.HIGH,
            BusinessSignal.SEARCH: BusinessCriticality.MEDIUM,
            BusinessSignal.REPORTING: BusinessCriticality.MEDIUM,
            BusinessSignal.NOTIFICATION: BusinessCriticality.LOW,
            BusinessSignal.AUDIT: BusinessCriticality.HIGH,
        }
        
        logger.info("[BUSINESS RISK MODELER] Initialized")
    
    def infer_component_criticality(
        self,
        component: Dict[str, Any],
    ) -> BusinessCriticality:
        """Infer business criticality of a component.
        
        Args:
            component: Component data with semantic information
            
        Returns:
            Inferred business criticality
        """
        # Get semantic signals from component
        text = self._extract_component_text(component)
        
        # Analyze signals
        signals = self._detect_business_signals(text)
        
        # Infer criticality from signals
        if not signals:
            return BusinessCriticality.MEDIUM
        
        # Get highest criticality from detected signals
        max_criticality = BusinessCriticality.LOW
        for signal in signals:
            signal_criticality = self.signal_criticality.get(signal, BusinessCriticality.MEDIUM)
            if self._compare_criticality(signal_criticality, max_criticality) > 0:
                max_criticality = signal_criticality
        
        logger.debug(
            f"[BUSINESS RISK MODELER] Component criticality: {max_criticality.value} "
            f"(signals: {[s.value for s in signals]})"
        )
        
        return max_criticality
    
    def infer_flow_criticality(
        self,
        flow: Dict[str, Any],
    ) -> BusinessCriticality:
        """Infer business criticality of a flow.
        
        Args:
            flow: Flow data with semantic information
            
        Returns:
            Inferred business criticality
        """
        # Get semantic signals from flow
        text = self._extract_flow_text(flow)
        
        # Analyze signals
        signals = self._detect_business_signals(text)
        
        # Infer criticality from signals
        if not signals:
            return BusinessCriticality.MEDIUM
        
        # Get highest criticality from detected signals
        max_criticality = BusinessCriticality.LOW
        for signal in signals:
            signal_criticality = self.signal_criticality.get(signal, BusinessCriticality.MEDIUM)
            if self._compare_criticality(signal_criticality, max_criticality) > 0:
                max_criticality = signal_criticality
        
        logger.debug(
            f"[BUSINESS RISK MODELER] Flow criticality: {max_criticality.value} "
            f"(signals: {[s.value for s in signals]})"
        )
        
        return max_criticality
    
    def _extract_component_text(self, component: Dict[str, Any]) -> str:
        """Extract text from component for analysis.
        
        Args:
            component: Component data
            
        Returns:
            Extracted text
        """
        text_parts = []
        
        # Add component text
        if "text" in component:
            text_parts.append(component["text"])
        
        # Add component tag
        if "tag" in component:
            text_parts.append(component["tag"])
        
        # Add component ID
        if "id" in component:
            text_parts.append(component["id"])
        
        # Add component class
        if "class" in component:
            text_parts.append(component["class"])
        
        # Add accessible name if available
        if "accessible_name" in component:
            text_parts.append(component["accessible_name"])
        
        # Add role if available
        if "role" in component:
            text_parts.append(component["role"])
        
        return " ".join(text_parts).lower()
    
    def _extract_flow_text(self, flow: Dict[str, Any]) -> str:
        """Extract text from flow for analysis.
        
        Args:
            flow: Flow data
            
        Returns:
            Extracted text
        """
        text_parts = []
        
        # Add flow name
        if "name" in flow:
            text_parts.append(flow["name"])
        
        # Add flow description
        if "description" in flow:
            text_parts.append(flow["description"])
        
        # Add flow steps
        if "steps" in flow:
            for step in flow["steps"]:
                if "action" in step:
                    text_parts.append(step["action"])
                if "target" in step:
                    text_parts.append(step["target"])
        
        return " ".join(text_parts).lower()
    
    def _detect_business_signals(self, text: str) -> List[BusinessSignal]:
        """Detect business signals from text.
        
        Args:
            text: Text to analyze
            
        Returns:
            List of detected business signals
        """
        detected_signals = []
        
        # Check each signal pattern
        for signal in BusinessSignal:
            signal_name = signal.value
            # Create pattern from signal name
            pattern = signal_name.replace("_", r"[_\s-]")
            if re.search(pattern, text, re.IGNORECASE):
                detected_signals.append(signal)
        
        return detected_signals
    
    def _compare_criticality(
        self,
        c1: BusinessCriticality,
        c2: BusinessCriticality,
    ) -> int:
        """Compare two criticality levels.
        
        Args:
            c1: First criticality
            c2: Second criticality
            
        Returns:
            -1 if c1 < c2, 0 if equal, 1 if c1 > c2
        """
        criticality_order = {
            BusinessCriticality.CRITICAL: 4,
            BusinessCriticality.HIGH: 3,
            BusinessCriticality.MEDIUM: 2,
            BusinessCriticality.LOW: 1,
        }
        
        return criticality_order[c1] - criticality_order[c2]
    
    def analyze_component_business_signals(
        self,
        component: Dict[str, Any],
    ) -> Dict[str, Any]:
        """Analyze business signals for a component.
        
        Args:
            component: Component data
            
        Returns:
            Business signal analysis
        """
        text = self._extract_component_text(component)
        signals = self._detect_business_signals(text)
        
        return {
            "component_id": component.get("id", ""),
            "detected_signals": [s.value for s in signals],
            "criticality": self.infer_component_criticality(component).value,
            "confidence": min(1.0, len(signals) * 0.3),
        }
    
    def analyze_flow_business_signals(
        self,
        flow: Dict[str, Any],
    ) -> Dict[str, Any]:
        """Analyze business signals for a flow.
        
        Args:
            flow: Flow data
            
        Returns:
            Business signal analysis
        """
        text = self._extract_flow_text(flow)
        signals = self._detect_business_signals(text)
        
        return {
            "flow_id": flow.get("flow_id", ""),
            "detected_signals": [s.value for s in signals],
            "criticality": self.infer_flow_criticality(flow).value,
            "confidence": min(1.0, len(signals) * 0.3),
        }

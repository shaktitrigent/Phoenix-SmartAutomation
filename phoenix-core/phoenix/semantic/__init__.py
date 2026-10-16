"""Semantic Understanding Module - Universal Application Understanding.

This module provides generic, application-agnostic understanding of web applications
through semantic page classification, UI component analysis, business intent detection,
and navigation structure analysis.

Phoenix should never recognize applications by product name (OrangeHRM, Jira, Salesforce, etc.).
Instead, it must understand applications semantically using reusable concepts.
"""

from __future__ import annotations

from phoenix.semantic.models import (
    SemanticPage,
    SemanticComponent,
    BusinessIntent,
    NavigationContext,
    PageType,
    ComponentType,
    BusinessIntentType,
)
from phoenix.semantic.page_classifier import SemanticPageClassifier
from phoenix.semantic.component_analyzer import UIComponentAnalyzer
from phoenix.semantic.intent_detector import BusinessIntentDetector
from phoenix.semantic.navigation_analyzer import NavigationStructureAnalyzer
from phoenix.semantic.semantic_integrator import SemanticIntegrator

__all__ = [
    "SemanticPage",
    "SemanticComponent",
    "BusinessIntent",
    "NavigationContext",
    "PageType",
    "ComponentType",
    "BusinessIntentType",
    "SemanticPageClassifier",
    "UIComponentAnalyzer",
    "BusinessIntentDetector",
    "NavigationStructureAnalyzer",
    "SemanticIntegrator",
]

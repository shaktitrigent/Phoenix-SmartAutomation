"""Priority 23 Integration Tests - Full Pipeline Integration.

This test verifies the complete integration of Priority 23 with
Priorities 20, 21, and 22, ensuring the full test intelligence pipeline works.
"""

import pytest
from phoenix.test_intelligence.models import (
    TestScenario,
    TestScenarioType,
    TestGenerationRequest,
    TestGenerationResponse,
)
from phoenix.test_intelligence.scenario_generator import TestScenarioGenerator
from phoenix.test_intelligence.scenario_reasoning import TestScenarioReasoning
from phoenix.test_intelligence.coverage_intelligence import CoverageIntelligence
from phoenix.test_intelligence.duplicate_detector import DuplicateDetector
from phoenix.test_intelligence.test_prioritizer import TestPrioritizer
from phoenix.test_intelligence.quality_validator import AITestValidator
from phoenix.test_intelligence.confidence_calculator import ConfidenceCalculator
from phoenix.test_intelligence.runtime_learning import TestRuntimeLearning
from phoenix.test_intelligence.healing_integration import TestHealingIntegration
from phoenix.semantic.models import (
    SemanticComponent,
    ComponentType,
    PageType,
    BusinessIntentType,
)
from phoenix.flow_detection.models import (
    BusinessFlow,
    FlowType,
)


class TestPriority23FullIntegration:
    """Test full Priority 23 integration."""
    
    def test_complete_pipeline_integration(self):
        """Test the complete test intelligence pipeline from generation to validation."""
        # Initialize all components
        generator = TestScenarioGenerator()
        reasoning = TestScenarioReasoning()
        coverage = CoverageIntelligence()
        duplicate_detector = DuplicateDetector()
        prioritizer = TestPrioritizer()
        validator = AITestValidator()
        calculator = ConfidenceCalculator()
        learning = TestRuntimeLearning(base_dir="test_runtime_integration")
        healing = TestHealingIntegration()
        
        # Create a realistic test context
        flows = [
            BusinessFlow(
                flow_id="auth_flow",
                flow_type=FlowType.AUTHENTICATION,
                flow_name="User Authentication",
            ),
            BusinessFlow(
                flow_id="search_flow",
                flow_type=FlowType.SEARCH_FLOW,
                flow_name="Product Search",
            ),
        ]
        
        components = [
            SemanticComponent(
                component_id="username_field",
                component_type=ComponentType.TEXT_FIELD,
                semantic_purpose="username_input",
                name="username",
                validation_rules=[
                    {"field": "username", "validation_type": "required", "confidence": 0.9},
                ],
            ),
            SemanticComponent(
                component_id="password_field",
                component_type=ComponentType.TEXT_FIELD,
                semantic_purpose="password_input",
                name="password",
                validation_rules=[
                    {"field": "password", "validation_type": "required", "confidence": 0.9},
                ],
            ),
            SemanticComponent(
                component_id="login_button",
                component_type=ComponentType.BUTTON,
                semantic_purpose="login_trigger",
                text_content="Login",
            ),
            SemanticComponent(
                component_id="search_input",
                component_type=ComponentType.TEXT_FIELD,
                semantic_purpose="search_input",
                name="search",
                placeholder="Search products...",
            ),
            SemanticComponent(
                component_id="search_button",
                component_type=ComponentType.BUTTON,
                semantic_purpose="search_trigger",
                text_content="Search",
            ),
        ]
        
        # Step 1: Generate scenarios
        request = TestGenerationRequest(
            business_flow_id="auth_flow",
            scenario_types=[TestScenarioType.POSITIVE, TestScenarioType.NEGATIVE, TestScenarioType.VALIDATION],
            max_scenarios=20,
            enable_duplicate_detection=True,
            enable_quality_validation=True,
            enable_prioritization=True,
        )
        
        response = generator.generate_scenarios(
            request,
            semantic_components=components,
            business_flows=flows,
            page_type=PageType.AUTHENTICATION_SCREEN,
            business_intent=BusinessIntentType.AUTHENTICATION,
        )
        
        assert len(response.scenarios) > 0
        assert response.total_generated > 0
        
        # Step 2: Remove duplicates
        deduplicated_scenarios, duplicate_info = duplicate_detector.detect_duplicates(response.scenarios)
        
        assert len(deduplicated_scenarios) <= len(response.scenarios)
        
        # Step 3: Calculate confidence
        for scenario in deduplicated_scenarios:
            calculator.calculate_confidence(
                scenario,
                dom_component_count=len(components),
                business_flow_count=len(flows),
                validation_rule_count=3,
                runtime_observation_count=0,
            )
        
        # Step 4: Prioritize scenarios
        prioritized_scenarios = prioritizer.prioritize_scenarios(deduplicated_scenarios)
        
        assert len(prioritized_scenarios) == len(deduplicated_scenarios)
        
        # Step 5: Validate scenarios
        valid_scenarios, rejected_scenarios, validation_stats = validator.validate_scenarios(
            prioritized_scenarios,
            available_components=components,
            available_flows=flows,
        )
        
        assert validation_stats["total"] > 0
        assert validation_stats["valid"] >= 0
        assert validation_stats["rejected"] >= 0
        
        # Step 6: Analyze coverage
        coverage_results = []
        for flow in flows:
            coverage_result = coverage.analyze_coverage(
                valid_scenarios,
                target_id=flow.flow_id,
                target_type="flow",
                target_name=flow.flow_name,
            )
            coverage_results.append(coverage_result)
        
        assert len(coverage_results) == len(flows)
        
        # Step 7: Test healing integration
        if valid_scenarios:
            test_scenario = valid_scenarios[0]
            healing_context = healing.analyze_failure_for_healing(
                test_scenario,
                failure_type="locator_failure",
                failure_reason="Element not found",
                failing_step_index=0,
                available_components=components,
                available_flows=flows,
            )
            
            assert healing_context.scenario_id == test_scenario.scenario_id
            assert len(healing_context.recovery_strategies) > 0
        
        # Step 8: Test runtime learning
        if valid_scenarios:
            from phoenix.test_intelligence.models import TestExecutionFeedback
            
            feedback = TestExecutionFeedback(
                scenario_id=valid_scenarios[0].scenario_id,
                execution_id="test_exec_1",
                success=True,
                execution_time_ms=1500.0,
                observed_behavior={"component_responsive": True},
                correct_assumptions=["Locator is stable"],
                incorrect_assumptions=[],
                quality_adequate=True,
            )
            
            learning.record_execution_feedback(feedback)
            
            success_rate = learning.get_scenario_success_rate(valid_scenarios[0].scenario_id)
            assert success_rate == 1.0
        
        # Verify the pipeline produced valid results
        assert len(valid_scenarios) > 0 or len(rejected_scenarios) > 0
        
        print(f"\n=== Priority 23 Integration Test Results ===")
        print(f"Scenarios Generated: {response.total_generated}")
        print(f"Duplicates Removed: {len(duplicate_info)}")
        print(f"Valid Scenarios: {validation_stats['valid']}")
        print(f"Rejected Scenarios: {validation_stats['rejected']}")
        print(f"Average Quality Score: {validation_stats['average_quality_score']:.1f}")
        print(f"Coverage Results: {len(coverage_results)} flows analyzed")
    
    def test_integration_with_priority20_semantic_understanding(self):
        """Test integration with Priority 20 semantic understanding."""
        from phoenix.semantic.semantic_integrator import SemanticIntegrator
        
        # This test verifies that Priority 23 can use Priority 20's semantic understanding
        semantic_integrator = SemanticIntegrator(
            base_dir="test_runtime",
            enable_page_classification=True,
            enable_component_analysis=True,
        )
        
        assert semantic_integrator is not None
        
        # Test that test intelligence can work with semantic components
        generator = TestScenarioGenerator()
        
        # Create semantic components (as would come from Priority 20)
        components = [
            SemanticComponent(
                component_id="test_component",
                component_type=ComponentType.TEXT_FIELD,
                page_type="authentication_screen",
                business_intent="authentication",
            ),
        ]
        
        # Generate scenarios should work with semantic components
        request = TestGenerationRequest(max_scenarios=5)
        response = generator.generate_scenarios(
            request,
            semantic_components=components,
        )
        
        assert response is not None
    
    def test_integration_with_priority21_flow_detection(self):
        """Test integration with Priority 21 flow detection."""
        # This test verifies that Priority 23 can use Priority 21's flow detection
        generator = TestScenarioGenerator()
        
        # Create business flows (as would come from Priority 21)
        flows = [
            BusinessFlow(
                flow_id="test_flow",
                flow_type=FlowType.AUTHENTICATION,
                flow_name="Test Flow",
            ),
        ]
        
        # Generate scenarios should work with business flows
        request = TestGenerationRequest(max_scenarios=5)
        response = generator.generate_scenarios(
            request,
            business_flows=flows,
        )
        
        assert response is not None
        assert len(response.scenarios) > 0
    
    def test_integration_with_priority22_component_intelligence(self):
        """Test integration with Priority 22 component intelligence."""
        # This test verifies that Priority 23 can use Priority 22's component intelligence
        generator = TestScenarioGenerator()
        
        # Create components with Priority 22 intelligence
        components = [
            SemanticComponent(
                component_id="test_component",
                component_type=ComponentType.TEXT_FIELD,
                semantic_purpose="username_input",
                purpose_confidence=0.9,
                validation_rules=[
                    {"field": "username", "validation_type": "required", "confidence": 0.95},
                ],
                locator_candidates=[
                    {
                        "strategy": "role",
                        "locator": "get_by_role('textbox', name='Username')",
                        "confidence": 0.9,
                    },
                ],
            ),
        ]
        
        # Generate scenarios should work with enhanced components
        request = TestGenerationRequest(max_scenarios=5)
        response = generator.generate_scenarios(
            request,
            semantic_components=components,
        )
        
        assert response is not None
        assert len(response.scenarios) > 0
    
    def test_cross_priority_coverage_analysis(self):
        """Test coverage analysis across flows and components."""
        coverage = CoverageIntelligence()
        
        # Create scenarios covering different aspects
        scenarios = [
            TestScenario(
                scenario_id="scenario_1",
                title="Auth positive",
                scenario_type=TestScenarioType.POSITIVE,
                related_flows=["auth_flow"],
                related_components=["username", "password"],
            ),
            TestScenario(
                scenario_id="scenario_2",
                title="Auth negative",
                scenario_type=TestScenarioType.NEGATIVE,
                related_flows=["auth_flow"],
                related_components=["username", "password"],
            ),
            TestScenario(
                scenario_id="scenario_3",
                title="Search positive",
                scenario_type=TestScenarioType.POSITIVE,
                related_flows=["search_flow"],
                related_components=["search_input"],
            ),
        ]
        
        # Analyze flow coverage
        auth_coverage = coverage.analyze_coverage(
            scenarios,
            target_id="auth_flow",
            target_type="flow",
        )
        
        search_coverage = coverage.analyze_coverage(
            scenarios,
            target_id="search_flow",
            target_type="flow",
        )
        
        # Auth flow should have better coverage
        assert auth_coverage.positive_coverage == "covered"
        assert auth_coverage.negative_coverage == "covered"
        
        # Search flow should have basic coverage
        assert search_coverage.positive_coverage == "covered"
        assert search_coverage.negative_coverage == "not_covered"
    
    def test_end_to_end_scenario_generation(self):
        """Test end-to-end scenario generation with all components."""
        # Initialize all intelligence components
        generator = TestScenarioGenerator()
        reasoning = TestScenarioReasoning()
        duplicate_detector = DuplicateDetector()
        prioritizer = TestPrioritizer()
        validator = AITestValidator()
        
        # Create comprehensive context
        flows = [
            BusinessFlow(
                flow_id="crud_create",
                flow_type=FlowType.CRUD_CREATE,
                flow_name="Create User",
            ),
        ]
        
        components = [
            SemanticComponent(
                component_id="name_field",
                component_type=ComponentType.TEXT_FIELD,
                name="name",
                validation_rules=[
                    {"field": "name", "validation_type": "required", "confidence": 0.9},
                    {"field": "name", "validation_type": "min_length", "rule_value": "3", "confidence": 0.85},
                ],
            ),
            SemanticComponent(
                component_id="email_field",
                component_type=ComponentType.TEXT_FIELD,
                name="email",
                validation_rules=[
                    {"field": "email", "validation_type": "required", "confidence": 0.9},
                    {"field": "email", "validation_type": "email_format", "confidence": 0.95},
                ],
            ),
            SemanticComponent(
                component_id="submit_button",
                component_type=ComponentType.BUTTON,
                semantic_purpose="form_submit",
                text_content="Submit",
            ),
        ]
        
        # Generate using reasoning pipeline
        request = TestGenerationRequest(
            business_flow_id="crud_create",
            max_scenarios=15,
            enable_duplicate_detection=True,
            enable_quality_validation=True,
            enable_prioritization=True,
        )
        
        response = reasoning.reason_and_generate(
            request,
            user_story="User should be able to create a new account",
            requirements=["Name is required", "Email is required and must be valid"],
            semantic_components=components,
            business_flows=flows,
            page_type=PageType.CRUD_FORM,
            business_intent=BusinessIntentType.DATA_ENTRY,
        )
        
        assert len(response.scenarios) > 0
        
        # Process through pipeline
        deduplicated, _ = duplicate_detector.detect_duplicates(response.scenarios)
        prioritized = prioritizer.prioritize_scenarios(deduplicated)
        valid, rejected, stats = validator.validate_scenarios(prioritized)
        
        # Verify results
        assert stats["total"] > 0
        assert stats["average_quality_score"] >= 0.0
        
        print(f"\n=== End-to-End Generation Results ===")
        print(f"Generated: {stats['total']}")
        print(f"Valid: {stats['valid']}")
        print(f"Rejected: {stats['rejected']}")
        print(f"Avg Quality: {stats['average_quality_score']:.1f}")

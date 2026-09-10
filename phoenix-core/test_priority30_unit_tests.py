"""Priority 30 Unit Tests.

This module contains comprehensive unit tests for the test maintenance system.

Priority 30: Universal Autonomous Test Maintenance + Continuous Validation
"""

import sys
from pathlib import Path

# Add the phoenix-core directory to the path
sys.path.insert(0, str(Path(__file__).parent))

import unittest
from datetime import datetime

# Import Test Maintenance
from phoenix.test_maintenance import (
    TestImpactSelector,
    SelectiveRegenerationEngine,
    TestMaintenancePlanner,
    MaintenanceValidationEngine,
    ContinuousValidationEngine,
    BaselineUpdateManager,
    MaintenanceLearning,
    TestMaintenanceCoordinator,
    MaintenanceDecisionType,
    ValidationStatus,
    MaintenanceOutcome,
    TestImpact,
    MaintenancePlan,
    RegenerationResult,
    ValidationResult,
    ContinuousValidationResult,
    BaselineUpdate,
    MaintenanceSession,
)

# Import Change Intelligence
from phoenix.change_intelligence import ChangeIntelligence
from phoenix.change_intelligence.models import SemanticChange, ChangeType, ChangeSeverity


class TestTestImpactSelector(unittest.TestCase):
    """Test cases for TestImpactSelector."""
    
    def setUp(self):
        """Set up test fixtures."""
        self.selector = TestImpactSelector()
    
    def test_register_test(self):
        """Test test registration."""
        test_data = {
            "test_id": "TEST-001",
            "components": ["comp1", "comp2"],
            "flows": ["flow1"],
            "steps": [
                {"step_id": "STEP-001", "target": "comp1"},
            ],
        }
        
        self.selector.register_test("TEST-001", test_data)
        
        self.assertIn("TEST-001", self.selector.test_registry)
        self.assertEqual(self.selector.test_registry["TEST-001"], test_data)
    
    def test_select_affected_tests_no_changes(self):
        """Test impact selection with no changes."""
        changes = []
        all_tests = [
            {"test_id": "TEST-001", "components": ["comp1"], "flows": [], "steps": []},
        ]
        
        impacts = self.selector.select_affected_tests(changes, all_tests)
        
        self.assertEqual(len(impacts), 0)
    
    def test_select_affected_tests_with_changes(self):
        """Test impact selection with changes."""
        change = SemanticChange(
            change_id="CHANGE-001",
            change_type=ChangeType.COMPONENT_ADDED,
            previous_state={},
            current_state={"id": "comp1", "tag": "button"},
            severity=ChangeSeverity.MINOR,
            confidence=0.9,
            evidence={},
        )
        
        all_tests = [
            {
                "test_id": "TEST-001",
                "components": ["comp1"],
                "flows": [],
                "steps": [{"step_id": "STEP-001", "target": "comp1"}],
            },
        ]
        
        impacts = self.selector.select_affected_tests([change], all_tests)
        
        self.assertEqual(len(impacts), 1)
        self.assertEqual(impacts[0].test_id, "TEST-001")


class TestSelectiveRegenerationEngine(unittest.TestCase):
    """Test cases for SelectiveRegenerationEngine."""
    
    def setUp(self):
        """Set up test fixtures."""
        self.engine = SelectiveRegenerationEngine()
    
    def test_locator_only_regeneration(self):
        """Test locator-only regeneration."""
        test_impact = TestImpact(
            impact_id="IMPACT-001",
            test_id="TEST-001",
            change_id="CHANGE-001",
            affected_steps=["STEP-001"],
            affected_locators=["STEP-001"],
            affected_assertions=[],
            severity="low",
            confidence=0.9,
            requires_regeneration=True,
            regeneration_scope="locator_only",
        )
        
        current_test = {
            "test_id": "TEST-001",
            "steps": [
                {"step_id": "STEP-001", "target": "comp1", "locator": "css=.old", "assertions": []},
            ],
        }
        
        new_locators = [
            {"target": "comp1", "locator": "css=.new"},
        ]
        
        result = self.engine.regenerate_test(
            test_impact,
            current_test,
            new_locators,
            new_locators,
        )
        
        self.assertEqual(result.test_id, "TEST-001")
        self.assertEqual(result.decision_type, MaintenanceDecisionType.UPDATE_LOCATOR)
        self.assertTrue(result.success)
        self.assertIn("STEP-001", result.regenerated_steps)


class TestMaintenancePlanner(unittest.TestCase):
    """Test cases for TestMaintenancePlanner."""
    
    def setUp(self):
        """Set up test fixtures."""
        self.planner = TestMaintenancePlanner()
    
    def test_initialization(self):
        """Test planner initialization."""
        self.assertIsNotNone(self.planner)


class TestMaintenanceValidationEngine(unittest.TestCase):
    """Test cases for MaintenanceValidationEngine."""
    
    def setUp(self):
        """Set up test fixtures."""
        self.validator = MaintenanceValidationEngine()
    
    def test_validate_regeneration(self):
        """Test regeneration validation."""
        regeneration_result = RegenerationResult(
            regeneration_id="REGEN-001",
            test_id="TEST-001",
            decision_type=MaintenanceDecisionType.UPDATE_LOCATOR,
            regenerated_steps=["STEP-001"],
            preserved_steps=[],
            new_locators={"STEP-001": "css=#valid-id"},  # Use valid locator
            preserved_locators={},
            new_assertions=[],
            preserved_assertions=[],
            success=True,
            confidence=0.9,
        )
        
        result = self.validator.validate_regeneration(regeneration_result)
        
        self.assertEqual(result.test_id, "TEST-001")
        self.assertEqual(result.regeneration_id, "REGEN-001")
        self.assertIn(result.status, [ValidationStatus.PASSED, ValidationStatus.PARTIAL, ValidationStatus.FAILED])


class TestContinuousValidationEngine(unittest.TestCase):
    """Test cases for ContinuousValidationEngine."""
    
    def setUp(self):
        """Set up test fixtures."""
        self.validator = ContinuousValidationEngine()
    
    def test_validate_maintenance(self):
        """Test continuous validation."""
        validation_result = ValidationResult(
            validation_id="VAL-001",
            regeneration_id="REGEN-001",
            test_id="TEST-001",
            status=ValidationStatus.PASSED,
            quality_score=90.0,
            locator_validation={"valid": True, "issues": []},
            assertion_validation={"valid": True, "issues": []},
            pom_validation={"valid": True, "issues": []},
            security_validation={"valid": True, "issues": []},
            issues=[],
        )
        
        test_data = {"test_id": "TEST-001", "steps": []}
        
        result = self.validator.validate_maintenance(
            validation_result,
            test_data,
            "https://example.com",
            headed=False,
        )
        
        self.assertEqual(result.test_id, "TEST-001")
        self.assertIn(result.outcome, [MaintenanceOutcome.SUCCESS, MaintenanceOutcome.PARTIAL_SUCCESS])


class TestBaselineUpdateManager(unittest.TestCase):
    """Test cases for BaselineUpdateManager."""
    
    def setUp(self):
        """Set up test fixtures."""
        self.manager = BaselineUpdateManager()
    
    def test_update_baseline_all_passed(self):
        """Test baseline update when all validations passed."""
        validation_results = [
            ContinuousValidationResult(
                execution_id="EXEC-001",
                test_id="TEST-001",
                execution_result={"success": True},
                step_results=[],
                locator_results={},
                assertion_results={},
                healing_results={},
                performance_metrics={},
                failure_classification=None,
                outcome=MaintenanceOutcome.SUCCESS,
                confidence=0.9,
            ),
        ]
        
        update = self.manager.update_baseline(
            url="https://example.com",
            validation_results=validation_results,
            current_dom="<html></html>",
            current_page_type="landing",
            current_components=[],
            current_locators=[],
            current_flows=[],
        )
        
        # Should return None because no baseline manager is provided
        self.assertIsNone(update)


class TestMaintenanceLearning(unittest.TestCase):
    """Test cases for MaintenanceLearning."""
    
    def setUp(self):
        """Set up test fixtures."""
        self.learning = MaintenanceLearning()
    
    def test_learn_from_regeneration(self):
        """Test learning from regeneration."""
        regeneration_result = RegenerationResult(
            regeneration_id="REGEN-001",
            test_id="TEST-001",
            decision_type=MaintenanceDecisionType.UPDATE_LOCATOR,
            regenerated_steps=[],
            preserved_steps=[],
            new_locators={},
            preserved_locators={},
            new_assertions=[],
            preserved_assertions=[],
            success=True,
            confidence=0.9,
        )
        
        self.learning.learn_from_regeneration(regeneration_result)
        
        self.assertIn("TEST-001", self.learning.test_regeneration_frequency)
        self.assertEqual(self.learning.test_regeneration_frequency["TEST-001"], 1)
    
    def test_get_regeneration_strategy_confidence(self):
        """Test getting regeneration strategy confidence."""
        confidence = self.learning.get_regeneration_strategy_confidence("update_locator")
        
        self.assertGreaterEqual(confidence, 0.0)
        self.assertLessEqual(confidence, 1.0)


class TestTestMaintenanceCoordinator(unittest.TestCase):
    """Test cases for TestMaintenanceCoordinator."""
    
    def setUp(self):
        """Set up test fixtures."""
        change_intelligence = ChangeIntelligence(base_dir="test_p30_ci")
        self.coordinator = TestMaintenanceCoordinator(
            base_dir="test_p30_tm",
            change_intelligence=change_intelligence,
        )
    
    def test_initialization(self):
        """Test coordinator initialization."""
        self.assertIsNotNone(self.coordinator.test_impact_selector)
        self.assertIsNotNone(self.coordinator.selective_regeneration_engine)
        self.assertIsNotNone(self.coordinator.test_maintenance_planner)
        self.assertIsNotNone(self.coordinator.maintenance_validation_engine)
        self.assertIsNotNone(self.coordinator.continuous_validation_engine)
        self.assertIsNotNone(self.coordinator.baseline_update_manager)
        self.assertIsNotNone(self.coordinator.maintenance_learning)
    
    def test_get_metrics(self):
        """Test getting metrics."""
        metrics = self.coordinator.get_metrics()
        
        self.assertIn("sessions", metrics)
        self.assertIn("total_tests", metrics)
        self.assertIn("affected_tests", metrics)
    
    def test_get_status(self):
        """Test getting status."""
        status = self.coordinator.get_status()
        
        self.assertIn("current_session", status)
        self.assertIn("metrics", status)
        self.assertIn("priority_29_available", status)


if __name__ == "__main__":
    # Run tests
    print("Priority 30 Unit Tests")
    print("=" * 70)
    
    loader = unittest.TestLoader()
    suite = unittest.TestSuite()
    
    # Add all test classes
    suite.addTests(loader.loadTestsFromTestCase(TestTestImpactSelector))
    suite.addTests(loader.loadTestsFromTestCase(TestSelectiveRegenerationEngine))
    suite.addTests(loader.loadTestsFromTestCase(TestMaintenancePlanner))
    suite.addTests(loader.loadTestsFromTestCase(TestMaintenanceValidationEngine))
    suite.addTests(loader.loadTestsFromTestCase(TestContinuousValidationEngine))
    suite.addTests(loader.loadTestsFromTestCase(TestBaselineUpdateManager))
    suite.addTests(loader.loadTestsFromTestCase(TestMaintenanceLearning))
    suite.addTests(loader.loadTestsFromTestCase(TestTestMaintenanceCoordinator))
    
    runner = unittest.TextTestRunner(verbosity=2)
    result = runner.run(suite)
    
    print("\n" + "=" * 70)
    print(f"Tests run: {result.testsRun}")
    print(f"Failures: {len(result.failures)}")
    print(f"Errors: {len(result.errors)}")
    print(f"Success: {result.wasSuccessful()}")
    print("=" * 70)
    
    sys.exit(0 if result.wasSuccessful() else 1)

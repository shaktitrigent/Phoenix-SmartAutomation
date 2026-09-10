"""Direct test of Priority 24 automation generation without full Phoenix imports."""

import sys
from pathlib import Path

# Add the phoenix-core directory to the path
sys.path.insert(0, str(Path(__file__).parent))

# Import automation generation modules directly
from phoenix.automation_generation.models import (
    AutomationStatus,
    ActionType,
    AssertionType,
    TestDataType,
    AutomationPlan,
    Action,
    Assertion,
    TestDataRequirement,
    GeneratedAutomation,
    FailureClassification,
    AutomationMetrics,
    QualityIssueType,
)
from phoenix.automation_generation.automation_planner import AutomationPlanner
from phoenix.automation_generation.action_generator import ActionGenerator
from phoenix.automation_generation.assertion_generator import AssertionGenerator
from phoenix.automation_generation.pom_manager import POMManager
from phoenix.automation_generation.locator_strategy import LocatorStrategyManager
from phoenix.automation_generation.quality_gate import AutomationQualityGate
from phoenix.automation_generation.test_data_intelligence import TestDataIntelligence
from phoenix.automation_generation.sensitive_data_protection import SensitiveDataProtection
from phoenix.automation_generation.failure_classifier import FailureClassifier
from phoenix.automation_generation.automation_regeneration import AutomationRegeneration

print("Priority 24 Automation Generation - Direct Module Test")
print("=" * 60)

# Test 1: Models
print("\n1. Testing Models...")
try:
    assert AutomationStatus.PLANNED == "planned"
    assert ActionType.CLICK == "click"
    assert AssertionType.VISIBLE_TEXT == "visible_text"
    assert TestDataType.USERNAME == "username"
    assert QualityIssueType.PLACEHOLDER_IMPLEMENTATION == "placeholder_implementation"
    print("[PASS] All models imported successfully")
except Exception as e:
    print(f"[FAIL] Model test failed: {e}")

# Test 2: Automation Planner
print("\n2. Testing Automation Planner...")
try:
    planner = AutomationPlanner()
    print("[PASS] AutomationPlanner initialized")
except Exception as e:
    print(f"[FAIL] AutomationPlanner failed: {e}")

# Test 3: Action Generator
print("\n3. Testing Action Generator...")
try:
    action_gen = ActionGenerator()
    print("[PASS] ActionGenerator initialized")
except Exception as e:
    print(f"[FAIL] ActionGenerator failed: {e}")

# Test 4: Assertion Generator
print("\n4. Testing Assertion Generator...")
try:
    assertion_gen = AssertionGenerator()
    print("[PASS] AssertionGenerator initialized")
except Exception as e:
    print(f"[FAIL] AssertionGenerator failed: {e}")

# Test 5: POM Manager
print("\n5. Testing POM Manager...")
try:
    import tempfile
    temp_dir = tempfile.mkdtemp()
    pom_mgr = POMManager(pom_directory=temp_dir)
    print("[PASS] POMManager initialized")
except Exception as e:
    print(f"[FAIL] POMManager failed: {e}")

# Test 6: Locator Strategy Manager
print("\n6. Testing Locator Strategy Manager...")
try:
    locator_mgr = LocatorStrategyManager()
    print("[PASS] LocatorStrategyManager initialized")
except Exception as e:
    print(f"[FAIL] LocatorStrategyManager failed: {e}")

# Test 7: Quality Gate
print("\n7. Testing Quality Gate...")
try:
    quality_gate = AutomationQualityGate()
    print("[PASS] AutomationQualityGate initialized")
except Exception as e:
    print(f"[FAIL] AutomationQualityGate failed: {e}")

# Test 8: Test Data Intelligence
print("\n8. Testing Test Data Intelligence...")
try:
    data_intel = TestDataIntelligence()
    print("[PASS] TestDataIntelligence initialized")
except Exception as e:
    print(f"[FAIL] TestDataIntelligence failed: {e}")

# Test 9: Sensitive Data Protection
print("\n9. Testing Sensitive Data Protection...")
try:
    sensitive_prot = SensitiveDataProtection()
    print("[PASS] SensitiveDataProtection initialized")
except Exception as e:
    print(f"[FAIL] SensitiveDataProtection failed: {e}")

# Test 10: Failure Classifier
print("\n10. Testing Failure Classifier...")
try:
    failure_classifier = FailureClassifier()
    print("[PASS] FailureClassifier initialized")
except Exception as e:
    print(f"[FAIL] FailureClassifier failed: {e}")

# Test 11: Automation Regeneration
print("\n11. Testing Automation Regeneration...")
try:
    auto_regen = AutomationRegeneration()
    print("[PASS] AutomationRegeneration initialized")
except Exception as e:
    print(f"[FAIL] AutomationRegeneration failed: {e}")

print("\n" + "=" * 60)
print("Priority 24 Direct Module Test Complete")
print("=" * 60)

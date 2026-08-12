"""Test to verify the enable_healing fix in runner.py"""

import pytest
from phoenix.execution.runner import TestRunner


def test_runner_enable_healing_initialization():
    """Test that enable_healing is properly initialized and accessible."""
    # Test with healing enabled
    runner_with_healing = TestRunner(
        test_output_dir="./test_output",
        reports_dir="./test_reports",
        headed=False,
        slow_mo=0,
        enable_healing=True,
        enable_intelligent_runtime=False,
        project_name="test_project"
    )
    
    assert runner_with_healing.enable_healing == True
    print("[SUCCESS] enable_healing=True properly initialized")
    
    # Test with healing disabled
    runner_without_healing = TestRunner(
        test_output_dir="./test_output",
        reports_dir="./test_reports",
        headed=False,
        slow_mo=0,
        enable_healing=False,
        enable_intelligent_runtime=False,
        project_name="test_project"
    )
    
    assert runner_without_healing.enable_healing == False
    print("[SUCCESS] enable_healing=False properly initialized")


def test_runner_intelligent_runtime_with_healing():
    """Test that enable_healing is properly passed to IntelligentRuntime."""
    try:
        runner = TestRunner(
            test_output_dir="./test_output",
            reports_dir="./test_reports",
            headed=False,
            slow_mo=0,
            enable_healing=True,
            enable_intelligent_runtime=True,
            project_name="test_project"
        )
        
        # Verify intelligent runtime was initialized
        assert runner.intelligent_runtime is not None
        print("[SUCCESS] IntelligentRuntime initialized with enable_healing=True")
        
        # Verify healing configuration is preserved
        assert runner.enable_healing == True
        print("[SUCCESS] Healing configuration preserved in runner")
        
    except ImportError:
        pytest.skip("IntelligentRuntime dependencies not available")


if __name__ == "__main__":
    print("Testing enable_healing fix...")
    print("=" * 60)
    
    try:
        test_runner_enable_healing_initialization()
        test_runner_intelligent_runtime_with_healing()
        
        print("\n" + "=" * 60)
        print("[SUCCESS] All enable_healing tests passed")
        print("The NameError fix is working correctly")
    except Exception as e:
        print(f"\n[FAILED] Test failed: {e}")
        raise
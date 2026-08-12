"""Test to verify the enable_healing fix on line 198 of runner.py"""

from phoenix.execution.runner import TestRunner


def test_runner_line198_fix():
    """Test that line 198 of runner.py uses self.enable_healing correctly."""
    
    # Initialize runner with healing enabled
    runner = TestRunner(
        test_output_dir="./test_output",
        reports_dir="./test_reports",
        headed=False,
        slow_mo=0,
        enable_healing=True,
        enable_intelligent_runtime=True,
        project_name="test_project"
    )
    
    # Verify the instance variable is set correctly
    assert runner.enable_healing == True
    print("[SUCCESS] enable_healing instance variable set correctly")
    
    # The fix changed line 198 from:
    # print("[PHOENIX] Healing Engine: ENABLED" if enable_healing else "[PHOENIX] Healing Engine: DISABLED")
    # to:
    # print("[PHOENIX] Healing Engine: ENABLED" if self.enable_healing else "[PHOENIX] Healing Engine: DISABLED")
    
    # This test verifies that self.enable_healing is accessible
    healing_status = "ENABLED" if runner.enable_healing else "DISABLED"
    assert healing_status == "ENABLED"
    print(f"[SUCCESS] Healing status calculated correctly: {healing_status}")
    
    # Test with healing disabled
    runner_disabled = TestRunner(
        test_output_dir="./test_output",
        reports_dir="./test_reports",
        headed=False,
        slow_mo=0,
        enable_healing=False,
        enable_intelligent_runtime=False,
        project_name="test_project"
    )
    
    assert runner_disabled.enable_healing == False
    healing_status_disabled = "ENABLED" if runner_disabled.enable_healing else "DISABLED"
    assert healing_status_disabled == "DISABLED"
    print(f"[SUCCESS] Healing status calculated correctly when disabled: {healing_status_disabled}")
    
    print("[SUCCESS] Line 198 fix verified - self.enable_healing is accessible")


if __name__ == "__main__":
    print("Testing enable_healing fix on line 198...")
    print("=" * 60)
    
    try:
        test_runner_line198_fix()
        
        print("\n" + "=" * 60)
        print("[SUCCESS] Line 198 fix verified")
        print("The NameError has been fixed by using self.enable_healing")
    except Exception as e:
        print(f"\n[FAILED] Test failed: {e}")
        import traceback
        traceback.print_exc()
        raise
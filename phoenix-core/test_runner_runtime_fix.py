"""Test to verify the enable_healing fix in the actual run_tests execution path"""

import tempfile
import os
from pathlib import Path
from phoenix.execution.runner import TestRunner


def test_runner_run_tests_with_healing_enabled():
    """Test that run_tests() method works correctly with enable_healing in the print statement."""
    
    temp_dir = tempfile.mkdtemp()
    
    try:
        # Create a simple test file that will be collected
        test_dir = Path(temp_dir) / "tests"
        test_dir.mkdir()
        
        test_file = test_dir / "test_simple.py"
        test_file.write_text("""
def test_simple():
    assert True
""")
        
        # Initialize runner with healing enabled and intelligent runtime
        runner = TestRunner(
            test_output_dir=temp_dir + "/output",
            reports_dir=temp_dir + "/reports",
            headed=False,
            slow_mo=0,
            enable_healing=True,
            enable_intelligent_runtime=True,
            project_name="test_project"
        )
        
        # This should not crash with NameError on line 198
        # The line 198 fix: changed from `enable_healing` to `self.enable_healing`
        result = runner.run_tests(
            test_paths=[str(test_file)],
            project_name="test_project"
        )
        
        # Verify the runner executed without NameError
        assert result is not None
        assert "status" in result
        
        # Verify healing configuration was used
        assert runner.enable_healing == True
        
        print("[SUCCESS] run_tests() executed without NameError")
        print(f"[SUCCESS] Test execution status: {result['status']}")
        print("[SUCCESS] The enable_healing fix in line 198 is working correctly")
            
    except NameError as e:
        if "enable_healing" in str(e):
            print(f"[FAILED] NameError still occurs: {e}")
            raise
        else:
            # Some other NameError
            raise
    finally:
        # Cleanup temp directory
        import shutil
        shutil.rmtree(temp_dir, ignore_errors=True)


if __name__ == "__main__":
    print("Testing enable_healing fix in run_tests() execution path...")
    print("=" * 60)
    
    try:
        test_runner_run_tests_with_healing_enabled()
        
        print("\n" + "=" * 60)
        print("[SUCCESS] run_tests() execution path verified")
        print("The NameError on line 198 has been fixed")
    except Exception as e:
        print(f"\n[FAILED] Test failed: {e}")
        import traceback
        traceback.print_exc()
        raise
import subprocess
import tempfile
import os
from typing import Tuple
from .base import BaseExecutor

class LocalExecutor(BaseExecutor):
    def execute_python_code(self, code: str) -> Tuple[bool, str, str]:
        """
        Executes Python code locally in a subprocess and captures stdout/stderr.
        Used for local capability testing instead of E2B.
        """
        try:
            with tempfile.NamedTemporaryFile(mode='w', suffix='.py', delete=False) as f:
                f.write(code)
                temp_file = f.name
            
            result = subprocess.run(
                ['python', temp_file],
                capture_output=True,
                text=True,
                timeout=10  # Prevent infinite loops
            )
            
            # Cleanup
            os.remove(temp_file)
            
            success = result.returncode == 0
            
            return success, result.stdout, result.stderr
        except subprocess.TimeoutExpired:
            if 'temp_file' in locals() and os.path.exists(temp_file):
                os.remove(temp_file)
            return False, "", "Execution timed out."
        except Exception as e:
            return False, "", str(e)

    def execute_sdk_test(self, sdk_files: dict, test_script: str) -> Tuple[bool, str, str]:
        """
        Executes a test script inside a directory containing the sdk_files.
        Used for local capability testing instead of E2B.
        """
        import shutil
        try:
            temp_dir = tempfile.mkdtemp()
            
            # Write SDK files
            sdk_dir = os.path.join(temp_dir, "apiforge_sdk")
            os.makedirs(sdk_dir)
            for filename, content in sdk_files.items():
                filepath = os.path.join(sdk_dir, filename)
                with open(filepath, "w") as f:
                    f.write(content)
            
            # Write test script
            test_file = os.path.join(temp_dir, "test_script.py")
            with open(test_file, "w") as f:
                f.write(test_script)
                
            result = subprocess.run(
                ['python', test_file],
                cwd=temp_dir,
                capture_output=True,
                text=True,
                timeout=10
            )
            
            # Cleanup
            shutil.rmtree(temp_dir)
            
            success = result.returncode == 0
            return success, result.stdout, result.stderr
        except subprocess.TimeoutExpired:
            if 'temp_dir' in locals() and os.path.exists(temp_dir):
                shutil.rmtree(temp_dir)
            return False, "", "Execution timed out."
        except Exception as e:
            if 'temp_dir' in locals() and os.path.exists(temp_dir):
                shutil.rmtree(temp_dir)
            return False, "", str(e)

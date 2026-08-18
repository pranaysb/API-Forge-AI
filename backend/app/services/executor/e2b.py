from typing import Tuple
from .base import BaseExecutor
from app.core.config import settings

SANDBOX_TIMEOUT_SECONDS = 60
COMMAND_TIMEOUT_SECONDS = 30

class E2BExecutor(BaseExecutor):
    """Runs generated code in an isolated E2B cloud sandbox instead of the host.

    Requires E2B_API_KEY in the environment/.env. Each execution uses a fresh
    sandbox so generated code can never touch the host machine or leak state
    between runs.
    """

    def _create_sandbox(self):
        from e2b_code_interpreter import Sandbox
        if not settings.E2B_API_KEY:
            raise RuntimeError("E2B_API_KEY is not configured but USE_E2B_EXECUTOR is enabled.")
        return Sandbox.create(api_key=settings.E2B_API_KEY, timeout=SANDBOX_TIMEOUT_SECONDS)

    def execute_python_code(self, code: str) -> Tuple[bool, str, str]:
        try:
            sandbox = self._create_sandbox()
        except Exception as e:
            return False, "", f"Failed to create E2B sandbox: {e}"
        try:
            sandbox.files.write("/home/user/script.py", code)
            result = sandbox.commands.run(
                "python /home/user/script.py", timeout=COMMAND_TIMEOUT_SECONDS
            )
            return result.exit_code == 0, result.stdout, result.stderr
        except Exception as e:
            # e2b raises CommandExitException on non-zero exit; it carries the output
            return False, getattr(e, "stdout", ""), getattr(e, "stderr", None) or str(e)
        finally:
            try:
                sandbox.kill()
            except Exception:
                pass

    def execute_sdk_test(self, sdk_files: dict, test_script: str) -> Tuple[bool, str, str]:
        try:
            sandbox = self._create_sandbox()
        except Exception as e:
            return False, "", f"Failed to create E2B sandbox: {e}"
        try:
            for filename, content in sdk_files.items():
                sandbox.files.write(f"/home/user/apiforge_sdk/{filename}", content)
            sandbox.files.write("/home/user/test_script.py", test_script)
            result = sandbox.commands.run(
                "cd /home/user && python test_script.py", timeout=COMMAND_TIMEOUT_SECONDS
            )
            return result.exit_code == 0, result.stdout, result.stderr
        except Exception as e:
            return False, getattr(e, "stdout", ""), getattr(e, "stderr", None) or str(e)
        finally:
            try:
                sandbox.kill()
            except Exception:
                pass

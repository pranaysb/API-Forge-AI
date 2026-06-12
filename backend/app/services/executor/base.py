from abc import ABC, abstractmethod
from typing import Tuple

class BaseExecutor(ABC):
    @abstractmethod
    def execute_python_code(self, code: str) -> Tuple[bool, str, str]:
        """
        Executes Python code.
        Returns: (success: bool, stdout: str, stderr: str)
        """
        pass

    @abstractmethod
    def execute_sdk_test(self, sdk_files: dict, test_script: str) -> Tuple[bool, str, str]:
        """
        Executes a test script inside a directory containing the sdk_files.
        Returns: (success: bool, stdout: str, stderr: str)
        """
        pass

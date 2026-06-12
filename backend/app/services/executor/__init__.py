import os
from .base import BaseExecutor
from .local import LocalExecutor
from .e2b import E2BExecutor

def get_executor() -> BaseExecutor:
    """
    Factory to return the appropriate executor based on environment config.
    """
    use_e2b = os.getenv("USE_E2B_EXECUTOR", "false").lower() == "true"
    
    if use_e2b:
        return E2BExecutor()
    return LocalExecutor()

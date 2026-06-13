import io
import zipfile
from typing import List, Dict
from pydantic import BaseModel, Field
from app.services.llm_factory import get_llm
from langchain_core.prompts import ChatPromptTemplate
from app.core.config import settings

class SDKOutput(BaseModel):
    client_code: str = Field(description="The client.py file containing the main API client class and methods.")
    models_code: str = Field(description="The models.py file containing Pydantic models for request/response payloads.")
    test_client_code: str = Field(description="The test_client.py file containing pytest unit tests for the SDK.")

def generate_sdk_zip(sdk_files: dict) -> io.BytesIO:
    """
    Packages the generated Python SDK files into a ZIP archive.
    """
    zip_buffer = io.BytesIO()
    with zipfile.ZipFile(zip_buffer, "w", zipfile.ZIP_DEFLATED) as zip_file:
        for filename, content in sdk_files.items():
            zip_file.writestr(f"apiforge_sdk/src/apiforge_sdk/{filename}", content)
            
        pyproject_toml = """[build-system]
requires = ["setuptools>=61.0"]
build-backend = "setuptools.build_meta"

[project]
name = "apiforge-sdk"
version = "0.1.0"
description = "Auto-generated SDK by APIForge AI"
authors = [
  { name="APIForge", email="info@apiforge.ai" }
]
requires-python = ">=3.9"
dependencies = [
  "httpx>=0.24.0",
  "pydantic>=2.0.0"
]
"""
        zip_file.writestr("apiforge_sdk/pyproject.toml", pyproject_toml)
        
        readme_md = """# APIForge SDK
This is an auto-generated Python SDK.

## Installation
```bash
pip install .
```

## Usage
```python
from apiforge_sdk.client import ApiClient

client = ApiClient()
```
"""
        zip_file.writestr("apiforge_sdk/README.md", readme_md)
        
        # Explicitly make it a proper package
        if "__init__.py" not in sdk_files:
            zip_file.writestr("apiforge_sdk/src/apiforge_sdk/__init__.py", "")
            
    zip_buffer.seek(0)
    return zip_buffer

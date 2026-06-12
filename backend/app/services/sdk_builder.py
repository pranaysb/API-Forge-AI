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
            zip_file.writestr(f"apiforge_sdk/{filename}", content)
            
        zip_file.writestr("requirements.txt", "httpx>=0.24.0\npydantic>=2.0.0\npytest>=7.0.0\n")
    
    zip_buffer.seek(0)
    return zip_buffer

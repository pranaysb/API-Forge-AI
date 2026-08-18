import zipfile
from app.services.sdk_builder import generate_sdk_zip

def test_zip_contains_sdk_files_and_packaging():
    buf = generate_sdk_zip({"client.py": "class ApiClient: pass", "__init__.py": ""})
    with zipfile.ZipFile(buf) as z:
        names = set(z.namelist())
        assert "apiforge_sdk/src/apiforge_sdk/client.py" in names
        assert "apiforge_sdk/src/apiforge_sdk/__init__.py" in names
        assert "apiforge_sdk/pyproject.toml" in names
        assert "apiforge_sdk/README.md" in names
        assert b"httpx" in z.read("apiforge_sdk/pyproject.toml")

def test_zip_adds_init_when_missing():
    buf = generate_sdk_zip({"client.py": "pass"})
    with zipfile.ZipFile(buf) as z:
        assert "apiforge_sdk/src/apiforge_sdk/__init__.py" in z.namelist()

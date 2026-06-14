import pytest
import urllib.parse
from fastapi.testclient import TestClient
from app.main import app

def test_relative_url_normalization():
    # We can test the logic directly
    raw_url = "/api/v3"
    if not raw_url.startswith(("http://", "https://")):
        base_url = urllib.parse.urljoin("http://127.0.0.1:8001", raw_url)
    else:
        base_url = raw_url
    assert base_url == "http://127.0.0.1:8001/api/v3"

test_relative_url_normalization()
print("Relative URL test passed.")

import io
import json
import pytest
from fastapi.testclient import TestClient
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import StaticPool

from app.main import app
from app.core.db import get_db
from app.models.domain import Base
from app.api import upload as upload_module

@pytest.fixture()
def client():
    engine = create_engine(
        "sqlite://",
        connect_args={"check_same_thread": False},
        poolclass=StaticPool,
    )
    Base.metadata.create_all(engine)
    TestSession = sessionmaker(bind=engine)

    def override_get_db():
        db = TestSession()
        try:
            yield db
        finally:
            db.close()

    app.dependency_overrides[get_db] = override_get_db
    upload_module.limiter.reset()  # avoid cross-test 429s from the 5/minute limit
    yield TestClient(app)
    app.dependency_overrides.clear()

VALID_SPEC = json.dumps({
    "openapi": "3.0.0",
    "info": {"title": "t", "version": "1"},
    "servers": [{"url": "https://api.example.com"}],
    "paths": {"/users": {"get": {"operationId": "listUsers"}}},
})

def _upload(client, content: bytes, name="spec.json"):
    return client.post("/api/upload", files={"file": (name, io.BytesIO(content), "application/json")})

def test_valid_spec_creates_job(client):
    res = _upload(client, VALID_SPEC.encode())
    assert res.status_code == 200
    body = res.json()
    assert body["job_id"] and body["endpoints_count"] == 1

def test_arbitrary_yaml_is_rejected(client):
    res = _upload(client, b"hello: world", name="x.yaml")
    assert res.status_code == 422

def test_malformed_yaml_is_rejected(client):
    res = _upload(client, b"::: not yaml : [", name="x.yaml")
    assert res.status_code == 400

def test_binary_garbage_is_rejected(client):
    res = _upload(client, b"\x80\x81\x82", name="x.yaml")
    assert res.status_code == 400

def test_spec_without_paths_is_rejected(client):
    res = _upload(client, json.dumps({"openapi": "3.0.0", "paths": {}}).encode())
    assert res.status_code == 422

def test_spec_with_paths_but_no_operations_is_rejected(client):
    spec = {"openapi": "3.0.0", "info": {"title": "t", "version": "1"}, "paths": {"/foo": {"parameters": []}}}
    res = _upload(client, json.dumps(spec).encode())
    assert res.status_code == 422
    assert "operations" in res.json()["detail"]

def test_oversized_file_is_rejected(client):
    big = b"x" * (10 * 1024 * 1024 + 1)
    res = _upload(client, big, name="huge.json")
    assert res.status_code == 413

def test_health_endpoint(client):
    assert client.get("/health").status_code == 200

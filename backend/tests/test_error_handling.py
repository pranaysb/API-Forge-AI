"""Verifies unhandled exceptions return a proper JSON 500 with CORS headers
intact, instead of the default Starlette error response (which drops CORS
headers on unhandled exceptions, making the browser report a same-origin-safe
but cross-origin-opaque "Failed to fetch" and hiding the real error)."""
import pytest
from fastapi.testclient import TestClient

from app.main import app
from app.core.db import get_db


def _raise_db_error():
    raise RuntimeError("simulated database failure")
    yield  # pragma: no cover - unreachable, keeps this a generator


@pytest.fixture()
def broken_db_client():
    app.dependency_overrides[get_db] = _raise_db_error
    yield TestClient(app, raise_server_exceptions=False)
    app.dependency_overrides.clear()


def test_unhandled_exception_returns_json_500(broken_db_client):
    res = broken_db_client.get(
        "/api/dashboard/projects",
        headers={"Origin": "http://localhost:3000"},
    )
    assert res.status_code == 500
    assert res.json() == {"detail": "Internal server error. Please try again or check the server logs."}


def test_unhandled_exception_keeps_cors_header(broken_db_client):
    res = broken_db_client.get(
        "/api/dashboard/projects",
        headers={"Origin": "http://localhost:3000"},
    )
    assert res.headers.get("access-control-allow-origin") == "http://localhost:3000"

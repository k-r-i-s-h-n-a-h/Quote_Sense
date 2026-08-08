"""FastAPI smoke tests for root + health endpoints."""

from __future__ import annotations

from unittest.mock import patch

import pytest
from fastapi.testclient import TestClient


@pytest.fixture
def client(mock_env_unconfigured):
    from main import app

    with TestClient(app) as test_client:
        yield test_client


def test_root(client):
    response = client.get("/")
    assert response.status_code == 200
    assert "QuoteSense" in response.json()["status"]


def test_health_unconfigured(client, mock_env_unconfigured):
    response = client.get("/api/health")
    assert response.status_code == 200
    body = response.json()
    assert body["ok"] is False
    assert body["supabase_configured"] is False
    assert body["gemini_configured"] is False
    assert "GEMINI_API_KEY" in body["missing_keys"]


def test_health_ok(mock_env_unconfigured):
    from main import app

    ok_payload = {
        "path": "backend/.env",
        "size_on_disk": 100,
        "readable_bytes": 100,
        "corrupted": False,
        "gemini_configured": True,
        "supabase_configured": True,
        "placeholder_keys": False,
        "missing": [],
    }
    with patch("main.env_diagnostics", return_value=ok_payload):
        with TestClient(app) as client:
            response = client.get("/api/health")
    assert response.status_code == 200
    body = response.json()
    assert body["ok"] is True
    assert body["hint"] is None


def test_market_rate_cache_control_helpers():
    from main import _market_rate_by_category_cache_control

    err = _market_rate_by_category_cache_control(None, error=True)
    assert err["Cache-Control"] == "no-store"

    verdict = _market_rate_by_category_cache_control(120.0)
    assert "max-age=300" in verdict["Cache-Control"]

    bulk = _market_rate_by_category_cache_control(None)
    assert "max-age=7200" in bulk["Cache-Control"]
    assert bulk["CDN-Cache-Control"] == "no-store"


def test_require_service_type():
    from main import _require_service_type

    resolved, err = _require_service_type(service_type="luxury")
    assert resolved == "LUXURY"
    assert err is None

    missing, err2 = _require_service_type(service_type="")
    assert missing is None
    assert err2 is not None

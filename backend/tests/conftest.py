"""Shared pytest fixtures for QuoteSense backend tests."""

from __future__ import annotations

import sys
import types
from unittest.mock import MagicMock, patch

import pytest

# Keep unit-test imports light when venv site-packages is slow/unavailable.
if "dotenv" not in sys.modules:
    _dotenv = types.ModuleType("dotenv")
    _dotenv.load_dotenv = lambda *a, **k: False  # type: ignore[attr-defined]
    sys.modules["dotenv"] = _dotenv


@pytest.fixture
def mock_env_unconfigured():
    """Prevent startup Supabase probes and keep health checks deterministic."""
    payload = {
        "path": "backend/.env",
        "size_on_disk": 0,
        "readable_bytes": 0,
        "corrupted": False,
        "gemini_configured": False,
        "supabase_configured": False,
        "placeholder_keys": True,
        "missing": ["GEMINI_API_KEY", "SUPABASE_URL", "SUPABASE_SERVICE_ROLE_KEY"],
    }
    with patch("main.env_diagnostics", return_value=payload):
        with patch("services.env_config.env_diagnostics", return_value=payload):
            yield payload


@pytest.fixture
def mock_heavy_clients():
    """Stub Gemini/Supabase clients so FastAPI app import stays offline."""
    with patch("services.env_config.get_supabase_client", return_value=MagicMock()):
        with patch("services.env_config.get_gemini_client", return_value=MagicMock()):
            yield

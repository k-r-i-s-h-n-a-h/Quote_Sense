"""Gemini model id helpers."""

from __future__ import annotations

from services.env_config import (
    DEFAULT_COMPARE_MODEL,
    DEFAULT_EXTRACT_MODEL,
    gemini_compare_model,
    gemini_extract_model,
    gemini_generate_config,
    gemini_is_v3,
    gemini_space_model,
    gemini_work_model,
)


class _Types:
    class GenerateContentConfig:
        def __init__(self, **kwargs):
            self.kwargs = kwargs


def test_defaults(monkeypatch):
    monkeypatch.delenv("GEMINI_EXTRACT_MODEL", raising=False)
    monkeypatch.delenv("GEMINI_COMPARE_MODEL", raising=False)
    monkeypatch.delenv("GEMINI_SPACE_MODEL", raising=False)
    monkeypatch.delenv("GEMINI_WORK_MODEL", raising=False)
    assert gemini_extract_model() == DEFAULT_EXTRACT_MODEL
    assert gemini_compare_model() == DEFAULT_COMPARE_MODEL
    assert gemini_space_model() == DEFAULT_COMPARE_MODEL
    assert gemini_work_model() == DEFAULT_COMPARE_MODEL


def test_space_falls_back_to_compare(monkeypatch):
    monkeypatch.delenv("GEMINI_SPACE_MODEL", raising=False)
    monkeypatch.setenv("GEMINI_COMPARE_MODEL", "gemini-3.7-flash")
    assert gemini_space_model() == "gemini-3.7-flash"


def test_v3_omits_temperature():
    cfg = gemini_generate_config(
        _Types, model="gemini-3.7-flash", temperature=0.0, response_mime_type="application/json"
    )
    assert "temperature" not in cfg.kwargs
    assert cfg.kwargs["response_mime_type"] == "application/json"


def test_v25_keeps_temperature():
    cfg = gemini_generate_config(_Types, model="gemini-2.5-flash", temperature=0.0)
    assert cfg.kwargs["temperature"] == 0.0


def test_gemini_is_v3():
    assert gemini_is_v3("gemini-3.5-flash") is True
    assert gemini_is_v3("gemini-2.5-flash") is False

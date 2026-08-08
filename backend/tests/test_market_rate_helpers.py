"""Unit tests for pure market-rate helpers (high coverage, no DB)."""

from __future__ import annotations

import pytest

from services.market_rate import (
    DEFAULT_SERVICE_TYPE,
    bundle_key,
    is_amount_based_pricing_method,
    is_finalize_quote_flag,
    market_rate_updates_enabled,
    normalize_pricing_method,
    normalize_service_type,
    normalize_text,
    resolve_effective_rate,
    resolve_service_type,
    finalized_quote_session_id,
)


@pytest.mark.parametrize(
    "value,fallback,expected",
    [
        (None, "x", "x"),
        ("", "x", "x"),
        ("  ", "x", "x"),
        ("nan", "x", "x"),
        ("None", "x", "x"),
        ("null", "x", "x"),
        ("  Area (sqft)  ", "", "Area (sqft)"),
        (42, "", "42"),
    ],
)
def test_normalize_text(value, fallback, expected):
    assert normalize_text(value, fallback) == expected


@pytest.mark.parametrize(
    "raw,expected",
    [
        ("sqft", "Area (sqft)"),
        ("area (in sqft)", "Area (sqft)"),
        ("AREA (SQFT)", "Area (sqft)"),
        ("Unit", "Unit"),
        (None, "Unit"),
        ("", "Unit"),
        ("Per Project", "Per Project"),
    ],
)
def test_normalize_pricing_method(raw, expected):
    assert normalize_pricing_method(raw) == expected


@pytest.mark.parametrize(
    "raw,expected",
    [
        ("essential", "ESSENTIAL"),
        ("affordable", "ESSENTIAL"),
        ("mid-segment", "MID_SEGMENT"),
        ("mid_segment", "MID_SEGMENT"),
        ("luxury", "LUXURY"),
        ("premium", "LUXURY"),
        ("", DEFAULT_SERVICE_TYPE),
        (None, DEFAULT_SERVICE_TYPE),
        ("ESSENTIAL", "ESSENTIAL"),
        ("CUSTOM_TIER", "CUSTOM_TIER"),
    ],
)
def test_normalize_service_type(raw, expected):
    assert normalize_service_type(raw) == expected


def test_resolve_effective_rate_uses_real_rate():
    assert resolve_effective_rate(120.0, quantity=10, amount=500) == 120.0


def test_resolve_effective_rate_amount_based_fallback():
    rate = resolve_effective_rate(
        1.0, quantity=10, amount=500, pricing_method="On Actuals"
    )
    assert rate == 50.0


def test_resolve_effective_rate_amount_based_zero_qty():
    rate = resolve_effective_rate(
        0.5, quantity=0, amount=200, pricing_method="Lumpsum"
    )
    assert rate == 200.0


def test_resolve_effective_rate_invalid_inputs():
    assert resolve_effective_rate("bad", quantity="x", amount="y") == 0.0


@pytest.mark.parametrize(
    "method,expected",
    [
        ("On Actuals", True),
        ("per project", True),
        ("Lump Sum", True),
        ("Area (sqft)", False),
        ("", False),
        (None, False),
    ],
)
def test_is_amount_based_pricing_method(method, expected):
    assert is_amount_based_pricing_method(method) is expected


def test_bundle_key_normalizes_fields():
    key = bundle_key("essential", "  Flooring ", " Tile ", "sqft")
    assert key["service_type"] == "ESSENTIAL"
    assert key["service_category"] == "Flooring"
    assert key["sub_service"] == "Tile"
    assert key["pricing_method"] == "Area (sqft)"


def test_resolve_service_type_returns_none_when_unknown():
    assert resolve_service_type(service_type="", quote_type_id="") is None
    assert resolve_service_type(service_type="not-a-tier") is None


def test_resolve_service_type_aliases():
    assert resolve_service_type(service_type="luxury") == "LUXURY"
    assert resolve_service_type(service_type="mid segment") == "MID_SEGMENT"


def test_market_rate_updates_enabled_default(monkeypatch):
    monkeypatch.delenv("MARKET_RATE_UPDATES_ENABLED", raising=False)
    assert market_rate_updates_enabled() is True


def test_market_rate_updates_disabled(monkeypatch):
    monkeypatch.setenv("MARKET_RATE_UPDATES_ENABLED", "false")
    assert market_rate_updates_enabled() is False


@pytest.mark.parametrize(
    "payload,expected",
    [
        ({"isFinalizeQuote": True}, True),
        ({"isFinalizeQuote": "true"}, True),
        ({"isFinalizedQuote": 1}, True),
        ({"isFinalized": True}, True),
        ({"is_finalized": True}, True),
        ({"is_finalized": "true"}, True),
        ({"finalizeQuote": "1"}, True),
        ({"isFinalizeQuote": False}, False),
        ({"is_finalized": False}, False),
        ({"quoteNumber": "Q-1"}, False),
        ({"data": {"isFinalizeQuote": True, "quoteNumber": "X"}}, True),
        ({"data": {"is_finalized": True, "quoteNumber": "Y"}}, True),
        (None, False),
    ],
)
def test_is_finalize_quote_flag(payload, expected):
    assert is_finalize_quote_flag(payload) is expected


def test_finalized_quote_session_id_uses_quote_number():
    assert finalized_quote_session_id({"quoteNumber": "#AB-12"}) == "finalize:AB-12"
    assert finalized_quote_session_id({"_id": "oid1"}) == "finalize:oid1"

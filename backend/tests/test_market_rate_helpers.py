"""Unit tests for pure market-rate helpers (high coverage, no DB)."""

from __future__ import annotations

from datetime import date
from unittest.mock import MagicMock

import pytest

from services.market_rate import (
    DEFAULT_SERVICE_TYPE,
    bundle_key,
    finalize_quote_meets_min_date,
    is_amount_based_pricing_method,
    is_finalize_quote_flag,
    market_rate_updates_enabled,
    normalize_pricing_method,
    normalize_service_type,
    normalize_text,
    parse_quote_event_date,
    resolve_effective_rate,
    resolve_service_type,
    finalized_quote_session_id,
    _label_ids,
    list_market_rates_by_category,
)

LIVE_AREA_SQFT = "6a79ab1cf47d48a866051b3f"
CATALOG_SQUARE_FEET = "6a79ab23f47d48a866051bf7"
MA_SUB_SERVICE = "6a744f7c895836cf85370001"
MA_SERVICE = "6926b1978ba6a3cfc5a191ce"


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


@pytest.mark.parametrize(
    "raw,expected",
    [
        ("2026-08-14T12:00:00.000Z", date(2026, 8, 14)),
        ("2026-08-14", date(2026, 8, 14)),
        ("14/08/2026", date(2026, 8, 14)),
        ("14-08-2026", date(2026, 8, 14)),
        ("", None),
        (None, None),
    ],
)
def test_parse_quote_event_date(raw, expected):
    assert parse_quote_event_date(raw) == expected


def test_finalize_quote_meets_min_date_default(monkeypatch):
    monkeypatch.setenv("MA_FINALIZE_MIN_DATE", "2026-08-14")
    assert finalize_quote_meets_min_date(
        {"isFinalizeQuote": True, "quoteDate": "2026-08-14"}
    )
    assert finalize_quote_meets_min_date(
        {"isFinalizeQuote": True, "updatedAt": "2026-08-15T01:00:00Z"}
    )
    assert not finalize_quote_meets_min_date(
        {"isFinalizeQuote": True, "quoteDate": "2026-08-13"}
    )
    assert not finalize_quote_meets_min_date(
        {"isFinalizeQuote": True, "quoteNumber": "Q-no-date"}
    )


def test_finalize_quote_meets_min_date_disabled(monkeypatch):
    monkeypatch.setenv("MA_FINALIZE_MIN_DATE", "")
    assert finalize_quote_meets_min_date({"isFinalizeQuote": True, "quoteNumber": "Q1"})


def test_label_ids_use_ma_columns_not_catalog(monkeypatch):
    called = {"pm": 0, "sub": 0}

    def fake_pm(_label):
        called["pm"] += 1
        return CATALOG_SQUARE_FEET

    def fake_sub(_label):
        called["sub"] += 1
        return "bbbbbbbbbbbbbbbbbbbbbbbb"

    monkeypatch.setattr("services.tatva_catalog.resolve_pricing_method_id", fake_pm)
    monkeypatch.setattr("services.tatva_catalog.resolve_sub_service_id", fake_sub)

    ids = _label_ids(
        "Wardrobe",
        "Area – Direct Entry (sq ft)",
        pricing_id=LIVE_AREA_SQFT,
        sub_service_id=MA_SUB_SERVICE,
        service_id=MA_SERVICE,
    )
    assert ids["pricing_id"] == LIVE_AREA_SQFT
    assert ids["sub_service_id"] == MA_SUB_SERVICE
    assert ids["service_id"] == MA_SERVICE
    assert called == {"pm": 0, "sub": 0}


def test_by_category_items_use_ma_ids_not_catalog(monkeypatch):
    monkeypatch.setattr(
        "services.tatva_catalog.resolve_pricing_method_id",
        lambda _label: CATALOG_SQUARE_FEET,
    )
    monkeypatch.setattr(
        "services.tatva_catalog.resolve_sub_service_id",
        lambda _label: "bbbbbbbbbbbbbbbbbbbbbbbb",
    )

    def _catalog_must_not_run(**_kwargs):
        raise AssertionError("ensure_live_catalog must not run on /by-category")

    monkeypatch.setattr(
        "services.tatva_catalog.ensure_live_catalog", _catalog_must_not_run
    )

    fake_table = MagicMock()
    fake_table.select.return_value = fake_table
    fake_table.eq.return_value = fake_table
    fake_table.execute.return_value = MagicMock(
        data=[
            {
                "service_type": "ESSENTIAL",
                "service_category": "Residential Interiors",
                "sub_service": "Wardrobe",
                "pricing_method": "Area – Direct Entry (sq ft)",
                "rate_moving_average": 1400,
                "weight": 5,
                "pricing_method_id": LIVE_AREA_SQFT,
                "sub_service_id": MA_SUB_SERVICE,
                "service_id": MA_SERVICE,
            }
        ]
    )
    fake_client = MagicMock()
    fake_client.table.return_value = fake_table
    monkeypatch.setattr(
        "services.market_rate.get_supabase_client", lambda: fake_client
    )

    result = list_market_rates_by_category("Residential Interiors", "ESSENTIAL")
    assert result["count"] == 1
    item = result["items"][0]
    assert item["pricing_id"] == LIVE_AREA_SQFT
    assert item["pricing_id"] != CATALOG_SQUARE_FEET
    assert item["sub_service_id"] == MA_SUB_SERVICE
    assert item["service_id"] == MA_SERVICE
    assert item["pricing_method_label"] == "Area – Direct Entry (sq ft)"


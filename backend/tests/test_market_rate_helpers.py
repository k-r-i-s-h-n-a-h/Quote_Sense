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
    update_rate_moving_average,
    update_rates_from_dataframe,
    apply_finalized_quotes_to_market_rates,
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


SQMM_PM = "6a79ab1df47d48a866051b99"
NEW_ROW_ID = "aaaaaaaa-bbbb-cccc-dddd-eeeeeeeeeeee"


class _PersistTable:
    def __init__(self, store):
        self.store = store

    def update(self, payload):
        self.store["update"] = payload
        return self

    def eq(self, *_args, **_kwargs):
        return self

    def insert(self, payload):
        self.store["insert"] = payload
        return self

    def execute(self):
        return MagicMock(data=[{"id": self.store.get("inserted_id") or "row-1"}])


def _patch_ma_persist(monkeypatch, *, existing=None, store=None):
    store = store if store is not None else {}
    monkeypatch.setattr(
        "services.market_rate.fetch_market_rate_row", lambda _key: existing
    )
    monkeypatch.setattr("services.market_rate._session_already_applied", lambda *_a: False)
    monkeypatch.setattr("services.market_rate._record_session", lambda *_a, **_k: None)
    monkeypatch.delenv("MARKET_RATE_UPDATES_ENABLED", raising=False)
    fake_client = MagicMock()
    fake_client.table.return_value = _PersistTable(store)
    monkeypatch.setattr("services.market_rate.get_supabase_client", lambda: fake_client)
    return store


def test_finalize_existing_bundle_blends_and_does_not_insert(monkeypatch):
    existing = {
        "id": "row-1",
        "rate_moving_average": 1000.0,
        "moving_average": 1000.0,
        "weight": 1,
    }
    store = _patch_ma_persist(monkeypatch, existing=existing)
    avg, weight = update_rate_moving_average(
        "finalize:Q1",
        "ESSENTIAL",
        "Residential Interiors",
        "Wardrobe",
        "Area – Direct Entry (sq ft)",
        [1200.0],
        allow_insert=True,
        service_id=MA_SERVICE,
        sub_service_id=MA_SUB_SERVICE,
        pricing_method_id=LIVE_AREA_SQFT,
    )
    assert store.get("insert") is None
    assert store["update"]["rate_moving_average"] == 1100.0
    assert "sub_service_id" not in store["update"]
    assert avg == 1100.0
    assert weight == 2


def test_finalize_new_combo_inserts_this_tier_only_with_ids(monkeypatch):
    store = _patch_ma_persist(monkeypatch, existing=None)
    store["inserted_id"] = NEW_ROW_ID
    avg, weight = update_rate_moving_average(
        "finalize:Q2",
        "ESSENTIAL",
        "Residential Interiors",
        "Wardrobe",
        "Area (in sqmm)",
        [850.0],
        allow_insert=True,
        service_id=MA_SERVICE,
        sub_service_id=MA_SUB_SERVICE,
        pricing_method_id=SQMM_PM,
    )
    inserted = store["insert"]
    assert store.get("update") is None
    assert inserted["service_type"] == "ESSENTIAL"
    assert inserted["pricing_method"] == "Area (in sqmm)"
    assert inserted["sub_service_id"] == MA_SUB_SERVICE
    assert inserted["pricing_method_id"] == SQMM_PM
    assert inserted["service_id"] == MA_SERVICE
    assert inserted["rate_moving_average"] == 850.0
    assert inserted["weight"] == 1
    assert avg == 850.0
    assert weight == 1


def test_finalize_new_combo_without_ids_skips_insert(monkeypatch):
    store = _patch_ma_persist(monkeypatch, existing=None)
    avg, weight = update_rate_moving_average(
        "finalize:Q3",
        "ESSENTIAL",
        "Residential Interiors",
        "Wardrobe",
        "Area (in sqmm)",
        [850.0],
        allow_insert=True,
    )
    assert store.get("insert") is None
    assert store.get("update") is None
    assert avg == 0.0
    assert weight == 0


def test_finalize_already_applied_does_not_blend_again(monkeypatch):
    existing = {
        "id": "row-1",
        "rate_moving_average": 1000.0,
        "moving_average": 1000.0,
        "weight": 2,
    }
    store = _patch_ma_persist(monkeypatch, existing=existing)
    monkeypatch.setattr("services.market_rate._session_already_applied", lambda *_a: True)
    avg, weight = update_rate_moving_average(
        "finalize:Q1",
        "ESSENTIAL",
        "Residential Interiors",
        "Wardrobe",
        "Area – Direct Entry (sq ft)",
        [2000.0],
        allow_insert=True,
        sub_service_id=MA_SUB_SERVICE,
        pricing_method_id=LIVE_AREA_SQFT,
    )
    assert store.get("insert") is None
    assert store.get("update") is None
    assert avg == 1000.0
    assert weight == 2


def test_finalize_frozen_skips_write(monkeypatch):
    existing = {
        "id": "row-1",
        "rate_moving_average": 1000.0,
        "moving_average": 1000.0,
        "weight": 1,
    }
    store = _patch_ma_persist(monkeypatch, existing=existing)
    monkeypatch.setenv("MARKET_RATE_UPDATES_ENABLED", "false")
    avg, weight = update_rate_moving_average(
        "finalize:Q1",
        "ESSENTIAL",
        "Residential Interiors",
        "Wardrobe",
        "Area – Direct Entry (sq ft)",
        [2000.0],
        allow_insert=True,
        sub_service_id=MA_SUB_SERVICE,
        pricing_method_id=LIVE_AREA_SQFT,
    )
    assert store.get("insert") is None
    assert store.get("update") is None
    assert avg == 1000.0
    assert weight == 1


def test_apply_finalized_passes_allow_insert_true(monkeypatch):
    captured = {}

    monkeypatch.delenv("MARKET_RATE_UPDATES_ENABLED", raising=False)
    monkeypatch.setattr(
        "services.market_rate.finalize_quote_meets_min_date", lambda _q: True
    )
    monkeypatch.setattr(
        "services.market_rate.finalize_quote_already_applied_to_ma", lambda _q: False
    )

    def fake_df(_quotes):
        import pandas as pd

        return pd.DataFrame(
            [
                {
                    "vendor_name": "Acme",
                    "service_type": "ESSENTIAL",
                    "service_category": "Residential Interiors",
                    "sub_service": "Wardrobe",
                    "pricing_method": "Area (in sqmm)",
                    "rate": 850,
                    "quantity": 1,
                    "amount": 850,
                    "service_id": MA_SERVICE,
                    "sub_service_id": MA_SUB_SERVICE,
                    "pricing_method_id": SQMM_PM,
                }
            ]
        )

    def fake_update(df, sid, fast=False, allow_insert=False):
        captured["allow_insert"] = allow_insert
        captured["sid"] = sid
        return {("ESSENTIAL", "Residential Interiors", "Wardrobe", "Area (in sqmm)"): (850.0, 1)}

    monkeypatch.setattr(
        "services.comparator.mongodb_quotes_to_dataframe", fake_df
    )
    monkeypatch.setattr(
        "services.market_rate.update_rates_from_dataframe", fake_update
    )

    result = apply_finalized_quotes_to_market_rates(
        [{"isFinalizeQuote": True, "quoteNumber": "Q-NEW"}],
        source="test",
    )
    assert captured["allow_insert"] is True
    assert result["seed_match_only"] is False
    assert result["quotes_applied"] == 1
    assert result["bundles_updated"] == 1


def test_update_rates_from_dataframe_threads_ids(monkeypatch):
    import pandas as pd

    captured = {}

    def fake_update(*args, **kwargs):
        captured["kwargs"] = kwargs
        captured["args"] = args
        return 850.0, 1

    monkeypatch.setattr("services.market_rate.update_rate_moving_average", fake_update)
    df = pd.DataFrame(
        [
            {
                "vendor_name": "Acme",
                "service_type": "ESSENTIAL",
                "service_category": "Residential Interiors",
                "sub_service": "Wardrobe",
                "pricing_method": "Area (in sqmm)",
                "rate": 850,
                "quantity": 1,
                "amount": 850,
                "service_id": MA_SERVICE,
                "sub_service_id": MA_SUB_SERVICE,
                "pricing_method_id": SQMM_PM,
            }
        ]
    )
    update_rates_from_dataframe(df, "finalize:Q2", allow_insert=True)
    assert captured["kwargs"]["allow_insert"] is True
    assert captured["kwargs"]["sub_service_id"] == MA_SUB_SERVICE
    assert captured["kwargs"]["pricing_method_id"] == SQMM_PM
    assert captured["kwargs"]["service_id"] == MA_SERVICE


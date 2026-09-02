"""Unit tests for Tatva catalog pure helpers."""

from __future__ import annotations

from unittest.mock import MagicMock

from services.tatva_catalog import (
    _entry_name_and_id,
    _unwrap_catalog_list,
    is_object_id,
    payload_looks_like_catalog_maps,
    register_pricing_method,
    resolve_item_labels,
    resolve_pricing_method_id,
    resolve_pricing_method_label,
)

LIVE_AREA_SQFT = "6a79ab1cf47d48a866051b3f"
LIVE_SQUARE_FEET = "6a79ab23f47d48a866051bf7"
STALE_AREA_SQFT = "6a02eb4398c21380f8efdd65"


def test_unwrap_plain_list():
    assert _unwrap_catalog_list([{"_id": "a"}, "skip"]) == [{"_id": "a"}]


def test_unwrap_nested_data_docs():
    payload = {"data": {"docs": [{"name": "Tile", "_id": "1"}]}}
    assert _unwrap_catalog_list(payload) == [{"name": "Tile", "_id": "1"}]


def test_unwrap_items_key():
    payload = {"items": [{"label": "Sqft", "id": "x"}]}
    assert _unwrap_catalog_list(payload) == [{"label": "Sqft", "id": "x"}]


def test_unwrap_invalid():
    assert _unwrap_catalog_list(None) == []
    assert _unwrap_catalog_list("x") == []
    assert _unwrap_catalog_list(123) == []


def test_is_object_id():
    assert is_object_id("507f1f77bcf86cd799439011") is True
    assert is_object_id("not-an-oid") is False
    assert is_object_id("") is False
    assert is_object_id(None) is False


def test_entry_name_and_id():
    name, oid = _entry_name_and_id(
        {"name": "Flooring", "_id": "507f1f77bcf86cd799439011"}
    )
    assert name == "Flooring"
    assert oid == "507f1f77bcf86cd799439011"

    name2, oid2 = _entry_name_and_id({"title": "Paint", "id": "bad"})
    assert name2 == "Paint"
    assert oid2 is None


def test_payload_looks_like_catalog_maps():
    assert payload_looks_like_catalog_maps({"sub_services": {}}) is True
    assert payload_looks_like_catalog_maps({"pricing_methods": {}}) is True
    assert payload_looks_like_catalog_maps({"quotes": []}) is False
    assert payload_looks_like_catalog_maps(None) is False


def test_register_square_feet_does_not_steal_area_sqft_id():
    previous_sqft = resolve_pricing_method_id("Square Feet")
    register_pricing_method("Area – Direct Entry (sq ft)", LIVE_AREA_SQFT, persist=False)
    register_pricing_method("Square Feet", LIVE_SQUARE_FEET, persist=False)
    try:
        assert resolve_pricing_method_id("Area – Direct Entry (sq ft)") == LIVE_AREA_SQFT
        assert resolve_pricing_method_id("Square Feet") == LIVE_SQUARE_FEET
        assert resolve_pricing_method_label(LIVE_AREA_SQFT) == "Area – Direct Entry (sq ft)"
    finally:
        if previous_sqft:
            register_pricing_method("Square Feet", previous_sqft, persist=False)


def test_stale_area_sqft_id_still_resolves_to_live_label():
    assert resolve_pricing_method_label(STALE_AREA_SQFT) == "Area – Direct Entry (sq ft)"
    sub, pm = resolve_item_labels(pricing_id=STALE_AREA_SQFT, sub_service="Wardrobe")
    assert pm == "Area – Direct Entry (sq ft)"
    assert sub == "Wardrobe"


def test_unknown_pricing_id_reverse_maps_from_ma(monkeypatch):
    unknown = "aaaaaaaaaaaaaaaaaaaaaaaa"
    fake_table = MagicMock()
    fake_table.select.return_value = fake_table
    fake_table.eq.return_value = fake_table
    fake_table.limit.return_value = fake_table
    fake_table.execute.return_value = MagicMock(
        data=[{"pricing_method": "Per Window"}]
    )
    fake_client = MagicMock()
    fake_client.table.return_value = fake_table
    monkeypatch.setattr(
        "services.env_config.get_supabase_client", lambda: fake_client
    )
    assert resolve_pricing_method_label(unknown) == "Per Window"
    fake_client.table.assert_called_with("market_moving_averages")


def test_unknown_sub_service_id_reverse_maps_from_ma(monkeypatch):
    from services.tatva_catalog import resolve_sub_service_label

    unknown = "cccccccccccccccccccccccc"
    fake_table = MagicMock()
    fake_table.select.return_value = fake_table
    fake_table.eq.return_value = fake_table
    fake_table.limit.return_value = fake_table
    fake_table.execute.return_value = MagicMock(
        data=[{"sub_service": "Loft & Door Type"}]
    )
    fake_client = MagicMock()
    fake_client.table.return_value = fake_table
    monkeypatch.setattr(
        "services.env_config.get_supabase_client", lambda: fake_client
    )
    assert resolve_sub_service_label(unknown) == "Loft & Door Type"
    fake_client.table.assert_called_with("market_moving_averages")

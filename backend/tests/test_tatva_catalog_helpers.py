"""Unit tests for Tatva catalog pure helpers."""

from __future__ import annotations

from services.tatva_catalog import (
    _entry_name_and_id,
    _unwrap_catalog_list,
    is_object_id,
    payload_looks_like_catalog_maps,
)


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

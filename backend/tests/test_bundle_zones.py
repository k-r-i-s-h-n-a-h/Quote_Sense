"""BUNDLE_NOT_DECOMPOSABLE catch-all zones — not the older lumpsum-line bundles."""

from __future__ import annotations

import pandas as pd

from services.bundles import (
    _is_generic_zone,
    apply_bundle_zones,
    bundle_zone_map,
)


def _zone_df(rows: list[dict]) -> pd.DataFrame:
    return pd.DataFrame(rows)


def test_common_washroom_is_not_a_generic_zone():
    assert _is_generic_zone("Common Washroom") is False
    assert _is_generic_zone("Common Bathroom") is False


def test_bare_catch_alls_are_still_generic():
    assert _is_generic_zone("Common") is True
    assert _is_generic_zone("General") is True
    assert _is_generic_zone("Whole home electrical") is True


def test_ordinary_rooms_were_never_generic():
    assert _is_generic_zone("Kitchen") is False
    assert _is_generic_zone("Ground Floor Bedroom 1") is False


def _washroom_lines(vendor: str = "EXCESS INTERIORS") -> list[dict]:
    space = "Common Washroom"
    return [
        {
            "vendor_name": vendor,
            "space": space,
            "space_raw": space,
            "space_id": "common_washroom",
            "sub_service": "Cummode modifications",
            "item_name": "Cummode modifications",
            "amount": 12000.0,
        },
        {
            "vendor_name": vendor,
            "space": space,
            "space_raw": space,
            "space_id": "common_washroom",
            "sub_service": "Plumbing materials",
            "item_name": "Plumbing materials",
            "amount": 18000.0,
        },
        {
            "vendor_name": vendor,
            "space": space,
            "space_raw": space,
            "space_id": "common_washroom",
            "sub_service": "Tiles requirement",
            "item_name": "Tiles requirement",
            "amount": 22000.0,
        },
    ]


def test_three_line_common_washroom_is_not_a_bundle_zone():
    df = _zone_df(_washroom_lines())
    assert bundle_zone_map(df) == {}
    out = apply_bundle_zones(df.copy())
    assert bool(out["bundle_zone"].any()) is False


def test_bare_common_catch_all_is_still_a_bundle_zone():
    vendor = "INT360 DESIGN"
    space = "Common"
    rows = [
        {
            "vendor_name": vendor,
            "space": space,
            "space_raw": space,
            "space_id": "common",
            "sub_service": "Plumbing",
            "item_name": "Plumbing",
            "amount": 180000.0,
        },
        {
            "vendor_name": vendor,
            "space": space,
            "space_raw": space,
            "space_id": "common",
            "sub_service": "Metal grill",
            "item_name": "Metal grill",
            "amount": 120000.0,
        },
        {
            "vendor_name": vendor,
            "space": space,
            "space_raw": space,
            "space_id": "common",
            "sub_service": "False ceiling",
            "item_name": "False ceiling",
            "amount": 117114.0,
        },
        {
            "vendor_name": vendor,
            "space": space,
            "space_raw": space,
            "space_id": "common",
            "sub_service": "Termite treatment",
            "item_name": "Termite treatment",
            "amount": 25000.0,
        },
        {
            "vendor_name": vendor,
            "space": space,
            "space_raw": space,
            "space_id": "common",
            "sub_service": "Window glazing",
            "item_name": "Window glazing",
            "amount": 40000.0,
        },
    ]
    df = _zone_df(rows)
    zones = bundle_zone_map(df)
    assert (vendor, "common") in zones
    assert len(zones[(vendor, "common")]) >= 2
    out = apply_bundle_zones(df.copy())
    assert bool(out["bundle_zone"].all()) is True

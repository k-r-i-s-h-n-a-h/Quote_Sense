"""S4b — POSSIBLE_CROSS_SCOPE_MATCH, including washroom civil work."""

from __future__ import annotations

import pandas as pd

from services.cross_scope import (
    CROSS_SCOPE_MIN_INR,
    cross_scope_candidates,
    functional_group,
)

A = "North Interiors (Q-AA)"
B = "South Fitouts (Q-BB)"
VENDORS = [A, B]


def _row(**kwargs):
    base = {
        "vendor_name": A,
        "space_id": "bathroom",
        "space": "Ensuite Bathroom",
        "space_raw": "Ensuite Bathroom",
        "sub_service": "",
        "item_name": "",
        "work_label": "",
        "description": "",
        "amount": 30_000.0,
        "line_id": "a1",
    }
    base.update(kwargs)
    return base


def test_washroom_civil_flags_disjoint_wet_area_containers():
    df = pd.DataFrame(
        [
            _row(
                vendor_name=A,
                space_id="ensuite_bath",
                space="Ensuite Bathroom",
                space_raw="Ensuite Bathroom",
                sub_service="Tile removal",
                item_name="Tile removal",
                amount=28_000.0,
                line_id="a-tile-rm",
            ),
            _row(
                vendor_name=A,
                space_id="ensuite_bath",
                space="Ensuite Bathroom",
                space_raw="Ensuite Bathroom",
                sub_service="Tile fixing",
                item_name="Tile fixing",
                amount=40_000.0,
                line_id="a-tile-fx",
            ),
            _row(
                vendor_name=A,
                space_id="ensuite_bath",
                space="Ensuite Bathroom",
                space_raw="Ensuite Bathroom",
                sub_service="Waterproofing",
                item_name="Waterproofing",
                amount=22_000.0,
                line_id="a-wp",
            ),
            _row(
                vendor_name=B,
                space_id="walkin_closet",
                space="Walk-in Closet",
                space_raw="Walk-in Closet",
                description="Attached washroom tiling",
                sub_service="Tile removal",
                item_name="Old tiles",
                amount=26_000.0,
                line_id="b-tile-rm",
            ),
            _row(
                vendor_name=B,
                space_id="walkin_closet",
                space="Walk-in Closet",
                space_raw="Walk-in Closet",
                description="Attached washroom new tiles",
                sub_service="New tiles",
                item_name="New tiles",
                amount=55_000.0,
                line_id="b-tile-fx",
            ),
        ]
    )
    flagged = [
        e for e in cross_scope_candidates(df, VENDORS) if e["group"] == "washroom_civil"
    ]
    assert flagged, "disjoint washroom civil work should be a possible match"
    assert flagged[0]["match_tier"] == "POSSIBLE_CROSS_SCOPE_MATCH"
    assert flagged[0]["vendors"][A]["amount"] == 90_000
    assert flagged[0]["vendors"][B]["amount"] == 81_000


def test_kitchen_tiling_is_not_washroom_civil():
    df = pd.DataFrame(
        [
            _row(
                vendor_name=A,
                space_id="kitchen",
                space="Kitchen",
                space_raw="Kitchen",
                sub_service="Kitchen tiles",
                item_name="Kitchen tiles",
                amount=80_000.0,
                line_id="a-kit",
            ),
            _row(
                vendor_name=B,
                space_id="living",
                space="Living Room",
                space_raw="Living Room",
                sub_service="Living plastering",
                item_name="Plastering",
                amount=70_000.0,
                line_id="b-liv",
            ),
        ]
    )
    assert functional_group(df.iloc[0].to_dict()) == ""
    assert functional_group(df.iloc[1].to_dict()) == ""
    assert cross_scope_candidates(df, VENDORS) == []


def test_washroom_civil_respects_min_inr():
    df = pd.DataFrame(
        [
            _row(
                vendor_name=A,
                space_id="bath_a",
                space="Bathroom",
                space_raw="Bathroom",
                sub_service="Waterproofing",
                amount=float(CROSS_SCOPE_MIN_INR - 1),
                line_id="a-low",
            ),
            _row(
                vendor_name=B,
                space_id="closet_b",
                space="Dressing Closet",
                space_raw="Dressing Closet",
                description="Toilet waterproofing",
                sub_service="Waterproofing",
                amount=80_000.0,
                line_id="b-ok",
            ),
        ]
    )
    assert not [
        e for e in cross_scope_candidates(df, VENDORS) if e["group"] == "washroom_civil"
    ]

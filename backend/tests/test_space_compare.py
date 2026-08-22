"""Space clustering + lighting rollup for compare."""

from __future__ import annotations

import os

os.environ["GEMINI_SPACE_LLM"] = "0"

import pandas as pd

from services.space_clusters import cluster_spaces_heuristic, apply_space_clusters
from services.work_rollup import apply_work_rollup


def test_bedroom_aliases_merge_to_gf_bedroom1():
    mapping = cluster_spaces_heuristic(
        ["Bedroom 1", "Ground Floor Bedroom 1", "GF Bedroom 1"]
    )
    labels = {mapping[k]["canonical"] for k in mapping}
    assert labels == {"GF-Bedroom1"}


def test_kitchen_and_bedroom_stay_apart():
    mapping = cluster_spaces_heuristic(["Kitchen", "Ground Floor Bedroom 1"])
    assert mapping["Kitchen"]["canonical"] == "Kitchen"
    assert mapping["Ground Floor Bedroom 1"]["canonical"] == "GF-Bedroom1"


def test_spot_lights_are_project_level():
    mapping = cluster_spaces_heuristic(["Spot lights", "Adaptors", "Electrical"])
    for raw in mapping.values():
        assert raw["canonical"] == "Project-level"
        assert raw["kind"] == "not_a_space"


def test_mbr_and_walkin_do_not_merge():
    mapping = cluster_spaces_heuristic(["MBR", "Walk-in closet"])
    assert mapping["MBR"]["canonical"] != mapping["Walk-in closet"]["canonical"]


def test_common_washroom_canonical():
    mapping = cluster_spaces_heuristic(["Common Washroom", "common washroom"])
    assert mapping["Common Washroom"]["canonical"] == "Common-Washroom"


def test_dining_and_dining_area_are_one_space():
    mapping = cluster_spaces_heuristic(["Dining", "dining area", "Dining area"])
    labels = {mapping[k]["canonical"] for k in mapping}
    assert labels == {"Dining"}


def test_foyer_and_living_area_aliases():
    mapping = cluster_spaces_heuristic(
        ["Foyer", "Foyer area", ": Foyer area", "Living", "Living area"]
    )
    assert mapping["Foyer"]["canonical"] == "Foyer"
    assert mapping["Foyer area"]["canonical"] == "Foyer"
    assert mapping[": Foyer area"]["canonical"] == "Foyer"
    assert mapping["Living"]["canonical"] == "Living"
    assert mapping["Living area"]["canonical"] == "Living"


def test_kids_bedroom_is_not_gf_bedroom1():
    mapping = cluster_spaces_heuristic(["Kids bedroom", "Kids Bedroom"])
    assert mapping["Kids bedroom"]["canonical"] == "Kids-Bedroom"
    assert mapping["Kids Bedroom"]["canonical"] == "Kids-Bedroom"


def test_apply_space_clusters_column():
    df = pd.DataFrame({"space_raw": ["Bedroom 1", "Ground Floor Bedroom 1", "Kitchen"]})
    out = apply_space_clusters(df)
    assert list(out["space"]) == ["GF-Bedroom1", "GF-Bedroom1", "Kitchen"]


def test_lighting_lumpsum_vs_itemized_rollups():
    df = pd.DataFrame(
        [
            {
                "vendor_name": "INT360",
                "space": "Project-level",
                "space_raw": "Electrical",
                "sub_service": "Electrical Works",
                "item_name": "Electrical Works",
                "item_label": "Electrical Works",
                "pricing_method": "Lump Sum",
                "description": "",
                "amount": 100000,
            },
            {
                "vendor_name": "Excess",
                "space": "Project-level",
                "space_raw": "Spot lights",
                "sub_service": "Spot lights",
                "item_name": "Spot lights",
                "item_label": "Spot lights",
                "pricing_method": "Unit",
                "description": "",
                "amount": 40000,
            },
            {
                "vendor_name": "Excess",
                "space": "Project-level",
                "space_raw": "Profile lights",
                "sub_service": "Profile lights",
                "item_name": "Profile lights",
                "item_label": "Profile lights",
                "pricing_method": "Unit",
                "description": "",
                "amount": 20000,
            },
        ]
    )
    out = apply_work_rollup(df)
    assert set(out["sub_service"].unique()) == {"Electrical / lighting"}


def test_run_comparison_omits_moving_average(monkeypatch):
    monkeypatch.setattr(
        "services.comparator._generate_recommendation",
        lambda prompt, chart: "- **Lowest Total:** Excess is cheaper.",
    )
    from services.comparator import run_comparison

    df = pd.DataFrame(
        [
            {
                "vendor_name": "Excess (Q1)",
                "company": "Excess",
                "source_filename": "Q1",
                "grand_total": 150000,
                "service_category": "Interiors",
                "sub_service": "Wardrobe",
                "work_title": "Bedroom 1",
                "space_raw": "Bedroom 1",
                "item_name": "Wardrobe",
                "description": "",
                "pricing_method": "Per Sqft",
                "service_type": "midlevel",
                "rate": 1500,
                "amount": 80000,
            },
            {
                "vendor_name": "INT360 (Q2)",
                "company": "INT360",
                "source_filename": "Q2",
                "grand_total": 180000,
                "service_category": "Interiors",
                "sub_service": "Wardrobe",
                "work_title": "Ground Floor Bedroom 1",
                "space_raw": "Ground Floor Bedroom 1",
                "item_name": "Wardrobe",
                "description": "",
                "pricing_method": "Per Sqft",
                "service_type": "midlevel",
                "rate": 1600,
                "amount": 90000,
            },
        ]
    )
    out = run_comparison("sess-1", df=df)
    assert "error" not in out
    row = out["tableData"][0]
    assert row["space"] == "GF-Bedroom1"
    assert "moving_average" not in row
    assert "market_average" not in row
    assert row["Excess (Q1)"] == 80000
    assert row["INT360 (Q2)"] == 90000


def test_mongodb_keeps_nested_object_ids(monkeypatch):
    monkeypatch.setattr(
        "services.tatva_catalog.harvest_ids_from_quotes",
        lambda quotes: {},
    )
    from services.comparator import mongodb_quotes_to_dataframe

    quotes = [
        {
            "quoteNumber": "Q1",
            "quoteType": "midlevel",
            "vendorDetail": {"companyName": "Excess"},
            "pricingSummary": [{"label": "Grand Total", "value": 1000}],
            "workSummary": [
                {
                    "services": [
                        {
                            "serviceId": {"_id": "aaaaaaaaaaaaaaaaaaaaaaaa", "name": "Interiors"},
                            "workItems": [
                                {
                                    "workTitle": "Bedroom 1",
                                    "subService": {
                                        "_id": "bbbbbbbbbbbbbbbbbbbbbbbb",
                                        "name": "Wardrobe",
                                    },
                                    "pricingMethod": {
                                        "_id": "cccccccccccccccccccccccc",
                                        "name": "Per Sqft",
                                    },
                                    "pricingInput": [{"grandTotal": 500, "quantity": 10, "rate": 50}],
                                }
                            ],
                        }
                    ]
                }
            ],
        }
    ]
    df = mongodb_quotes_to_dataframe(quotes)
    assert df.iloc[0]["sub_service_id"] == "bbbbbbbbbbbbbbbbbbbbbbbb"
    assert df.iloc[0]["pricing_method_id"] == "cccccccccccccccccccccccc"
    assert df.iloc[0]["service_id"] == "aaaaaaaaaaaaaaaaaaaaaaaa"
    assert df.iloc[0]["space_raw"] == "Bedroom 1"


def test_wardrobe_does_not_roll_into_lighting():
    df = pd.DataFrame(
        [
            {
                "vendor_name": "A",
                "space": "GF-Bedroom1",
                "space_raw": "Bedroom 1",
                "sub_service": "Wardrobe",
                "item_name": "Wardrobe",
                "item_label": "Wardrobe",
                "pricing_method": "Per Sqft",
                "description": "",
                "amount": 50000,
            },
            {
                "vendor_name": "B",
                "space": "Project-level",
                "space_raw": "Electrical",
                "sub_service": "Electrical Works",
                "item_name": "Electrical",
                "item_label": "Electrical",
                "pricing_method": "Lump Sum",
                "description": "",
                "amount": 80000,
            },
        ]
    )
    out = apply_work_rollup(df)
    wardrobe = out[out["sub_service"] == "Wardrobe"]
    assert len(wardrobe) == 1

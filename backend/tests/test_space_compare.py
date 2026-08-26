"""Space clustering (S3) and its interaction with the rest of the pipeline."""

from __future__ import annotations

import os

# Deterministic: the LLM overlays are refinements, never the source of truth.
os.environ["GEMINI_SPACE_LLM"] = "0"
os.environ["GEMINI_WORK_LLM"] = "0"

import pandas as pd

from services.space_clusters import (
    apply_space_clusters,
    cluster_spaces_heuristic,
    is_room_label,
    resolve_space,
)


def test_bedroom_aliases_merge_into_one_room():
    """Same room, three spellings: one cluster, named by the vendors."""
    mapping = cluster_spaces_heuristic(
        ["Bedroom 1", "Ground Floor Bedroom 1", "GF Bedroom 1"]
    )
    assert len({mapping[k]["cluster_id"] for k in mapping}) == 1
    labels = {mapping[k]["canonical"] for k in mapping}
    assert labels == {"Ground Floor Bedroom 1"}


def test_floor_is_never_invented():
    """Nobody said ground floor, so the heading must not claim one.

    The old default put every unqualified bedroom in `gf_bedroom1` and titled it
    "GF-Bedroom1", printing a floor that appeared in neither quote.
    """
    mapping = cluster_spaces_heuristic(["Bedroom 1", "BR 1", "Kitchen"])
    assert mapping["Bedroom 1"]["canonical"] == "Bedroom 1"
    assert mapping["BR 1"]["cluster_id"] == mapping["Bedroom 1"]["cluster_id"]


def test_ambiguous_bedroom_does_not_pick_a_floor():
    """With both floors quoted, an unqualified bedroom stays on its own."""
    mapping = cluster_spaces_heuristic(
        ["Bedroom 1", "GF Bedroom 1", "First Floor Bedroom 1"]
    )
    assert len({mapping[k]["cluster_id"] for k in mapping}) == 3


def test_living_room_abbreviations_merge():
    """LIVING / L R / LVR / L ROOM / Lroom / Living Room are one customer space.

    Showing each spelling as its own section is the failure this test locks.
    Customers need one living-area total, not four fragments to add by hand.
    """
    mapping = cluster_spaces_heuristic(
        ["LIVING", "Living Room", "L R", "LVR", "L ROOM", "Lroom", "Liv"]
    )
    assert len({mapping[k]["cluster_id"] for k in mapping}) == 1
    assert mapping["Living Room"]["cluster_id"] == "living"
    heading = mapping["Living Room"]["canonical"]
    assert "living" in heading.casefold()


def test_abbreviation_only_cluster_falls_back_to_a_room_word():
    """No vendor spelled it out, so an abbreviation cannot be the heading."""
    mapping = cluster_spaces_heuristic(["L R", "LVR"])
    assert mapping["L R"]["canonical"] == "Living"


def test_kitchen_and_bedroom_stay_apart():
    mapping = cluster_spaces_heuristic(["Kitchen", "Ground Floor Bedroom 1"])
    assert mapping["Kitchen"]["canonical"] == "Kitchen"
    assert mapping["Ground Floor Bedroom 1"]["canonical"] == "Ground Floor Bedroom 1"


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
    assert mapping["Common Washroom"]["canonical"] == "Common Washroom"


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


def test_kids_bedroom_is_not_a_numbered_bedroom():
    mapping = cluster_spaces_heuristic(["Kids bedroom", "Kids Bedroom"])
    assert mapping["Kids bedroom"]["cluster_id"] == "kids_bedroom"
    assert mapping["Kids bedroom"]["canonical"] == "Kids Bedroom"


def test_lounge_spellings_on_one_floor_merge():
    mapping = cluster_spaces_heuristic(
        ["Second Floor Family Lounge", "Second Floor Lounge", "Second F Lounge"]
    )
    ids = {mapping[k]["cluster_id"] for k in mapping}
    assert len(ids) == 1
    heading = mapping["Second Floor Family Lounge"]["canonical"]
    assert heading in {
        "Second Floor Family Lounge",
        "Second Floor Lounge",
        "Second F Lounge",
    }


def test_bathroom_is_not_swallowed_by_the_bedroom_it_is_attached_to():
    """'Master attached' names the wet room, not the bedroom."""
    assert (
        resolve_space({"space_raw": "First floor Bathroom (Master attached)"})["space_id"]
        == "1f_mbr_bathroom"
    )
    assert resolve_space({"space_raw": "Kids room attached bathroom"})["space_id"] == "kids_bathroom"


def test_unqualified_bathroom_is_not_the_ground_floor_common():
    """The old fallback filed every unknown bathroom as common_washroom."""
    third = resolve_space({"space_raw": "Third Floor Bathroom Attached"})
    assert third["space_id"] == "3f_attached_bathroom"
    assert "common" not in third["space_id"]


def test_bathroom_typo_still_groups():
    mapping = cluster_spaces_heuristic(
        ["Third Floor Bathroom Attached", "Third floor Attached batroom"]
    )
    assert mapping["Third Floor Bathroom Attached"]["cluster_id"] == mapping[
        "Third floor Attached batroom"
    ]["cluster_id"]


def test_ground_floor_bathroom_joins_the_common_one_not_the_attached():
    mapping = cluster_spaces_heuristic(
        [
            "Ground floor Common Bathroom",
            "Ground floor bathroom",
            "bedroom ground floor attached bathroom",
        ]
    )
    common_id = mapping["Ground floor Common Bathroom"]["cluster_id"]
    assert mapping["Ground floor bathroom"]["cluster_id"] == common_id
    assert mapping["bedroom ground floor attached bathroom"]["cluster_id"] != common_id


def test_floor_only_label_uses_the_description_hint():
    """'Ground floor' is not a room; the line is about the living room."""
    assert is_room_label("Ground floor") is False
    resolved = resolve_space(
        {
            "space_raw": "Ground floor",
            "item_name": "TV Units",
            "description": "Tv units for living room",
        }
    )
    assert resolved["space_id"] == "living"
    assert resolved["space_source"] == "description"


def test_bare_room_on_a_floor_joins_the_unique_bedroom():
    df = pd.DataFrame(
        {
            "space_raw": [
                "ground floor bedroom",
                "G F room",
                "Third Floor Bedroom(Guest/Kids)",
                "Third floor room",
            ]
        }
    )
    out = apply_space_clusters(df)
    gf = out[out["space_raw"].isin(["ground floor bedroom", "G F room"])]
    assert len(set(gf["space_id"])) == 1
    third = out[
        out["space_raw"].isin(
            ["Third Floor Bedroom(Guest/Kids)", "Third floor room"]
        )
    ]
    assert len(set(third["space_id"])) == 1
    assert set(gf["space_id"]).isdisjoint(set(third["space_id"]))


def test_whole_home_and_full_house_are_project_level():
    for raw in ("Whole Home", "Full House design", "Full House"):
        resolved = resolve_space({"space_raw": raw})
        assert resolved["space_id"] == "project_level", raw


def test_kids_attached_bathroom_joins_the_third_floor_attached():
    mapping = cluster_spaces_heuristic(
        [
            "Third Floor Bedroom(Guest/Kids)",
            "Third Floor Bathroom Attached",
            "Kids room attached bathroom",
        ]
    )
    assert (
        mapping["Kids room attached bathroom"]["cluster_id"]
        == mapping["Third Floor Bathroom Attached"]["cluster_id"]
    )
    assert (
        mapping["Third Floor Bedroom(Guest/Kids)"]["cluster_id"]
        != mapping["Third Floor Bathroom Attached"]["cluster_id"]
    )


def test_apply_space_clusters_column():
    df = pd.DataFrame({"space_raw": ["Bedroom 1", "Ground Floor Bedroom 1", "Kitchen"]})
    out = apply_space_clusters(df)
    assert list(out["space"]) == [
        "Ground Floor Bedroom 1",
        "Ground Floor Bedroom 1",
        "Kitchen",
    ]


def test_description_derived_row_borrows_its_siblings_wording():
    """A row placed by its description has no room string of its own.

    It must inherit the heading the other vendor supplied rather than fall back
    to a canonical name we made up.
    """
    df = pd.DataFrame(
        [
            {
                "space_raw": "Used cloth unit",
                "item_name": "MBR Used cloth units",
                "description": "MBR Used cloth storages",
            },
            {"space_raw": "Master Bedroom", "item_name": "Wardrobe", "description": ""},
        ]
    )
    out = apply_space_clusters(df)
    assert list(out["space"]) == ["Master Bedroom", "Master Bedroom"]


def test_item_name_in_space_column_is_not_a_room():
    """The phantom-space bug: `Used cloth unit` became its own room.

    It is an item name with no room prefix, so the old literal blocklist missed
    it, while the room sat in plain sight in the line's own description.
    """
    row = {
        "space_raw": "Used cloth unit",
        "item_name": "MBR Used cloth units",
        "description": "MBR Used cloth storages - laminate finish.",
    }
    assert is_room_label(row["space_raw"], row["item_name"]) is False
    resolved = resolve_space(row)
    assert resolved["space_id"] == "mbr"
    assert resolved["space_source"] == "description"


def test_room_prefixed_item_labels_fold_into_their_room():
    for raw in ("MBR Dressing unit", "MBR Dressing Mirror", "MBR Study unit"):
        assert resolve_space({"space_raw": raw})["space_id"] == "mbr"
    assert resolve_space({"space_raw": "Kitchen Accessories"})["space_id"] == "kitchen"
    assert (
        resolve_space({"space_raw": "Common vanity unit"})["space_id"]
        == "common_washroom"
    )
    # A room-prefixed item is not fit to be a heading, so the cluster falls back
    # to the room word rather than titling the column "MBR Dressing unit".
    df = pd.DataFrame({"space_raw": ["MBR Dressing unit", "MBR Study unit"]})
    assert set(apply_space_clusters(df)["space"]) == {"Master Bedroom"}


def test_explicit_room_outranks_a_description_hint():
    explicit = resolve_space({"space_raw": "Master bedroom", "description": "Kitchen unit"})
    assert explicit["space_id"] == "mbr"
    assert explicit["space"] == "Master bedroom"
    assert explicit["space_source"] == "space_raw"
    # Confidence must reflect that a description-derived room is a weaker signal.
    derived = resolve_space(
        {"space_raw": "Used cloth unit", "description": "MBR storages"}
    )
    assert derived["space_confidence"] < explicit["space_confidence"]


def test_project_wide_items_have_no_room():
    for raw in (
        "Window blinds",
        "Tissue Paper holder",
        "Profile lights Required areas",
        "Electrical work required areas",
    ):
        assert resolve_space({"space_raw": raw})["space"] == "Project-level"


def test_run_comparison_omits_moving_average(monkeypatch):
    monkeypatch.setattr(
        "services.comparator._generate_recommendation",
        lambda prompt, chart, bundles=None: "- **Lowest Total:** Excess is cheaper.",
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
    assert row["space"] == "Ground Floor Bedroom 1"
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


def test_gst_mode_from_work_summary_flags():
    from services.comparator import gst_mode_from_quote

    assert gst_mode_from_quote(
        {"workSummary": [{"exclusiveGst": True, "inclusiveGst": False}]}
    ) == "exclusive"
    assert gst_mode_from_quote(
        {"workSummary": [{"exclusiveGst": False, "inclusiveGst": True}]}
    ) == "inclusive"
    assert gst_mode_from_quote({"workSummary": []}) == ""
    assert gst_mode_from_quote(
        {
            "workSummary": [
                {"exclusiveGst": True, "inclusiveGst": False},
                {"exclusiveGst": False, "inclusiveGst": True},
            ]
        }
    ) == "mixed"


def test_exclusive_quote_compares_grand_total_not_pre_gst_amount(monkeypatch):
    monkeypatch.setattr(
        "services.tatva_catalog.harvest_ids_from_quotes",
        lambda quotes: {},
    )
    from services.comparator import mongodb_quotes_to_dataframe

    quotes = [
        {
            "quoteNumber": "QEXC",
            "quoteType": "essential",
            "vendorDetail": {"companyName": "INFOSYS LIMITED"},
            "pricingSummary": [{"label": "Grand total", "value": 1180}],
            "workSummary": [
                {
                    "exclusiveGst": True,
                    "inclusiveGst": False,
                    "services": [
                        {
                            "serviceId": {"_id": "aaaaaaaaaaaaaaaaaaaaaaaa", "name": "Interiors"},
                            "workItems": [
                                {
                                    "workTitle": "Bedroom",
                                    "subService": {
                                        "_id": "bbbbbbbbbbbbbbbbbbbbbbbb",
                                        "name": "Wardrobe",
                                    },
                                    "pricingMethod": {
                                        "_id": "cccccccccccccccccccccccc",
                                        "name": "Per Sqft",
                                    },
                                    "pricingInput": [
                                        {
                                            "amount": 1000,
                                            "gstPercentage": 18,
                                            "grandTotal": 1180,
                                            "quantity": 1,
                                            "rate": 1000,
                                        }
                                    ],
                                }
                            ],
                        }
                    ],
                }
            ],
        },
        {
            "quoteNumber": "QINC",
            "quoteType": "essential",
            "vendorDetail": {"companyName": "INFOSYS LIMITED"},
            "pricingSummary": [{"label": "Grand total", "value": 1180}],
            "workSummary": [
                {
                    "exclusiveGst": False,
                    "inclusiveGst": True,
                    "services": [
                        {
                            "serviceId": {"_id": "aaaaaaaaaaaaaaaaaaaaaaaa", "name": "Interiors"},
                            "workItems": [
                                {
                                    "workTitle": "Bedroom",
                                    "subService": {
                                        "_id": "bbbbbbbbbbbbbbbbbbbbbbbb",
                                        "name": "Wardrobe",
                                    },
                                    "pricingMethod": {
                                        "_id": "cccccccccccccccccccccccc",
                                        "name": "Per Sqft",
                                    },
                                    "pricingInput": [
                                        {
                                            "amount": 1180,
                                            "gstPercentage": 18,
                                            "grandTotal": 1180,
                                            "quantity": 1,
                                            "rate": 1180,
                                        }
                                    ],
                                }
                            ],
                        }
                    ],
                }
            ],
        },
    ]
    df = mongodb_quotes_to_dataframe(quotes)
    by_quote = {row["quote_number"]: row for _, row in df.iterrows()}
    assert by_quote["QEXC"]["gst_mode"] == "exclusive"
    assert by_quote["QINC"]["gst_mode"] == "inclusive"
    assert by_quote["QEXC"]["amount"] == 1180
    assert by_quote["QINC"]["amount"] == 1180


def test_wardrobe_does_not_roll_into_lighting():
    """A non-family line must survive S4 untouched, in its own room."""
    from services.bundles import apply_bundles, family_of
    from services.work_catalog import apply_work_catalog

    df = pd.DataFrame(
        [
            {
                "vendor_name": "A",
                "space_raw": "Bedroom 1",
                "sub_service": "Wardrobe",
                "item_name": "Wardrobe",
                "pricing_method": "Per Sqft",
                "description": "",
                "amount": 50000,
            },
            {
                "vendor_name": "B",
                "space_raw": "Electrical",
                "sub_service": "Electrical Works",
                "item_name": "Electrical",
                "pricing_method": "Lump Sum",
                "description": "",
                "amount": 80000,
            },
        ]
    )
    out = apply_bundles(apply_space_clusters(apply_work_catalog(df)))
    wardrobe = out[out["sub_service"] == "Wardrobe"]
    assert len(wardrobe) == 1
    assert wardrobe.iloc[0]["space"] == "Bedroom 1"
    assert wardrobe.iloc[0]["scope"] == "space"
    assert family_of(wardrobe.iloc[0]) != "lighting"

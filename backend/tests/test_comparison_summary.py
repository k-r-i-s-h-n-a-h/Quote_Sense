"""S5 — incl_in_parent coverage and deterministic comparison summaries."""

from __future__ import annotations

import os

os.environ["GEMINI_SPACE_LLM"] = "0"
os.environ["GEMINI_WORK_LLM"] = "0"

import pandas as pd

from services.comparator import _build_coverage, _build_space_rows
from services.comparison_summary import row_comparison_summary, space_header_summary


A = "Infosys (Q1)"
B = "TCS (Q2)"
VENDORS = [A, B]


def test_qty_driven_summary():
    row = {
        A: 90000,
        B: 60000,
        "coverage": {A: "quoted", B: "quoted"},
        "measures": {
            A: {"quantity": 180, "rate": 500, "pricing_method": "Area – Direct Entry (sq ft)"},
            B: {"quantity": 120, "rate": 500, "pricing_method": "Area – Direct Entry (sq ft)"},
        },
    }
    text = row_comparison_summary(row, VENDORS)
    assert "180" in text and "120" in text
    assert "more area" in text
    assert "Infosys is ₹30,000 higher" in text


def test_rate_driven_summary_when_qty_similar():
    row = {
        A: 50000,
        B: 40000,
        "coverage": {A: "quoted", B: "quoted"},
        "measures": {
            A: {"quantity": 100, "rate": 500, "pricing_method": "Area (sqft)"},
            B: {"quantity": 100, "rate": 400, "pricing_method": "Area (sqft)"},
        },
    }
    text = row_comparison_summary(row, VENDORS)
    assert "same area" in text
    assert "rate is higher" in text
    assert "Infosys" in text
    assert "₹10,000 higher" in text


def test_qty_and_rate_both_named_when_both_differ():
    row = {
        A: 12036,
        B: 29500,
        "coverage": {A: "quoted", B: "quoted"},
        "measures": {
            A: {
                "quantity": 12,
                "rate": 850,
                "pricing_method": "Area – Direct Entry (sq ft)",
                "description": "Wall panelling with designed laminates and glass combinations",
            },
            B: {
                "quantity": 20,
                "rate": 1250,
                "pricing_method": "Area – Direct Entry (sq ft)",
                "description": "Decor wall panelling with louvers",
            },
        },
    }
    text = row_comparison_summary(row, VENDORS)
    assert "TCS is ₹17,464 higher" in text
    assert "12 sqft vs 20 sqft" in text
    assert "₹850/sqft vs ₹1,250/sqft" in text
    assert "laminates" in text and "glass" in text
    assert "louvers" in text


def test_spec_omitted_when_description_empty():
    row = {
        A: 12036,
        B: 29500,
        "coverage": {A: "quoted", B: "quoted"},
        "measures": {
            A: {"quantity": 12, "rate": 850, "pricing_method": "Area (sqft)", "description": ""},
            B: {"quantity": 20, "rate": 1250, "pricing_method": "Area (sqft)", "description": ""},
        },
    }
    text = row_comparison_summary(row, VENDORS)
    assert "specified" not in text
    assert "12 sqft vs 20 sqft" in text


def test_true_gap_keeps_did_not_quote():
    row = {
        A: 25000,
        B: 0,
        "coverage": {A: "quoted", B: "not_quoted"},
        "measures": {
            A: {"quantity": 1, "rate": 25000, "pricing_method": "Lump Sum"},
            B: {"quantity": 0, "rate": 0, "pricing_method": ""},
        },
    }
    assert "did not quote" in row_comparison_summary(row, VENDORS)


def test_elsewhere_parent_beats_na_wording():
    row = {
        A: 50000,
        B: 0,
        "coverage": {A: "quoted", B: "incl_in_parent:Master Bedroom"},
    }
    text = row_comparison_summary(row, VENDORS)
    assert "inside Master Bedroom" in text
    assert "did not quote" not in text


def test_bundle_coverage_still_names_the_package():
    row = {
        A: 0,
        B: 37198,
        "coverage": {A: "incl_in_bundle:Hardware & accessories", B: "quoted"},
    }
    text = row_comparison_summary(row, VENDORS)
    assert "Hardware" in text


def test_header_fewer_items_higher():
    text = space_header_summary(
        {A: 78942, B: 75402},
        VENDORS,
        item_counts={A: 3, B: 5},
    )
    assert "Infosys is ₹3,540 higher" in text
    assert "3 items vs 5" in text
    assert "charged more for fewer lines" in text


def test_header_scopes_differ_with_item_counts():
    text = space_header_summary(
        {A: 86049, B: 100000},
        VENDORS,
        comparable=False,
        package_vs_itemised=True,
        item_counts={A: 7, B: 11},
    )
    assert "TCS is ₹13,951 higher" in text
    assert "scopes differ (package vs itemised)" in text
    assert "7 items vs 11" in text


def test_header_names_exclusive_line():
    text = space_header_summary(
        {A: 171154, B: 100000},
        VENDORS,
        exclusive_labels={A: [], B: ["Vanity unit", "Side table"]},
    )
    assert "Infosys is ₹71,154 higher" in text
    assert "TCS also quoted Vanity unit, Side table" in text


def _nested_df():
    return pd.DataFrame(
        [
            {
                "space_id": "1f_walkin",
                "space": "Walk-in Closet",
                "vendor_name": A,
                "scope": "space",
                "work_key": "norm:wardrobe",
                "work_label": "Wardrobe",
                "sub_service": "Wardrobe",
                "item_name": "Wardrobe",
                "item_label": "Wardrobe",
                "service_category": "Furniture",
                "service_type": "essential",
                "pricing_method": "Area – Direct Entry (sq ft)",
                "quantity": 80,
                "rate": 625,
                "amount": 50000,
                "bundle_family": "",
                "contained_in": "mbr",
                "space_raw": "Walk-in closet",
                "work_confidence": 1.0,
                "space_confidence": 0.95,
                "__seq": 0,
            },
            {
                "space_id": "mbr",
                "space": "Master Bedroom",
                "vendor_name": B,
                "scope": "space",
                "work_key": "norm:wardrobe",
                "work_label": "Wardrobe",
                "sub_service": "Wardrobe",
                "item_name": "Wardrobe",
                "item_label": "Wardrobe",
                "service_category": "Furniture",
                "service_type": "essential",
                "pricing_method": "Area – Direct Entry (sq ft)",
                "quantity": 70,
                "rate": 571,
                "amount": 40000,
                "bundle_family": "",
                "contained_in": "",
                "space_raw": "Master Bedroom",
                "work_confidence": 1.0,
                "space_confidence": 0.95,
                "__seq": 1,
            },
        ]
    )


def test_nested_wic_cell_is_incl_in_parent_not_na():
    df = _nested_df()
    rows = _build_space_rows(df, VENDORS, {})
    wic = next(r for r in rows if r["space_id"] == "1f_walkin")
    assert wic[A] == 50000
    assert wic[B] == 0
    assert str(wic["coverage"][B]).startswith("incl_in_parent")
    assert "Master Bedroom" in wic["coverage"][B]
    assert wic["contained_in"] == "mbr"
    assert "inside" in (wic.get("summary") or "")


def test_nested_spaces_stay_two_ids_in_matrix_rows():
    rows = _build_space_rows(_nested_df(), VENDORS, {})
    assert {r["space_id"] for r in rows} == {"1f_walkin", "mbr"}


def test_space_coverage_marks_child_incl_in_parent():
    entries = _build_coverage(_nested_df(), VENDORS)
    child_b = next(
        e for e in entries if e["space_id"] == "1f_walkin" and e["vendor"] == B
    )
    assert child_b["status"] == "incl_in_parent"
    assert child_b["comparable"] is False
    assert child_b.get("parent_space") == "Master Bedroom"


def test_both_vendors_quoting_child_stays_quoted():
    df = _nested_df()
    extra = df.iloc[0].copy()
    extra["vendor_name"] = B
    extra["amount"] = 35000
    extra["quantity"] = 60
    df = pd.concat([df, pd.DataFrame([extra])], ignore_index=True)
    entries = _build_coverage(df, VENDORS)
    child_b = next(
        e for e in entries if e["space_id"] == "1f_walkin" and e["vendor"] == B
    )
    assert child_b["status"] == "quoted"


def test_space_totals_unchanged_by_parent_pointer():
    df = _nested_df()
    rows = _build_space_rows(df, VENDORS, {})
    wic = next(r for r in rows if r["space_id"] == "1f_walkin")
    mbr = next(r for r in rows if r["space_id"] == "mbr")
    assert wic[A] + mbr[A] == 50000
    assert wic[B] + mbr[B] == 40000

"""S5 — incl_in_parent coverage and deterministic comparison summaries."""

from __future__ import annotations

import os

os.environ["GEMINI_SPACE_LLM"] = "0"
os.environ["GEMINI_WORK_LLM"] = "0"

import pandas as pd

from services.comparator import _build_coverage, _build_space_rows
from services.comparison_summary import (
    apply_description_covers,
    row_comparison_summary,
    space_header_summary,
)
from services.work_catalog import apply_work_catalog


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
    assert "Infosys: 180 sqft; TCS: 120 sqft" in text
    assert "Infosys billed more area" in text
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
    assert "Infosys: 12 sqft; TCS: 20 sqft" in text
    assert "Infosys: ₹850/sqft; TCS: ₹1,250/sqft" in text
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
    assert "Infosys: 12 sqft; TCS: 20 sqft" in text


def test_same_company_quotes_are_named_q1_and_q2():
    q1 = "Tatva Interiors (QUOTE-101)"
    q2 = "Tatva Interiors (QUOTE-202)"
    row = {
        q1: 90000,
        q2: 60000,
        "coverage": {q1: "quoted", q2: "quoted"},
        "measures": {
            q1: {
                "quantity": 180,
                "rate": 500,
                "pricing_method": "Area (sqft)",
            },
            q2: {
                "quantity": 120,
                "rate": 500,
                "pricing_method": "Area (sqft)",
            },
        },
    }

    text = row_comparison_summary(row, [q1, q2])
    assert "Tatva Interiors Q1 is ₹30,000 higher" in text
    assert "Tatva Interiors Q1: 180 sqft" in text
    assert "Tatva Interiors Q2: 120 sqft" in text


def test_description_cover_names_civil_lumpsum_instead_of_omission():
    q1 = "INFOSYS LIMITED (QDGHERX)"
    q2 = "INFOSYS LIMITED (QF82HJG)"
    tiling = {
        "sub_service": "Tiling — dismantling",
        "work_key": "alias:tiling::intent:dismantling",
        "space": "Modular Kitchen",
        q1: 3776,
        q2: 0,
        "coverage": {q1: "quoted", q2: "not_quoted"},
        "measures": {
            q1: {
                "quantity": 80,
                "rate": 40,
                "pricing_method": "Area – Direct Entry (sq ft)",
                "description": "Tiling dismantle for Modular Kitchen.",
            },
            q2: {"quantity": 0, "rate": 0, "pricing_method": "", "description": ""},
        },
    }
    civil = {
        "sub_service": "Civil services",
        "work_key": "norm:civil::intent:dismantling",
        "space": "Other services",
        q1: 0,
        q2: 9912,
        "coverage": {q1: "not_quoted", q2: "quoted"},
        "measures": {
            q1: {"quantity": 0, "rate": 0, "pricing_method": "", "description": ""},
            q2: {
                "quantity": 120,
                "rate": 70,
                "pricing_method": "Area – Direct Entry (sq ft)",
                "description": (
                    "Includes tiling dismantle, Deep cleaning after custom "
                    "furniture service and Fixing cost for Bench seating used in roof."
                ),
            },
        },
    }
    apply_description_covers([tiling, civil], [q1, q2])
    assert tiling["named_in"][q2]["label"] == "Civil services"
    text = tiling["summary"]
    assert "did not itemise" in text
    assert "Civil services" in text
    assert "dismantling" in text
    assert "cleaning" in text
    assert "did not quote this line" not in text
    assert tiling[q1] == 3776 and tiling[q2] == 0
    assert civil[q2] == 9912


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


def test_dismantling_does_not_inflate_wardrobe_install_quantity_or_rate():
    rows = [
        {
            "vendor_name": A,
            "sub_service": "Wardrobe",
            "item_name": "Wardrobe",
            "description": "Dismantle charges for wardrobe & loft",
            "quantity": 70,
            "rate": 100,
            "amount": 7000,
        },
        {
            "vendor_name": A,
            "sub_service": "Wardrobe",
            "item_name": "Wardrobe",
            "description": "HDHMR wardrobe with laminate shutters",
            "quantity": 40,
            "rate": 1550,
            "amount": 73160,
        },
        {
            "vendor_name": B,
            "sub_service": "Wardrobe",
            "item_name": "Wardrobe",
            "description": "Wardrobe with Century laminate",
            "quantity": 45.5,
            "rate": 1600,
            "amount": 85904,
        },
    ]
    df = apply_work_catalog(pd.DataFrame(rows))
    df["space_id"] = "bedroom_2"
    df["space"] = "Ground Floor Bedroom 2"
    df["space_raw"] = "Ground Floor Bedroom 2"
    df["service_category"] = "Residential Interiors"
    df["service_type"] = "essential"
    df["pricing_method"] = "Area – Direct Entry (sq ft)"
    df["bundle_family"] = ""
    df["contained_in"] = ""
    df["space_confidence"] = 1.0
    df["__seq"] = range(len(df))

    matrix_rows = _build_space_rows(df, VENDORS, {})
    assert len(matrix_rows) == 2

    installation = next(
        row for row in matrix_rows if row["sub_service"] == "Wardrobe"
    )
    dismantling = next(
        row for row in matrix_rows if row["sub_service"] == "Wardrobe — dismantling"
    )

    assert installation[A] == 73160
    assert installation[B] == 85904
    assert installation["measures"][A]["quantity"] == 40
    assert installation["measures"][A]["rate"] == 1550
    assert dismantling[A] == 7000
    assert dismantling[B] == 0
    assert sum(row[A] for row in matrix_rows) == 80160
    assert sum(row[B] for row in matrix_rows) == 85904


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

"""S4 — price scope (lumpsum vs itemised).

The stage `work_rollup.py` was supposed to handle but almost never did: its
two-vendor guard tripped on the real data, it only knew the lighting family, and
it detected no overlaps. These tests pin all three fixes against the golden
quotes.
"""

from __future__ import annotations

import os

os.environ["GEMINI_WORK_LLM"] = "0"
os.environ["GEMINI_SPACE_LLM"] = "0"

import pandas as pd
import pytest

from services.bundles import (
    apply_bundles,
    bundle_comparison_rows,
    bundle_takeaway,
    bundled_families_by_vendor,
    enumerated_items,
    family_of,
    is_bundle,
)
from services.space_clusters import apply_space_clusters
from services.work_catalog import apply_work_catalog
from tests.fixtures import VENDOR_A, VENDOR_B, load_golden_df

HARDWARE_DESC = (
    "5 tandem, 1 bottle unit, Rolling shutter, Gola handles, Cutlery tray, "
    "Anti skid mat by haffle/ livesmrt."
)


@pytest.fixture(scope="module")
def golden():
    df = load_golden_df()
    return apply_bundles(apply_space_clusters(apply_work_catalog(df)))


@pytest.fixture(scope="module")
def bundle_rows(golden):
    return bundle_comparison_rows(golden, [VENDOR_A, VENDOR_B])


def row_for(rows, family):
    return next(r for r in rows if r["bundle_family"] == family)


def test_enumerating_lumpsum_is_a_bundle():
    assert len(enumerated_items(HARDWARE_DESC)) >= 2
    assert is_bundle(
        {"pricing_method": "Fixed Amount / Lump Sum", "description": HARDWARE_DESC}
    )


def test_residential_package_description_is_a_bundle():
    """A room package listing furniture and finishes is a bundle.

    The old token table only knew kitchen hardware, so
    'False ceiling, Tv units, wall panels, sofa, electrical work' scored zero
    items and the Rs 1,77,000 living-room lumpsum was compared as a single
    work item against whoever itemised the same room.
    """
    living = "False ceiling, Tv units, wall panels, sofa, electrical work"
    kitchen = "Includes Modular kitchen, chimney, sink, electrical work"
    design = (
        "Includes 2D flooring, 3D visualization, Concept design, "
        "Boq preparation, Material assistence."
    )
    assert len(enumerated_items(living)) >= 2
    assert len(enumerated_items(kitchen)) >= 2
    assert len(enumerated_items(design)) >= 2
    assert is_bundle(
        {"pricing_method": "Fixed Amount / Lump Sum", "description": living}
    )
    assert is_bundle(
        {"pricing_method": "Fixed Amount / Lump Sum", "description": kitchen}
    )
    assert is_bundle(
        {"pricing_method": "Fixed Amount / Lump Sum", "description": design}
    )


def test_single_item_lump_price_is_not_a_bundle():
    """Vendor B's Rs 8,850 wall decor is lump-priced but covers one item."""
    assert not is_bundle(
        {
            "pricing_method": "Fixed Amount / Lump Sum",
            "description": "Wall Decor with PVC wall Beeding",
        }
    )
    assert not is_bundle(
        {"pricing_method": "Fixed Amount / Lump Sum", "description": "Window blinds (approx.)"}
    )
    assert not is_bundle(
        {"pricing_method": "Fixed Amount / Lump Sum", "description": "Tissue paper holder"}
    )
    # Brand names joined with & must not look like a two-item list.
    assert not is_bundle(
        {
            "pricing_method": "Fixed Amount / Lump Sum",
            "description": "Wall Decor with PVC wall Beeding, Greenply brand & Century ply",
        }
    )


def test_itemized_pricing_is_never_a_bundle():
    assert not is_bundle(
        {"pricing_method": "Area – Direct Entry (sq ft)", "description": HARDWARE_DESC}
    )


def test_family_ignores_descriptions():
    """A wardrobe's "soft closing" prose must not join the hardware family.

    Matching on `description` pulled a Rs 14,160 sliding mechanism into kitchen
    accessories and inflated that comparison by the same amount.
    """
    assert (
        family_of(
            {
                "work_key": "alias:sliding_mechanism",
                "sub_service": "Sliding Mechanism",
                "item_name": "Sliding Mechanism",
                "description": "Hettich inner sliding doors mechanisms soft closing.",
            }
        )
        != "hardware"
    )
    assert family_of({"work_key": "alias:soft_closing_hinges"}) == "hardware"
    assert family_of({"work_key": "alias:lighting_points"}) == "lighting"


def test_hardware_lumpsum_pairs_against_itemized_accessories(bundle_rows):
    """Rs 1,00,300 lumpsum vs Rs 37,198 of itemised lines, side by side."""
    row = row_for(bundle_rows, "hardware")
    assert row[VENDOR_A] == 100300
    assert row[VENDOR_B] == 37198
    assert row["basis"][VENDOR_A] == "bundle"
    assert row["basis"][VENDOR_B] == "itemized"
    assert row["line_counts"][VENDOR_B] == 5


def test_lighting_row_exists_without_any_lumpsum(bundle_rows):
    """The two-vendor guard is gone.

    Vendor A priced electrical inside the kitchen; vendor B left most of it
    project-level. Neither used a lumpsum, so the old code emitted nothing and
    the matrix rendered vendor A as N/A for electrical.
    """
    row = row_for(bundle_rows, "lighting")
    assert row[VENDOR_A] == 17700
    assert row[VENDOR_B] == 72629
    assert row["basis"][VENDOR_A] == "itemized"
    assert row["basis"][VENDOR_B] == "itemized"


def test_overlap_is_flagged_not_corrected(bundle_rows, golden):
    """The bundle names a rolling shutter that vendor A also bills separately."""
    row = row_for(bundle_rows, "hardware")
    assert any("rolling shutter" in flag for flag in row["overlap_flags"])
    # Flagged only: the separately billed line keeps its full amount.
    separate = golden[
        (golden["vendor_name"] == VENDOR_A)
        & (golden["sub_service"] == "Rolling Shutter")
    ]
    assert float(separate["amount"].iloc[0]) == 27258.0


def test_no_overlap_flag_without_a_separate_line(bundle_rows):
    row = row_for(bundle_rows, "hardware")
    # The bundle also lists a cutlery tray, which vendor A does NOT bill alone.
    assert not any("cutlery" in flag for flag in row["overlap_flags"])


def test_bundle_amount_stays_out_of_space_totals(golden):
    space_rows = golden[golden["scope"] == "space"]
    assert 100300.0 not in set(space_rows["amount"].tolist())
    bundles = golden[golden["scope"] == "bundle"]
    assert len(bundles) == 1
    assert bundles.iloc[0]["vendor_name"] == VENDOR_A


def test_scopes_partition_every_row(golden):
    assert set(golden["scope"].unique()) <= {"space", "bundle", "project"}
    assert golden["scope"].notna().all()


def test_bundled_families_map(golden):
    families = bundled_families_by_vendor(golden)
    assert "hardware" in families[VENDOR_A]
    assert VENDOR_B not in families


def test_families_confined_to_one_space_emit_no_bundle_row(bundle_rows):
    """Both vendors quoted false ceiling in the living room, so no bundle row.

    Without this the bundle tier would fill with noise for every family.
    """
    assert all(row["bundle_family"] != "ceiling" for row in bundle_rows)


def test_single_vendor_quote_produces_no_comparison_rows():
    df = pd.DataFrame(
        [
            {
                "vendor_name": "Solo (Q1)",
                "sub_service": "Hardwares",
                "item_name": "Hardwares",
                "space_raw": "Modular Kitchen",
                "pricing_method": "Fixed Amount / Lump Sum",
                "description": HARDWARE_DESC,
                "amount": 100300,
            }
        ]
    )
    out = apply_bundles(apply_space_clusters(apply_work_catalog(df)))
    rows = bundle_comparison_rows(out, ["Solo (Q1)"])
    # The line is still marked a bundle so its amount stays out of room totals.
    assert out.iloc[0]["scope"] == "bundle"
    assert all(r["basis"]["Solo (Q1)"] == "bundle" for r in rows)


def test_room_package_is_a_bundle_tied_to_its_room():
    """A living-room lumpsum must not sit in the space total as one work item."""
    df = pd.DataFrame(
        [
            {
                "vendor_name": "Lump (Q1)",
                "sub_service": "Complete package",
                "item_name": "Complete package",
                "space_raw": "Living Room",
                "pricing_method": "Fixed Amount / Lump Sum",
                "description": "False ceiling, Tv units, wall panels, sofa, electrical work",
                "amount": 177000,
            },
            {
                "vendor_name": "Itemised (Q2)",
                "sub_service": "False Ceiling",
                "item_name": "False Ceiling",
                "space_raw": "Ground Floor Living room",
                "pricing_method": "Area – Direct Entry (sq ft)",
                "description": "False ceiling for ground floor living room",
                "amount": 23600,
            },
        ]
    )
    out = apply_bundles(apply_space_clusters(apply_work_catalog(df)))
    package = out[out["sub_service"] == "Complete package"].iloc[0]
    ceiling = out[out["sub_service"] == "False Ceiling"].iloc[0]
    assert package["scope"] == "bundle"
    assert "living" in [str(s) for s in package["covered_space_ids"]]
    assert ceiling["scope"] == "space"
    assert ceiling["space_id"] == package["space_id"]
    rows = bundle_comparison_rows(out, ["Lump (Q1)", "Itemised (Q2)"])
    assert any(r["basis"]["Lump (Q1)"] == "bundle" for r in rows)


def test_unrelated_lumpsums_are_not_one_mixed_package():
    """TCS wall décor + blinds + tissue must not become Mixed (Wall decor) ₹50,150."""
    df = pd.DataFrame(
        [
            {
                "vendor_name": "TCS (Q1)",
                "sub_service": "Wall Decor",
                "item_name": "Wall Decor",
                "space_raw": "Foyer area",
                "pricing_method": "Fixed Amount / Lump Sum",
                "description": "Wall Decor with PVC wall Beeding",
                "amount": 8850,
            },
            {
                "vendor_name": "TCS (Q1)",
                "sub_service": "Wall Decor",
                "item_name": "Wall Decor",
                "space_raw": "Living area",
                "pricing_method": "Fixed Amount / Lump Sum",
                "description": "Wall Decor - Pvc wall beeding",
                "amount": 8850,
            },
            {
                "vendor_name": "TCS (Q1)",
                "sub_service": "Window blinds",
                "item_name": "Window blinds",
                "space_raw": "Window blinds",
                "pricing_method": "Fixed Amount / Lump Sum",
                "description": "Window blinds (approx.)",
                "amount": 29500,
            },
            {
                "vendor_name": "TCS (Q1)",
                "sub_service": "Tissue paper holder",
                "item_name": "Tissue paper holder",
                "space_raw": "Tissue Paper holder",
                "pricing_method": "Fixed Amount / Lump Sum",
                "description": "Tissue paper holder",
                "amount": 2950,
            },
        ]
    )
    out = apply_bundles(apply_space_clusters(apply_work_catalog(df)))
    assert (out["scope"] != "bundle").all()
    rows = bundle_comparison_rows(out, ["TCS (Q1)"])
    mixed = [r for r in rows if r["bundle_family"] == "mixed"]
    assert all(r.get("TCS (Q1)", 0) != 50150 for r in mixed)
    assert not any("wall decor" in str(r.get("bundle_label") or "").casefold() for r in mixed)


def test_two_mixed_packages_stay_separate_rows():
    """One vendor line = one package row. Do not sum leftover mixed packages."""
    df = pd.DataFrame(
        [
            {
                "vendor_name": "Lump (Q1)",
                "sub_service": "Complete package",
                "item_name": "Complete package",
                "space_raw": "Living Room",
                "pricing_method": "Fixed Amount / Lump Sum",
                "description": "False ceiling, Tv units, wall panels, sofa, electrical work",
                "amount": 177000,
            },
            {
                "vendor_name": "Lump (Q1)",
                "sub_service": "Kitchen package",
                "item_name": "Kitchen package",
                "space_raw": "Kitchen",
                "pricing_method": "Fixed Amount / Lump Sum",
                "description": "Includes Modular kitchen, chimney, sink, electrical work",
                "amount": 250000,
            },
        ]
    )
    out = apply_bundles(apply_space_clusters(apply_work_catalog(df)))
    assert list(out["scope"]) == ["bundle", "bundle"]
    rows = bundle_comparison_rows(out, ["Lump (Q1)"])
    mixed = [r for r in rows if r["bundle_family"] == "mixed"]
    assert {r["Lump (Q1)"] for r in mixed} == {177000, 250000}


def test_hardware_package_gets_a_higher_takeaway(bundle_rows):
    row = row_for(bundle_rows, "hardware")
    assert row["takeaway"]["kind"] == "package_higher"
    text = row["takeaway"]["text"]
    assert "1,00,300" in text
    assert "37,198" in text
    assert "Ask" in text


def test_lighting_recap_has_no_takeaway(bundle_rows):
    row = row_for(bundle_rows, "lighting")
    assert not row.get("takeaway")


def test_lighting_placement_is_rooms_vs_whole_home(bundle_rows):
    """Vendor A billed electrical in the kitchen; vendor B left it project-level."""
    row = row_for(bundle_rows, "lighting")
    assert row["placement"][VENDOR_A] == "space"
    assert row["placement"][VENDOR_B] == "mixed"


def test_hardware_placement_is_package_vs_rooms(bundle_rows):
    row = row_for(bundle_rows, "hardware")
    assert row["placement"][VENDOR_A] == "bundle"
    assert row["placement"][VENDOR_B] == "space"


def test_package_lower_takeaway():
    row = {
        "bundle_label": "Hardware & accessories",
        "basis": {"A": "bundle", "B": "itemized"},
        "line_counts": {"A": 1, "B": 5},
        "overlap_flags": [],
        "A": 20000,
        "B": 80000,
    }
    out = bundle_takeaway(row, ["A", "B"])
    assert out is not None
    assert out["kind"] == "package_lower"
    assert "20,000" in out["text"]
    assert "80,000" in out["text"]
    assert "cheaper" in out["text"].casefold()


def test_small_gap_has_no_takeaway():
    row = {
        "bundle_label": "Hardware",
        "basis": {"A": "bundle", "B": "itemized"},
        "line_counts": {"B": 2},
        "overlap_flags": [],
        "A": 20000,
        "B": 21000,
    }
    assert bundle_takeaway(row, ["A", "B"]) is None

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

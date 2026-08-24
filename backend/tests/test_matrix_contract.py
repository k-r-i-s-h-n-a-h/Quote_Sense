"""S5/S6 — MatrixV1 contract and the golden-comparison outcomes.

Runs the whole pipeline over the two real quotes. These assertions are the
regression net for every grouping defect the redesign fixed; see
tests/fixtures/README.md for the catalogue.
"""

from __future__ import annotations

import os

os.environ["GEMINI_WORK_LLM"] = "0"
os.environ["GEMINI_SPACE_LLM"] = "0"

import pytest

from tests.fixtures import VENDOR_A, VENDOR_B, load_golden_df

VENDORS = [VENDOR_A, VENDOR_B]


@pytest.fixture(scope="module")
def matrix(module_mocker=None):
    import services.comparator as comparator

    original = comparator._generate_recommendation
    comparator._generate_recommendation = lambda *a, **k: "- **Stub:** ok."
    try:
        return comparator.run_comparison("golden-test", df=load_golden_df())
    finally:
        comparator._generate_recommendation = original


def rows_named(matrix, label, space=None):
    out = []
    for row in matrix["spaceTier"] + matrix["projectTier"]:
        if row["sub_service"].casefold() != label.casefold():
            continue
        if space and row["space"] != space:
            continue
        out.append(row)
    return out


# --- contract ---------------------------------------------------------------


def test_payload_has_every_required_key(matrix):
    for key in (
        "contract_version",
        "vendors",
        "vendorMeta",
        "chartData",
        "spaceTier",
        "bundleTier",
        "projectTier",
        "coverage",
        "tableData",
        "report",
    ):
        assert key in matrix, f"missing {key}"
    assert matrix["contract_version"] == "MatrixV1"


def test_table_data_is_the_legacy_flat_view(matrix):
    assert matrix["tableData"] == matrix["spaceTier"] + matrix["projectTier"]


def test_every_row_carries_canonical_keys(matrix):
    for row in matrix["tableData"]:
        assert row["work_key"], f"empty work_key on {row['sub_service']}"
        assert row["space_id"]
        assert "coverage" in row


def test_tier_totals_reconcile_with_the_quotes(matrix):
    """Every rupee lands in exactly one tier — none lost, none double counted."""
    df = load_golden_df()
    for vendor in VENDORS:
        expected = float(df[df["vendor_name"] == vendor]["amount"].sum())
        tiered = (
            sum(r[vendor] for r in matrix["spaceTier"])
            + sum(r[vendor] for r in matrix["projectTier"])
            + sum(
                r[vendor]
                for r in matrix["bundleTier"]
                if r["basis"][vendor] == "bundle"
            )
        )
        # Per-row rounding of paise amounts allows a couple of rupees of drift.
        assert abs(tiered - expected) < 5, f"{vendor}: {tiered} vs {expected}"


# --- golden grouping outcomes ----------------------------------------------


def test_phantom_space_is_gone(matrix):
    spaces = {row["space"] for row in matrix["spaceTier"]}
    for phantom in (
        "Used cloth unit",
        "USED CLOTH UNIT",
        "MBR Dressing unit",
        "MBR Dressing Mirror",
        "Kitchen Accessories",
        "Common vanity unit",
    ):
        assert phantom not in spaces


def test_expected_rooms_exist(matrix):
    spaces = {row["space"] for row in matrix["spaceTier"]}
    for room in (
        "Foyer",
        "Living",
        "Dining",
        "Kitchen",
        "Master-Bedroom",
        "Kids-Bedroom",
        "Common-Washroom",
    ):
        assert room in spaces


def test_used_cloth_storage_compares_across_vendors(matrix):
    """Was stranded in a phantom room, so the two vendors never met."""
    rows = rows_named(matrix, "Used cloth storage", "Master-Bedroom")
    assert len(rows) == 1
    assert rows[0][VENDOR_A] == 23954
    assert rows[0][VENDOR_B] == 13629


@pytest.mark.parametrize(
    "label,space,amount_a,amount_b",
    [
        ("Side table", "Master-Bedroom", 14160, 9440),
        ("Rolling shutter", "Kitchen", 27258, 17700),
        ("False ceiling", "Living", 61950, 49560),
        ("Loft", "Kitchen", 60534, 47082),
        ("Crockery units", "Dining", 38940, 70092),
        ("Study table", "Kids-Bedroom", 14160, 23364),
    ],
)
def test_equivalent_work_lands_on_one_row(matrix, label, space, amount_a, amount_b):
    rows = rows_named(matrix, label, space)
    assert len(rows) == 1, f"{label} in {space} produced {len(rows)} rows"
    assert rows[0][VENDOR_A] == amount_a
    assert rows[0][VENDOR_B] == amount_b


def test_base_and_wall_units_stay_separate(matrix):
    """The dangerous direction: a false merge would silently sum both."""
    base = rows_named(matrix, "Base unit", "Kitchen")
    wall = rows_named(matrix, "Wall unit", "Kitchen")
    assert len(base) == 1 and len(wall) == 1
    assert base[0]["work_key"] != wall[0]["work_key"]


# --- bundles and coverage ---------------------------------------------------


def test_hardware_bundle_is_paired_in_the_bundle_tier(matrix):
    row = next(r for r in matrix["bundleTier"] if r["bundle_family"] == "hardware")
    assert row[VENDOR_A] == 100300
    assert row[VENDOR_B] == 37198
    assert row["overlap_flags"]


def test_electrical_is_visible_for_both_vendors(matrix):
    """Previously read `Project-level 83,544` vs `N/A`."""
    row = next(r for r in matrix["bundleTier"] if r["bundle_family"] == "lighting")
    assert row[VENDOR_A] > 0
    assert row[VENDOR_B] > 0


def test_bundled_cells_are_not_reported_as_not_quoted(matrix):
    """The five accessory cells that used to read N/A for the bundling vendor."""
    bundled = [
        row
        for row in matrix["spaceTier"]
        if str(row["coverage"].get(VENDOR_A, "")).startswith("incl_in_bundle")
    ]
    assert len(bundled) == 5
    for row in bundled:
        assert row["space"] == "Kitchen"
        assert row[VENDOR_A] == 0


def test_space_with_a_bundle_is_flagged_not_comparable(matrix):
    by_space = {}
    for entry in matrix["coverage"]:
        by_space.setdefault(entry["space"], set()).add(entry["comparable"])
    assert by_space["Kitchen"] == {False}
    assert by_space["Foyer"] == {True}


def test_coverage_covers_every_space_and_vendor(matrix):
    spaces = {row["space_id"] for row in matrix["spaceTier"]}
    pairs = {(entry["space_id"], entry["vendor"]) for entry in matrix["coverage"]}
    for space_id in spaces:
        for vendor in VENDORS:
            assert (space_id, vendor) in pairs


# --- recommendation prompt --------------------------------------------------


def test_prompt_does_not_claim_zero_means_not_quoted():
    import services.comparator as comparator

    captured = {}

    def capture(prompt, chart, bundle_tier=None):
        captured["prompt"] = prompt
        return "- **Stub:** ok."

    original = comparator._generate_recommendation
    comparator._generate_recommendation = capture
    try:
        comparator.run_comparison("golden-prompt", df=load_golden_df())
    finally:
        comparator._generate_recommendation = original

    prompt = captured["prompt"]
    assert "did not quote that work" not in prompt
    assert "incl_in_bundle" in prompt
    assert "possible_double_count" in prompt
    assert "NOT DIRECTLY COMPARABLE" in prompt


def test_fallback_report_mentions_bundles_only_when_present(matrix):
    from services.comparator import _build_fallback_report

    with_bundles = _build_fallback_report(matrix["chartData"], matrix["bundleTier"])
    without = _build_fallback_report(matrix["chartData"], [])
    assert "Bundled Scope" in with_bundles
    assert "Bundled Scope" not in without

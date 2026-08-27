"""S5/S6 — MatrixV1 contract and the golden-comparison outcomes.

Runs the whole pipeline over the two real quotes. These assertions are the
regression net for every grouping defect the redesign fixed; see
tests/fixtures/README.md for the catalogue.
"""

from __future__ import annotations

import os
import re

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


def rows_named(matrix, label, space_id=None):
    """Look rows up by `space_id`, never by the heading.

    The heading is chosen from the vendors' own wording and changes with the
    quotes; the id is the stable grouping key, so assertions belong on it.
    """
    out = []
    for row in matrix["spaceTier"] + matrix["projectTier"]:
        if row["sub_service"].casefold() != label.casefold():
            continue
        if space_id and row["space_id"] != space_id:
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
    spaces = {row["space_id"] for row in matrix["spaceTier"]}
    for room in (
        "foyer",
        "living",
        "dining",
        "kitchen",
        "mbr",
        "kids_bedroom",
        "common_washroom",
    ):
        assert room in spaces


def test_headings_come_from_the_quotes(matrix):
    """No heading may contain a word neither vendor wrote.

    The invented "GF-" prefix is the case that prompted this: the quotes never
    mention a floor, so the matrix must not either.
    """
    df = load_golden_df()
    quoted = " ".join(str(v) for v in df["space_raw"].fillna("").tolist()).casefold()
    for row in matrix["spaceTier"]:
        for word in re.findall(r"[a-z]+", row["space"].casefold()):
            assert word in quoted, f"{row['space']} invents '{word}'"


def test_used_cloth_storage_compares_across_vendors(matrix):
    """Was stranded in a phantom room, so the two vendors never met."""
    rows = rows_named(matrix, "Used cloth storage", "mbr")
    assert len(rows) == 1
    assert rows[0][VENDOR_A] == 23954
    assert rows[0][VENDOR_B] == 13629


def test_dressing_mirror_is_not_rolled_into_used_cloth(matrix):
    used = rows_named(matrix, "Used cloth storage", "mbr")
    assert used[0][VENDOR_B] == 13629
    mirrors = rows_named(matrix, "Mirror", "mbr")
    assert mirrors and mirrors[0][VENDOR_B] >= 2832
    assert "mirror" in mirrors[0]["work_key"]


def test_seater_does_not_merge_with_bench_or_crockery(matrix):
    crockery = rows_named(matrix, "Crockery units", "dining")
    assert len(crockery) == 1
    assert crockery[0][VENDOR_B] == 38940
    bench = rows_named(matrix, "Bench seating", "dining")
    assert len(bench) == 1
    assert bench[0][VENDOR_A] == 40120
    assert bench[0][VENDOR_B] in (0, None)
    seater = [
        row
        for row in matrix["spaceTier"]
        if row["space_id"] == "dining" and str(row["work_key"]).endswith("seating_unit")
    ]
    assert len(seater) == 1
    assert seater[0][VENDOR_B] == 31152


def test_tcs_wall_decor_stays_in_its_rooms(matrix):
    """Single-item lumpsums are not a Mixed (Wall decor) package of ₹50,150."""
    foyer = rows_named(matrix, "Wall decor", "foyer")
    living = rows_named(matrix, "Wall decor", "living")
    assert foyer and foyer[0][VENDOR_B] == 8850
    assert living and living[0][VENDOR_B] == 8850
    mixed = [r for r in matrix["bundleTier"] if r["bundle_family"] == "mixed"]
    assert all(r.get(VENDOR_B, 0) != 50150 for r in mixed)


@pytest.mark.parametrize(
    "label,space_id,amount_a,amount_b",
    [
        ("Side table", "mbr", 14160, 9440),
        ("Rolling shutter", "kitchen", 27258, 17700),
        ("False ceiling", "living", 61950, 49560),
        ("Loft", "kitchen", 60534, 47082),
        ("Crockery units", "dining", 38940, 38940),
        ("Study table", "kids_bedroom", 14160, 23364),
    ],
)
def test_equivalent_work_lands_on_one_row(matrix, label, space_id, amount_a, amount_b):
    rows = rows_named(matrix, label, space_id)
    assert len(rows) == 1, f"{label} in {space_id} produced {len(rows)} rows"
    assert rows[0][VENDOR_A] == amount_a
    assert rows[0][VENDOR_B] == amount_b


def test_base_and_wall_units_stay_separate(matrix):
    """The dangerous direction: a false merge would silently sum both."""
    base = rows_named(matrix, "Base unit", "kitchen")
    wall = rows_named(matrix, "Wall unit", "kitchen")
    assert len(base) == 1 and len(wall) == 1
    assert base[0]["work_key"] != wall[0]["work_key"]


# --- bundles and coverage ---------------------------------------------------


def test_space_and_project_rows_carry_bundle_family(matrix):
    lighting_project = [
        row
        for row in matrix["projectTier"]
        if any(
            token in str(row["work_key"])
            for token in ("lighting", "adaptor", "electrical")
        )
    ]
    assert lighting_project
    assert all(row.get("bundle_family") == "lighting" for row in lighting_project)
    blinds = [row for row in matrix["projectTier"] if "blind" in str(row["work_key"])]
    assert blinds and not blinds[0].get("bundle_family")


def test_hardware_bundle_is_paired_in_the_bundle_tier(matrix):
    row = next(r for r in matrix["bundleTier"] if r["bundle_family"] == "hardware")
    assert row[VENDOR_A] == 100300
    assert row[VENDOR_B] == 37198
    assert row["overlap_flags"]
    assert row["takeaway"]["kind"] == "package_higher"
    assert "1,00,300" in row["takeaway"]["text"]


def test_electrical_is_visible_for_both_vendors(matrix):
    """Previously read `Project-level 83,544` vs `N/A`."""
    row = next(r for r in matrix["bundleTier"] if r["bundle_family"] == "lighting")
    assert row[VENDOR_A] > 0
    assert row[VENDOR_B] > 0
    assert row["placement"][VENDOR_A] == "space"
    assert row["placement"][VENDOR_B] == "mixed"


def test_bundled_cells_are_not_reported_as_not_quoted(matrix):
    """The five accessory cells that used to read N/A for the bundling vendor."""
    bundled = [
        row
        for row in matrix["spaceTier"]
        if str(row["coverage"].get(VENDOR_A, "")).startswith("incl_in_bundle")
    ]
    assert len(bundled) == 5
    for row in bundled:
        assert row["space_id"] == "kitchen"
        assert row[VENDOR_A] == 0


def test_space_with_a_bundle_is_flagged_not_comparable(matrix):
    by_space = {}
    for entry in matrix["coverage"]:
        by_space.setdefault(entry["space_id"], set()).add(entry["comparable"])
    assert by_space["kitchen"] == {False}
    assert by_space["foyer"] == {True}


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
    assert "Package vs itemised" in prompt
    assert "takeaway" in prompt


def test_fallback_report_mentions_bundles_only_when_present(matrix):
    from services.comparator import _build_fallback_report

    with_bundles = _build_fallback_report(matrix["chartData"], matrix["bundleTier"])
    without = _build_fallback_report(matrix["chartData"], [])
    assert "Package vs itemised" in with_bundles
    assert "1,00,300" in with_bundles
    assert "Package vs itemised" not in without

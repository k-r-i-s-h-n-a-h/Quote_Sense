"""The five client-safety guards, on a fixture shaped like Project 0F42C9.

Each test names the real defect it locks. The quotes below reproduce the
shapes that broke — not the client's figures — so the suite stays runnable
without the customer payload:

1. a line that vanished with no lineage (Soft closing hinges);
2. two lines silently merged and relabelled (Profile + Strip lights ->
   Lighting points) beside an unrelated line that took the same label
   (Spot lights);
3. an unnumbered vendor space label force-assigned to Bedroom 1
   (Ground floor bedroom civil work) with a qty that spans rooms;
4. a washroom fit-out embedded in a walk-in closet vs a standalone bathroom;
5. a catch-all "Common" zone spanning several trades;
6. a rolling shutter priced per unit by one vendor and by area by the other.
"""

from __future__ import annotations

import os

os.environ["GEMINI_WORK_LLM"] = "0"
os.environ["GEMINI_SPACE_LLM"] = "0"

import pytest

VENDOR_A = "EXCESS INTERIORS (QCN21BW)"
VENDOR_B = "INT360 DESIGN (Q1K7W0G)"
VENDORS = [VENDOR_A, VENDOR_B]


def _line(**kwargs):
    row = {
        "service_category": "Interiors",
        "service_type": "midlevel",
        "sub_service": "",
        "item_name": "",
        "space_raw": "",
        "description": "",
        "pricing_method": "Area – Direct Entry (sq ft)",
        "pricing_method_id": "pm_area",
        "sub_service_id": "",
        "quantity": 1.0,
        "rate": 0.0,
        "amount": 0.0,
    }
    row.update(kwargs)
    row["work_title"] = row["space_raw"]
    return row


def _quote(vendor, company, quote_number, items):
    rows = []
    total = sum(item["amount"] for item in items)
    for item in items:
        row = dict(item)
        row.update(
            {
                "vendor_name": vendor,
                "company": company,
                "source_filename": quote_number,
                "quote_number": quote_number,
                "quote_date": "2026-09-01",
                "grand_total": total,
            }
        )
        rows.append(row)
    return rows


EXCESS_ITEMS = [
    # Bug 1: this line disappeared from the comparison entirely.
    _line(
        sub_service="Soft closing hinges",
        item_name="Soft closing hinges",
        space_raw="Kitchen",
        pricing_method="Per Unit / Each",
        pricing_method_id="pm_unit",
        quantity=26,
        rate=1121.0,
        amount=29146.0,
    ),
    # Bug 1: two lines that merged into one relabelled "Lighting points" row.
    _line(
        sub_service="Profile lights",
        item_name="Profile lights",
        space_raw="Living Room",
        quantity=18,
        rate=905.0,
        amount=16284.0,
    ),
    _line(
        sub_service="Strip lights",
        item_name="Strip lights",
        space_raw="Living Room",
        quantity=19,
        rate=913.0,
        amount=17346.0,
    ),
    # Bug 1: an unrelated line that also resolves to "Lighting points".
    _line(
        sub_service="Spot lights",
        item_name="Spot lights",
        space_raw="Ground Floor Bedroom 1",
        quantity=22,
        rate=1019.0,
        amount=22420.0,
    ),
    # Bug 5: priced per unit; the other vendor prices the same by area.
    _line(
        sub_service="Rolling shutter",
        item_name="Rolling shutter",
        space_raw="Kitchen",
        pricing_method="Per Unit / Each",
        pricing_method_id="pm_unit",
        quantity=1,
        rate=27258.0,
        amount=27258.0,
    ),
    # Bug 3: a whole washroom fit-out inside a closet space.
    _line(
        sub_service="Cummode",
        item_name="Cummode with flush tank",
        space_raw="Walkin Closet Area 1st Floor",
        description="Wall mounted cummode with concealed flush tank",
        amount=64000.0,
    ),
    _line(
        sub_service="Wash basin",
        item_name="Wash basin with vanity",
        space_raw="Walkin Closet Area 1st Floor",
        amount=88000.0,
    ),
    _line(
        sub_service="Shower mixer",
        item_name="Shower mixer and diverter",
        space_raw="Walkin Closet Area 1st Floor",
        amount=52000.0,
    ),
    _line(
        sub_service="WPC door",
        item_name="WPC door for washroom",
        space_raw="Walkin Closet Area 1st Floor",
        amount=200324.0,
    ),
    _line(
        sub_service="Bedroom wardrobe",
        item_name="Wardrobe",
        space_raw="Ground Floor Bedroom 2",
        quantity=64,
        rate=1400.0,
        amount=89600.0,
    ),
]

INT360_ITEMS = [
    _line(
        sub_service="Lighting points",
        item_name="Lighting points",
        space_raw="Living Room",
        quantity=30,
        rate=1000.0,
        amount=30000.0,
    ),
    # Bug 5: same work, priced by area.
    _line(
        sub_service="Rolling shutter",
        item_name="Rolling shutter",
        space_raw="Kitchen",
        pricing_method="Area – Direct Entry (sq ft)",
        pricing_method_id="pm_area",
        quantity=8,
        rate=2212.0,
        amount=17700.0,
    ),
    # Bug 2: an unnumbered bedroom label, and a qty that spans rooms.
    _line(
        sub_service="Cielling plastering",
        item_name="Cielling plastering",
        space_raw="Ground floor bedroom",
        quantity=118,
        rate=180.0,
        amount=21240.0,
    ),
    _line(
        sub_service="Concrete chhajja removal",
        item_name="Concrete chhajja removal, qty 4 considered",
        space_raw="Ground floor bedroom",
        pricing_method="Per Unit / Each",
        pricing_method_id="pm_unit",
        quantity=4,
        rate=9440.0,
        amount=37760.0,
    ),
    # Bug 3: the same washroom work as its own space.
    _line(
        sub_service="Cummode",
        item_name="Cummode with flush tank",
        space_raw="First Floor Bathroom",
        amount=120000.0,
    ),
    _line(
        sub_service="Wash basin",
        item_name="Wash basin",
        space_raw="First Floor Bathroom",
        amount=116590.0,
    ),
    # Bug 4: a catch-all zone spanning plumbing, electrical, glazing, ceiling.
    _line(
        sub_service="Plumbing",
        item_name="Plumbing",
        space_raw="Common",
        pricing_method="Fixed Amount / Lump Sum",
        pricing_method_id="pm_lump",
        amount=180000.0,
    ),
    _line(
        sub_service="Electrical wiring",
        item_name="Electrical wiring",
        space_raw="Common",
        pricing_method="Fixed Amount / Lump Sum",
        pricing_method_id="pm_lump",
        amount=150000.0,
    ),
    _line(
        sub_service="Metal grill",
        item_name="Metal grill",
        space_raw="Common",
        pricing_method="Fixed Amount / Lump Sum",
        pricing_method_id="pm_lump",
        amount=120000.0,
    ),
    _line(
        sub_service="False cielling",
        item_name="False cielling",
        space_raw="Common",
        pricing_method="Fixed Amount / Lump Sum",
        pricing_method_id="pm_lump",
        amount=117114.0,
    ),
    _line(
        sub_service="Bedroom wardrobe",
        item_name="Wardrobe",
        space_raw="Ground Floor Bedroom 2",
        quantity=70,
        rate=1300.0,
        amount=91000.0,
    ),
]


def load_df():
    import pandas as pd

    return pd.DataFrame(
        _quote(VENDOR_A, "EXCESS INTERIORS", "QCN21BW", EXCESS_ITEMS)
        + _quote(VENDOR_B, "INT360 DESIGN", "Q1K7W0G", INT360_ITEMS)
    )


@pytest.fixture(scope="module")
def matrix():
    import services.comparator as comparator

    original = comparator._generate_recommendation
    comparator._generate_recommendation = lambda *a, **k: "- **Stub:** ok."
    try:
        return comparator.run_comparison("guards-test", df=load_df())
    finally:
        comparator._generate_recommendation = original


def all_rows(matrix):
    return matrix["spaceTier"] + matrix["projectTier"]


# --- bug 1: lineage and reconciliation -------------------------------------


def test_every_row_carries_lineage(matrix):
    for row in all_rows(matrix):
        assert "source_line_ids" in row, row["sub_service"]
        assert row["source_line_ids"], f"{row['sub_service']} traces to nothing"
        assert isinstance(row["line_ids"], dict)


def test_reconciliation_is_green_for_both_vendors(matrix):
    report = matrix["reconciliation"]
    assert report["ok"] is True, report
    for vendor in VENDORS:
        entry = report["vendors"][vendor]
        assert entry["unaccounted_line_ids"] == []
        assert abs(entry["delta"]) <= report["tolerance_inr"]


def test_no_source_line_is_dropped(matrix):
    """The hinges line is the one that vanished. Every line must land."""
    placed = {
        line_id for row in all_rows(matrix) for line_id in row["source_line_ids"]
    }
    for row in matrix["bundleTier"]:
        placed.update(row.get("source_line_ids") or [])
    df = load_df()
    from services.lineage import ensure_line_ids

    df = ensure_line_ids(df)
    for _, line in df.iterrows():
        assert line["line_id"] in placed, f"{line['item_name']} was dropped"


def test_hinges_line_is_visible_and_traceable(matrix):
    rows = [
        row
        for row in all_rows(matrix) + matrix["bundleTier"]
        if "hinge" in str(row.get("sub_service") or row.get("bundle_label") or "").casefold()
    ]
    assert rows, "Soft closing hinges is missing from the comparison"
    assert any(row.get(VENDOR_A) == 29146 for row in rows)


def test_a_dropped_row_turns_the_gate_red():
    """The gate must catch the failure, not just describe the good case."""
    import services.comparator as comparator
    from services.lineage import reconcile_vendor_totals

    original = comparator._generate_recommendation
    comparator._generate_recommendation = lambda *a, **k: "stub"
    try:
        payload = comparator.run_comparison("gate-test", df=load_df())
    finally:
        comparator._generate_recommendation = original

    kept = [
        row
        for row in payload["spaceTier"]
        if "hinge" not in str(row.get("sub_service") or "").casefold()
    ]
    report = reconcile_vendor_totals(
        load_df(), VENDORS, kept, payload["projectTier"], payload["bundleTier"]
    )
    assert report["ok"] is False
    entry = report["vendors"][VENDOR_A]
    assert entry["unaccounted_line_ids"]
    assert entry["unaccounted"][0]["amount"] == 29146


def test_merged_lines_say_so_and_do_not_collide(matrix):
    merged = [row for row in all_rows(matrix) if row.get("combined_from")]
    assert merged, "Profile lights + Strip lights should merge into one row"
    combined = merged[0]
    assert "combines:" in combined["summary"]
    assert "Profile lights" in combined["summary"]
    assert "Strip lights" in combined["summary"]

    labels = [
        str(row["sub_service"]).casefold()
        for row in all_rows(matrix)
        if (row.get("line_ids") or {}).get(VENDOR_A)
    ]
    assert len(labels) == len(set(labels)), f"duplicate display labels: {labels}"


def test_every_merge_has_a_combines_note(matrix):
    """A merge of 2+ source lines must never ship silent (ACTION.md §13.16)."""
    _assert_merges_disclose(matrix, VENDORS)


def _assert_merges_disclose(payload, vendors):
    for row in all_rows(payload):
        line_ids = row.get("line_ids") or {}
        combines = row.get("combines") or {}
        for vendor in vendors:
            ids = line_ids.get(vendor) or []
            if len(ids) < 2:
                continue
            note = [str(v).strip() for v in (combines.get(vendor) or []) if str(v).strip()]
            assert note, (
                f"silent merge on {row.get('sub_service')} / {vendor}: "
                f"combined_from={row.get('combined_from')}"
            )
            summary = str(row.get("summary") or "")
            assert "combines:" in summary, row.get("sub_service")


def _run_stubbed_comparison(df, session_id: str):
    import services.comparator as comparator

    original = comparator._generate_recommendation
    comparator._generate_recommendation = lambda *a, **k: "- **Stub:** ok."
    try:
        return comparator.run_comparison(session_id, df=df)
    finally:
        comparator._generate_recommendation = original


def test_identical_headings_disclose_via_description():
    """Sub-items that reuse the heading still get a combines note from description."""
    import pandas as pd

    items_a = [
        _line(
            sub_service="Storage cabinet",
            item_name="Storage cabinet",
            space_raw="Kitchen",
            description="Storage cabinet base carcass with drawers and laminate shutters",
            pricing_method="Per Unit / Each",
            pricing_method_id="pm_unit",
            amount=70210.0,
        ),
        _line(
            sub_service="Storage cabinet",
            item_name="Storage cabinet",
            space_raw="Kitchen",
            description="Storage cabinet wall hanging unit with open shelves above the hob",
            pricing_method="Per Unit / Each",
            pricing_method_id="pm_unit",
            amount=43365.0,
        ),
        _line(
            sub_service="Storage cabinet",
            item_name="Storage cabinet",
            space_raw="Kitchen",
            description="Storage cabinet loft over the cabinets along the wet wall",
            pricing_method="Per Unit / Each",
            pricing_method_id="pm_unit",
            amount=75048.0,
        ),
    ]
    items_b = [
        _line(
            sub_service="Storage cabinet",
            item_name="Storage cabinet",
            space_raw="Kitchen",
            description="Single storage cabinet line",
            pricing_method="Per Unit / Each",
            pricing_method_id="pm_unit",
            amount=180000.0,
        ),
    ]
    df = pd.DataFrame(
        _quote(VENDOR_A, "EXCESS INTERIORS", "QCN21BW", items_a)
        + _quote(VENDOR_B, "INT360 DESIGN", "Q1K7W0G", items_b)
    )
    payload = _run_stubbed_comparison(df, "merge-desc")
    _assert_merges_disclose(payload, VENDORS)
    merged = [
        row
        for row in all_rows(payload)
        if len((row.get("line_ids") or {}).get(VENDOR_A) or []) >= 2
    ]
    assert len(merged) == 1, [row.get("sub_service") for row in merged]
    note = merged[0]["combines"][VENDOR_A]
    joined = " ".join(note).casefold()
    assert "base carcass" in joined
    assert "wall hanging" in joined
    assert "loft over" in joined
    assert "line items" not in joined
    assert abs(merged[0][VENDOR_A] - 188623) < 1


def test_identical_headings_and_descriptions_disclose_via_amounts():
    """When labels and descriptions cannot name the parts, still disclose count + ₹."""
    import pandas as pd

    shared = dict(
        sub_service="Display unit",
        item_name="Display unit",
        space_raw="Living Room",
        description="Display unit",
        pricing_method="Per Unit / Each",
        pricing_method_id="pm_unit",
    )
    items_a = [
        _line(**shared, amount=70210.0),
        _line(**shared, amount=43365.0),
        _line(**shared, amount=75048.0),
    ]
    items_b = [
        _line(
            sub_service="Display unit",
            item_name="Display unit",
            space_raw="Living Room",
            description="One display unit",
            pricing_method="Per Unit / Each",
            pricing_method_id="pm_unit",
            amount=200000.0,
        ),
    ]
    df = pd.DataFrame(
        _quote(VENDOR_A, "EXCESS INTERIORS", "QCN21BW", items_a)
        + _quote(VENDOR_B, "INT360 DESIGN", "Q1K7W0G", items_b)
    )
    payload = _run_stubbed_comparison(df, "merge-amounts")
    _assert_merges_disclose(payload, VENDORS)
    merged = [
        row
        for row in all_rows(payload)
        if len((row.get("line_ids") or {}).get(VENDOR_A) or []) >= 2
    ]
    assert len(merged) == 1, [row.get("sub_service") for row in merged]
    note = merged[0]["combines"][VENDOR_A]
    assert len(note) >= 1
    text = " ".join(note)
    assert "3 line items" in text
    assert "₹70,210" in text
    assert "₹43,365" in text
    assert "₹75,048" in text
    summary = merged[0]["summary"]
    assert "combines:" in summary
    assert "3 line items" in summary


def test_the_lighting_work_meets_on_one_row(matrix):
    """One vendor wrote the catalog title itself; it must still pair up.

    `Lighting points` used to resolve by normalisation while the other
    vendor's `Profile lights` resolved by alias, so the same work printed as
    two N/A rows in the same room.
    """
    rows = [
        row
        for row in all_rows(matrix)
        if row["space_id"].endswith("living")
        and "lighting" in str(row["sub_service"]).casefold()
    ]
    assert len(rows) == 1, [row["sub_service"] for row in rows]
    assert rows[0][VENDOR_A] == 33630
    assert rows[0][VENDOR_B] == 30000


# --- bug 2: ambiguous space label ------------------------------------------


def test_unnumbered_bedroom_is_not_folded_into_bedroom_1(matrix):
    unassigned = [row for row in all_rows(matrix) if row["match_tier"] == "UNASSIGNED"]
    assert unassigned, "Ground floor bedroom should be UNASSIGNED"
    assert all(row["space_id"].startswith("unassigned:") for row in unassigned)
    total = sum(row[VENDOR_B] for row in unassigned)
    assert total == 21240 + 37760

    bedroom_1 = [
        row for row in all_rows(matrix) if row["space_id"].endswith("bedroom1")
    ]
    assert all(row[VENDOR_B] == 0 for row in bedroom_1), (
        "the ambiguous civil work must not be attributed to Bedroom 1"
    )


def test_unassigned_rows_carry_a_confirm_note(matrix):
    for row in all_rows(matrix):
        if row["match_tier"] != "UNASSIGNED":
            continue
        assert "confirm before allocating" in row["space_note"]
        assert "confirm before allocating" in row["summary"]
    notes = {
        note["space_id"]: note
        for note in matrix["spaceNotes"]
        if note["match_tier"] == "UNASSIGNED"
    }
    assert notes


def test_multi_room_quantity_is_flagged(matrix):
    flagged = [row for row in all_rows(matrix) if row.get("qty_scope_note")]
    assert flagged, "qty 4 against 2 numbered bedrooms should be flagged"
    assert any("chhajja" in str(row["sub_service"]).casefold() for row in flagged)
    assert "multi-room scope" in flagged[0]["qty_scope_note"]


# --- bug 3: cross-scope possible match --------------------------------------


def test_washroom_fitout_is_flagged_as_a_possible_match(matrix):
    entries = [
        entry
        for entry in matrix["crossScope"]
        if entry["group"] == "bathroom_fitout"
    ]
    assert entries, "walk-in closet washroom vs First Floor Bathroom was dropped"
    entry = entries[0]
    assert entry["match_tier"] == "POSSIBLE_CROSS_SCOPE_MATCH"
    assert entry["vendors"][VENDOR_A]["amount"] == 404324
    assert entry["vendors"][VENDOR_B]["amount"] == 236590
    assert "confirm with vendor" in entry["note"]
    # Never auto-clubbed: the two figures stay on their own rows.
    assert entry["vendors"][VENDOR_A]["space_id"] != entry["vendors"][VENDOR_B]["space_id"]


def test_flagged_rows_stop_claiming_the_other_vendor_quoted_nothing(matrix):
    """The N/A sentence is the false statement the client read. Kill it."""
    flagged = [
        row
        for row in all_rows(matrix)
        if row["match_tier"] == "POSSIBLE_CROSS_SCOPE_MATCH"
    ]
    assert flagged, "the washroom rows should be flagged, not blank"
    for row in flagged:
        assert "did not quote this line" not in row["summary"]
        assert "Possible match with" in row["summary"]
        assert "confirm with vendor" in row["summary"]
    spaces = {row["space"] for row in flagged}
    assert "Walkin Closet Area 1st Floor" in spaces
    assert "First Floor Bathroom" in spaces


def test_possible_match_does_not_move_any_money(matrix):
    """The flag is a note. The tier totals must be untouched by it."""
    report = matrix["reconciliation"]
    assert report["ok"] is True
    assert report["vendors"][VENDOR_A]["rows_total"] == pytest.approx(
        sum(item["amount"] for item in EXCESS_ITEMS), abs=5
    )


# --- bug 4: bundled zone ----------------------------------------------------


def test_common_zone_is_bundle_not_decomposable(matrix):
    zones = matrix["bundleZones"]
    assert zones, "the Common zone should be marked BUNDLE_NOT_DECOMPOSABLE"
    zone = zones[0]
    assert zone["match_tier"] == "BUNDLE_NOT_DECOMPOSABLE"
    assert zone["vendor"] == VENDOR_B
    assert zone["amount"] == 567114
    assert len(zone["categories"]) >= 2
    assert "can't be compared line-by-line" in zone["note"]


def test_bundled_zone_suppresses_line_matching(matrix):
    notes = [
        note
        for note in matrix["spaceNotes"]
        if note["match_tier"] == "BUNDLE_NOT_DECOMPOSABLE"
    ]
    assert notes and notes[0]["suppress_line_matching"] is True
    rows = [
        row
        for row in all_rows(matrix)
        if row["space_id"] == notes[0]["space_id"]
    ]
    assert rows
    assert all(row["match_tier"] == "BUNDLE_NOT_DECOMPOSABLE" for row in rows)


def test_a_real_room_is_never_a_bundled_zone(matrix):
    """A bedroom holds carpentry, electrical, and civil work legitimately."""
    for row in all_rows(matrix):
        if row["space_id"].endswith(("bedroom1", "bedroom2", "kitchen", "living")):
            assert row["match_tier"] != "BUNDLE_NOT_DECOMPOSABLE"


# --- bug 5: pricing-method guard -------------------------------------------


def test_rolling_shutter_does_not_claim_a_quantity_difference(matrix):
    rows = [
        row
        for row in all_rows(matrix)
        if "rolling shutter" in str(row["sub_service"]).casefold()
    ]
    assert len(rows) == 1
    summary = rows[0]["summary"]
    assert "1 units" not in summary
    assert "8 units" not in summary
    assert "billed more area" not in summary
    assert "different pricing methods" in summary
    assert "Rate difference only" in summary


def test_same_pricing_method_still_uses_quantity_language(matrix):
    """The guard must not mute honest quantity comparisons."""
    rows = [
        row
        for row in all_rows(matrix)
        if "wardrobe" in str(row["sub_service"]).casefold()
        and row[VENDOR_A] > 0
        and row[VENDOR_B] > 0
    ]
    assert rows
    assert "different pricing methods" not in rows[0]["summary"]

"""S2 — work identity.

The comparison join key used to be the raw vendor string, which split rows that
differed only in casing or plurals. These tests pin both directions: things that
must merge, and — more importantly — things that must NOT, since a false merge
silently sums unrelated amounts.
"""

from __future__ import annotations

import os

os.environ["GEMINI_WORK_LLM"] = "0"

import pandas as pd

from services.work_catalog import (
    apply_work_catalog,
    is_known_work_label,
    normalize_work_label,
    resolve_work,
    work_slug_for,
)


def key(label: str, description: str = "") -> str:
    return resolve_work(
        {"sub_service": label, "item_name": label, "description": description}
    )["work_key"]


def test_casing_and_plurals_collapse():
    assert key("Side table") == key("Side Table")
    assert key("Rolling Shutter") == key("Rolling shutters")
    assert normalize_work_label("Rolling shutters") == "rolling shutter"


def test_cross_vendor_synonyms_merge():
    assert key("False Ceiling") == key("False ceiling with painting")
    assert key("Loft") == key("Loft unit")
    assert key("Loft") == key("Loft & Door Type")
    assert key("folding study table") == key("Study Table")


def test_one_to_many_shares_a_key():
    """Vendor B split crockery into base + wall; both fold onto A's single row.

    1:N needs no special machinery — a shared key lets the matrix groupby sum
    them into one figure.
    """
    single = key("Crockery Units")
    assert key("Crockery Base unit") == single
    assert key("Crockery Wall unit") == single


def test_distinct_work_stays_distinct():
    # Filler-word stripping must not go so far that it merges real differences.
    assert key("Base Unit") != key("Wall Unit")
    assert key("Wardrobe") != key("King Size Bed")
    assert key("Tall Unit") != key("Janitor Unit")
    assert key("Soft closing hinges") != key("Soft closing channels")


def test_description_wins_only_on_contradiction():
    """A vendor labelled a dressing mirror as used-cloth storage."""
    mirror = resolve_work(
        {
            "sub_service": "MBR Used cloth units",
            "item_name": "MBR Used cloth units",
            "description": "Dressing Mirror",
        }
    )
    assert mirror["work_source"] == "description"
    assert mirror["work_key"] != key("Used cloth storage unit")

    # A consistent row must be left alone.
    wardrobe = resolve_work(
        {
            "sub_service": "Wardrobe",
            "item_name": "Wardrobe",
            "description": "Hinged wardrobe",
        }
    )
    assert wardrobe["work_source"] == "alias"


def test_ancillary_intent_keeps_dismantling_out_of_installation_row():
    installation = resolve_work(
        {
            "sub_service": "Wardrobe",
            "item_name": "Wardrobe",
            "description": "HDHMR wardrobe with laminate shutters",
        }
    )
    dismantling = resolve_work(
        {
            "sub_service": "Wardrobe",
            "item_name": "Wardrobe",
            "description": "Dismantle charges for wardrobe & loft",
        }
    )

    assert installation["work_key"] == key("Wardrobe")
    assert dismantling["work_key"] == f"{installation['work_key']}::intent:dismantling"
    assert dismantling["work_label"] == "Wardrobe — dismantling"


def test_same_ancillary_intent_merges_but_other_intents_stay_separate():
    dismantle = key("Wardrobe", "Dismantle existing wardrobe")
    demolition = key("Wardrobe", "Demolition of existing wardrobe")
    cleaning = key("Wardrobe", "Cleaning after wardrobe work")
    shifting = key("Wardrobe", "Shifting the existing wardrobe")

    assert dismantle == demolition
    assert dismantle != cleaning
    assert dismantle != shifting
    assert cleaning != shifting


def test_generic_civil_line_is_not_forced_into_wardrobe_dismantling():
    wardrobe = key("Wardrobe", "Dismantle charges for wardrobe")
    civil = key("Civil", "Dismantling and civil alteration charges")

    assert wardrobe != civil


def test_seater_unit_does_not_fold_into_crockery_or_bench():
    """TCS labelled a seater as Crockery Wall unit; it is neither crockery nor bench."""
    seater = resolve_work(
        {
            "sub_service": "Crockery Wall unit",
            "item_name": "Crockery Wall unit",
            "description": (
                "Seater unit - Matt / Hi Glossy Laminates Finish for shutters "
                "using HDHMR Greenply brand & Carcass made by using Greenply"
            ),
        }
    )
    assert seater["work_source"] == "description"
    assert seater["work_key"] != key("Crockery Units")
    assert seater["work_key"] != key("Bench Seating")

    # A genuine crockery wall whose spec starts with its own name stays crockery.
    wall = resolve_work(
        {
            "sub_service": "Crockery Wall unit",
            "item_name": "Crockery Wall unit",
            "description": (
                "Crockery Wall unit - Matt / Hi Glossy Laminates Finish for "
                "shutters using HDHMR Greenply brand"
            ),
        }
    )
    assert wall["work_key"] == key("Crockery Units")


def test_boilerplate_description_never_overrides():
    """Long spec prose is not a work name and must not hijack the key."""
    row = resolve_work(
        {
            "sub_service": "Base Unit",
            "item_name": "Base Unit",
            "description": (
                "Kitchen base unit - Matt / Hi Glossy Laminates Finish for shutters "
                "using HDHMR Greenply brand & Carcass made by using Greenply Brand "
                "IS-710 BWP Grade Plywood."
            ),
        }
    )
    assert row["work_key"] == key("Base Unit")


def test_alias_outranks_a_per_vendor_object_id():
    """An ObjectId identifies one catalog entry, not a shared work identity.

    In the golden comparison `False Ceiling` carried an id while `False ceiling
    with painting` did not, so keying on the id split a row the alias joins.
    """
    with_id = resolve_work(
        {
            "sub_service": "False Ceiling",
            "item_name": "False Ceiling",
            "description": "",
            "sub_service_id": "69957fcd25ccc8cecd1ddcf9",
        }
    )
    without_id = resolve_work(
        {
            "sub_service": "False ceiling with painting",
            "item_name": "False ceiling with painting",
            "description": "",
        }
    )
    assert with_id["work_key"] == without_id["work_key"]


def test_object_id_used_when_no_label_match():
    row = resolve_work(
        {
            "sub_service": "Some Bespoke Vendor Thing",
            "item_name": "Some Bespoke Vendor Thing",
            "description": "",
            "sub_service_id": "aaaaaaaaaaaaaaaaaaaaaaaa",
        }
    )
    assert row["work_key"] == "tatva:aaaaaaaaaaaaaaaaaaaaaaaa"


def test_work_key_is_never_empty():
    for label in ("", "   ", "Units", "Provision", "?!"):
        row = resolve_work({"sub_service": label, "item_name": "", "description": ""})
        assert row["work_key"]


def test_is_known_work_label_backs_the_space_predicate():
    # S3 relies on this to keep item names out of the space column.
    assert is_known_work_label("Used cloth unit") is True
    assert is_known_work_label("Window blinds") is True
    # Real rooms must not be mistaken for work items.
    assert is_known_work_label("Master bedroom") is False
    assert is_known_work_label("Kitchen area") is False
    assert is_known_work_label("Foyer") is False


def test_work_slug_for_uses_the_same_vocabulary_as_resolve():
    assert work_slug_for("False ceiling") == "false_ceiling"
    assert work_slug_for("TV Units") == "tv_units"
    assert work_slug_for("Modular Kitchen") == "modular_kitchen"
    assert work_slug_for("not a real sub-service") is None


def test_apply_work_catalog_adds_all_columns():
    df = pd.DataFrame(
        [
            {
                "vendor_name": "A",
                "sub_service": "Side table",
                "item_name": "Side table",
                "description": "",
            },
            {
                "vendor_name": "B",
                "sub_service": "Side Table",
                "item_name": "Side Table",
                "description": "",
            },
        ]
    )
    out = apply_work_catalog(df)
    for column in ("work_key", "work_label", "work_confidence", "work_source"):
        assert column in out.columns
    assert out["work_key"].nunique() == 1

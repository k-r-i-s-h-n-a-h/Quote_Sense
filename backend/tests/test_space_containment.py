"""S3b — containment edges, not merges.

Walk-in closet vs Master Bedroom stay two space_ids. The child points at the
parent so S5 can say incl_in_parent instead of N/A.
"""

from __future__ import annotations

import os

os.environ["GEMINI_SPACE_LLM"] = "0"
os.environ["GEMINI_WORK_LLM"] = "0"

import pandas as pd

from services.space_clusters import (
    apply_space_clusters,
    cluster_spaces_heuristic,
    containment_parent,
    resolve_space,
)


def test_walkin_and_mbr_stay_two_ids():
    mapping = cluster_spaces_heuristic(["Walk-in closet", "Master Bedroom"])
    assert mapping["Walk-in closet"]["cluster_id"] != mapping["Master Bedroom"]["cluster_id"]


def test_walkin_points_at_mbr_when_both_present():
    mapping = cluster_spaces_heuristic(["Walk-in closet", "Master Bedroom"])
    wic = mapping["Walk-in closet"]["cluster_id"]
    mbr = mapping["Master Bedroom"]["cluster_id"]
    assert containment_parent(wic, {wic, mbr}) == mbr


def test_first_floor_walkin_does_not_attach_to_gf_mbr():
    present = {"1f_walkin", "gf_mbr", "1f_mbr"}
    assert containment_parent("1f_walkin", present) == "1f_mbr"


def test_kitchen_never_contains_bedroom():
    present = {"kitchen", "bedroom1", "mbr"}
    assert containment_parent("kitchen", present) == ""
    assert containment_parent("bedroom1", present) == ""
    assert containment_parent("mbr", present) == ""


def test_utility_points_at_kitchen():
    assert containment_parent("utility", {"utility", "kitchen"}) == "kitchen"


def test_balcony_points_at_living():
    token = resolve_space({"space_raw": "Balcony"})["space_id"]
    assert token.endswith("balcony") or token == "balcony"
    living = resolve_space({"space_raw": "Living Room"})["space_id"]
    assert containment_parent(token, {token, living}) == living


def test_mbr_bathroom_points_at_mbr():
    bath = resolve_space({"space_raw": "Master Bathroom"})["space_id"]
    mbr = resolve_space({"space_raw": "Master Bedroom"})["space_id"]
    assert bath != mbr
    assert containment_parent(bath, {bath, mbr}) == mbr


def test_parent_absent_means_no_edge():
    assert containment_parent("1f_walkin", {"1f_walkin"}) == ""


def test_apply_clusters_sets_contained_in_without_merging():
    df = pd.DataFrame(
        {
            "space_raw": ["Walk-in closet", "Master Bedroom", "Kitchen"],
            "item_name": ["Wardrobe", "Bed", "Base unit"],
            "description": ["", "", ""],
        }
    )
    out = apply_space_clusters(df.copy())
    ids = set(out["space_id"].astype(str))
    assert len(ids) == 3
    wic = out.loc[out["space_raw"] == "Walk-in closet", "space_id"].iloc[0]
    mbr = out.loc[out["space_raw"] == "Master Bedroom", "space_id"].iloc[0]
    kit = out.loc[out["space_raw"] == "Kitchen", "space_id"].iloc[0]
    assert out.loc[out["space_raw"] == "Walk-in closet", "contained_in"].iloc[0] == mbr
    assert out.loc[out["space_raw"] == "Kitchen", "contained_in"].iloc[0] == ""
    assert wic != mbr != kit

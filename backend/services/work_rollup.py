"""Rule-based work rollup: lumpsum vs itemized lighting/electrical.

Does not merge spaces. Only collapses lighting-family lines that sit on
Project-level (item-as-space) or use Lump Sum / Per Project, so Bedroom fan-point
shifting stays under GF-Bedroom1.
"""

from __future__ import annotations

import re

_LIGHTING_RE = re.compile(
    r"light|electrical|adaptor|adapter|spot\s|profile\s|strip\s",
    re.I,
)
_LUMP_RE = re.compile(r"lump|per project|fixed amount", re.I)
_FAMILY_LABEL = "Electrical / lighting"


def _blob(row) -> str:
    return " ".join(
        str(row.get(c, "") or "")
        for c in ("sub_service", "item_name", "item_label", "description", "space_raw")
    )


def is_lighting_family(row) -> bool:
    return bool(_LIGHTING_RE.search(_blob(row)))


def is_lump_pricing(row) -> bool:
    return bool(_LUMP_RE.search(str(row.get("pricing_method") or "")))


def _is_rollup_candidate(row) -> bool:
    if not is_lighting_family(row):
        return False
    space = str(row.get("space") or "").strip()
    if space == "Project-level":
        return True
    return is_lump_pricing(row)


def apply_work_rollup(df):
    """If one vendor lumps electrical and another itemizes on Project-level, unify sub_service."""
    if df is None or len(df) == 0:
        return df
    if "space" not in df.columns:
        return df

    mask = df.apply(_is_rollup_candidate, axis=1)
    if not mask.any():
        return df

    subset = df.loc[mask]
    vendors = subset["vendor_name"].unique().tolist() if "vendor_name" in subset.columns else []
    if len(vendors) < 2:
        return df

    has_lump = False
    itemized_counts: dict[str, int] = {}
    for vendor in vendors:
        vrows = subset[subset["vendor_name"] == vendor]
        itemized_counts[vendor] = len(vrows)
        if any(is_lump_pricing(r) for _, r in vrows.iterrows()):
            has_lump = True

    other_has_lines = any(
        (not any(is_lump_pricing(r) for _, r in subset[subset["vendor_name"] == v].iterrows()))
        and itemized_counts.get(v, 0) >= 1
        for v in vendors
    )
    if not (has_lump and other_has_lines):
        return df

    df.loc[mask, "sub_service"] = _FAMILY_LABEL
    df.loc[mask, "item_name"] = _FAMILY_LABEL
    df.loc[mask, "item_label"] = _FAMILY_LABEL
    if "sub_service_id" in df.columns:
        df.loc[mask, "sub_service_id"] = "family:lighting"
    return df

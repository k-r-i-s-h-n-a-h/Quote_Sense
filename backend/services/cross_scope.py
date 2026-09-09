"""S4b — POSSIBLE_CROSS_SCOPE_MATCH. Related work in different containers.

Two vendors can quote the same functional work inside structurally different
containers. In a real comparison one vendor put a whole washroom fit-out (tile
removal, tiles, cummode, flush tank, basin, shower mixer, plumbing, WPC door,
window, grill, vanity — Rs 4,04,324) *inside* its "Walkin Closet Area 1st
Floor" space, while the other quoted first-floor washroom work as its own
"First Floor Bathroom" space (Rs 2,36,590). The containment guard correctly
refused to merge those two spaces, and the matrix then printed the first
vendor's closet as "scopes differ — N/A", which reads to a client as "the
other vendor quoted nothing for this". That is false, and it is the most
expensive kind of false the matrix can print.

This module abstains loudly instead. It never merges totals and never changes
a coverage status: it emits a flagged "possible match — confirm with vendor"
entry naming both figures and both containers.

Structural guards still win. This tier exists precisely for the case where the
guard says "different container" but the functional content looks related.

See backend/docs/plan/04-bundles.md.
"""

from __future__ import annotations

import re
from typing import Any

# Functional purpose, independent of which container the vendor used. Narrow on
# purpose: a group that matched half the quote would flag everything and teach
# the reader to skip the section.
FUNCTIONAL_GROUPS: tuple[tuple[str, str, "re.Pattern[str]"], ...] = (
    (
        "bathroom_fitout",
        "Bathroom / washroom fit-out",
        re.compile(
            r"\b(?:cummode|commode|water\s*closet|wc|flush\s*tank|wash\s*basin|"
            r"basin|shower|health\s*faucet|bib\s*cock|diverter|sanitary|"
            r"cp\s*fitting|geyser|toilet|urinal|vanity|wpc\s*door)\b",
            re.I,
        ),
    ),
    (
        "storage_units",
        "Wardrobe / loft storage",
        re.compile(r"\b(?:wardrobe|loft|walk[\s-]?in\s*closet|almirah)\b", re.I),
    ),
    (
        "structural_walls",
        "Structural walls & openings",
        re.compile(
            r"\b(?:masonry|brick\s*work|block\s*work|rcc|chhajja|lintel|"
            r"structural\s*wall)\b",
            re.I,
        ),
    ),
    (
        "washroom_civil",
        "Washroom civil / tiling",
        re.compile(
            r"\b(?:tiles?|tiling|dado|waterproof(?:ing)?|plaster(?:ing)?|"
            r"epoxy|grout(?:ing)?)\b",
            re.I,
        ),
    ),
)

# Below this the pair is noise rather than a decision the client needs.
CROSS_SCOPE_MIN_INR = 25_000

# A space whose own id names the functional purpose is a standalone container
# ("First Floor Bathroom"); anything else holds the work inside something else
# (a "Walk-in Closet" holding a washroom fit-out).
_SPACE_PURPOSE = {
    "bathroom_fitout": re.compile(r"bath|wash|toilet|wc", re.I),
    "storage_units": re.compile(r"wardrobe|closet|walkin", re.I),
    "washroom_civil": re.compile(r"bath|wash|toilet|wc", re.I),
}


def functional_group(row: dict[str, Any]) -> str:
    """Functional purpose slug for a line, or "" when none applies.

    `washroom_civil` also needs a wet-area container signal. Tile and plaster
    keywords show up in kitchens and living rooms constantly; without that
    gate the group would flag half the quote.
    """
    blob = " ".join(
        str(row.get(col, "") or "")
        for col in ("sub_service", "item_name", "work_label", "description")
    )
    place = " ".join(
        str(row.get(col, "") or "")
        for col in ("space", "space_raw", "space_id", "description")
    )
    for slug, _label, pattern in FUNCTIONAL_GROUPS:
        if not pattern.search(blob):
            continue
        purpose = _SPACE_PURPOSE.get(slug)
        if slug == "washroom_civil" and purpose and not purpose.search(place):
            continue
        return slug
    return ""


def _inr(amount: float) -> str:
    from services.bundles import inr_indian

    return inr_indian(amount)


def _who(vendor: str) -> str:
    return (vendor.split(" (")[0] or vendor).strip() or vendor


def _label_for(slug: str) -> str:
    for candidate, label, _pattern in FUNCTIONAL_GROUPS:
        if candidate == slug:
            return label
    return slug.replace("_", " ").capitalize()


def cross_scope_candidates(df, vendors: list[str]) -> list[dict[str, Any]]:
    """Flagged possible matches across structurally different containers.

    Emitted only when, for one functional group, the two vendors used
    *disjoint* space ids — meaning no space-tier row can ever pair them, so the
    matrix would otherwise show two unrelated N/A blocks.
    """
    if df is None or len(df) == 0 or len(vendors) < 2:
        return []
    for column in ("vendor_name", "space_id", "amount"):
        if column not in df.columns:
            return []

    per_group: dict[str, dict[str, dict[str, Any]]] = {}
    for _, row in df.iterrows():
        slug = functional_group(row)
        if not slug:
            continue
        vendor = str(row.get("vendor_name") or "")
        space_id = str(row.get("space_id") or "")
        try:
            amount = float(row.get("amount") or 0)
        except (TypeError, ValueError):
            amount = 0.0
        bucket = per_group.setdefault(slug, {}).setdefault(
            vendor,
            {"spaces": {}, "amount": 0.0, "line_ids": [], "lines": 0},
        )
        bucket["amount"] += amount
        bucket["lines"] += 1
        line_id = str(row.get("line_id") or "")
        if line_id:
            bucket["line_ids"].append(line_id)
        space = bucket["spaces"].setdefault(
            space_id,
            {"label": str(row.get("space") or space_id), "amount": 0.0},
        )
        space["amount"] += amount

    out: list[dict[str, Any]] = []
    for slug in sorted(per_group):
        by_vendor = per_group[slug]
        quoting = [v for v in vendors if v in by_vendor]
        if len(quoting) < 2:
            continue
        if any(by_vendor[v]["amount"] < CROSS_SCOPE_MIN_INR for v in quoting):
            continue

        shared = set.intersection(*(set(by_vendor[v]["spaces"]) for v in quoting))
        if shared:
            # At least one space already puts both vendors on the same rows, so
            # the space tier compares this work honestly. Nothing to flag.
            continue

        purpose = _SPACE_PURPOSE.get(slug)
        per_vendor: dict[str, Any] = {}
        source_line_ids: list[str] = []
        for vendor in quoting:
            bucket = by_vendor[vendor]
            main_id, main = max(
                bucket["spaces"].items(), key=lambda kv: kv[1]["amount"]
            )
            standalone = bool(purpose and purpose.search(main_id))
            per_vendor[vendor] = {
                "space_id": main_id,
                "space": main["label"],
                "spaces": [entry["label"] for entry in bucket["spaces"].values()],
                "amount": round(bucket["amount"]),
                "line_count": bucket["lines"],
                "container": "standalone" if standalone else "embedded",
            }
            source_line_ids.extend(bucket["line_ids"])

        a, b = quoting[0], quoting[1]
        label = _label_for(slug)
        note = (
            "Possible match — confirm with vendor: "
            f"{_who(a)}'s [{per_vendor[a]['space']} {label.lower()}, "
            f"{_inr(per_vendor[a]['amount'])}] may correspond to "
            f"{_who(b)}'s [{per_vendor[b]['space']}, "
            f"{_inr(per_vendor[b]['amount'])}]. Totals are not merged."
        )
        out.append(
            {
                "match_tier": "POSSIBLE_CROSS_SCOPE_MATCH",
                "group": slug,
                "label": label,
                "confidence": 0.5,
                "rationale": (
                    "same functional purpose in different containers "
                    f"({per_vendor[a]['container']} vs {per_vendor[b]['container']})"
                ),
                "vendors": per_vendor,
                "note": note,
                "source_line_ids": sorted(set(source_line_ids)),
            }
        )

    return out

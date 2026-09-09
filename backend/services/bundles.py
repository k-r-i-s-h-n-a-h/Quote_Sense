"""S4 — price scope. Decide HOW WIDE each line's price reaches.

This is the stage that makes lumpsum-vs-itemised comparable. One vendor prices
all electrical as a single figure; another itemises lighting per room. A strictly
space-grouped matrix has nowhere correct to put the lumpsum, so it used to land
in Project-level, silently dropping out of every room total.

Replaces `work_rollup.py`, which almost never fired. It required two vendors to
have candidate rows, where a candidate had to be lighting-family AND either
project-level or lump-priced. In the golden comparison one vendor's only
electrical line was priced by running length inside the kitchen, so it was not a
candidate at all, the subset collapsed to a single vendor, and the guard returned
the frame untouched. The matrix then showed that vendor as N/A for electrical
when it had in fact quoted Rs 17,700 of it.

Two further gaps: `work_rollup` only knew the lighting family, so a real hardware
lumpsum (Rs 1,00,300 against Rs 37,198 of itemised accessories) was invisible;
and nothing detected that the lumpsum's description named an item the same vendor
also billed separately.

Design notes:
  - Bundle detection is PER LINE with no cross-vendor precondition.
  - Families let a bundle find its counterpart without an exact key match.
  - A bundle's amount NEVER contributes to a space total. Pro-rata allocating a
    lumpsum across rooms would invent a figure the vendor never quoted.
  - Overlaps are flagged, never corrected. Only the vendor knows whether the
    lumpsum includes the separate line or duplicates it.

See backend/docs/plan/04-bundles.md.
"""

from __future__ import annotations

import re
from typing import Any

_LUMP_RE = re.compile(r"lump|per project|fixed amount|whole project", re.I)

# Coarse families for counterpart matching. Keyed on canonical work slugs from
# S2, with a text fallback for keys the catalog did not resolve.
FAMILY_BY_SLUG = {
    "lighting_points": "lighting",
    "electrical_points": "lighting",
    "adaptors": "lighting",
    "hardware": "hardware",
    "tandem_drawers": "hardware",
    "bottle_pullouts": "hardware",
    "cutlery_tray": "hardware",
    "soft_closing_hinges": "hardware",
    "soft_closing_channels": "hardware",
    "false_ceiling": "ceiling",
}

_FAMILY_PATTERNS = (
    ("lighting", re.compile(r"\blight|electrical|adaptor|adapter|spot light|profile light|strip light|point creation", re.I)),
    ("hardware", re.compile(r"\bhardware|tandem|soft clos|pullout|pull out|cutlery|gola|skid mat|accessor", re.I)),
    ("painting", re.compile(r"\bpaint|emulsion|primer", re.I)),
    ("ceiling", re.compile(r"\bfalse ceiling|gyproc", re.I)),
    ("civil", re.compile(r"\bmasonry|plaster|waterproof|flooring|tiling", re.I)),
)

FAMILY_LABELS = {
    "lighting": "Electrical & lighting",
    "hardware": "Hardware & accessories",
    "painting": "Painting",
    "ceiling": "False ceiling",
    "civil": "Civil work",
}

# Separators a vendor uses when listing what a lumpsum covers.
# `&` is not one of them: "Greenply & Century" is a brand pair, not two works.
_LIST_SPLIT_RE = re.compile(r",|;|\band\b|\+|/")

# Substring fallback for fragments the catalog does not resolve as a whole
# phrase — "5 tandem" never matches an alias, but "tandem" still names the item.
# Prefer `work_slug_for` (S2) for everything else.
_ITEM_TOKENS = {
    "tandem": "tandem_drawers",
    "bottle": "bottle_pullouts",
    "cutlery": "cutlery_tray",
    "hinge": "soft_closing_hinges",
    "channel": "soft_closing_channels",
    "rolling shutter": "rolling_shutter",
    "shutter": "rolling_shutter",
    "handle": "handles",
    "skid mat": "skid_mat",
    "basket": "wicker_basket",
    "spot light": "lighting_points",
    "profile light": "lighting_points",
    "strip light": "lighting_points",
    "adaptor": "adaptors",
    "wire": "electrical_points",
    "point": "electrical_points",
    "blind": "window_blinds",
    "mirror": "mirror",
    "loft": "loft",
    "wardrobe": "wardrobe",
    "painting": "painting",
}

_INCLUDES_RE = re.compile(r"^(includes?|including)\s+", re.I)


# --- bundle zones (BUNDLE_NOT_DECOMPOSABLE) --------------------------------
#
# A vendor sometimes parks several trades in one catch-all zone ("Common":
# plumbing + electrical + grill + window + false ceiling + termite treatment,
# one figure each, no room named). The other vendor scopes the same work per
# room in fine detail. Line-matching those two produces invented pairings, so
# the zone is compared at space level only and says so.
#
# Fixed trade list. Order matters only for reporting; a line belongs to at most
# one category.
TRADE_CATEGORIES: tuple[tuple[str, "re.Pattern[str]"], ...] = (
    ("plumbing", re.compile(r"\bplumb|sanitary|cp fitting|basin|cummode|commode|flush tank|faucet|geyser|water\s*line", re.I)),
    ("electrical", re.compile(r"\belectric|wiring|light|switch|adaptor|adapter|point creation|db\b", re.I)),
    ("carpentry", re.compile(r"\bwardrobe|loft|unit\b|cabinet|shutter|panel|door|partition|bed\b|table|storage|carpent", re.I)),
    ("civil", re.compile(r"\bcivil|masonry|brick|plaster|chhajja|concrete|tile|tiling|flooring|waterproof|dismantl|demolit", re.I)),
    ("painting", re.compile(r"\bpaint|emulsion|primer|putty", re.I)),
    ("ceiling", re.compile(r"\bfalse\s*cei?l+ing|gyproc|pop\b", re.I)),
    ("glazing", re.compile(r"\bwindow|glazing|glass|grill|mesh", re.I)),
    ("pest_control", re.compile(r"\btermite|pest|anti[\s-]?borer", re.I)),
    ("housekeeping", re.compile(r"\bdeep clean|cleaning|debris|floor protection|housekeep", re.I)),
)

# Catch-all zone names. A real room ("Kitchen", "Bedroom 1") is never a bundle
# zone, however many trades it contains — a bedroom legitimately holds
# carpentry, electrical, and civil work, and flagging it would suppress the
# comparison customers actually need.
_GENERIC_ZONE_RE = re.compile(
    r"\b(common|commons|general|generals|others?|misc|miscellaneous|balance|"
    r"remaining|package|combined|overall|whole\s*home|whole\s*house|"
    r"full\s*home|full\s*house)\b",
    re.I,
)

# A generic word plus a room-type noun is a room ("Common Washroom"), not a
# catch-all. Bare "Common" / "General" / "Whole home electrical" still qualify.
_ROOM_NOUN_RE = re.compile(
    r"\b(washrooms?|bathrooms?|toilets?|bedrooms?|kitchens?|closets?|"
    r"dressing|balcon(?:y|ies)|pooja|utility|stores?|storage|halls?|"
    r"living|dining|foyers?|lobb(?:y|ies)|stud(?:y|ies)|offices?|"
    r"garages?|terraces?|verandahs?|verandas?|decks?)\b",
    re.I,
)

# Below this a "zone" is just a couple of stray lines, not a bundled scope.
BUNDLE_ZONE_MIN_LINES = 3
BUNDLE_ZONE_MIN_CATEGORIES = 2

TRADE_LABELS = {
    "plumbing": "plumbing",
    "electrical": "electrical",
    "carpentry": "carpentry",
    "civil": "civil work",
    "painting": "painting",
    "ceiling": "false ceiling",
    "glazing": "windows & grills",
    "pest_control": "pest control",
    "housekeeping": "cleaning",
}


def trade_category_of(row: dict[str, Any]) -> str:
    """Coarse trade for a line, or "" when none of the patterns match."""
    blob = " ".join(
        str(row.get(col, "") or "")
        for col in ("sub_service", "item_name", "work_label")
    )
    for category, pattern in TRADE_CATEGORIES:
        if pattern.search(blob):
            return category
    return ""


def _is_generic_zone(label: str) -> bool:
    text = str(label or "")
    if not _GENERIC_ZONE_RE.search(text):
        return False
    if _ROOM_NOUN_RE.search(text):
        return False
    return True


def bundle_zone_map(df) -> dict[tuple[str, str], list[str]]:
    """(vendor, space_id) -> trade categories, for catch-all zones only.

    Requires all three: a catch-all zone name, at least
    `BUNDLE_ZONE_MIN_LINES` lines, and at least
    `BUNDLE_ZONE_MIN_CATEGORIES` structurally distinct trades.
    """
    if df is None or len(df) == 0:
        return {}
    if "space_id" not in df.columns or "vendor_name" not in df.columns:
        return {}

    grouped: dict[tuple[str, str], dict[str, Any]] = {}
    for _, row in df.iterrows():
        space_id = str(row.get("space_id") or "")
        if not space_id or space_id == "project_level":
            continue
        names = [row.get("space"), row.get("space_raw")]
        if not any(_is_generic_zone(str(name or "")) for name in names):
            continue
        key = (str(row.get("vendor_name") or ""), space_id)
        entry = grouped.setdefault(key, {"lines": 0, "categories": []})
        entry["lines"] += 1
        category = trade_category_of(row)
        if category and category not in entry["categories"]:
            entry["categories"].append(category)

    return {
        key: entry["categories"]
        for key, entry in grouped.items()
        if entry["lines"] >= BUNDLE_ZONE_MIN_LINES
        and len(entry["categories"]) >= BUNDLE_ZONE_MIN_CATEGORIES
    }


def apply_bundle_zones(df):
    """Add `trade_category` and `bundle_zone` columns."""
    if df is None or len(df) == 0:
        return df
    df["trade_category"] = [trade_category_of(row) for _, row in df.iterrows()]
    zones = bundle_zone_map(df)
    df["bundle_zone"] = [
        (str(row.get("vendor_name") or ""), str(row.get("space_id") or "")) in zones
        for _, row in df.iterrows()
    ]
    return df


def bundle_zone_note(vendor: str, categories: list[str]) -> str:
    who = _vendor_short(vendor)
    named = [TRADE_LABELS.get(c, c.replace("_", " ")) for c in categories]
    if len(named) > 1:
        trades = ", ".join(named[:-1]) + f" and {named[-1]}"
    else:
        trades = named[0] if named else "several trades"
    return (
        f"{who} priced this as a single bundled scope covering {trades} — not "
        "broken out by room or item, so it can't be compared line-by-line."
    )


def bundle_zone_rows(df, vendors: list[str]) -> list[dict[str, Any]]:
    """One space-level-only entry per catch-all zone.

    Rupees stay on the vendor's own lines in the space tier — this row is a
    rendering instruction ("show the total, suppress the line matching"), not
    a second copy of the money.
    """
    zones = bundle_zone_map(df)
    if not zones:
        return []

    rows: list[dict[str, Any]] = []
    for (vendor, space_id), categories in zones.items():
        slice_ = df[
            (df["vendor_name"] == vendor) & (df["space_id"].astype(str) == space_id)
        ]
        if len(slice_) == 0:
            continue
        amount = float(
            slice_["amount"].fillna(0).sum() if "amount" in slice_.columns else 0.0
        )
        rows.append(
            {
                "match_tier": "BUNDLE_NOT_DECOMPOSABLE",
                "space_id": space_id,
                "space": str(slice_["space"].iloc[0] or space_id),
                "vendor": vendor,
                "categories": categories,
                "line_count": int(len(slice_)),
                "amount": round(amount),
                "confidence": 1.0,
                "rationale": (
                    f"{len(categories)} distinct trades in one catch-all zone"
                ),
                "note": bundle_zone_note(vendor, categories),
                "source_line_ids": [
                    str(v)
                    for v in (
                        slice_["line_id"].tolist() if "line_id" in slice_.columns else []
                    )
                    if str(v)
                ],
            }
        )
    rows.sort(key=lambda r: (r["space_id"], r["vendor"]))
    return rows


def family_of(row: dict[str, Any]) -> str:
    """Coarse family for a line, or "" when it belongs to none."""
    key = str(row.get("work_key") or "")
    slug = key.split(":", 1)[1] if ":" in key else key
    if slug in FAMILY_BY_SLUG:
        return FAMILY_BY_SLUG[slug]

    # Label fields only. Matching on `description` was too greedy: a wardrobe's
    # "Hettich inner sliding doors mechanisms soft closing" pulled furniture
    # hardware into the kitchen accessories family and inflated its total.
    blob = " ".join(
        str(row.get(col, "") or "")
        for col in ("sub_service", "item_name", "work_label")
    )
    for family, pattern in _FAMILY_PATTERNS:
        if pattern.search(blob):
            return family
    return ""


def is_lump_pricing(row: dict[str, Any]) -> bool:
    return bool(_LUMP_RE.search(str(row.get("pricing_method") or "")))


def _slug_for_fragment(fragment: str) -> str | None:
    """Resolve one comma-separated piece of a bundle description to a work slug.

    Order: S2 catalog (aliases + taxonomy), then the substring token table for
    phrases like "5 tandem" that never match as a whole label. Unknown
    fragments do not count — slugifying leftover prose ("Greenply", "Century")
    is what turned a single-item lumpsum into a fake package.
    """
    cleaned = _INCLUDES_RE.sub("", (fragment or "").strip())
    if not cleaned:
        return None

    try:
        from services.work_catalog import work_slug_for
    except Exception:
        work_slug_for = None  # type: ignore[assignment]

    if work_slug_for:
        slug = work_slug_for(cleaned)
        if slug:
            return slug

    folded = cleaned.casefold()
    for token, slug in _ITEM_TOKENS.items():
        if token in folded:
            return slug
    return None


def enumerated_items(description: str) -> list[str]:
    """Work keys a bundle description enumerates.

    Requires real separators and recognised items, so a long prose description
    of a single item does not read as a list. Recognition goes through S2 so
    the token table is not a second vocabulary that has to be kept in sync.
    """
    text = (description or "").strip()
    if not text:
        return []
    found: list[str] = []
    for fragment in _LIST_SPLIT_RE.split(text):
        slug = _slug_for_fragment(fragment)
        if slug and slug not in found:
            found.append(slug)
    return found


def is_bundle(row: dict[str, Any]) -> bool:
    """A bundle is lump-priced AND enumerates two or more distinct items.

    The second condition is what separates a genuine bundle from an ordinary
    single-item fixed price: a lump Rs 8,850 for one room's wall decor is not a
    bundle, while a lump Rs 1,00,300 listing six accessories is.
    """
    if not is_lump_pricing(row):
        return False
    return len(enumerated_items(str(row.get("description") or ""))) >= 2


def _bundle_id(vendor: str, family: str, label: str) -> str:
    slug = re.sub(r"[^a-z0-9]+", "_", f"{vendor}_{family}_{label}".casefold()).strip("_")
    return f"bundle:{slug}"[:120]


def apply_bundles(df):
    """Add scope / bundle_* / covered_* / overlap_flags columns."""
    if df is None or len(df) == 0:
        return df

    families = []
    scopes = []
    bundle_ids = []
    bundle_labels = []
    bundle_families = []
    covered_work = []
    covered_spaces = []

    for _, row in df.iterrows():
        family = family_of(row)
        families.append(family)

        if is_bundle(row):
            vendor = str(row.get("vendor_name") or "")
            label = str(row.get("work_label") or row.get("sub_service") or "Bundle")
            items = enumerated_items(str(row.get("description") or ""))
            scopes.append("bundle")
            # Mixed leftovers have no family to pair on. Include the space so
            # two unrelated packages with the same label stay distinct rows.
            fam = family or "mixed"
            id_label = f"{label}_{row.get('space_id') or ''}" if fam == "mixed" else label
            bundle_ids.append(_bundle_id(vendor, fam, id_label))
            bundle_labels.append(label)
            bundle_families.append(family or "mixed")
            covered_work.append(items)
            # A room-level package (Living Room complete package) names its room
            # on the line itself. Recording that space keeps coverage honest for
            # mixed-family bundles, which have no single FAMILY to fan out.
            # Empty still means "unknown, possibly all" for project-wide lumpsums.
            space_id = str(row.get("space_id") or "")
            if space_id and space_id != "project_level":
                covered_spaces.append([space_id])
            else:
                covered_spaces.append([])
        elif str(row.get("space_id") or "") == "project_level":
            scopes.append("project")
            bundle_ids.append("")
            bundle_labels.append("")
            bundle_families.append(family)
            covered_work.append([])
            covered_spaces.append([])
        else:
            scopes.append("space")
            bundle_ids.append("")
            bundle_labels.append("")
            bundle_families.append(family)
            covered_work.append([])
            covered_spaces.append([])

    df["bundle_family"] = bundle_families
    df["scope"] = scopes
    df["bundle_id"] = bundle_ids
    df["bundle_label"] = bundle_labels
    df["covered_work_keys"] = covered_work
    df["covered_space_ids"] = covered_spaces
    df["_family"] = families

    # Overlap: a bundle names an item the SAME vendor also bills on its own line.
    # We cannot know whether that is a duplicate or an inclusion, so we flag it.
    own_slugs: dict[str, set[str]] = {}
    for _, row in df.iterrows():
        if row["scope"] == "bundle":
            continue
        vendor = str(row.get("vendor_name") or "")
        key = str(row.get("work_key") or "")
        slug = key.split(":", 1)[1] if ":" in key else key
        own_slugs.setdefault(vendor, set()).add(slug)

    overlaps = []
    for _, row in df.iterrows():
        if row["scope"] != "bundle":
            overlaps.append([])
            continue
        vendor = str(row.get("vendor_name") or "")
        billed = own_slugs.get(vendor, set())
        overlaps.append([slug for slug in row["covered_work_keys"] if slug in billed])
    df["overlap_flags"] = overlaps

    df.drop(columns=["_family"], inplace=True, errors="ignore")
    return df


def _comparison_row_for_subset(subset, vendors: list[str], family: str, has_bundle: bool) -> dict[str, Any] | None:
    """Build one bundle-tier row from a family (or single mixed package) subset."""
    amounts: dict[str, float] = {}
    basis: dict[str, str] = {}
    line_counts: dict[str, int] = {}
    for vendor in vendors:
        vrows = subset[subset["vendor_name"] == vendor]
        if len(vrows) == 0:
            amounts[vendor] = 0.0
            basis[vendor] = "none"
            line_counts[vendor] = 0
            continue
        bundled = vrows[vrows["scope"] == "bundle"]
        if len(bundled) > 0:
            # The bundle price is the vendor's figure for this family. Adding
            # its other family lines on top would double count whatever the
            # lumpsum already covers.
            amounts[vendor] = float(bundled["amount"].sum())
            basis[vendor] = "bundle"
            line_counts[vendor] = len(bundled)
        else:
            amounts[vendor] = float(vrows["amount"].sum())
            basis[vendor] = "itemized"
            line_counts[vendor] = len(vrows)

    if not any(v > 0 for v in amounts.values()):
        return None

    placement: dict[str, str] = {}
    for vendor in vendors:
        vrows = subset[subset["vendor_name"] == vendor]
        if len(vrows) == 0 or basis.get(vendor) == "none":
            placement[vendor] = "none"
            continue
        if basis.get(vendor) == "bundle":
            placement[vendor] = "bundle"
            continue
        space_ids = {str(s) for s in vrows["space_id"].tolist()}
        in_project = "project_level" in space_ids
        in_rooms = any(s and s != "project_level" for s in space_ids)
        if in_project and in_rooms:
            placement[vendor] = "mixed"
        elif in_project:
            placement[vendor] = "project"
        else:
            placement[vendor] = "space"

    bundle_rows = subset[subset["scope"] == "bundle"]
    label = FAMILY_LABELS.get(family, family.replace("_", " ").capitalize())
    if len(bundle_rows) > 0:
        vendor_label = str(bundle_rows.iloc[0].get("bundle_label") or "").strip()
        if vendor_label and vendor_label.casefold() != label.casefold():
            label = f"{label} ({vendor_label})"

    covered_items: list[str] = []
    overlap_flags: list[str] = []
    for _, row in bundle_rows.iterrows():
        for slug in row.get("covered_work_keys") or []:
            if slug not in covered_items:
                covered_items.append(slug)
        for slug in row.get("overlap_flags") or []:
            if slug not in overlap_flags:
                overlap_flags.append(slug)

    covered_space_labels = sorted(
        {
            str(s)
            for s in subset["space"].tolist()
            if str(s) and str(s) != "Project-level"
        }
    )

    # Lineage per vendor. The reconciliation gate reads `line_ids`, and only
    # counts a bundle row's rupees when that vendor's basis is "bundle" — an
    # itemised figure is already counted in the space or project tier.
    line_ids: dict[str, list[str]] = {}
    for vendor in vendors:
        vrows = subset[subset["vendor_name"] == vendor]
        if basis.get(vendor) == "bundle":
            vrows = vrows[vrows["scope"] == "bundle"]
        line_ids[vendor] = [
            str(v)
            for v in (vrows["line_id"].tolist() if "line_id" in vrows.columns else [])
            if str(v)
        ]

    row_dict: dict[str, Any] = {
        "match_tier": "MATCH",
        "line_ids": line_ids,
        "source_line_ids": [lid for ids in line_ids.values() for lid in ids],
        "bundle_id": (
            str(bundle_rows.iloc[0]["bundle_id"])
            if len(bundle_rows) > 0
            else f"family:{family}"
        ),
        "bundle_label": label,
        "bundle_family": family,
        "covered_spaces": covered_space_labels,
        "covered_items": [s.replace("_", " ") for s in covered_items],
        "overlap_flags": [s.replace("_", " ") for s in overlap_flags],
        "basis": basis,
        "line_counts": line_counts,
        "has_bundle": has_bundle,
        "placement": placement,
    }
    for vendor in vendors:
        amount = amounts.get(vendor, 0.0)
        row_dict[vendor] = round(amount) if amount > 0 else 0
    takeaway = bundle_takeaway(row_dict, vendors)
    if takeaway:
        row_dict["takeaway"] = takeaway
    return row_dict


TAKEAWAY_MIN_GAP_ABS = 15_000
TAKEAWAY_MIN_GAP_PCT = 0.25


def inr_indian(n: float) -> str:
    """Rupees in Indian digit grouping. Client-facing notes use this."""
    n = int(round(n))
    sign = "-" if n < 0 else ""
    n = abs(n)
    digits = str(n)
    if len(digits) <= 3:
        return f"{sign}₹{digits}"
    last3, rest = digits[-3:], digits[:-3]
    groups: list[str] = []
    while rest:
        groups.append(rest[-2:])
        rest = rest[:-2]
    return f"{sign}₹{','.join(reversed(groups))},{last3}"


def _vendor_short(name: str) -> str:
    text = (name or "").strip()
    if "(" in text:
        text = text.split("(", 1)[0].strip()
    return text or name


def bundle_takeaway(row: dict[str, Any], vendors: list[str]) -> dict[str, str] | None:
    """Plain-English package vs itemised note, or None when the gap is small.

    Only fires when one vendor priced a family as a lumpsum and another listed
    it line by line. Scattered recaps (both itemised) never get a takeaway.
    """
    basis = row.get("basis") or {}
    bundlers = [v for v in vendors if basis.get(v) == "bundle"]
    itemizers = [v for v in vendors if basis.get(v) == "itemized"]
    if not bundlers or not itemizers:
        return None

    best: tuple[float, str, str, float, float] | None = None
    for bundler in bundlers:
        for itemizer in itemizers:
            package = float(row.get(bundler) or 0)
            listed = float(row.get(itemizer) or 0)
            if package <= 0 or listed <= 0:
                continue
            gap = abs(package - listed)
            floor = min(package, listed)
            if gap < TAKEAWAY_MIN_GAP_ABS or gap < TAKEAWAY_MIN_GAP_PCT * floor:
                continue
            if best is None or gap > best[0]:
                best = (gap, bundler, itemizer, package, listed)
    if best is None:
        return None

    gap, bundler, itemizer, package, listed = best
    pkg_name = _vendor_short(bundler)
    listed_name = _vendor_short(itemizer)
    label = str(row.get("bundle_label") or "this work")
    counts = row.get("line_counts") or {}
    n_lines = int(counts.get(itemizer) or 0)
    lines_phrase = (
        f"{n_lines} line{'s' if n_lines != 1 else ''}" if n_lines > 0 else "listed lines"
    )
    flags = [str(f) for f in (row.get("overlap_flags") or []) if str(f).strip()]
    overlap_ask = ""
    if flags:
        overlap_ask = f", and whether {', '.join(flags)} is also billed separately"

    if package > listed:
        text = (
            f"{pkg_name} priced {label} as one package of {inr_indian(package)}. "
            f"{listed_name} listed the same kind of work in {lines_phrase} totalling "
            f"{inr_indian(listed)}. {pkg_name} is about {inr_indian(gap)} higher. "
            f"That can mean a fuller kit — or a dear package. Ask {pkg_name} what "
            f"the package includes{overlap_ask}. Ask {listed_name} whether those "
            f"{lines_phrase} cover the same set."
        )
        return {"kind": "package_higher", "text": text}

    text = (
        f"{pkg_name} priced {label} as one package of {inr_indian(package)}. "
        f"{listed_name}'s listed lines add up to {inr_indian(listed)}, which is "
        f"about {inr_indian(gap)} more. The package looks cheaper — it may also "
        f"cover less. Ask {pkg_name} for a written list of what is inside the "
        f"package, and match it to {listed_name}'s line items before treating this "
        f"as a saving."
    )
    return {"kind": "package_lower", "text": text}


def bundle_comparison_rows(df, vendors: list[str]) -> list[dict[str, Any]]:
    """One comparison row per family that cannot be compared space by space.

    Emitted when either:
      (a) some vendor bundled that family, or
      (b) the family's lines are scattered across different spaces between
          vendors, so a room-by-room comparison would be misleading.

    Condition (b) is what surfaces the electrical gap the old two-vendor guard
    hid: one vendor priced it inside the kitchen, the other left it
    project-level, and neither used a lumpsum.

    `mixed` is a leftover bucket, not a real family. Unrelated mixed packages
    (wall décor, blinds, a living-room complete package) must each stay their
    own row — summing them invents a figure no vendor quoted.
    """
    if df is None or len(df) == 0 or not vendors:
        return []
    if "bundle_family" not in df.columns:
        return []

    rows: list[dict[str, Any]] = []
    families = [f for f in df["bundle_family"].unique().tolist() if f]

    for family in sorted(families):
        subset = df[df["bundle_family"] == family]
        if len(subset) == 0:
            continue

        family_vendors = subset["vendor_name"].unique().tolist()
        has_bundle = bool((subset["scope"] == "bundle").any())
        space_ids = {str(s) for s in subset["space_id"].tolist()}
        scattered = len(space_ids) > 1 and len(family_vendors) > 1

        if family == "mixed":
            # Never recap leftover unmatched lines as one Mixed total.
            if not has_bundle:
                continue
            bundled = subset[subset["scope"] == "bundle"]
            for _, group in bundled.groupby("bundle_id", sort=False):
                row = _comparison_row_for_subset(group, vendors, family, True)
                if row:
                    rows.append(row)
            continue

        if not has_bundle and not scattered:
            continue

        row = _comparison_row_for_subset(subset, vendors, family, has_bundle)
        if row:
            rows.append(row)

    return rows


def bundled_families_by_vendor(df) -> dict[str, dict[str, str]]:
    """Vendor -> {family: bundle label}.

    Used to decide, cell by cell, whether a zero means "did not quote" or
    "already inside that vendor's bundle". Without this the matrix reports the
    two identically, which is the single most misleading thing it can do.
    """
    if df is None or len(df) == 0 or "scope" not in df.columns:
        return {}

    out: dict[str, dict[str, str]] = {}
    for _, row in df[df["scope"] == "bundle"].iterrows():
        vendor = str(row.get("vendor_name") or "")
        family = str(row.get("bundle_family") or "")
        if not family:
            continue
        label = str(row.get("bundle_label") or FAMILY_LABELS.get(family) or family)
        out.setdefault(vendor, {})[family] = label
    return out


def bundled_space_ids(df) -> dict[str, set[str]]:
    """Vendor -> space ids whose price is (partly) inside a bundle.

    A bundle names items rather than rooms, so the affected rooms are those where
    the same family appears for any vendor. That is what turns a misleading N/A
    into "incl. in <bundle>".
    """
    if df is None or len(df) == 0 or "scope" not in df.columns:
        return {}

    affected: dict[str, set[str]] = {}
    bundles = df[df["scope"] == "bundle"]
    for _, row in bundles.iterrows():
        vendor = str(row.get("vendor_name") or "")
        family = str(row.get("bundle_family") or "")
        if not family:
            continue
        explicit = {str(s) for s in (row.get("covered_space_ids") or []) if str(s)}
        if explicit:
            affected.setdefault(vendor, set()).update(explicit)
            continue
        family_rows = df[(df["bundle_family"] == family) & (df["scope"] == "space")]
        for space_id in family_rows["space_id"].tolist():
            affected.setdefault(vendor, set()).add(str(space_id))
    return affected

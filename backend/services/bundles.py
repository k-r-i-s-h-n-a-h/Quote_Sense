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
_LIST_SPLIT_RE = re.compile(r",|;|\band\b|&|\+|/")

# Tokens that name a work item inside a bundle description. Used only to count
# how many distinct items a description enumerates, and to spot overlaps.
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


def enumerated_items(description: str) -> list[str]:
    """Work keys a bundle description enumerates.

    Requires real separators and recognised item tokens, so a long prose
    description of a single item does not read as a list.
    """
    text = (description or "").casefold()
    if not text:
        return []
    found: list[str] = []
    for fragment in _LIST_SPLIT_RE.split(text):
        fragment = fragment.strip()
        if not fragment:
            continue
        for token, slug in _ITEM_TOKENS.items():
            if token in fragment and slug not in found:
                found.append(slug)
                break
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
            bundle_ids.append(_bundle_id(vendor, family or "mixed", label))
            bundle_labels.append(label)
            bundle_families.append(family or "mixed")
            covered_work.append(items)
            # A bundle description rarely names rooms; leaving this empty means
            # "unknown, possibly all", which the coverage step treats as
            # affecting every room where the family appears.
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


def bundle_comparison_rows(df, vendors: list[str]) -> list[dict[str, Any]]:
    """One comparison row per family that cannot be compared space by space.

    Emitted when either:
      (a) some vendor bundled that family, or
      (b) the family's lines are scattered across different spaces between
          vendors, so a room-by-room comparison would be misleading.

    Condition (b) is what surfaces the electrical gap the old two-vendor guard
    hid: one vendor priced it inside the kitchen, the other left it
    project-level, and neither used a lumpsum.
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

        if not has_bundle and not scattered:
            continue

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
            continue

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

        row_dict: dict[str, Any] = {
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
        }
        for vendor in vendors:
            amount = amounts.get(vendor, 0.0)
            row_dict[vendor] = round(amount) if amount > 0 else 0
        rows.append(row_dict)

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

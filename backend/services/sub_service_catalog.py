"""
PM Interiors sub-service catalog + spreadsheet alias map.

Lookup is case-insensitive (casefold) but returns the exact PM catalog string
so market_moving_averages.sub_service always stores the canonical name.
"""

from __future__ import annotations

import re
from typing import Iterable

# Exact PM catalog names (case-sensitive as provided by platform).
INTERIORS_SUB_SERVICES: tuple[str, ...] = (
    "Wall & Ceiling",
    "Wall Decor",
    "Bedroom Decor",
    "Profile Shutters",
    "Wall Unit",
    "Wardrobe",
    "Hardwares",
    "PVC Tray and Thali",
    "Sink",
    "Arch Work",
    "Pelmet",
    "Dressing Unit",
    "Electrical Work",
    "Columns",
    "2D Floor Planning",
    "3D Visualization",
    "Concept Design",
    "BOQ Preparation",
    "Material Selection Assistance",
    "Modular Kitchen",
    "TV Units",
    "Crockery Units",
    "Vanity Units",
    "Storage Solutions",
    "False Ceiling",
    "Flooring Replacement",
    "Tiling",
    "Partition Walls",
    "Structural Alterations",
    "Bathroom Renovation",
    "Wallpaper",
    "Wall Panels",
    "Soft Furnishings",
    "Custom Furniture",
    "Lighting Design",
    "Seater",
    "Tall Unit",
    "Paneling",
    "Shower Partition",
    "Study Table",
    "Janitor Unit",
    "Cot",
    "Single Bed",
    "Queen Size Bed",
    "King Size Bed",
    "Ultra King Size Bed",
    "Mirror",
    "Dressing Table",
    "Upholstery",
    "Base Unit",
    "Loft",
    "Handles",
    "Knobs",
    "Utility Unit",
    "Sliding Mechanism",
    "Tandem Pullouts",
    "Bottle Pullouts",
    "Corner Unit",
    "Pantry Pullout",
    "Hob",
    "Rolling Shutter",
    "Wicker Baskets",
    "Lift-up Mechanisms",
    "Chimney",
    "Countertops",
    "Partitions",
    "Pooja Unit",
    "Granite",
    "Bench Seating",
    "Seating Unit",
    "Drawer Unit",
    "Shoe Rack",
    "Accessories",
    "Console unit",
    "Sofa",
    "Head Board",
    "Middle unit",
    "Tandem channels",
    "cabinet",
    "Loft & Door Type",
    "Loose Furniture",
    "Wall beedings",
    "Bed",
    "Shutters",
)

# Spreadsheet / free-text label (casefold key) → one or more PM catalog names.
# Combined spreadsheet rows can expand to multiple catalog entries.
SUB_SERVICE_ALIASES: dict[str, tuple[str, ...]] = {
    "base unit": ("Base Unit",),
    "middle unit / wall unit": ("Middle unit", "Wall Unit"),
    "middle unit": ("Middle unit",),
    "wall unit": ("Wall Unit",),
    "loft": ("Loft",),
    "tv unit": ("TV Units",),
    "tv units": ("TV Units",),
    "crockery unit": ("Crockery Units",),
    "crockery units": ("Crockery Units",),
    "wardrobe": ("Wardrobe",),
    "wardrobes": ("Wardrobe",),
    "dressing unit": ("Dressing Unit",),
    "vanity unit": ("Vanity Units",),
    "vanity units": ("Vanity Units",),
    "study table": ("Study Table",),
    "wall panels": ("Wall Panels",),
    "bottle pullout": ("Bottle Pullouts",),
    "bottle pullouts": ("Bottle Pullouts",),
    "tandem channel": ("Tandem channels",),
    "tandem channels": ("Tandem channels",),
    "rolling shutter mechanism": ("Rolling Shutter",),
    "rolling shutter": ("Rolling Shutter",),
    "pvc tray & thali": ("PVC Tray and Thali",),
    "pvc tray and thali": ("PVC Tray and Thali",),
    "shoe rack": ("Shoe Rack",),
    "pooja unit": ("Pooja Unit",),
    "false ceiling": ("False Ceiling",),
    "wallpaper": ("Wallpaper",),
    # Known spreadsheet labels with no PM catalog entry yet — empty = reject.
    "breakfast counter": (),
    "deep cleaning": (),
}

_PM_BY_CASEFOLD: dict[str, str] = {n.casefold(): n for n in INTERIORS_SUB_SERVICES}


def normalize_label(value: str | None) -> str:
    """Trim and collapse internal whitespace."""
    if not value:
        return ""
    return re.sub(r"\s+", " ", str(value).strip())


def resolve_sub_services(raw: str | None) -> list[str]:
    """
    Map a free-text sub_service to exact PM catalog name(s).

    Matching order:
      1) alias map (case-insensitive)
      2) direct catalog match (case-insensitive → canonical casing)

    Returns [] when unknown or explicitly unmapped (caller should skip/flag).
    """
    key = normalize_label(raw).casefold()
    if not key:
        return []

    if key in SUB_SERVICE_ALIASES:
        return list(SUB_SERVICE_ALIASES[key])

    canonical = _PM_BY_CASEFOLD.get(key)
    return [canonical] if canonical else []


def is_known_sub_service(raw: str | None) -> bool:
    return bool(resolve_sub_services(raw))


def assert_aliases_point_at_catalog(names: Iterable[str] = INTERIORS_SUB_SERVICES) -> None:
    catalog = set(names)
    for alias, targets in SUB_SERVICE_ALIASES.items():
        for t in targets:
            if t not in catalog:
                raise ValueError(f"Alias {alias!r} points at unknown catalog name {t!r}")

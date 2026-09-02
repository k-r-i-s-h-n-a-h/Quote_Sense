#!/usr/bin/env python3
"""
Rename market_moving_averages (and optionally quote_items) to the new Tatva
catalog labels, and backfill service_id / sub_service_id / pricing_method_id.

Uses backend/data/tatva_service_ids.json. Sub-service and pricing-method
JSON maps were removed; those dicts are empty unless leftover files exist.

Usage (from backend/):

  # Preview from the exported CSV (no DB writes)
  python scripts/migrate_ma_catalog_names.py \\
    --csv "data/market_moving_averages_rows (2).csv" \\
    --dry-run

  # Write a remapped CSV you can inspect / import
  python scripts/migrate_ma_catalog_names.py \\
    --csv "data/market_moving_averages_rows (2).csv" \\
    --out-csv data/market_moving_averages_remapped.csv

  # Apply updates to Supabase market_moving_averages (row-by-id)
  python scripts/migrate_ma_catalog_names.py --from-db --apply

  # Also rename + backfill ids on quote_items
  python scripts/migrate_ma_catalog_names.py --from-db --apply --also-quote-items

Requires SUPABASE_URL + SUPABASE_SERVICE_ROLE_KEY in backend/.env for --from-db / --apply.
"""
from __future__ import annotations

import argparse
import csv
import json
import os
import sys
from collections import Counter
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

DATA = ROOT / "data"

# Old display names → new Tatva service_category (same ObjectId).
SERVICE_CATEGORY_ALIASES: dict[str, str] = {
    "Interiors": "Residential Interior",
    "Interior Design": "Residential Interior",
    "Residential Interiors": "Residential Interior",
    "Electrical Services": "Home Renovation",
    "Electrical": "Home Renovation",
    "Painting": "Property Management & Rental Operations",
    "Plumbing Services": "Facility Management and Security",
    "Plumbing": "Facility Management and Security",
    "Solar Services": "Solar, Energy & Automation Solutions",
    "Solar": "Solar, Energy & Automation Solutions",
    "Property Development": "Property Advisory, Sales & Leasing",
    "Home Automation": "Home Maintenance & Appliance Care",
    "Event Management": "Event Management",
    "Residential Construction": "Residential Construction",
    "Farm Infrastructure": "Farm Infrastructure Setup",
    "Farm Infrastructure Setup": "Farm Infrastructure Setup",
    "Irrigation Automation": "Irrigation Automation",
}

# Old pricing_method labels in MA / PDFs → new catalog name (new ObjectId).
# This is a label bridge — old stub ObjectIds are intentionally ignored.
PRICING_METHOD_ALIASES: dict[str, str] = {
    "Area (sqft)": "Area – Direct Entry (sq ft)",
    "Area (in sqft)": "Area – Direct Entry (sq ft)",
    "Area in sqft": "Area – Direct Entry (sq ft)",
    "sqft": "Area – Direct Entry (sq ft)",
    "Area (sqft)/Per Unit": "Area – Direct Entry (sq ft)",
    "Square Feet": "Area – Direct Entry (sq ft)",
    "Area (in sqmm)": "Area – Direct Entry (sq m)",
    "Area(in sqmm)": "Area – Direct Entry (sq m)",
    "Area(in sqm)": "Area – Direct Entry (sq m)",
    "Area (in sqm)": "Area – Direct Entry (sq m)",
    "Per Unit": "Per Unit / Each",
    "Running Feet": "Running Length (rft)",
    "Lump Sum": "Fixed Amount / Lump Sum",
    "Fixed Amount": "Fixed Amount / Lump Sum",
    "Unit": "Per Unit / Each",
    # Already matching (or close) — keep explicit so we still attach ids
    "Per Project": "Per Project",
    "Per Point": "Per Point",
    "Per Visit": "Per Visit",
    "Per View": "Per View",
    "Per Window": "Per Window",
    "Per Event": "Per Event",
    "Per Panel": "Per Panel",
    "Cubic Feet": "Cubic Feet",
}


def _load_json(path: Path) -> dict:
    try:
        raw = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        return {}
    return raw if isinstance(raw, dict) else {}


def load_catalogs() -> tuple[dict[str, str], dict[str, str], dict[str, str]]:
    """Return (category→service_id, sub→id, pricing→id) with casefold keys for lookup."""
    services = _load_json(DATA / "tatva_service_ids.json")
    subs = _load_json(DATA / "tatva_sub_service_ids.json")
    pms = _load_json(DATA / "tatva_pricing_method_ids.json")

    cat_to_sid: dict[str, str] = {}
    for sid, entry in services.items():
        if isinstance(entry, dict):
            name = str(entry.get("service_category") or "").strip()
            if name:
                cat_to_sid[name.casefold()] = str(sid).strip()

    sub_to_id = {
        str(k).strip().casefold(): str(v).strip()
        for k, v in subs.items()
        if str(k).strip() and str(v).strip()
    }
    pm_to_id = {
        str(k).strip().casefold(): str(v).strip()
        for k, v in pms.items()
        if str(k).strip() and str(v).strip()
    }
    return cat_to_sid, sub_to_id, pm_to_id


def canonicalize_category(name: str) -> str:
    text = (name or "").strip()
    if not text:
        return text
    return SERVICE_CATEGORY_ALIASES.get(text, text)


def canonicalize_pricing_method(name: str) -> str:
    text = (name or "").strip()
    if not text:
        return text
    if text in PRICING_METHOD_ALIASES:
        return PRICING_METHOD_ALIASES[text]
    # case-insensitive alias hit
    hit = PRICING_METHOD_ALIASES.get(text)
    if hit:
        return hit
    for old, new in PRICING_METHOD_ALIASES.items():
        if old.casefold() == text.casefold():
            return new
    return text


def remap_row(
    row: dict[str, Any],
    *,
    cat_to_sid: dict[str, str],
    sub_to_id: dict[str, str],
    pm_to_id: dict[str, str],
) -> dict[str, Any]:
    out = dict(row)
    old_cat = (row.get("service_category") or "").strip()
    old_sub = (row.get("sub_service") or "").strip()
    old_pm = (row.get("pricing_method") or "").strip()

    new_cat = canonicalize_category(old_cat)
    new_pm = canonicalize_pricing_method(old_pm)
    new_sub = old_sub  # sub names in this export already match catalog

    out["service_category"] = new_cat
    out["sub_service"] = new_sub
    out["pricing_method"] = new_pm
    out["item_key"] = f"{new_sub}::{new_pm}"

    out["service_id"] = cat_to_sid.get(new_cat.casefold(), "") or (row.get("service_id") or "")
    out["sub_service_id"] = sub_to_id.get(new_sub.casefold(), "") or (row.get("sub_service_id") or "")
    out["pricing_method_id"] = pm_to_id.get(new_pm.casefold(), "") or (row.get("pricing_method_id") or "")
    return out


def read_csv(path: Path) -> list[dict[str, str]]:
    with path.open(encoding="utf-8-sig", newline="") as f:
        return list(csv.DictReader(f))


def write_csv(path: Path, rows: list[dict[str, Any]]) -> None:
    if not rows:
        path.write_text("", encoding="utf-8")
        return
    fieldnames = list(rows[0].keys())
    # Prefer a stable column order when present
    preferred = [
        "id",
        "service_type",
        "service_category",
        "service_id",
        "sub_service",
        "sub_service_id",
        "pricing_method",
        "pricing_method_id",
        "item_key",
        "moving_average",
        "rate_moving_average",
        "weight",
        "last_session_id",
        "updated_at",
    ]
    ordered = [c for c in preferred if c in fieldnames] + [
        c for c in fieldnames if c not in preferred
    ]
    with path.open("w", encoding="utf-8", newline="") as f:
        w = csv.DictWriter(f, fieldnames=ordered, extrasaction="ignore")
        w.writeheader()
        for r in rows:
            w.writerow(r)


def fetch_ma_from_db() -> list[dict[str, Any]]:
    from services.env_config import get_supabase_client

    client = get_supabase_client()
    rows: list[dict[str, Any]] = []
    batch = 500
    offset = 0
    while True:
        res = (
            client.table("market_moving_averages")
            .select("*")
            .range(offset, offset + batch - 1)
            .execute()
        )
        chunk = res.data or []
        if not chunk:
            break
        rows.extend(chunk)
        if len(chunk) < batch:
            break
        offset += batch
    return rows


def fetch_quote_items_from_db() -> list[dict[str, Any]]:
    from services.env_config import get_supabase_client

    client = get_supabase_client()
    rows: list[dict[str, Any]] = []
    batch = 500
    offset = 0
    cols = (
        "id,service_type,service_category,sub_service,pricing_method,"
        "service_id,sub_service_id,pricing_method_id"
    )
    while True:
        res = (
            client.table("quote_items")
            .select(cols)
            .range(offset, offset + batch - 1)
            .execute()
        )
        chunk = res.data or []
        if not chunk:
            break
        rows.extend(chunk)
        if len(chunk) < batch:
            break
        offset += batch
    return rows


def apply_ma_updates(rows: list[dict[str, Any]]) -> int:
    from services.env_config import get_supabase_client

    client = get_supabase_client()
    updated = 0
    for row in rows:
        rid = row.get("id")
        if not rid:
            continue
        payload = {
            "service_category": row["service_category"],
            "sub_service": row["sub_service"],
            "pricing_method": row["pricing_method"],
            "item_key": row["item_key"],
            "service_id": row.get("service_id") or None,
            "sub_service_id": row.get("sub_service_id") or None,
            "pricing_method_id": row.get("pricing_method_id") or None,
        }
        client.table("market_moving_averages").update(payload).eq("id", rid).execute()
        updated += 1
        if updated % 50 == 0:
            print(f"  … updated {updated} MA rows")
    return updated


def apply_quote_item_updates(rows: list[dict[str, Any]]) -> int:
    from services.env_config import get_supabase_client

    client = get_supabase_client()
    updated = 0
    for row in rows:
        rid = row.get("id")
        if rid is None:
            continue
        payload = {
            "service_category": row["service_category"],
            "sub_service": row["sub_service"],
            "pricing_method": row["pricing_method"],
            "service_id": row.get("service_id") or None,
            "sub_service_id": row.get("sub_service_id") or None,
            "pricing_method_id": row.get("pricing_method_id") or None,
        }
        client.table("quote_items").update(payload).eq("id", rid).execute()
        updated += 1
        if updated % 100 == 0:
            print(f"  … updated {updated} quote_items")
    return updated


def summarize(
    before: list[dict[str, Any]],
    after: list[dict[str, Any]],
) -> None:
    cat_changes = Counter()
    pm_changes = Counter()
    missing_sid = 0
    missing_sub = 0
    missing_pm = 0
    for b, a in zip(before, after):
        if (b.get("service_category") or "") != (a.get("service_category") or ""):
            cat_changes[f"{b.get('service_category')} → {a.get('service_category')}"] += 1
        if (b.get("pricing_method") or "") != (a.get("pricing_method") or ""):
            pm_changes[f"{b.get('pricing_method')} → {a.get('pricing_method')}"] += 1
        if not a.get("service_id"):
            missing_sid += 1
        if not a.get("sub_service_id"):
            missing_sub += 1
        if not a.get("pricing_method_id"):
            missing_pm += 1

    print("\n=== Remap summary ===")
    print(f"rows: {len(after)}")
    print("service_category changes:")
    for k, v in cat_changes.most_common():
        print(f"  {v:4d}  {k}")
    if not cat_changes:
        print("  (none)")
    print("pricing_method changes:")
    for k, v in pm_changes.most_common():
        print(f"  {v:4d}  {k}")
    if not pm_changes:
        print("  (none)")
    print(
        f"missing ids after remap — service_id: {missing_sid}, "
        f"sub_service_id: {missing_sub}, pricing_method_id: {missing_pm}"
    )

    # Unique-key collision check (would break UNIQUE constraint if applied)
    keys: dict[tuple, list] = {}
    for a in after:
        key = (
            a.get("service_type"),
            a.get("service_category"),
            a.get("sub_service"),
            a.get("pricing_method"),
        )
        keys.setdefault(key, []).append(a.get("id"))
    collisions = {k: ids for k, ids in keys.items() if len(ids) > 1}
    if collisions:
        print(f"\n⚠️  {len(collisions)} unique-key collisions after remap — merge before apply:")
        for k, ids in list(collisions.items())[:10]:
            print(f"  {k} → {ids}")
    else:
        print("\n✓ No unique-key collisions after remap")


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument(
        "--csv",
        type=Path,
        default=DATA / "market_moving_averages_rows (2).csv",
        help="Input MA CSV export",
    )
    ap.add_argument("--from-db", action="store_true", help="Load rows from Supabase instead of CSV")
    ap.add_argument("--out-csv", type=Path, default=None, help="Write remapped CSV here")
    ap.add_argument("--dry-run", action="store_true", help="Print summary only (default if not --apply)")
    ap.add_argument("--apply", action="store_true", help="UPDATE Supabase rows by id")
    ap.add_argument(
        "--also-quote-items",
        action="store_true",
        help="Also remap quote_items names + ids (requires --from-db or --apply with DB)",
    )
    args = ap.parse_args()

    if not args.apply:
        args.dry_run = True

    cat_to_sid, sub_to_id, pm_to_id = load_catalogs()
    print(
        f"Catalogs loaded: {len(cat_to_sid)} services, "
        f"{len(sub_to_id)} sub-services, {len(pm_to_id)} pricing methods"
    )

    if args.from_db:
        before = fetch_ma_from_db()
        print(f"Loaded {len(before)} rows from market_moving_averages")
    else:
        csv_path = args.csv if args.csv.is_absolute() else ROOT / args.csv
        if not csv_path.exists():
            print(f"CSV not found: {csv_path}", file=sys.stderr)
            return 1
        before = read_csv(csv_path)
        print(f"Loaded {len(before)} rows from {csv_path.name}")

    after = [
        remap_row(r, cat_to_sid=cat_to_sid, sub_to_id=sub_to_id, pm_to_id=pm_to_id)
        for r in before
    ]
    summarize(before, after)

    if args.out_csv:
        out = args.out_csv if args.out_csv.is_absolute() else ROOT / args.out_csv
        write_csv(out, after)
        print(f"\nWrote remapped CSV → {out}")

    if args.apply:
        print("\nApplying market_moving_averages updates…")
        n = apply_ma_updates(after)
        print(f"Updated {n} market_moving_averages rows")

        if args.also_quote_items:
            print("\nRemapping quote_items…")
            qi_before = fetch_quote_items_from_db()
            qi_after = [
                remap_row(r, cat_to_sid=cat_to_sid, sub_to_id=sub_to_id, pm_to_id=pm_to_id)
                for r in qi_before
            ]
            # quote_items has no item_key — drop if added
            for r in qi_after:
                r.pop("item_key", None)
            summarize(qi_before, qi_after)
            nq = apply_quote_item_updates(qi_after)
            print(f"Updated {nq} quote_items rows")
    elif args.dry_run:
        print("\nDry-run only. Re-run with --apply (and --from-db) to write to Supabase.")

    return 0


if __name__ == "__main__":
    raise SystemExit(main())

#!/usr/bin/env python3
"""
Rebuild market_moving_averages from quote_items.raw rate + pricing_method bundles.

Usage (from backend/):
  venv/bin/python scripts/backfill_market_rates.py
  venv/bin/python scripts/backfill_market_rates.py --dry-run
"""
from __future__ import annotations

import argparse
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from services.env_config import get_supabase_client
from services.market_rate import DEFAULT_SERVICE_TYPE, normalize_pricing_method, normalize_service_type, normalize_text

BATCH = 500


def fetch_all_quote_items():
    client = get_supabase_client()
    rows = []
    offset = 0
    while True:
        res = (
            client.table("quote_items")
            .select("service_type,service_category,sub_service,pricing_method,rate")
            .gt("rate", 0)
            .range(offset, offset + BATCH - 1)
            .execute()
        )
        chunk = res.data or []
        if not chunk:
            break
        rows.extend(chunk)
        if len(chunk) < BATCH:
            break
        offset += BATCH
    return rows


def aggregate(rows):
    buckets: dict[tuple, list[float]] = {}
    for row in rows:
        st = normalize_service_type(row.get("service_type"))
        cat = normalize_text(row.get("service_category"), "Other")
        sub = normalize_text(row.get("sub_service"), "General")
        pm = normalize_pricing_method(row.get("pricing_method"))
        rate = float(row.get("rate") or 0)
        if rate <= 0 or not cat or not sub or not pm:
            continue
        buckets.setdefault((st, cat, sub, pm), []).append(rate)

    out = []
    for (st, cat, sub, pm), rates in buckets.items():
        avg = round(sum(rates) / len(rates), 2)
        out.append(
            {
                "service_type": st,
                "service_category": cat,
                "sub_service": sub,
                "pricing_method": pm,
                "rate_moving_average": avg,
                "moving_average": avg,
                "weight": len(rates),
                "item_key": sub,
                "last_session_id": "BACKFILL_FROM_QUOTE_ITEMS",
            }
        )
    return out


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--dry-run", action="store_true")
    args = parser.parse_args()

    rows = fetch_all_quote_items()
    print(f"Loaded {len(rows)} quote_items with rate > 0")
    payloads = aggregate(rows)
    print(f"Aggregated {len(payloads)} market bundles")

    samples = [
        ("Interiors", "Wardrobes", "Area (in sqft)"),
        ("Residential Construction", "Site Clearing & Excavation", "Area (in sqft)"),
        ("Residential Construction", "Site Clearing & Excavation", "Per Visit"),
    ]
    for cat, sub, pm in samples:
        match = next(
            (p for p in payloads if p["service_category"] == cat and p["sub_service"] == sub and p["pricing_method"] == pm),
            None,
        )
        if match:
            print(f"  ✓ {sub} / {pm} → ₹{match['rate_moving_average']:,.2f} (n={match['weight']})")
        else:
            print(f"  ✗ {sub} / {pm} — no quote_items data")

    if args.dry_run:
        print("Dry run — no writes.")
        return

    client = get_supabase_client()
    # Clear legacy rows (sessions FK cascades)
    client.table("market_moving_averages").delete().neq("id", "00000000-0000-0000-0000-000000000000").execute()

    for i in range(0, len(payloads), BATCH):
        chunk = payloads[i : i + BATCH]
        client.table("market_moving_averages").insert(chunk).execute()

    print(f"Inserted {len(payloads)} rows into market_moving_averages.")


if __name__ == "__main__":
    main()

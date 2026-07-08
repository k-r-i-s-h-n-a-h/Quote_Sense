#!/usr/bin/env python3
"""
Delete comparison staging data after market rates were merged.

Only removes quotes/quote_items where market_rates_applied_at is set and older
than --days. Never touches market_moving_averages.

Usage (from backend/):
  venv/bin/python scripts/cleanup_comparison_sessions.py --dry-run
  venv/bin/python scripts/cleanup_comparison_sessions.py --days 7
"""
from __future__ import annotations

import argparse
import os
import sys
from datetime import datetime, timedelta, timezone

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from services.env_config import get_supabase_client

BATCH = 200


def _cutoff_iso(days: int) -> str:
    return (datetime.now(timezone.utc) - timedelta(days=days)).isoformat()


def _fetch_stale_quote_ids(client, cutoff: str) -> list[str]:
    ids: list[str] = []
    offset = 0
    while True:
        res = (
            client.table("quotes")
            .select("id")
            .not_.is_("market_rates_applied_at", "null")
            .lt("market_rates_applied_at", cutoff)
            .range(offset, offset + BATCH - 1)
            .execute()
        )
        chunk = res.data or []
        if not chunk:
            break
        ids.extend(str(row["id"]) for row in chunk if row.get("id"))
        if len(chunk) < BATCH:
            break
        offset += BATCH
    return ids


def cleanup(days: int, *, dry_run: bool = False) -> dict:
    client = get_supabase_client()
    cutoff = _cutoff_iso(days)
    quote_ids = _fetch_stale_quote_ids(client, cutoff)

    item_count = 0
    if quote_ids:
        for i in range(0, len(quote_ids), BATCH):
            batch = quote_ids[i : i + BATCH]
            res = (
                client.table("quote_items")
                .select("id", count="exact")
                .in_("quote_id", batch)
                .execute()
            )
            item_count += int(res.count or 0)

    print(f"Cutoff: market_rates_applied_at < {cutoff} ({days} days)")
    print(f"Quotes to delete: {len(quote_ids)}")
    print(f"Quote items to delete: {item_count}")

    if dry_run:
        print("Dry run — no deletes.")
        return {
            "dry_run": True,
            "quotes": len(quote_ids),
            "quote_items": item_count,
        }

    deleted_items = item_count
    for i in range(0, len(quote_ids), BATCH):
        batch = quote_ids[i : i + BATCH]
        client.table("quote_items").delete().in_("quote_id", batch).execute()

    deleted_quotes = 0
    if quote_ids:
        for i in range(0, len(quote_ids), BATCH):
            batch = quote_ids[i : i + BATCH]
            client.table("quotes").delete().in_("id", batch).execute()
        deleted_quotes = len(quote_ids)

    # Orphan session dedup rows (quotes already gone)
    try:
        remaining = (
            client.table("quotes")
            .select("session_id")
            .not_.is_("session_id", "null")
            .execute()
        )
        live_sessions = {
            str(r["session_id"]) for r in (remaining.data or []) if r.get("session_id")
        }
        sessions_res = client.table("market_moving_avg_sessions").select("id,session_id").execute()
        orphan_ids = [
            r["id"]
            for r in (sessions_res.data or [])
            if r.get("session_id") not in live_sessions
        ]
        for i in range(0, len(orphan_ids), BATCH):
            batch = orphan_ids[i : i + BATCH]
            client.table("market_moving_avg_sessions").delete().in_("id", batch).execute()
        print(f"Removed {len(orphan_ids)} orphan market_moving_avg_sessions rows")
    except Exception as e:
        print(f"⚠️ Could not trim market_moving_avg_sessions: {e}")

    print(f"Deleted {deleted_quotes} quotes and ~{deleted_items} quote_items.")
    return {
        "dry_run": False,
        "quotes_deleted": deleted_quotes,
        "quote_items_deleted": deleted_items,
    }


def main():
    parser = argparse.ArgumentParser(description="Cleanup old comparison sessions from Supabase")
    parser.add_argument("--days", type=int, default=7, help="Retention after market_rates_applied_at")
    parser.add_argument("--dry-run", action="store_true")
    args = parser.parse_args()
    cleanup(args.days, dry_run=args.dry_run)


if __name__ == "__main__":
    main()

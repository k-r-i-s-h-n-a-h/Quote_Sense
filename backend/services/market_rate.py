"""
Market rate moving averages and vendor form recommendations.

Bundle key (exact match only):
  service_type + service_category + sub_service + pricing_method

Values are raw per-unit rates — GST is the vendor's choice, not normalized here.
"""

from __future__ import annotations

import os
from typing import Any

from services.env_config import get_supabase_client

DEFAULT_SERVICE_TYPE = "ESSENTIAL"
SERVICE_TYPE_ESSENTIAL = "ESSENTIAL"
SERVICE_TYPE_MID_SEGMENT = "MID_SEGMENT"
SERVICE_TYPE_LUXURY = "LUXURY"

_SERVICE_TYPE_ALIASES: dict[str, str] = {
    "essential": SERVICE_TYPE_ESSENTIAL,
    "affordable": SERVICE_TYPE_ESSENTIAL,
    "budget": SERVICE_TYPE_ESSENTIAL,
    "mid-segment": SERVICE_TYPE_MID_SEGMENT,
    "mid segment": SERVICE_TYPE_MID_SEGMENT,
    "mid_segment": SERVICE_TYPE_MID_SEGMENT,
    "midsegment": SERVICE_TYPE_MID_SEGMENT,
    "mid level": SERVICE_TYPE_MID_SEGMENT,
    "mid_level": SERVICE_TYPE_MID_SEGMENT,
    "midlevel": SERVICE_TYPE_MID_SEGMENT,
    "mid-level": SERVICE_TYPE_MID_SEGMENT,
    "standard": SERVICE_TYPE_MID_SEGMENT,
    "luxury": SERVICE_TYPE_LUXURY,
    "premium": SERVICE_TYPE_LUXURY,
}

# Seed / base-rate rows use weight=0 until finalized quotes arrive.
MIN_WEIGHT_FOR_RECOMMEND = 0

ABOVE_MARKET_MESSAGE = (
    "Current rates exceed the recommended base rate of {amount}. "
    "Kindly review your pricing to improve closure rates."
)


def market_rate_updates_enabled() -> bool:
    """
    When false, finalized-quote MA writers must not rewrite market_moving_averages
    (keeps seed base rates frozen). Recommendations still read the table.
    Compare sessions never write MA — only isFinalizeQuote payloads do.

    Env: MARKET_RATE_UPDATES_ENABLED=false|0|no  → frozen
         unset / true / 1 / yes                 → updates allowed (default)
    """
    raw = (os.getenv("MARKET_RATE_UPDATES_ENABLED") or "true").strip().lower()
    return raw in ("1", "true", "yes", "on")


# Vendors sometimes fill Rate = 1 as a form placeholder on line items priced
# "On Actuals" / "Per Project" — the real total lives in Amount instead. A rate
# this low is never a genuine per-unit price for any TatvaOps service, so treat
# it as invalid.
MIN_VALID_RATE = 1.0

# Pricing methods where the vendor's "rate" column is not a real unit price
# (it's filled with a placeholder like 1) and Amount holds the true value.
_AMOUNT_BASED_PRICING_METHODS = {
    "on actuals",
    "per project",
    "lumpsum",
    "lump sum",
    "actuals",
}


def is_amount_based_pricing_method(pricing_method: Any) -> bool:
    return normalize_text(pricing_method, "").strip().lower() in _AMOUNT_BASED_PRICING_METHODS


def resolve_effective_rate(
    rate: float, quantity: float = 0.0, amount: float = 0.0, pricing_method: Any = ""
) -> float:
    """
    Return a trustworthy per-unit rate for moving-average purposes.

    If the vendor supplied a real rate (> MIN_VALID_RATE), use it as-is. If the
    rate looks like a placeholder (<= MIN_VALID_RATE) on an amount-based pricing
    method (e.g. "On Actuals"), fall back to Amount / Quantity so a junk "₹1"
    line item doesn't drag the market average down to ₹1.
    """
    try:
        rate = float(rate or 0)
    except (TypeError, ValueError):
        rate = 0.0
    if rate > MIN_VALID_RATE:
        return rate
    if is_amount_based_pricing_method(pricing_method):
        try:
            amount = float(amount or 0)
        except (TypeError, ValueError):
            amount = 0.0
        try:
            quantity = float(quantity or 0)
        except (TypeError, ValueError):
            quantity = 0.0
        if amount > 0:
            qty = quantity if quantity > 0 else 1.0
            return round(amount / qty, 2)
    return rate

_SESSIONS_TABLE_AVAILABLE: bool | None = None


def normalize_text(value: Any, fallback: str = "") -> str:
    if value is None:
        return fallback
    text = str(value).strip()
    if not text or text.lower() in ("nan", "none", "null"):
        return fallback
    return text


# Spreadsheet / PM label variants → canonical DB pricing_method string.
_PRICING_METHOD_ALIASES: dict[str, str] = {
    "area (sqft)": "Area (sqft)",
    "area (in sqft)": "Area (sqft)",
    "area in sqft": "Area (sqft)",
    "sqft": "Area (sqft)",
    "area (sqft)/per unit": "Area (sqft)/Per Unit",
    "area (in sqmm)": "Area (in sqmm)",
    "area(in sqmm)": "Area (in sqmm)",
    "area(in sqm)": "Area(in sqm)",
    "area (in sqm)": "Area(in sqm)",
}


def normalize_pricing_method(value: Any) -> str:
    text = normalize_text(value, "Unit")
    if not text:
        return "Unit"
    return _PRICING_METHOD_ALIASES.get(text.casefold(), text)


def normalize_service_type(value: Any) -> str:
    text = normalize_text(value, "")
    if not text:
        return DEFAULT_SERVICE_TYPE
    # Tatva PM quotation-type ObjectId (from env — never hardcode IDs here).
    by_id = _quote_type_id_map().get(text.lower())
    if by_id:
        return by_id
    canonical = _SERVICE_TYPE_ALIASES.get(text.lower().replace("_", " ").replace("-", " "))
    if canonical:
        return canonical
    collapsed = text.lower().replace("-", "_").replace(" ", "_")
    if collapsed == "mid_segment":
        return SERVICE_TYPE_MID_SEGMENT
    if text.upper() in (
        SERVICE_TYPE_ESSENTIAL,
        SERVICE_TYPE_MID_SEGMENT,
        SERVICE_TYPE_LUXURY,
    ):
        return text.upper()
    return text


def _quote_type_id_map() -> dict[str, str]:
    """Map Tatva quote-type ObjectIds from env → ESSENTIAL / MID_SEGMENT / LUXURY."""
    import os

    mapping: dict[str, str] = {}
    pairs = (
        ("TATVA_QUOTE_TYPE_ESSENTIAL_ID", SERVICE_TYPE_ESSENTIAL),
        ("TATVA_QUOTE_TYPE_MID_SEGMENT_ID", SERVICE_TYPE_MID_SEGMENT),
        ("TATVA_QUOTE_TYPE_LUXURY_ID", SERVICE_TYPE_LUXURY),
    )
    for env_key, service_type in pairs:
        raw = (os.getenv(env_key) or "").strip()
        if raw:
            mapping[raw.lower()] = service_type
    return mapping


def resolve_service_type(
    service_type: Any = None,
    quote_type_id: Any = None,
) -> str | None:
    """
    Resolve quotation type from service_type string and/or quote_type_id ObjectId.
    Returns None if neither resolves (caller should not fall back to ESSENTIAL).
    """
    for raw in (quote_type_id, service_type):
        text = normalize_text(raw, "")
        if not text:
            continue
        by_id = _quote_type_id_map().get(text.lower())
        if by_id:
            return by_id
        # Avoid DEFAULT fallback when empty aliases — only accept known types / aliases.
        lowered = text.lower().replace("_", " ").replace("-", " ")
        if lowered in _SERVICE_TYPE_ALIASES:
            return _SERVICE_TYPE_ALIASES[lowered]
        collapsed = text.lower().replace("-", "_").replace(" ", "_")
        if collapsed == "mid_segment":
            return SERVICE_TYPE_MID_SEGMENT
        upper = text.upper()
        if upper in (
            SERVICE_TYPE_ESSENTIAL,
            SERVICE_TYPE_MID_SEGMENT,
            SERVICE_TYPE_LUXURY,
        ):
            return upper
    return None


def _canonical_sub_service_names(raw: Any) -> list[str]:
    """Map free-text sub_service → PM catalog name(s); fall back to normalized raw."""
    try:
        from services.sub_service_catalog import resolve_sub_services
    except ImportError:
        resolve_sub_services = None  # type: ignore

    text = normalize_text(raw, "")
    if not text:
        return []
    if resolve_sub_services:
        resolved = resolve_sub_services(text)
        if resolved:
            return resolved
    return [text]


def bundle_key(
    service_type: str,
    service_category: str,
    sub_service: str,
    pricing_method: str,
) -> dict[str, str]:
    return {
        "service_type": normalize_service_type(service_type),
        "service_category": normalize_text(service_category, "Other"),
        "sub_service": normalize_text(sub_service, "General"),
        "pricing_method": normalize_pricing_method(pricing_method),
    }


def _sessions_table_available() -> bool:
    global _SESSIONS_TABLE_AVAILABLE
    if _SESSIONS_TABLE_AVAILABLE is not None:
        return _SESSIONS_TABLE_AVAILABLE
    try:
        from services.env_config import env_diagnostics

        if not env_diagnostics()["supabase_configured"]:
            _SESSIONS_TABLE_AVAILABLE = False
            return False
        get_supabase_client().table("market_moving_avg_sessions").select("id").limit(1).execute()
        _SESSIONS_TABLE_AVAILABLE = True
    except Exception as e:
        err = str(e)
        if "market_moving_avg_sessions" in err or "PGRST205" in err:
            _SESSIONS_TABLE_AVAILABLE = False
        else:
            _SESSIONS_TABLE_AVAILABLE = True
    return _SESSIONS_TABLE_AVAILABLE


def fetch_market_rate_row(key: dict[str, str]) -> dict | None:
    try:
        res = (
            get_supabase_client()
            .table("market_moving_averages")
            .select("*")
            .match(key)
            .limit(1)
            .execute()
        )
        return res.data[0] if res.data else None
    except Exception as e:
        print(f"⚠️ Could not fetch market rate for {key}: {e}")
        return None


def lookup_market_rate(
    service_type: str,
    service_category: str,
    sub_service: str,
    pricing_method: str,
) -> dict | None:
    """Return market rate row for an exact bundle match, or None."""
    st = normalize_service_type(service_type)
    cat = normalize_text(service_category, "Other")
    pm = normalize_pricing_method(pricing_method)

    for name in _canonical_sub_service_names(sub_service):
        key = bundle_key(st, cat, name, pm)
        # Prefer exact catalog casing stored in DB.
        key["sub_service"] = name
        row = fetch_market_rate_row(key)
        if not row:
            continue

        rate = float(row.get("rate_moving_average") or row.get("moving_average") or 0)
        weight = int(row.get("weight") or 0)
        if rate <= MIN_VALID_RATE or weight < MIN_WEIGHT_FOR_RECOMMEND:
            continue

        return {
            "service_type": key["service_type"],
            "service_category": key["service_category"],
            "sub_service": name,
            "pricing_method": key["pricing_method"],
            "market_rate": round(rate, 2),
            "weight": weight,
        }
    return None


def _above_market_message(market_rate: float) -> str:
    amount = f"₹{market_rate:,.2f}"
    return ABOVE_MARKET_MESSAGE.format(amount=amount)


def _session_already_applied(session_id: str, item_id: str) -> bool:
    if not session_id or not item_id or not _sessions_table_available():
        return False
    try:
        res = (
            get_supabase_client()
            .table("market_moving_avg_sessions")
            .select("id")
            .eq("session_id", session_id)
            .eq("item_id", item_id)
            .limit(1)
            .execute()
        )
        return bool(res.data)
    except Exception:
        return False


def _record_session(session_id: str, item_id: str, batch_avg: float, batch_weight: int):
    if not _sessions_table_available():
        return
    try:
        get_supabase_client().table("market_moving_avg_sessions").insert(
            {
                "session_id": session_id,
                "item_id": item_id,
                "batch_avg": round(batch_avg, 2),
                "batch_weight": batch_weight,
            }
        ).execute()
    except Exception as e:
        print(f"⚠️ Could not record market-rate session {session_id}: {e}")


def update_rate_moving_average(
    session_id: str,
    service_type: str,
    service_category: str,
    sub_service: str,
    pricing_method: str,
    batch_rates: list[float],
) -> tuple[float, int]:
    """Merge session batch of raw rates into stored weighted moving average."""
    key = bundle_key(service_type, service_category, sub_service, pricing_method)
    label = f"{key['sub_service']} / {key['pricing_method']}"

    # Frozen base rates: read existing seed, never write averages or sessions.
    if not market_rate_updates_enabled():
        existing = fetch_market_rate_row(key)
        if existing:
            rate = float(existing.get("rate_moving_average") or existing.get("moving_average") or 0)
            return rate, int(existing.get("weight") or 0)
        return 0.0, 0

    positive = [float(r) for r in batch_rates if r and float(r) > 0]
    batch_weight = len(positive)

    if batch_weight == 0:
        existing = fetch_market_rate_row(key)
        if existing:
            rate = float(existing.get("rate_moving_average") or existing.get("moving_average") or 0)
            return rate, int(existing.get("weight") or 0)
        return 0.0, 0

    batch_avg = sum(positive) / batch_weight
    existing = fetch_market_rate_row(key)

    if existing and _session_already_applied(session_id, existing["id"]):
        rate = float(existing.get("rate_moving_average") or existing.get("moving_average") or 0)
        return rate, int(existing.get("weight") or 0)

    if existing is None:
        moving_avg = batch_avg
        weight = batch_weight
        print(
            f"  📊 Rate avg bootstrap: {label} → "
            f"₹{moving_avg:,.2f} (weight {weight})"
        )
    else:
        prev_avg = float(existing.get("rate_moving_average") or existing.get("moving_average") or 0)
        prev_weight = int(existing.get("weight") or 0)
        moving_avg = ((prev_avg * prev_weight) + (batch_avg * batch_weight)) / (prev_weight + batch_weight)
        weight = prev_weight + batch_weight
        print(
            f"  📊 Rate avg updated: {label} → "
            f"₹{moving_avg:,.2f} (weight {prev_weight} + {batch_weight} = {weight})"
        )

    payload = {
        **key,
        "rate_moving_average": round(moving_avg, 2),
        "moving_average": round(moving_avg, 2),
        "weight": weight,
        "last_session_id": session_id,
        "item_key": key["sub_service"],
    }

    try:
        if existing and existing.get("id"):
            get_supabase_client().table("market_moving_averages").update(payload).eq(
                "id", existing["id"]
            ).execute()
            item_id = existing["id"]
        else:
            res = get_supabase_client().table("market_moving_averages").insert(payload).execute()
            item_id = res.data[0]["id"] if res.data else None

        if item_id:
            _record_session(session_id, item_id, batch_avg, batch_weight)
    except Exception as e:
        print(f"⚠️ Could not persist market rate for {key}: {e}")

    return round(moving_avg, 2), weight


def _verdict(entered_rate: float, market_rate: float) -> str:
    """Compare entered rate to recommended base only (no ±% band)."""
    entered = round(float(entered_rate), 2)
    base = round(float(market_rate), 2)
    if entered < base:
        return "low"
    if entered > base:
        return "high"
    return "fair"


def _verdict_label(verdict: str) -> str:
    return {
        "low": "At or Below Base",
        "fair": "At Base Rate",
        "high": "Above Base Rate",
    }.get(verdict, "Unknown")


def _verdict_suggestion(verdict: str, market_rate: float | None = None) -> str:
    """Short actionable guidance for PM UI chips / banners."""
    if verdict == "high":
        amount = (
            f"₹{market_rate:,.2f}"
            if market_rate is not None
            else "the recommended base rate"
        )
        return (
            f"Current rates exceed the recommended base rate of {amount}. "
            f"Kindly review your pricing to improve closure rates."
        )
    if verdict == "low":
        return "Your rate is at or below the recommended base — no suggestion."
    return "Your rate matches the recommended base — no suggestion."


def _base_rate_message(market_rate: float, pricing_method: str) -> str:
    unit = pricing_method or "unit"
    return (
        f"Recommended base rate: ₹{market_rate:,.2f}/{unit}. "
        f"Suggestion appears only when the entered rate is above this base."
    )


def _verdict_message(verdict: str, entered_rate: float, market_rate: float, pricing_method: str, weight: int) -> str:
    unit = pricing_method or "unit"
    if verdict == "high":
        return (
            f"Current rates exceed the recommended base rate of ₹{market_rate:,.2f}/{unit}. "
            f"Kindly review your pricing to improve closure rates."
        )
    if verdict == "low":
        return (
            f"Your rate ₹{entered_rate:,.2f}/{unit} is below the recommended base "
            f"(₹{market_rate:,.2f}/{unit}) — no suggestion."
        )
    return (
        f"Your rate ₹{entered_rate:,.2f}/{unit} matches the recommended base "
        f"(₹{market_rate:,.2f}/{unit}) — no suggestion."
    )


def _market_hint_message(market_rate: float, pricing_method: str, weight: int) -> str:
    pm = pricing_method or "unit"
    return f"Recommended base rate: ₹{market_rate:,.2f}/{pm}"


def _label_ids(sub_service: str, pricing_method: str) -> dict:
    """Attach Tatva ObjectIds when the catalog (live or static) knows the labels."""
    from services.tatva_catalog import resolve_pricing_method_id, resolve_sub_service_id

    return {
        "sub_service_id": resolve_sub_service_id(sub_service),
        "sub_service_label": sub_service,
        "pricing_id": resolve_pricing_method_id(pricing_method),
        "pricing_method_label": pricing_method,
    }


def _slim_bulk_item(
    sub_service: str,
    pricing_method: str,
    market_rate: float,
    weight: int,
) -> dict:
    """Flat item row for PM bulk cache — labels + ObjectIds when known."""
    return {
        **_label_ids(sub_service, pricing_method),
        "market_rate": market_rate,
        "weight": weight,
        "suggestion": _base_rate_message(market_rate, pricing_method),
    }


def _slim_selected_recommendation(
    sub_service: str,
    pricing_method: str,
    full: dict,
) -> dict:
    """Verdict payload for the active work-item row only."""
    labels = _label_ids(
        full.get("sub_service_label") or full.get("sub_service") or sub_service,
        full.get("pricing_method_label") or full.get("pricing_method") or pricing_method,
    )
    if not full.get("recommend"):
        return {"recommend": False, **labels}

    slim: dict = {
        "recommend": True,
        **labels,
        "market_rate": full["market_rate"],
        "weight": full.get("weight", 0),
        "verdict": full.get("verdict", "high"),
        "message": full.get("message", ""),
    }
    if full.get("entered_rate") is not None:
        slim["entered_rate"] = full["entered_rate"]
    return slim


def list_market_rates_by_category(
    service_category: str,
    service_type: str = DEFAULT_SERVICE_TYPE,
    *,
    sub_service: str | None = None,
    pricing_method: str | None = None,
    entered_rate: float | None = None,
    service_id: str | None = None,
) -> dict:
    """Return all recommendable bundles for one service category (PM bulk-load)."""
    # Refresh ObjectId maps from Tatva admin catalogs (cached) so new items
    # tomorrow get ids without a redeploy. Falls back to static JSON if no token.
    try:
        from services.tatva_catalog import ensure_live_catalog

        ensure_live_catalog(
            service_id=service_id,
            service_category=service_category,
            force=False,
            persist=False,
        )
    except Exception as e:
        print(f"⚠️ Live Tatva catalog refresh skipped: {e}")

    cat = normalize_text(service_category, "")
    if not cat:
        return {
            "service_category": "",
            "service_type": normalize_service_type(service_type),
            "count": 0,
            "items": [],
            "message": "service_category is required.",
        }

    st = normalize_service_type(service_type)
    try:
        res = (
            get_supabase_client()
            .table("market_moving_averages")
            .select(
                "service_type,service_category,sub_service,pricing_method,"
                "rate_moving_average,moving_average,weight"
            )
            .eq("service_category", cat)
            .eq("service_type", st)
            .execute()
        )
        rows = res.data or []
    except Exception as e:
        print(f"⚠️ Could not list market rates for {cat}: {e}")
        return {
            "service_category": cat,
            "service_type": st,
            "count": 0,
            "items": [],
            "message": "Could not load market rates for this category.",
        }

    items: list[dict] = []
    for row in rows:
        rate = float(row.get("rate_moving_average") or row.get("moving_average") or 0)
        weight = int(row.get("weight") or 0)
        if rate <= MIN_VALID_RATE or weight < MIN_WEIGHT_FOR_RECOMMEND:
            continue
        sub = normalize_text(row.get("sub_service"), "General")
        pm = normalize_pricing_method(row.get("pricing_method"))
        rounded_rate = round(rate, 2)
        items.append(_slim_bulk_item(sub, pm, rounded_rate, weight))

    items.sort(
        key=lambda x: (
            (x.get("sub_service_label") or "").lower(),
            (x.get("pricing_method_label") or "").lower(),
        )
    )
    result = {
        "service_category": cat,
        "service_type": st,
        "count": len(items),
        "items": items,
    }

    if sub_service and pricing_method:
        selected = recommend_rate(
            st,
            cat,
            sub_service,
            pricing_method,
            entered_rate if entered_rate and entered_rate > 0 else None,
        )
        result["selected_recommendation"] = _slim_selected_recommendation(
            normalize_text(sub_service),
            normalize_pricing_method(pricing_method),
            selected,
        )

    return result


def recommend_rate(
    service_type: str,
    service_category: str,
    sub_service: str,
    pricing_method: str,
    entered_rate: float | None = None,
) -> dict:
    """
    Vendor form guidance against spreadsheet recommended base rates.

    - No entered_rate → no UI banner (recommend=false).
    - entered_rate <= base → silent (recommend=false).
    - entered_rate > base (even ₹1 above) → recommend=true.
    No ±% interval / band — compare to the single base only.
    """
    try:
        from services.tatva_catalog import ensure_live_catalog

        ensure_live_catalog(service_category=service_category, force=False, persist=False)
    except Exception as e:
        print(f"⚠️ Live Tatva catalog refresh skipped (suggest): {e}")

    lookup = lookup_market_rate(service_type, service_category, sub_service, pricing_method)
    if not lookup:
        return {
            "recommend": False,
            "message": "No market data for this item and pricing method yet.",
        }

    base = round(float(lookup["market_rate"]), 2)
    labels = _label_ids(lookup["sub_service"], lookup["pricing_method"])
    common = {
        "service_type": lookup["service_type"],
        "service_category": lookup["service_category"],
        **labels,
        "market_rate": base,
        "weight": lookup["weight"],
    }

    if entered_rate is None or float(entered_rate) <= 0:
        # Preload / pricing-method selected — do not notify the vendor yet.
        return {"recommend": False, **common}

    rate = round(float(entered_rate), 2)
    verdict = _verdict(rate, base)
    if verdict != "high":
        # At or below recommended base — no suggestion.
        return {"recommend": False, **common, "entered_rate": rate, "verdict": verdict}

    return {
        "recommend": True,
        **common,
        "entered_rate": rate,
        "verdict": "high",
        "message": _above_market_message(base),
    }


def update_rates_from_dataframe(df, session_id: str, fast: bool = False) -> dict[tuple, tuple[float, int]]:
    """
    Collect one rate per vendor per bundle from a compare dataframe.
    Returns map of bundle tuple -> (rate_avg, weight) for display lookups.
    """
    if df is None or len(df) == 0:
        return {}

    if "service_type" not in df.columns:
        df = df.copy()
        df["service_type"] = DEFAULT_SERVICE_TYPE

    results: dict[tuple, tuple[float, int]] = {}
    grouped: dict[tuple, dict[str, float]] = {}

    for _, row in df.iterrows():
        pm = normalize_pricing_method(row.get("pricing_method"))
        rate = resolve_effective_rate(
            row.get("rate"), row.get("quantity"), row.get("amount"), pm
        )
        if rate <= MIN_VALID_RATE:
            continue
        st = normalize_service_type(row.get("service_type"))
        cat = normalize_text(row.get("service_category"), "Other")
        sub = normalize_text(row.get("sub_service"), "General")
        vendor = normalize_text(row.get("vendor_name"))
        if not vendor:
            continue
        bundle = (st, cat, sub, pm)
        grouped.setdefault(bundle, {})[vendor] = rate

    for bundle, vendor_rates in grouped.items():
        rates = list(vendor_rates.values())
        st, cat, sub, pm = bundle
        if fast:
            avg = round(sum(rates) / len(rates), 2) if rates else 0.0
            weight = len(rates)
        else:
            avg, weight = update_rate_moving_average(session_id, st, cat, sub, pm, rates)
        results[bundle] = (avg, weight)

    return results


def quote_number_is_rate_source_already(quote_number: str) -> bool:
    """
    Return True if a quote with this number has already been recorded in Supabase.
    Used on re-ingest so staging cleanup can skip double bookkeeping for the same number.
    """
    if not quote_number or not quote_number.strip():
        return False
    try:
        res = (
            get_supabase_client()
            .table("quotes")
            .select("id")
            .eq("quote_number", quote_number.strip())
            .limit(1)
            .execute()
        )
        return bool(res.data)
    except Exception as e:
        print(f"⚠️ Could not check duplicate quote_number '{quote_number}': {e}")
        return False


def _unwrap_quote_dict(quote_entry: Any) -> dict:
    if not isinstance(quote_entry, dict):
        return {}
    inner = quote_entry.get("data") or quote_entry.get("quote")
    if isinstance(inner, dict) and (
        "quoteNumber" in inner
        or "vendorDetail" in inner
        or "workSummary" in inner
        or "isFinalizeQuote" in inner
        or "isFinalizedQuote" in inner
        or "is_finalized" in inner
        or "isFinalized" in inner
    ):
        return inner
    return quote_entry


def is_finalize_quote_flag(quote_entry: Any) -> bool:
    """True when Tatva/platform marks this payload as the user-selected final quote."""
    raw = _unwrap_quote_dict(quote_entry)
    # camelCase (Tatva UI) + snake_case (some APIs) + short aliases
    for key in (
        "isFinalizeQuote",
        "isFinalizedQuote",
        "isFinalized",
        "finalizeQuote",
        "is_finalize_quote",
        "is_finalized_quote",
        "is_finalized",
        "finalized",
    ):
        v = raw.get(key)
        if v is True or v == 1 or v == "1" or str(v).strip().lower() == "true":
            return True
    return False


def finalized_quote_session_id(quote_entry: Any) -> str:
    """Stable session key so the same finalized quote is never applied twice."""
    raw = _unwrap_quote_dict(quote_entry)
    quote_number = str(raw.get("quoteNumber") or "").lstrip("#").strip()
    quote_id = str(raw.get("_id") or raw.get("id") or "").strip()
    key = quote_number or quote_id or "unknown"
    return f"finalize:{key}"


def finalize_quote_already_applied_to_ma(quote_entry: Any) -> bool:
    """Check market_moving_avg_sessions for a prior apply of this finalized quote."""
    sid = finalized_quote_session_id(quote_entry)
    if not _sessions_table_available():
        return False
    try:
        res = (
            get_supabase_client()
            .table("market_moving_avg_sessions")
            .select("id")
            .eq("session_id", sid)
            .limit(1)
            .execute()
        )
        return bool(res.data)
    except Exception:
        return False


def apply_finalized_quotes_to_market_rates(
    quotes_list: list | None,
    *,
    source: str = "finalize-quote",
) -> dict:
    """
    Merge rates into market_moving_averages for quotes the user selected as final
    (isFinalizeQuote / isFinalizedQuote / finalizeQuote).

    Compare sessions only stage/compare selected quotes — they must not call this
    for every row; only payloads that carry the finalize flag are eligible.
    """
    if not market_rate_updates_enabled():
        print(
            f"ℹ️ MARKET_RATE_UPDATES_ENABLED=false — skipping finalized-quote MA "
            f"apply (source={source})."
        )
        return {
            "ok": True,
            "skipped": True,
            "reason": "MARKET_RATE_UPDATES_ENABLED=false",
            "quotes_considered": 0,
            "quotes_applied": 0,
            "bundles_updated": 0,
        }

    entries = list(quotes_list or [])
    finalized = [q for q in entries if is_finalize_quote_flag(q)]
    if not finalized:
        return {
            "ok": True,
            "skipped": True,
            "reason": "no_finalized_quotes",
            "quotes_considered": len(entries),
            "quotes_applied": 0,
            "bundles_updated": 0,
        }

    from services.comparator import mongodb_quotes_to_dataframe

    applied: list[dict] = []
    skipped_already: list[str] = []
    total_bundles = 0
    errors: list[str] = []

    for quote_entry in finalized:
        raw = _unwrap_quote_dict(quote_entry)
        label = str(raw.get("quoteNumber") or raw.get("_id") or "quote").strip()
        sid = finalized_quote_session_id(quote_entry)

        if finalize_quote_already_applied_to_ma(quote_entry):
            skipped_already.append(label)
            print(f"  ⏭️ Finalized quote #{label} already in MA — skip re-apply")
            continue

        try:
            df = mongodb_quotes_to_dataframe([quote_entry])
            bundles = update_rates_from_dataframe(df, sid, fast=False)
            total_bundles += len(bundles)
            applied.append(
                {
                    "quote_number": str(raw.get("quoteNumber") or "").lstrip("#").strip(),
                    "quote_id": str(raw.get("_id") or raw.get("id") or "").strip(),
                    "session_id": sid,
                    "bundles_updated": len(bundles),
                }
            )
            print(
                f"  ✅ Finalized quote #{label} → market MA "
                f"({len(bundles)} bundles, session={sid}, source={source})"
            )
        except Exception as e:
            msg = f"{label}: {e}"
            errors.append(msg)
            print(f"⚠️ Could not apply finalized quote #{label} to MA: {e}")

    return {
        "ok": len(errors) == 0,
        "source": source,
        "quotes_considered": len(entries),
        "finalized_found": len(finalized),
        "quotes_applied": len(applied),
        "skipped_already_applied": skipped_already,
        "bundles_updated": total_bundles,
        "applied": applied,
        "errors": errors,
    }


def finalize_session_market_rates(session_id: str, df=None) -> dict:
    """
    After a compare session finishes: mark staging quote rows for cleanup only.

    Does NOT update market_moving_averages. Compare uses only the quotes the user
    selected for that session (e.g. 3 of N); those rates stay compare/display-only.

    Market averages are updated solely via apply_finalized_quotes_to_market_rates()
    when a quote carries isFinalizeQuote.
    """
    from datetime import datetime, timezone

    sid = (session_id or "").strip()
    if not sid:
        return {"ok": False, "error": "session_id is required"}

    # Intentionally ignore df and never call update_rates_from_dataframe here.
    _ = df
    applied_at = datetime.now(timezone.utc).isoformat()

    try:
        get_supabase_client().table("quotes").update(
            {"market_rates_applied_at": applied_at}
        ).eq("session_id", sid).is_("market_rates_applied_at", "null").execute()
    except Exception as e:
        print(f"⚠️ Could not set market_rates_applied_at for compare session {sid}: {e}")
        return {
            "ok": False,
            "session_id": sid,
            "bundles_updated": 0,
            "error": str(e),
            "market_rates_written": False,
        }

    print(
        f"  ✅ Compare session {sid} staging marked for cleanup "
        f"(no MA write; only finalized quotes update market averages), "
        f"applied_at={applied_at}"
    )
    return {
        "ok": True,
        "session_id": sid,
        "bundles_updated": 0,
        "market_rates_written": False,
        "applied_at": applied_at,
        "reason": "compare_session_cleanup_only",
    }

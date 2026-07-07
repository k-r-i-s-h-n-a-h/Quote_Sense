"""
Market rate moving averages and vendor form recommendations.

Bundle key (exact match only):
  service_type + service_category + sub_service + pricing_method

Values are raw per-unit rates — GST is the vendor's choice, not normalized here.
"""

from __future__ import annotations

from typing import Any

from services.env_config import get_supabase_client

DEFAULT_SERVICE_TYPE = "ESSENTIAL"
SERVICE_TYPE_ESSENTIAL = "ESSENTIAL"
SERVICE_TYPE_MID_SEGMENT = "MID_SEGMENT"
SERVICE_TYPE_LUXURY = "LUXURY"

_SERVICE_TYPE_ALIASES: dict[str, str] = {
    "essential": SERVICE_TYPE_ESSENTIAL,
    "affordable": SERVICE_TYPE_ESSENTIAL,
    "mid-segment": SERVICE_TYPE_MID_SEGMENT,
    "mid segment": SERVICE_TYPE_MID_SEGMENT,
    "mid_segment": SERVICE_TYPE_MID_SEGMENT,
    "midsegment": SERVICE_TYPE_MID_SEGMENT,
    "luxury": SERVICE_TYPE_LUXURY,
}

MIN_WEIGHT_FOR_RECOMMEND = 1
LOW_THRESHOLD = 0.85
HIGH_THRESHOLD = 1.15

_SESSIONS_TABLE_AVAILABLE: bool | None = None


def normalize_text(value: Any, fallback: str = "") -> str:
    if value is None:
        return fallback
    text = str(value).strip()
    if not text or text.lower() in ("nan", "none", "null"):
        return fallback
    return text


def normalize_pricing_method(value: Any) -> str:
    return normalize_text(value, "Unit")


def normalize_service_type(value: Any) -> str:
    text = normalize_text(value, "")
    if not text:
        return DEFAULT_SERVICE_TYPE
    canonical = _SERVICE_TYPE_ALIASES.get(text.lower().replace("_", " ").replace("-", " "))
    if canonical:
        return canonical
    if text.lower().replace("-", "_").replace(" ", "_") == "MID_SEGMENT":
        return SERVICE_TYPE_MID_SEGMENT
    if text.upper() in (
        SERVICE_TYPE_ESSENTIAL,
        SERVICE_TYPE_MID_SEGMENT,
        SERVICE_TYPE_LUXURY,
    ):
        return text.upper()
    return text


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
    key = bundle_key(service_type, service_category, sub_service, pricing_method)
    row = fetch_market_rate_row(key)
    if not row:
        return None

    rate = float(row.get("rate_moving_average") or row.get("moving_average") or 0)
    weight = int(row.get("weight") or 0)
    if rate <= 0 or weight < MIN_WEIGHT_FOR_RECOMMEND:
        return None

    return {
        "service_type": key["service_type"],
        "service_category": key["service_category"],
        "sub_service": key["sub_service"],
        "pricing_method": key["pricing_method"],
        "market_rate": round(rate, 2),
        "weight": weight,
    }


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
    if entered_rate < market_rate * LOW_THRESHOLD:
        return "low"
    if entered_rate > market_rate * HIGH_THRESHOLD:
        return "high"
    return "fair"


def _verdict_label(verdict: str) -> str:
    return {
        "low": "Below Market",
        "fair": "Fair Price",
        "high": "Above Market",
    }.get(verdict, "Unknown")


def _verdict_suggestion(verdict: str) -> str:
    """Short actionable guidance for PM UI chips / banners."""
    if verdict == "low":
        return "Your rate is below market — consider increasing it to avoid underpricing."
    if verdict == "high":
        return "Your rate is above market — consider lowering it to stay competitive."
    return "Your rate is within market range — looks fair and competitive."


def _fair_range_message(band_low: float, band_high: float, pricing_method: str) -> str:
    unit = pricing_method or "unit"
    return (
        f"Fair market range: ₹{band_low:,.2f} – ₹{band_high:,.2f}/{unit}. "
        f"Enter your rate to see if it's low, fair, or high."
    )


def _verdict_message(verdict: str, entered_rate: float, market_rate: float, pricing_method: str, weight: int) -> str:
    unit = pricing_method or "unit"
    if verdict == "low":
        return (
            f"Your rate ₹{entered_rate:,.2f}/{unit} is below market "
            f"(~₹{market_rate:,.2f}, {weight} quotes). You may be underpricing."
        )
    if verdict == "high":
        return (
            f"Your rate ₹{entered_rate:,.2f}/{unit} is above market "
            f"(~₹{market_rate:,.2f}, {weight} quotes). Consider adjusting to stay competitive."
        )
    return (
        f"Your rate ₹{entered_rate:,.2f}/{unit} is within market range "
        f"(~₹{market_rate:,.2f}, {weight} quotes)."
    )


def _market_hint_message(market_rate: float, pricing_method: str, weight: int) -> str:
    pm = pricing_method or "unit"
    return (
        f"Market rate: ~₹{market_rate:,.2f}/{pm} "
        f"({weight} quote{'s' if weight != 1 else ''})"
    )


def _slim_bulk_item(
    sub_service: str,
    pricing_method: str,
    market_rate: float,
    weight: int,
    band_low: float,
    band_high: float,
) -> dict:
    """Flat item row for PM bulk cache — no nested objects or repeated category keys."""
    return {
        "sub_service": sub_service,
        "pricing_method": pricing_method,
        "market_rate": market_rate,
        "weight": weight,
        "band_low": band_low,
        "band_high": band_high,
        "suggestion": _fair_range_message(band_low, band_high, pricing_method),
    }


def _slim_selected_recommendation(
    sub_service: str,
    pricing_method: str,
    full: dict,
) -> dict:
    """Verdict payload for the active work-item row only."""
    if not full.get("recommend"):
        return {
            "sub_service": sub_service,
            "pricing_method": pricing_method,
            "suggestion": full.get("message", "No market data for this item and pricing method yet."),
        }

    slim: dict = {
        "sub_service": sub_service,
        "pricing_method": pricing_method,
        "market_rate": full["market_rate"],
        "weight": full["weight"],
        "band_low": full["band_low"],
        "band_high": full["band_high"],
        "suggestion": full["suggestion"],
    }
    if full.get("entered_rate"):
        slim["entered_rate"] = full["entered_rate"]
        slim["verdict"] = full["verdict"]
        slim["verdict_label"] = full["verdict_label"]
    return slim


def list_market_rates_by_category(
    service_category: str,
    service_type: str = DEFAULT_SERVICE_TYPE,
    *,
    sub_service: str | None = None,
    pricing_method: str | None = None,
    entered_rate: float | None = None,
) -> dict:
    """Return all recommendable bundles for one service category (PM bulk-load)."""
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
        if rate <= 0 or weight < MIN_WEIGHT_FOR_RECOMMEND:
            continue
        sub = normalize_text(row.get("sub_service"), "General")
        pm = normalize_pricing_method(row.get("pricing_method"))
        rounded_rate = round(rate, 2)
        band_low = round(rate * LOW_THRESHOLD, 2)
        band_high = round(rate * HIGH_THRESHOLD, 2)
        items.append(_slim_bulk_item(sub, pm, rounded_rate, weight, band_low, band_high))

    items.sort(key=lambda x: (x["sub_service"].lower(), x["pricing_method"].lower()))
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
    """Lookup-only when entered_rate is None; include verdict when rate is provided."""
    lookup = lookup_market_rate(service_type, service_category, sub_service, pricing_method)
    if not lookup:
        return {
            "recommend": False,
            "message": "No market data for this item and pricing method yet.",
        }

    result = {
        "recommend": True,
        **lookup,
        "band_low": round(lookup["market_rate"] * LOW_THRESHOLD, 2),
        "band_high": round(lookup["market_rate"] * HIGH_THRESHOLD, 2),
        "market_hint": _market_hint_message(
            lookup["market_rate"], lookup["pricing_method"], lookup["weight"]
        ),
    }

    if entered_rate is not None and float(entered_rate) > 0:
        rate = float(entered_rate)
        verdict = _verdict(rate, lookup["market_rate"])
        result["entered_rate"] = rate
        result["verdict"] = verdict
        result["verdict_label"] = _verdict_label(verdict)
        result["suggestion"] = _verdict_suggestion(verdict)
        result["message"] = _verdict_message(
            verdict, rate, lookup["market_rate"], lookup["pricing_method"], lookup["weight"]
        )
    else:
        result["suggestion"] = _fair_range_message(
            result["band_low"], result["band_high"], lookup["pricing_method"]
        )
        result["message"] = result["market_hint"]

    return result


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
        rate = float(row.get("rate") or 0)
        if rate <= 0:
            continue
        st = normalize_service_type(row.get("service_type"))
        cat = normalize_text(row.get("service_category"), "Other")
        sub = normalize_text(row.get("sub_service"), "General")
        pm = normalize_pricing_method(row.get("pricing_method"))
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

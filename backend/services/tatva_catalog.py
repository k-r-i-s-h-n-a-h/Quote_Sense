"""
Tatva PM ObjectId catalogs for market-rate API responses.

Maps human labels ↔ Mongo ObjectIds so PM can filter by id (preferred)
or label (fallback).

Sources (in order):
  1. Live Tatva admin catalogs (cached) — preferred for new IDs tomorrow
  2. Static JSON seed files
  3. Learned IDs from quote workItems / explicit sync-catalog maps

Live endpoints (auth via TATVA_API_KEY → x-api-key header):
  GET {TATVA_API_BASE}/admin/api/admin/quote-subservices?serviceId=…
  GET {TATVA_API_BASE}/admin/api/admin/pricing-methods
"""

from __future__ import annotations

import json
import os
import re
import ssl
import time
import urllib.error
import urllib.parse
import urllib.request
from pathlib import Path
from typing import Any

try:
    import certifi
except ImportError:
    certifi = None

_DATA_DIR = Path(__file__).resolve().parent.parent / "data"
_SUB_FILE = _DATA_DIR / "tatva_sub_service_ids.json"
_PM_FILE = _DATA_DIR / "tatva_pricing_method_ids.json"
_SERVICE_FILE = _DATA_DIR / "tatva_service_ids.json"

_OID_RE = re.compile(r"^[a-fA-F0-9]{24}$")

# Label variants that share one Tatva pricing-method ObjectId once any alias is known.
# Keys/values are matched casefold against tatva_pricing_method_ids.json labels.
_PM_LABEL_ALIASES: dict[str, tuple[str, ...]] = {
    # Legacy → Area – Direct Entry (sq ft)
    "area (sqft)": ("Area – Direct Entry (sq ft)", "Area (sqft)", "Area (in sqft)"),
    "area (in sqft)": ("Area – Direct Entry (sq ft)", "Area (sqft)", "Area (in sqft)"),
    "area in sqft": ("Area – Direct Entry (sq ft)", "Area (sqft)", "Area (in sqft)"),
    "area (sqft)/per unit": ("Area – Direct Entry (sq ft)", "Area (sqft)/Per Unit"),
    "square feet": ("Square Feet", "Area – Direct Entry (sq ft)"),
    # Legacy → Area – Direct Entry (sq m)
    "area(in sqm)": ("Area – Direct Entry (sq m)", "Area(in sqm)", "Area (in sqm)"),
    "area (in sqm)": ("Area – Direct Entry (sq m)", "Area(in sqm)", "Area (in sqm)"),
    "area in sqm": ("Area – Direct Entry (sq m)", "Area(in sqm)"),
    "area (in sqmm)": ("Area – Direct Entry (sq m)", "Area (in sqmm)"),
    # Common short names
    "per unit": ("Per Unit / Each", "Per Unit"),
    "lump sum": ("Fixed Amount / Lump Sum", "Lump Sum"),
    "fixed amount": ("Fixed Amount / Lump Sum",),
    "running feet": ("Running Length (rft)", "Running Feet"),
    "running length": ("Running Length (rft)",),
    "rft": ("Running Length (rft)",),
    "per visit / service call": ("Per Visit / Service Call", "Per Visit"),
    "weight – metric (mt)": ("Weight – Metric (MT)", "Weight – Metric Tonne (MT)"),
    "weight - metric (mt)": ("Weight – Metric (MT)", "Weight – Metric Tonne (MT)"),
    "dimension(l*b in m)": ("Dimension(L*B in m)", "Area – Length × Breadth (m → sq m)"),
    "dimension(l*b in sq)": ("Dimension(L*B in m)", "Dimension(L*B in sq)"),
    "cubic feet": ("Cubic Feet", "Volume – Direct Entry (cu ft)"),
}

# Old service category display names → current catalog names (same ObjectId).
_SERVICE_CATEGORY_ALIASES: dict[str, tuple[str, ...]] = {
    "interiors": ("Residential Interiors", "Interiors"),
    "interior design": ("Residential Interiors",),
    "electrical services": ("Home Renovation", "Electrical Services"),
    "electrical": ("Home Renovation",),
    "painting": ("Property Management & Rental Operations", "Painting"),
    "plumbing services": ("Facility Management and Security", "Plumbing Services"),
    "plumbing": ("Facility Management and Security",),
    "solar services": ("Solar, Energy & Automation Solutions", "Solar Services"),
    "solar": ("Solar, Energy & Automation Solutions",),
    "property development": ("Property Advisory, Sales & Leasing", "Property Development"),
    "home automation": ("Home Maintenance & Appliance Care", "Home Automation"),
    "event management": ("Event Management",),
}

# Seed label ↔ Tatva admin catalog name (same ObjectId).
_SUB_LABEL_ALIASES: dict[str, tuple[str, ...]] = {
    "wardrobe": ("Wardrobe", "Wardrobes"),
    "wardrobes": ("Wardrobe", "Wardrobes"),
    "tv unit": ("TV Unit", "TV Units"),
    "tv units": ("TV Unit", "TV Units"),
    "crockery unit": ("Crockery Unit", "Crockery Units"),
    "crockery units": ("Crockery Unit", "Crockery Units"),
    "vanity unit": ("Vanity Unit", "Vanity Units"),
    "vanity units": ("Vanity Unit", "Vanity Units"),
    "middle unit": ("Middle unit", "Middle Unit"),
    "loft": ("Loft", "Loft & Door Type"),
    "tandem channel": ("Tandem channels", "Tandem Channels"),
    "tandem channels": ("Tandem channels", "Tandem Channels"),
    "bottle pullout": ("Bottle Pullouts", "Bottle Pullout"),
    "bottle pullouts": ("Bottle Pullouts", "Bottle Pullout"),
}

_sub_by_label: dict[str, str] | None = None
_pm_by_label: dict[str, str] | None = None
_sub_by_id: dict[str, str] | None = None
_pm_by_id: dict[str, str] | None = None
_service_ids: set[str] | None = None

# Live-fetch cache keys → last successful refresh time.
_LIVE_AT: dict[str, float] = {}
_DEFAULT_LIVE_TTL_SEC = 3600


def _load_label_map(path: Path) -> dict[str, str]:
    try:
        raw = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        return {}
    out: dict[str, str] = {}
    if not isinstance(raw, dict):
        return out
    for label, oid in raw.items():
        key = str(label or "").strip().casefold()
        val = str(oid or "").strip()
        if key and val and _OID_RE.match(val):
            out[key] = val
    return out


def _invert(label_map: dict[str, str], prefer: dict[str, str] | None = None) -> dict[str, str]:
    """ObjectId → display label. `prefer` wins when multiple labels share an id."""
    out: dict[str, str] = {}
    preferred = {k.casefold(): v for k, v in (prefer or {}).items()}
    for label_cf, oid in label_map.items():
        oid_l = oid.lower()
        if oid_l in preferred:
            out[oid_l] = preferred[oid_l]
        elif oid_l not in out:
            out[oid_l] = label_cf
    return out


def _sub_map() -> dict[str, str]:
    global _sub_by_label, _sub_by_id
    if _sub_by_label is None:
        _sub_by_label = _load_label_map(_SUB_FILE)
        _sub_by_id = {oid.lower(): label for label, oid in _sub_by_label.items()}
        # Rebuild id→canonical display from original file casing when possible.
        try:
            raw = json.loads(_SUB_FILE.read_text(encoding="utf-8"))
            if isinstance(raw, dict):
                _sub_by_id = {
                    str(oid).strip().lower(): str(label).strip()
                    for label, oid in raw.items()
                    if str(label).strip() and str(oid).strip()
                }
        except (OSError, json.JSONDecodeError):
            pass
    return _sub_by_label


def _pm_map() -> dict[str, str]:
    global _pm_by_label, _pm_by_id
    if _pm_by_label is None:
        _pm_by_label = _load_label_map(_PM_FILE)
        try:
            raw = json.loads(_PM_FILE.read_text(encoding="utf-8"))
            _pm_by_id = {
                str(oid).strip().lower(): str(label).strip()
                for label, oid in (raw.items() if isinstance(raw, dict) else [])
                if str(label).strip() and str(oid).strip()
            }
        except (OSError, json.JSONDecodeError):
            _pm_by_id = {oid.lower(): label for label, oid in _pm_by_label.items()}
    return _pm_by_label


def _ensure_maps_loaded() -> None:
    _sub_map()
    _pm_map()


def known_service_ids() -> set[str]:
    """Lowercased Tatva main-service ObjectIds from static fallback map."""
    global _service_ids
    if _service_ids is None:
        ids: set[str] = set()
        try:
            raw = json.loads(_SERVICE_FILE.read_text(encoding="utf-8"))
            if isinstance(raw, dict):
                ids = {str(k).strip().lower() for k in raw.keys() if str(k).strip()}
        except (OSError, json.JSONDecodeError):
            pass
        _service_ids = ids
    return _service_ids


def _quote_type_ids_from_env() -> set[str]:
    ids: set[str] = set()
    for env_key in (
        "TATVA_QUOTE_TYPE_ESSENTIAL_ID",
        "TATVA_QUOTE_TYPE_MID_SEGMENT_ID",
        "TATVA_QUOTE_TYPE_LUXURY_ID",
    ):
        raw = (os.getenv(env_key) or "").strip().lower()
        if raw:
            ids.add(raw)
    return ids


def is_known_service_id(value: str | None) -> bool:
    text = (value or "").strip().lower()
    return bool(text) and text in known_service_ids()


def is_known_quote_type_id(value: str | None) -> bool:
    text = (value or "").strip().lower()
    return bool(text) and text in _quote_type_ids_from_env()


def is_object_id(value: str | None) -> bool:
    return bool(value and _OID_RE.match(str(value).strip()))


def resolve_sub_service_id(label: str | None) -> str | None:
    _ensure_maps_loaded()
    key = (label or "").strip().casefold()
    if not key or _sub_by_label is None:
        return None
    if key in _sub_by_label:
        return _sub_by_label[key]
    for alias in _SUB_LABEL_ALIASES.get(key, ()):
        oid = _sub_by_label.get(alias.casefold())
        if oid:
            return oid
    return None


def resolve_pricing_method_id(label: str | None) -> str | None:
    _ensure_maps_loaded()
    key = (label or "").strip().casefold()
    if not key or _pm_by_label is None:
        return None
    if key in _pm_by_label:
        return _pm_by_label[key]
    # If any area-sqft alias already learned an ObjectId, share it across aliases.
    for alias in _PM_LABEL_ALIASES.get(key, ()):
        oid = _pm_by_label.get(alias.casefold())
        if oid:
            return oid
    return None


def resolve_sub_service_label(sub_service_id: str | None) -> str | None:
    _ensure_maps_loaded()
    oid = (sub_service_id or "").strip().lower()
    if not oid or _sub_by_id is None:
        return None
    return _sub_by_id.get(oid)


def resolve_pricing_method_label(pricing_id: str | None) -> str | None:
    _ensure_maps_loaded()
    oid = (pricing_id or "").strip().lower()
    if not oid or _pm_by_id is None:
        return None
    return _pm_by_id.get(oid)


def resolve_item_labels(
    *,
    sub_service: str | None = None,
    pricing_method: str | None = None,
    sub_service_id: str | None = None,
    pricing_id: str | None = None,
) -> tuple[str | None, str | None]:
    """
    Resolve work-item labels from ObjectIds and/or labels.
    IDs win when both are provided and the ID is known.
    """
    sub_label = (sub_service or "").strip() or None
    pm_label = (pricing_method or "").strip() or None

    if sub_service_id:
        from_id = resolve_sub_service_label(sub_service_id)
        if from_id:
            sub_label = from_id
        elif not sub_label and is_object_id(sub_service_id):
            # Unknown id and no label — cannot look up market row.
            sub_label = None

    if pricing_id:
        from_id = resolve_pricing_method_label(pricing_id)
        if from_id:
            pm_label = from_id
        elif not pm_label and is_object_id(pricing_id):
            pm_label = None

    return sub_label, pm_label


def _persist_label_map(path: Path, label_map: dict[str, str], display: dict[str, str]) -> None:
    """Write label→id JSON using display casing when available."""
    payload: dict[str, str] = {}
    for key_cf, oid in sorted(label_map.items()):
        label = display.get(oid.lower()) or key_cf
        payload[label] = oid
    try:
        path.write_text(json.dumps(payload, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")
    except OSError as e:
        print(f"⚠️ Could not persist Tatva catalog {path.name}: {e}")


def register_sub_service(label: str | None, object_id: str | None, *, persist: bool = True) -> None:
    """Learn / refresh a sub-service ObjectId from a live Tatva quote payload."""
    name = (label or "").strip()
    oid = (object_id or "").strip()
    if not name or not is_object_id(oid):
        return
    _ensure_maps_loaded()
    assert _sub_by_label is not None and _sub_by_id is not None
    key = name.casefold()
    changed = _sub_by_label.get(key) != oid or _sub_by_id.get(oid.lower()) != name
    _sub_by_label[key] = oid
    _sub_by_id[oid.lower()] = name
    for alias in _SUB_LABEL_ALIASES.get(key, ()):
        _sub_by_label[alias.casefold()] = oid
        changed = True
    if changed and persist:
        _persist_label_map(_SUB_FILE, _sub_by_label, _sub_by_id)


def register_pricing_method(label: str | None, object_id: str | None, *, persist: bool = True) -> None:
    """Learn / refresh a pricing-method ObjectId from a live Tatva quote payload."""
    name = (label or "").strip()
    oid = (object_id or "").strip()
    if not name or not is_object_id(oid):
        return
    _ensure_maps_loaded()
    assert _pm_by_label is not None and _pm_by_id is not None
    key = name.casefold()
    changed = _pm_by_label.get(key) != oid or _pm_by_id.get(oid.lower()) != name
    _pm_by_label[key] = oid
    _pm_by_id[oid.lower()] = name
    # Mirror Area (sqft) family so seed labels and PM labels share one id.
    for alias in _PM_LABEL_ALIASES.get(key, ()):
        _pm_by_label[alias.casefold()] = oid
        changed = True
    if changed and persist:
        _persist_label_map(_PM_FILE, _pm_by_label, _pm_by_id)


def register_from_work_item(work_item: dict | None, *, persist: bool = True) -> None:
    """Pull nested subService / pricingMethod ObjectIds out of a Tatva work item."""
    if not isinstance(work_item, dict):
        return
    sub = work_item.get("subService") or work_item.get("sub_service") or {}
    pm = work_item.get("pricingMethod") or work_item.get("pricing_method") or {}
    if isinstance(sub, dict):
        register_sub_service(
            sub.get("name"),
            sub.get("_id") or sub.get("id"),
            persist=persist,
        )
    if isinstance(pm, dict):
        register_pricing_method(
            pm.get("name"),
            pm.get("_id") or pm.get("id"),
            persist=persist,
        )


def _iter_work_items_from_quote(quote_entry: Any) -> list[dict]:
    """Normalize Tatva quote wrappers and yield workItems."""
    if not isinstance(quote_entry, dict):
        return []
    data = quote_entry.get("data") if isinstance(quote_entry.get("data"), dict) else quote_entry
    if not isinstance(data, dict):
        return []
    items: list[dict] = []
    for section in data.get("workSummary") or []:
        if not isinstance(section, dict):
            continue
        for service_obj in section.get("services") or []:
            if not isinstance(service_obj, dict):
                continue
            for work_item in service_obj.get("workItems") or []:
                if isinstance(work_item, dict):
                    items.append(work_item)
    return items


def harvest_ids_from_quotes(quotes: Any) -> dict[str, int]:
    """
    Learn sub-service + pricing-method ObjectIds from Tatva project quote payloads.

    Call this with the same JSON you get from:
      GET /vendor/api/vendor/quotes/project/{projectId}?quotationShare=true
    """
    if isinstance(quotes, dict):
        # Unwrap list containers from Tatva API responses.
        for key in ("quotes", "data", "items", "results"):
            val = quotes.get(key)
            if isinstance(val, list):
                quotes = val
                break
            if isinstance(val, dict) and isinstance(val.get("quotes"), list):
                quotes = val["quotes"]
                break
        else:
            quotes = [quotes]

    if not isinstance(quotes, list):
        return {"quotes": 0, "work_items": 0, "sub_services": 0, "pricing_methods": 0}

    before_sub = len(_sub_map())
    before_pm = len(_pm_map())
    work_count = 0
    for entry in quotes:
        for work_item in _iter_work_items_from_quote(entry):
            work_count += 1
            register_from_work_item(work_item, persist=False)

    # Persist once after the batch.
    _ensure_maps_loaded()
    assert _sub_by_label is not None and _sub_by_id is not None
    assert _pm_by_label is not None and _pm_by_id is not None
    _persist_label_map(_SUB_FILE, _sub_by_label, _sub_by_id)
    _persist_label_map(_PM_FILE, _pm_by_label, _pm_by_id)

    return {
        "quotes": len(quotes),
        "work_items": work_count,
        "sub_services": len(_sub_by_label),
        "pricing_methods": len(_pm_by_label),
        "new_sub_services": max(0, len(_sub_by_label) - before_sub),
        "new_pricing_methods": max(0, len(_pm_by_label) - before_pm),
    }


def apply_catalog_maps(
    sub_services: dict | None = None,
    pricing_methods: dict | None = None,
) -> dict[str, int]:
    """
    Apply an explicit label → ObjectId map from PM (no quotes needed).

    Body shape:
      {
        "sub_services": { "Wardrobe": "6995...", "Base Unit": "6995..." },
        "pricing_methods": { "Area (sqft)": "6a02...", "Per Unit": "6994..." }
      }
    """
    before_sub = len(_sub_map())
    before_pm = len(_pm_map())
    registered_sub = 0
    registered_pm = 0

    if isinstance(sub_services, dict):
        for label, oid in sub_services.items():
            name = str(label or "").strip()
            val = str(oid or "").strip()
            if not name or not is_object_id(val):
                continue
            register_sub_service(name, val, persist=False)
            registered_sub += 1

    if isinstance(pricing_methods, dict):
        for label, oid in pricing_methods.items():
            name = str(label or "").strip()
            val = str(oid or "").strip()
            if not name or not is_object_id(val):
                continue
            register_pricing_method(name, val, persist=False)
            registered_pm += 1

    _ensure_maps_loaded()
    assert _sub_by_label is not None and _sub_by_id is not None
    assert _pm_by_label is not None and _pm_by_id is not None
    if registered_sub or registered_pm:
        _persist_label_map(_SUB_FILE, _sub_by_label, _sub_by_id)
        _persist_label_map(_PM_FILE, _pm_by_label, _pm_by_id)

    return {
        "registered_sub_services": registered_sub,
        "registered_pricing_methods": registered_pm,
        "sub_services": len(_sub_by_label),
        "pricing_methods": len(_pm_by_label),
        "new_sub_services": max(0, len(_sub_by_label) - before_sub),
        "new_pricing_methods": max(0, len(_pm_by_label) - before_pm),
    }


def payload_looks_like_catalog_maps(payload: Any) -> bool:
    """True when body is an explicit id map rather than Tatva quotes."""
    if not isinstance(payload, dict):
        return False
    return isinstance(payload.get("sub_services"), dict) or isinstance(
        payload.get("pricing_methods"), dict
    )


def split_service_and_category_ids(
    service_id: str | None = None,
    category_id: str | None = None,
    quote_type_id: str | None = None,
) -> tuple[str | None, str | None]:
    """
    PM contract (new):
      service_id  → main service ObjectId (Interiors, Painting, …)
      category_id → quotation-type ObjectId (Essential / Mid / Luxury)

    Legacy aliases:
      quote_type_id → same as new category_id
      old category_id that matches a known service ObjectId → service_id
    """
    sid = (service_id or "").strip() or None
    cid = (category_id or "").strip() or None
    qtid = (quote_type_id or "").strip() or None

    out_service = sid
    out_quote = qtid

    if cid:
        if is_known_quote_type_id(cid):
            out_quote = out_quote or cid
        elif is_known_service_id(cid):
            # legacy: category_id was main service
            out_service = out_service or cid
        else:
            # Prefer new meaning when unknown.
            out_quote = out_quote or cid

    return out_service, out_quote


def _tatva_api_base() -> str:
    return os.getenv("TATVA_API_BASE", "https://devopsapi.withtatva.ai").rstrip("/")


def _live_ttl_sec() -> float:
    raw = (os.getenv("TATVA_CATALOG_CACHE_TTL") or "").strip()
    try:
        return max(60.0, float(raw)) if raw else float(_DEFAULT_LIVE_TTL_SEC)
    except ValueError:
        return float(_DEFAULT_LIVE_TTL_SEC)


def _ssl_context() -> ssl.SSLContext:
    if certifi is not None:
        return ssl.create_default_context(cafile=certifi.where())
    return ssl.create_default_context()


def _admin_auth_headers() -> dict[str, str] | None:
    """
    Auth for Tatva admin catalog GETs.

    Preferred (PM service key):
      TATVA_API_KEY → header x-api-key

    Legacy fallback (login JWT):
      TATVA_ADMIN_TOKEN / TATVA_CATALOG_BEARER → Authorization: Bearer …
    """
    headers: dict[str, str] = {"Accept": "application/json"}

    api_key = (os.getenv("TATVA_API_KEY") or "").strip()
    if api_key:
        headers["x-api-key"] = api_key
        return headers

    token = (
        os.getenv("TATVA_ADMIN_TOKEN")
        or os.getenv("TATVA_CATALOG_BEARER")
        or ""
    ).strip()
    if not token:
        return None
    if not token.lower().startswith("bearer "):
        token = f"Bearer {token}"
    headers["Authorization"] = token
    return headers


def _catalog_auth_missing_message() -> str:
    return (
        "TATVA_API_KEY is not set (preferred: x-api-key). "
        "Legacy: TATVA_ADMIN_TOKEN / TATVA_CATALOG_BEARER."
    )


def _http_get_json(url: str, headers: dict[str, str]) -> Any | None:
    req = urllib.request.Request(url, headers=headers, method="GET")
    try:
        with urllib.request.urlopen(req, timeout=30, context=_ssl_context()) as resp:
            body = resp.read().decode("utf-8")
            return json.loads(body) if body else None
    except (urllib.error.HTTPError, urllib.error.URLError, json.JSONDecodeError, TimeoutError) as e:
        print(f"⚠️ Tatva catalog GET failed ({url}): {e}")
        return None


def _unwrap_catalog_list(payload: Any) -> list[dict]:
    """Accept common Tatva list wrappers: data[], data.docs, items, results."""
    if isinstance(payload, list):
        return [x for x in payload if isinstance(x, dict)]
    if not isinstance(payload, dict):
        return []
    for key in ("data", "items", "results", "docs", "subServices", "pricingMethods"):
        val = payload.get(key)
        if isinstance(val, list):
            return [x for x in val if isinstance(x, dict)]
        if isinstance(val, dict):
            for nested_key in ("docs", "items", "results", "data"):
                nested = val.get(nested_key)
                if isinstance(nested, list):
                    return [x for x in nested if isinstance(x, dict)]
    return []


def _entry_name_and_id(entry: dict) -> tuple[str | None, str | None]:
    name = (
        entry.get("name")
        or entry.get("label")
        or entry.get("title")
        or entry.get("subServiceName")
        or entry.get("pricingMethodName")
    )
    oid = entry.get("_id") or entry.get("id")
    name_s = str(name or "").strip() or None
    oid_s = str(oid or "").strip() or None
    if oid_s and not is_object_id(oid_s):
        oid_s = None
    return name_s, oid_s


def _cache_fresh(key: str) -> bool:
    at = _LIVE_AT.get(key)
    if at is None:
        return False
    return (time.time() - at) < _live_ttl_sec()


def _mark_cache(key: str) -> None:
    _LIVE_AT[key] = time.time()


def fetch_pricing_methods_from_tatva(*, force: bool = False, persist: bool = False) -> dict[str, Any]:
    """
    GET /admin/api/admin/pricing-methods → register name→_id in memory.
    """
    cache_key = "pricing_methods"
    if not force and _cache_fresh(cache_key):
        _ensure_maps_loaded()
        return {
            "ok": True,
            "cached": True,
            "registered": 0,
            "pricing_methods": len(_pm_by_label or {}),
        }

    headers = _admin_auth_headers()
    if not headers:
        return {
            "ok": False,
            "cached": False,
            "registered": 0,
            "message": _catalog_auth_missing_message(),
        }

    path = (
        os.getenv("TATVA_PRICING_METHODS_PATH")
        or "/admin/api/admin/pricing-methods"
    ).strip()
    if not path.startswith("/"):
        path = "/" + path
    url = f"{_tatva_api_base()}{path}"
    payload = _http_get_json(url, headers)
    if payload is None:
        return {
            "ok": False,
            "cached": False,
            "registered": 0,
            "message": "Failed to fetch pricing-methods from Tatva.",
            "url": url,
        }

    before = len(_pm_map())
    registered = 0
    for entry in _unwrap_catalog_list(payload):
        name, oid = _entry_name_and_id(entry)
        if not name or not oid:
            continue
        register_pricing_method(name, oid, persist=False)
        registered += 1

    if persist and registered:
        _ensure_maps_loaded()
        assert _pm_by_label is not None and _pm_by_id is not None
        _persist_label_map(_PM_FILE, _pm_by_label, _pm_by_id)

    _mark_cache(cache_key)
    return {
        "ok": True,
        "cached": False,
        "registered": registered,
        "pricing_methods": len(_pm_by_label or {}),
        "new": max(0, len(_pm_by_label or {}) - before),
        "url": url,
    }


def fetch_sub_services_from_tatva(
    service_id: str,
    *,
    force: bool = False,
    persist: bool = False,
) -> dict[str, Any]:
    """
    GET /admin/api/admin/quote-subservices?serviceId=… → register name→_id.
    """
    sid = (service_id or "").strip()
    if not sid:
        return {"ok": False, "registered": 0, "message": "service_id is required."}

    cache_key = f"sub_services:{sid}"
    if not force and _cache_fresh(cache_key):
        _ensure_maps_loaded()
        return {
            "ok": True,
            "cached": True,
            "registered": 0,
            "service_id": sid,
            "sub_services": len(_sub_by_label or {}),
        }

    headers = _admin_auth_headers()
    if not headers:
        return {
            "ok": False,
            "cached": False,
            "registered": 0,
            "service_id": sid,
            "message": _catalog_auth_missing_message(),
        }

    path = (
        os.getenv("TATVA_SUBSERVICES_PATH")
        or "/admin/api/admin/quote-subservices"
    ).strip()
    if not path.startswith("/"):
        path = "/" + path
    qs = urllib.parse.urlencode({"serviceId": sid, "page": "1", "limit": "500"})
    url = f"{_tatva_api_base()}{path}?{qs}"
    payload = _http_get_json(url, headers)
    if payload is None:
        return {
            "ok": False,
            "cached": False,
            "registered": 0,
            "service_id": sid,
            "message": "Failed to fetch quote-subservices from Tatva.",
            "url": url,
        }

    before = len(_sub_map())
    registered = 0
    for entry in _unwrap_catalog_list(payload):
        name, oid = _entry_name_and_id(entry)
        if not name or not oid:
            continue
        register_sub_service(name, oid, persist=False)
        registered += 1

    if persist and registered:
        _ensure_maps_loaded()
        assert _sub_by_label is not None and _sub_by_id is not None
        _persist_label_map(_SUB_FILE, _sub_by_label, _sub_by_id)

    _mark_cache(cache_key)
    return {
        "ok": True,
        "cached": False,
        "registered": registered,
        "service_id": sid,
        "sub_services": len(_sub_by_label or {}),
        "new": max(0, len(_sub_by_label or {}) - before),
        "url": url,
    }


def service_id_for_category(service_category: str | None) -> str | None:
    """Reverse-lookup main service ObjectId from static service map (by category name)."""
    cat = (service_category or "").strip().casefold()
    if not cat:
        return None
    try:
        raw = json.loads(_SERVICE_FILE.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        return None
    if not isinstance(raw, dict):
        return None

    candidates = {cat, *(a.casefold() for a in _SERVICE_CATEGORY_ALIASES.get(cat, ()))}
    for sid, entry in raw.items():
        if not isinstance(entry, dict):
            continue
        name = str(entry.get("service_category") or "").strip().casefold()
        if name in candidates and is_object_id(str(sid)):
            return str(sid).strip()
    return None


def ensure_live_catalog(
    *,
    service_id: str | None = None,
    service_category: str | None = None,
    force: bool = False,
    persist: bool = False,
) -> dict[str, Any]:
    """
    Refresh in-memory ObjectId maps from Tatva admin catalogs.

    Call before /by-category so responses include sub_service_id / pricing_id.
    Cache TTL defaults to 1h (TATVA_CATALOG_CACHE_TTL) so new Tatva items
    appear after the next refresh without a redeploy.
    """
    sid = (service_id or "").strip() or None
    if not sid and service_category:
        sid = service_id_for_category(service_category)

    pm = fetch_pricing_methods_from_tatva(force=force, persist=persist)
    sub: dict[str, Any] = {"ok": True, "skipped": True, "registered": 0}
    if sid:
        sub = fetch_sub_services_from_tatva(sid, force=force, persist=persist)
    else:
        sub = {
            "ok": False,
            "skipped": True,
            "registered": 0,
            "message": "No service_id — skipped quote-subservices fetch.",
        }

    _ensure_maps_loaded()
    return {
        "ok": bool(pm.get("ok")) or bool(sub.get("ok")),
        "service_id": sid,
        "pricing_methods": pm,
        "sub_services": sub,
        "catalog_sub_services": len(_sub_by_label or {}),
        "catalog_pricing_methods": len(_pm_by_label or {}),
        "has_catalog_auth": _admin_auth_headers() is not None,
    }

"""
Tatva PM ObjectId catalogs for market-rate API responses.

Maps human labels ↔ Mongo ObjectIds so PM can filter by id (preferred)
or label (fallback). Static JSON is the seed; Mongo quote ingest learns
more IDs at runtime and persists them when the filesystem is writable.
"""

from __future__ import annotations

import json
import os
import re
from pathlib import Path

_DATA_DIR = Path(__file__).resolve().parent.parent / "data"
_SUB_FILE = _DATA_DIR / "tatva_sub_service_ids.json"
_PM_FILE = _DATA_DIR / "tatva_pricing_method_ids.json"
_SERVICE_FILE = _DATA_DIR / "tatva_service_ids.json"

_OID_RE = re.compile(r"^[a-fA-F0-9]{24}$")

# Label variants that share one Tatva pricing-method ObjectId once any alias is known.
_PM_LABEL_ALIASES: dict[str, tuple[str, ...]] = {
    "area (sqft)": ("Area (sqft)", "Area (in sqft)", "Area in sqft"),
    "area (in sqft)": ("Area (sqft)", "Area (in sqft)", "Area in sqft"),
    "area in sqft": ("Area (sqft)", "Area (in sqft)", "Area in sqft"),
    "area(in sqm)": ("Area(in sqm)", "Area (in sqm)", "Area in sqm"),
    "area (in sqm)": ("Area(in sqm)", "Area (in sqm)", "Area in sqm"),
    "area (in sqmm)": ("Area (in sqmm)", "Area(in sqmm)"),
}

_sub_by_label: dict[str, str] | None = None
_pm_by_label: dict[str, str] | None = None
_sub_by_id: dict[str, str] | None = None
_pm_by_id: dict[str, str] | None = None
_service_ids: set[str] | None = None


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
    return _sub_by_label.get(key) if key and _sub_by_label is not None else None


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
    if _sub_by_label.get(key) == oid and _sub_by_id.get(oid.lower()) == name:
        return
    _sub_by_label[key] = oid
    _sub_by_id[oid.lower()] = name
    if persist:
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

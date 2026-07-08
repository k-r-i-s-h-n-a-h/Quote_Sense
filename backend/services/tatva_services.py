"""Resolve Tatva PM service ObjectIds to service category names."""

from __future__ import annotations

import json
import os
import re
import ssl
import time
import urllib.error
import urllib.request
from pathlib import Path

try:
    import certifi
except ImportError:
    certifi = None

_CACHE: list[dict] | None = None
_CACHE_AT: float = 0.0
_CACHE_TTL_SEC = 3600
_STATIC_MAP: dict[str, dict] | None = None

_DATA_FILE = Path(__file__).resolve().parent.parent / "data" / "tatva_service_ids.json"


def _tatva_api_base() -> str:
    return os.getenv("TATVA_API_BASE", "https://devopsapi.withtatva.ai").rstrip("/")


def _ssl_context() -> ssl.SSLContext:
    if certifi is not None:
        return ssl.create_default_context(cafile=certifi.where())
    return ssl.create_default_context()


def _normalize_service_name(value: str) -> str:
    """Strip zero-width chars Tatva sometimes prefixes on service names."""
    text = re.sub(r"[\u200b-\u200d\ufeff]", "", value or "")
    return text.strip()


def _unwrap_services(payload) -> list[dict]:
    if isinstance(payload, list):
        return [s for s in payload if isinstance(s, dict)]
    if not isinstance(payload, dict):
        return []
    data = payload.get("data")
    if isinstance(data, list):
        return [s for s in data if isinstance(s, dict)]
    return []


def _load_static_service_map() -> dict[str, dict]:
    """Built-in service_id → category map; used when Tatva API is unreachable."""
    global _STATIC_MAP
    if _STATIC_MAP is not None:
        return _STATIC_MAP

    merged: dict[str, dict] = {}
    try:
        if _DATA_FILE.is_file():
            raw = json.loads(_DATA_FILE.read_text(encoding="utf-8"))
            if isinstance(raw, dict):
                for sid, entry in raw.items():
                    if isinstance(entry, dict) and entry.get("service_category"):
                        merged[str(sid).strip()] = {
                            "service_category": _normalize_service_name(
                                str(entry["service_category"])
                            ),
                            "service_code": str(entry.get("service_code") or "").strip() or None,
                        }
    except (OSError, json.JSONDecodeError) as e:
        print(f"⚠️ Could not load static Tatva service map: {e}")

    env_raw = os.getenv("TATVA_SERVICE_ID_MAP", "").strip()
    if env_raw:
        try:
            env_map = json.loads(env_raw)
            if isinstance(env_map, dict):
                for sid, entry in env_map.items():
                    if isinstance(entry, str):
                        merged[str(sid).strip()] = {
                            "service_category": _normalize_service_name(entry),
                            "service_code": None,
                        }
                    elif isinstance(entry, dict) and entry.get("service_category"):
                        merged[str(sid).strip()] = {
                            "service_category": _normalize_service_name(
                                str(entry["service_category"])
                            ),
                            "service_code": str(entry.get("service_code") or "").strip() or None,
                        }
        except json.JSONDecodeError as e:
            print(f"⚠️ Invalid TATVA_SERVICE_ID_MAP env JSON: {e}")

    _STATIC_MAP = merged
    return merged


def _resolve_from_static_map(service_id: str) -> dict | None:
    entry = _load_static_service_map().get(service_id)
    if not entry or not entry.get("service_category"):
        return None
    return {
        "service_id": service_id,
        "service_category": entry["service_category"],
        "service_code": entry.get("service_code"),
        "source": "static_map",
    }


def _fetch_services_from_api() -> list[dict]:
    url = f"{_tatva_api_base()}/admin/api/services?page=1&limit=100"
    req = urllib.request.Request(url, headers={"Accept": "application/json"}, method="GET")
    try:
        with urllib.request.urlopen(req, timeout=30, context=_ssl_context()) as resp:
            body = resp.read().decode("utf-8")
            payload = json.loads(body) if body else {}
    except (urllib.error.HTTPError, urllib.error.URLError, json.JSONDecodeError) as e:
        print(f"⚠️ Tatva services fetch failed: {e}")
        return []
    return _unwrap_services(payload)


def _get_services_cached(force_refresh: bool = False) -> list[dict]:
    global _CACHE, _CACHE_AT
    now = time.time()
    if not force_refresh and _CACHE is not None and (now - _CACHE_AT) < _CACHE_TTL_SEC:
        return _CACHE
    services = _fetch_services_from_api()
    if services:
        _CACHE = services
        _CACHE_AT = now
    return services or (_CACHE or [])


def _resolve_from_api(service_id: str, *, force_refresh: bool = False) -> dict | None:
    for svc in _get_services_cached(force_refresh=force_refresh):
        svc_id = str(svc.get("id") or svc.get("_id") or "").strip()
        if svc_id != service_id:
            continue
        name = _normalize_service_name(str(svc.get("name") or ""))
        if not name:
            return None
        return {
            "service_id": service_id,
            "service_category": name,
            "service_code": str(svc.get("serviceCode") or "").strip() or None,
            "source": "tatva_api",
        }
    return None


def resolve_service_by_id(service_id: str, *, force_refresh: bool = False) -> dict | None:
    """
    Map Tatva PM service ObjectId → service_category name used in market_moving_averages.

    Tries Tatva services API first; falls back to backend/data/tatva_service_ids.json
    (and optional TATVA_SERVICE_ID_MAP env JSON) when the API is down or slow.
    """
    sid = (service_id or "").strip()
    if not sid:
        return None

    resolved = _resolve_from_api(sid, force_refresh=force_refresh)
    if resolved:
        return resolved

    if not force_refresh:
        resolved = _resolve_from_api(sid, force_refresh=True)
        if resolved:
            return resolved

    static = _resolve_from_static_map(sid)
    if static:
        print(f"ℹ️ Resolved service_id {sid} via static map → {static['service_category']}")
        return static

    return None

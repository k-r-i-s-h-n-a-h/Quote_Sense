"""Resolve Tatva PM service ObjectIds to service category names."""

from __future__ import annotations

import json
import os
import re
import ssl
import time
import urllib.error
import urllib.request

try:
    import certifi
except ImportError:
    certifi = None

_CACHE: list[dict] | None = None
_CACHE_AT: float = 0.0
_CACHE_TTL_SEC = 3600


def _tatva_api_base() -> str:
    return os.getenv("TATVA_API_BASE", "https://api.withtatva.ai").rstrip("/")


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


def resolve_service_by_id(service_id: str, *, force_refresh: bool = False) -> dict | None:
    """
    Map Tatva PM service ObjectId → service_category name used in market_moving_averages.
    Returns None when the id is unknown or services API is unreachable.
    """
    sid = (service_id or "").strip()
    if not sid:
        return None

    for svc in _get_services_cached(force_refresh=force_refresh):
        svc_id = str(svc.get("id") or svc.get("_id") or "").strip()
        if svc_id != sid:
            continue
        name = _normalize_service_name(str(svc.get("name") or ""))
        if not name:
            return None
        return {
            "service_id": sid,
            "service_category": name,
            "service_code": str(svc.get("serviceCode") or "").strip() or None,
        }

    if not force_refresh:
        return resolve_service_by_id(sid, force_refresh=True)

    return None

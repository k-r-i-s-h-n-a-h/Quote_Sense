"""
Gemini explicit context cache for PDF extraction static prompt (rules + taxonomy).

The PDF bytes change every request; rules + taxonomy (~3k+ tokens) are identical.
Caching them gives faster 2nd/3rd PDF extractions and lower input cost without
changing extraction quality.
"""

import os
import threading
import time
from datetime import datetime, timezone

from services.env_config import get_gemini_client
from services.taxonomy_prompt import build_extraction_system_instruction

_cache_lock = threading.Lock()
_cache_state: dict | None = None  # { name, model, expire_ts }


def _explicit_cache_enabled() -> bool:
    return os.getenv("GEMINI_EXPLICIT_CACHE", "true").lower() not in (
        "0",
        "false",
        "no",
    )


def _cache_ttl() -> str:
    return os.getenv("GEMINI_CACHE_TTL", "3600s")


def _parse_expire_ts(expire_time) -> float:
    if expire_time is None:
        return time.time() + 3600
    if isinstance(expire_time, datetime):
        dt = expire_time
        if dt.tzinfo is None:
            dt = dt.replace(tzinfo=timezone.utc)
        return dt.timestamp()
    return time.time() + 3600


def get_extraction_cached_content_name(model: str) -> str | None:
    """Return explicit cache resource name, creating or refreshing as needed."""
    if not _explicit_cache_enabled():
        return None

    with _cache_lock:
        global _cache_state
        now = time.time()

        if _cache_state and _cache_state["model"] == model:
            if now < _cache_state["expire_ts"] - 120:
                return _cache_state["name"]
            # Expiring soon — refresh below

        try:
            from google.genai import types

            client = get_gemini_client()
            system_instruction = build_extraction_system_instruction()

            if _cache_state and _cache_state.get("name"):
                try:
                    client.caches.update(
                        name=_cache_state["name"],
                        config=types.UpdateCachedContentConfig(ttl=_cache_ttl()),
                    )
                    _cache_state["expire_ts"] = now + 3600
                    print(f"  ♻️ Refreshed Gemini extraction cache TTL ({model})")
                    return _cache_state["name"]
                except Exception:
                    pass

            cache = client.caches.create(
                model=model,
                config=types.CreateCachedContentConfig(
                    display_name="quotesense-pdf-extraction",
                    system_instruction=system_instruction,
                    ttl=_cache_ttl(),
                ),
            )
            _cache_state = {
                "name": cache.name,
                "model": model,
                "expire_ts": _parse_expire_ts(getattr(cache, "expire_time", None)),
            }
            print(f"  💾 Created Gemini extraction context cache ({model})")
            return cache.name
        except Exception as e:
            print(f"  ⚠️ Gemini explicit cache unavailable, using inline prompt: {e}")
            return None


def invalidate_extraction_cache() -> None:
    """Clear in-process cache handle (e.g. after taxonomy update)."""
    global _cache_state
    with _cache_lock:
        _cache_state = None

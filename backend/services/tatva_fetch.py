"""Fetch Tatva PM vendor quotes server-side (MongoDB lane + project_id)."""

import json
import os
import urllib.error
import urllib.parse
import urllib.request

from services.comparator import _unwrap_quote_payload


def _tatva_api_base() -> str:
    return os.getenv("TATVA_API_BASE", "https://devopsapi.withtatva.ai").rstrip("/")


def _unwrap_quotes_list(payload) -> list:
    if isinstance(payload, list):
        return [q for q in payload if isinstance(q, dict)]
    if not isinstance(payload, dict):
        return []
    for key in ("quotes", "data", "items", "results"):
        val = payload.get(key)
        if isinstance(val, list):
            return [q for q in val if isinstance(q, dict)]
        nested = val if isinstance(val, dict) else None
        if nested and isinstance(nested.get("quotes"), list):
            return [q for q in nested["quotes"] if isinstance(q, dict)]
    return []


def fetch_project_quotes(project_id: str, authorization: str) -> list:
    """GET vendor quotes for a Tatva project (Mongo _id)."""
    if not project_id or not authorization:
        return []

    auth = authorization.strip()
    if not auth.lower().startswith("bearer "):
        auth = f"Bearer {auth}"

    url = (
        f"{_tatva_api_base()}/vendor/api/vendor/quotes/project/"
        f"{urllib.parse.quote(project_id)}?quotationShare=true"
    )
    req = urllib.request.Request(
        url,
        headers={"Authorization": auth, "Accept": "application/json"},
        method="GET",
    )

    try:
        with urllib.request.urlopen(req, timeout=60) as resp:
            body = resp.read().decode("utf-8")
            payload = json.loads(body) if body else {}
    except (urllib.error.HTTPError, urllib.error.URLError, json.JSONDecodeError) as e:
        print(f"⚠️ Tatva quotes fetch failed for {project_id}: {e}")
        return []

    return _unwrap_quotes_list(payload)


def filter_quotes_by_ids(quotes_list: list, quote_ids: list) -> list:
    if not quote_ids:
        return quotes_list
    wanted = {str(qid).strip() for qid in quote_ids if str(qid).strip()}
    if not wanted:
        return quotes_list

    out = []
    seen = set()
    for entry in quotes_list:
        data = _unwrap_quote_payload(entry)
        key = str(data.get("_id") or data.get("id") or "").strip()
        if not key or key not in wanted or key in seen:
            continue
        seen.add(key)
        out.append(entry)
    return out

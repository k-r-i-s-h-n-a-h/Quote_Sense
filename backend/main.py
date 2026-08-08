from fastapi import FastAPI, UploadFile, File, Form, Body, Header, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.concurrency import run_in_threadpool
from fastapi.responses import JSONResponse, Response
from pydantic import BaseModel
from typing import List,Any,Optional
import os
import shutil
import uuid
import asyncio
import json
import time
from datetime import datetime
from dotenv import load_dotenv

BASE_DIR = os.path.dirname(os.path.abspath(__file__))
load_dotenv(os.path.join(BASE_DIR, ".env"), override=True)

DEBUG_LOG_PATH = os.path.join(BASE_DIR, "..", ".cursor", "debug-b7c34a.log")


def _agent_debug_log(location, message, data=None, hypothesis_id=None, run_id="pre-fix"):
    # region agent log
    try:
        os.makedirs(os.path.dirname(DEBUG_LOG_PATH), exist_ok=True)
        with open(DEBUG_LOG_PATH, "a") as f:
            f.write(json.dumps({
                "sessionId": "b7c34a",
                "timestamp": int(time.time() * 1000),
                "location": location,
                "message": message,
                "data": data or {},
                "hypothesisId": hypothesis_id,
                "runId": run_id,
            }) + "\n")
    except Exception:
        pass
    # endregion

# Import your extractor and comparator functions!
from services.extractor import process_single_pdf
from services.comparator import (
    run_comparison,
    handle_chat_query,
    mongodb_quotes_to_dataframe,
)
from services.env_config import env_diagnostics, get_supabase_client
from services.tatva_fetch import fetch_project_quotes, filter_quotes_by_ids
from services.market_rate import (
    DEFAULT_SERVICE_TYPE,
    apply_finalized_quotes_to_market_rates,
    finalize_session_market_rates,
    list_market_rates_by_category,
    recommend_rate,
    resolve_service_type,
)
from services.tatva_services import resolve_service_by_id

MIN_COMPARE_QUOTES = 2
MAX_COMPARE_QUOTES = 3

# Bulk: private = browser/PM app may cache 2h; CDN (Cloudflare) should not → cf-cache-status: DYNAMIC
BULK_MARKET_RATE_CACHE = "private, max-age=7200, stale-while-revalidate=300"
BULK_MARKET_RATE_CDN_CACHE = "no-store"
RATE_VERDICT_CACHE = "private, max-age=300"
MARKET_RATE_ERROR_CACHE = "no-store"


def _market_rate_by_category_cache_control(
    entered_rate: Optional[float],
    *,
    error: bool = False,
) -> dict[str, str]:
    if error:
        return {"Cache-Control": MARKET_RATE_ERROR_CACHE}
    if entered_rate and entered_rate > 0:
        return {"Cache-Control": RATE_VERDICT_CACHE}
    return {
        "Cache-Control": BULK_MARKET_RATE_CACHE,
        "CDN-Cache-Control": BULK_MARKET_RATE_CDN_CACHE,
    }


def _market_rate_by_category_response(
    payload: dict,
    entered_rate: Optional[float],
    *,
    error: bool = False,
) -> JSONResponse:
    return JSONResponse(
        content=payload,
        headers=_market_rate_by_category_cache_control(entered_rate, error=error),
    )


def _missing_service_type_error(*, bulk: bool = False) -> dict:
    """
    No fallback: quotation type must be explicitly sent (service_type string
    and/or category_id / quote_type_id ObjectId mapped from env).
    """
    message = (
        "quotation type is required — send category_id (quote type ObjectId) "
        "or service_type / quote_type_id "
        "(vendor must select Essential / Mid-segment / Luxury first)."
    )
    if bulk:
        return {"service_type": None, "count": 0, "items": [], "message": message}
    return {"recommend": False, "message": message}


async def _resolve_lookup_category(
    service_id: Optional[str],
    service_category: Optional[str],
    category_id: Optional[str] = None,
    quote_type_id: Optional[str] = None,
) -> tuple[Optional[str], Optional[str], Optional[dict]]:
    """
    Resolve main-service category name for suggest/lookup/recommend.

    New PM contract:
      service_id  → main service ObjectId
      category_id → quotation-type ObjectId (Essential / Mid / Luxury)

    Returns (service_category_name, quote_type_object_id, error_payload).
    """
    from services.tatva_catalog import split_service_and_category_ids

    svc_id, qt_id = split_service_and_category_ids(
        service_id=service_id,
        category_id=category_id,
        quote_type_id=quote_type_id,
    )

    cat = (service_category or "").strip()
    if cat:
        return cat, qt_id, None
    if svc_id:
        resolved = await run_in_threadpool(resolve_service_by_id, svc_id)
        if not resolved:
            return None, qt_id, {
                "recommend": False,
                "message": "Unknown service_id.",
            }
        return resolved["service_category"], qt_id, None
    return None, qt_id, {
        "recommend": False,
        "message": "Provide service_id or service_category.",
    }


app = FastAPI(title="QuoteSense API")

# FIXED: We added both port 3000 and 3001 to ensure Next.js never gets blocked!
app.add_middleware(
    CORSMiddleware,
    allow_origins=[
        # Local
        "http://localhost:3000",
        "http://127.0.0.1:3000",

        # QuoteSense frontends (Vercel) — replace with your real URLs
        "https://quotesense.withtatva.ai",
        "https://devquotesense.withtatva.ai",
        "https://testquotesense.withtatva.ai",
        # custom domains if any:
        # "https://quotesense.withtatva.ai",

        # Tatva PM / vendor form
        "https://devops.withtatva.ai",
        "https://testops.withtatva.ai",
        "https://ops.withtatva.ai"
        # add staging/test Tatva hosts if different, e.g.:
        # "https://staging.withtatva.ai",
        # "https://dev.withtatva.ai",
    ],
    allow_credentials=False,
    allow_methods=["GET"],
    allow_headers=["*"],
)

UPLOAD_DIR = os.path.join(BASE_DIR, "temp_uploads")
os.makedirs(UPLOAD_DIR, exist_ok=True)

# In-memory progress store for the async compare pipeline. Keyed by session_id.
# NOTE: this lives in the process, so it assumes a single uvicorn worker (the
# default on Render's free tier). For multi-worker setups, swap this for Redis
# or a Supabase table.
JOBS: dict = {}


def _set_progress(session_id, **fields):
    job = JOBS.setdefault(session_id, {})
    job.update(fields)


def _format_quote_date(raw_date) -> str:
    """Normalize Tatva quoteDate (ISO) to DD/MM/YYYY like PDF extraction."""
    if not raw_date:
        return ""
    raw = str(raw_date).strip()
    if len(raw) >= 10 and raw[4] == "-" and raw[7] == "-":
        try:
            return datetime.strptime(raw[:10], "%Y-%m-%d").strftime("%d/%m/%Y")
        except ValueError:
            pass
    return raw


def _unwrap_mongodb_quote(quote_entry: dict) -> dict:
    """Accept raw quote objects or Tatva API envelopes { data: {...} }."""
    if not isinstance(quote_entry, dict):
        return quote_entry
    inner = quote_entry.get("data")
    if isinstance(inner, dict) and (
        "quoteNumber" in inner or "vendorDetail" in inner or "workSummary" in inner
    ):
        return inner
    return quote_entry


def _mongodb_quote_metadata(quote_data: dict) -> dict:
    """Map TatvaOps MongoDB quote fields to Supabase quotes columns."""
    client_detail = quote_data.get("clientDetail") or {}
    quote_number = str(quote_data.get("quoteNumber") or "").lstrip("#").strip()
    client_name = (
        client_detail.get("clientName")
        or client_detail.get("name")
        or "Unknown"
    )
    raw_date = quote_data.get("quoteDate") or quote_data.get("createdAt") or ""
    return {
        "quote_number": quote_number,
        "client_name": client_name,
        "quote_date": _format_quote_date(raw_date),
        "source_filename": quote_number or "DIRECT_SYNC",
    }


def _quote_line_item(
    quote_id: str,
    *,
    service_category: str,
    sub_service: str,
    work_title: str = "",
    description: str = "",
    quantity=0,
    pricing_method: str = "Unit",
    rate=0,
    amount=0,
    item_name: str = "",
    service_type: str = DEFAULT_SERVICE_TYPE,
) -> dict:
    return {
        "quote_id": quote_id,
        "service_type": service_type or DEFAULT_SERVICE_TYPE,
        "service_category": service_category,
        "sub_service": sub_service,
        "item_name": item_name or work_title or "",
        "work_title": work_title,
        "description": description,
        "quantity": quantity,
        "pricing_method": pricing_method or "Unit",
        "rate": rate,
        "amount": amount,
    }


class MarketRateRequest(BaseModel):
    # Quotation type: category_id (new) / quote_type_id (legacy) / service_type string.
    service_type: Optional[str] = None
    quote_type_id: Optional[str] = None  # legacy alias for category_id (quote type)
    service_id: Optional[str] = None  # main service ObjectId (Interiors, …)
    category_id: Optional[str] = None  # quotation-type ObjectId (Essential / Mid / Luxury)
    service_category: Optional[str] = None
    sub_service: Optional[str] = None
    pricing_method: Optional[str] = None
    sub_service_id: Optional[str] = None
    pricing_id: Optional[str] = None
    entered_rate: Optional[float] = None


class MarketRateSuggestRequest(BaseModel):
    """Vendor quote form (withtatva.ai) — exact bundle match for market guidance."""
    service_type: Optional[str] = None
    quote_type_id: Optional[str] = None  # legacy alias for category_id (quote type)
    service_id: Optional[str] = None  # main service ObjectId
    category_id: Optional[str] = None  # quotation-type ObjectId
    service_category: Optional[str] = None
    sub_service: Optional[str] = None
    pricing_method: Optional[str] = None
    sub_service_id: Optional[str] = None
    pricing_id: Optional[str] = None
    entered_rate: Optional[float] = None


def _resolve_work_item_labels(
    sub_service: Optional[str] = None,
    pricing_method: Optional[str] = None,
    sub_service_id: Optional[str] = None,
    pricing_id: Optional[str] = None,
) -> tuple[Optional[str], Optional[str], Optional[dict]]:
    """Resolve labels from ObjectIds and/or names. Returns (sub, pm, error)."""
    from services.tatva_catalog import resolve_item_labels

    sub_label, pm_label = resolve_item_labels(
        sub_service=sub_service,
        pricing_method=pricing_method,
        sub_service_id=sub_service_id,
        pricing_id=pricing_id,
    )
    if not sub_label or not pm_label:
        return None, None, {
            "recommend": False,
            "message": (
                "Provide sub_service + pricing_method labels, "
                "or known sub_service_id + pricing_id ObjectIds."
            ),
            "sub_service_id": (sub_service_id or "").strip() or None,
            "pricing_id": (pricing_id or "").strip() or None,
            "sub_service_label": sub_label,
            "pricing_method_label": pm_label,
        }
    return sub_label, pm_label, None


def _require_service_type(
    service_type: Optional[str] = None,
    quote_type_id: Optional[str] = None,
    *,
    bulk: bool = False,
) -> tuple[Optional[str], Optional[dict]]:
    """Resolve quotation type; return (type, None) or (None, error_payload)."""
    resolved = resolve_service_type(service_type, quote_type_id)
    if not resolved:
        return None, _missing_service_type_error(bulk=bulk)
    return resolved, None


class ChatRequest(BaseModel):
    session_id: str
    message: str


@app.get("/")
def read_root():
    return {"status": "QuoteSense Backend is running perfectly! 🚀"}


@app.get("/api/health")
def health():
    diag = env_diagnostics()
    return {
        "ok": diag["gemini_configured"] and diag["supabase_configured"],
        "supabase_configured": diag["supabase_configured"],
        "gemini_configured": diag["gemini_configured"],
        "env_file": {
            "readable_bytes": diag.get("readable_bytes"),
            "corrupted": diag.get("corrupted", False),
        },
        "missing_keys": diag.get("missing", []),
        "hint": (
            "Edit backend/.env with your real GEMINI_API_KEY, SUPABASE_URL, "
            "and SUPABASE_SERVICE_ROLE_KEY."
            if diag.get("missing")
            else None
        ),
    }


@app.get("/api/market-rate/by-category")
@app.head("/api/market-rate/by-category")
async def market_rate_by_category(
    request: Request,
    service_id: Optional[str] = None,
    category_id: Optional[str] = None,
    service_category: Optional[str] = None,
    service_type: Optional[str] = None,
    quote_type_id: Optional[str] = None,
    sub_service: Optional[str] = None,
    pricing_method: Optional[str] = None,
    sub_service_id: Optional[str] = None,
    pricing_id: Optional[str] = None,
    entered_rate: Optional[float] = None,
):
    """
    Bulk market rates for one Main Service.

    PM contract:
      service_id   → main service ObjectId (Interiors, …)
      category_id  → quotation-type ObjectId (Essential / Mid / Luxury)
      quote_type_id → legacy alias for category_id
      service_type  → optional string ESSENTIAL / MID_SEGMENT / LUXURY

    Legacy: category_id that matches a known service ObjectId still resolves as service.
    """
    from services.tatva_catalog import split_service_and_category_ids

    rate = entered_rate if entered_rate and entered_rate > 0 else None
    svc_id, qt_id = split_service_and_category_ids(
        service_id=service_id,
        category_id=category_id,
        quote_type_id=quote_type_id,
    )

    resolved_type, type_err = _require_service_type(
        service_type, qt_id, bulk=True
    )
    if type_err:
        if request.method == "HEAD":
            return Response(
                status_code=200,
                headers=_market_rate_by_category_cache_control(rate, error=True),
            )
        return _market_rate_by_category_response(type_err, rate, error=True)

    sub_label, pm_label = sub_service, pricing_method
    if sub_service_id or pricing_id or sub_service or pricing_method:
        resolved_sub, resolved_pm, _ = _resolve_work_item_labels(
            sub_service, pricing_method, sub_service_id, pricing_id
        )
        # Only use resolved labels when both present; otherwise leave unset for bulk-only.
        if resolved_sub and resolved_pm:
            sub_label, pm_label = resolved_sub, resolved_pm

    list_kwargs = {
        "sub_service": sub_label,
        "pricing_method": pm_label,
        "entered_rate": rate,
    }

    if svc_id:
        resolved = await run_in_threadpool(resolve_service_by_id, svc_id)
        if not resolved:
            payload = {
                "service_id": svc_id,
                "category_id": qt_id,
                "service_type": resolved_type,
                "count": 0,
                "items": [],
                "message": "Unknown service_id.",
            }
            if request.method == "HEAD":
                return Response(
                    status_code=200,
                    headers=_market_rate_by_category_cache_control(rate, error=True),
                )
            return _market_rate_by_category_response(payload, rate, error=True)
        result = await run_in_threadpool(
            list_market_rates_by_category,
            resolved["service_category"],
            resolved_type,
            service_id=resolved["service_id"],
            **list_kwargs,
        )
        result["service_id"] = resolved["service_id"]
        if qt_id:
            result["category_id"] = qt_id
        if resolved.get("service_code"):
            result["service_code"] = resolved["service_code"]
        if request.method == "HEAD":
            return Response(
                status_code=200,
                headers=_market_rate_by_category_cache_control(rate),
            )
        return _market_rate_by_category_response(result, rate)

    if service_category:
        result = await run_in_threadpool(
            list_market_rates_by_category,
            service_category,
            resolved_type,
            **list_kwargs,
        )
        if qt_id:
            result["category_id"] = qt_id
        if request.method == "HEAD":
            return Response(
                status_code=200,
                headers=_market_rate_by_category_cache_control(rate),
            )
        return _market_rate_by_category_response(result, rate)

    payload = {
        "service_type": resolved_type,
        "category_id": qt_id,
        "count": 0,
        "items": [],
        "message": "Provide service_id or service_category.",
    }
    if request.method == "HEAD":
        return Response(
            status_code=200,
            headers=_market_rate_by_category_cache_control(rate, error=True),
        )
    return _market_rate_by_category_response(payload, rate, error=True)


@app.get("/api/market-rate/lookup")
async def market_rate_lookup(
    service_type: Optional[str] = None,
    quote_type_id: Optional[str] = None,
    service_id: Optional[str] = None,
    category_id: Optional[str] = None,
    service_category: Optional[str] = None,
    sub_service: Optional[str] = None,
    pricing_method: Optional[str] = None,
    sub_service_id: Optional[str] = None,
    pricing_id: Optional[str] = None,
):
    """Return market rate when exact bundle exists; otherwise recommend=false."""
    cat, qt_id, error = await _resolve_lookup_category(
        service_id, service_category, category_id, quote_type_id
    )
    if error:
        return error
    resolved_type, type_err = _require_service_type(service_type, qt_id)
    if type_err:
        return type_err
    sub_label, pm_label, item_err = _resolve_work_item_labels(
        sub_service, pricing_method, sub_service_id, pricing_id
    )
    if item_err:
        return item_err
    return await run_in_threadpool(
        recommend_rate,
        resolved_type,
        cat,
        sub_label,
        pm_label,
        None,
    )


@app.get("/api/market-rate/suggest")
async def market_rate_suggest_get(
    service_type: Optional[str] = None,
    quote_type_id: Optional[str] = None,
    service_id: Optional[str] = None,
    category_id: Optional[str] = None,
    service_category: Optional[str] = None,
    sub_service: Optional[str] = None,
    pricing_method: Optional[str] = None,
    sub_service_id: Optional[str] = None,
    pricing_id: Optional[str] = None,
    entered_rate: Optional[float] = None,
):
    """
    Unified vendor-form endpoint (GET) — single exact-bundle match, no bulk scan.
    Prefer sub_service_id + pricing_id; labels still work as fallback.
    Banner only when entered_rate is above the recommended base rate.
    """
    cat, qt_id, error = await _resolve_lookup_category(
        service_id, service_category, category_id, quote_type_id
    )
    if error:
        return error
    resolved_type, type_err = _require_service_type(service_type, qt_id)
    if type_err:
        return type_err
    sub_label, pm_label, item_err = _resolve_work_item_labels(
        sub_service, pricing_method, sub_service_id, pricing_id
    )
    if item_err:
        return item_err
    return await run_in_threadpool(
        recommend_rate,
        resolved_type,
        cat,
        sub_label,
        pm_label,
        entered_rate if entered_rate and entered_rate > 0 else None,
    )


@app.post("/api/market-rate/suggest")
async def market_rate_suggest_post(body: MarketRateSuggestRequest):
    """
    Unified vendor-form endpoint (POST) — preferred for withtatva.ai quote form.
    Include entered_rate on Rate blur. recommend=true only when rate > base.
    """
    cat, qt_id, error = await _resolve_lookup_category(
        body.service_id, body.service_category, body.category_id, body.quote_type_id
    )
    if error:
        return error
    resolved_type, type_err = _require_service_type(body.service_type, qt_id)
    if type_err:
        return type_err
    sub_label, pm_label, item_err = _resolve_work_item_labels(
        body.sub_service, body.pricing_method, body.sub_service_id, body.pricing_id
    )
    if item_err:
        return item_err
    rate = body.entered_rate if body.entered_rate and body.entered_rate > 0 else None
    return await run_in_threadpool(
        recommend_rate,
        resolved_type,
        cat,
        sub_label,
        pm_label,
        rate,
    )


@app.post("/api/market-rate/recommend")
async def market_rate_recommend(body: MarketRateRequest):
    """
    Compare entered raw rate against stored market average for the bundle.
    Quotation type via category_id / quote_type_id / service_type — no ESSENTIAL fallback.
    """
    cat, qt_id, error = await _resolve_lookup_category(
        body.service_id, body.service_category, body.category_id, body.quote_type_id
    )
    if error:
        return error
    resolved_type, type_err = _require_service_type(body.service_type, qt_id)
    if type_err:
        return type_err
    sub_label, pm_label, item_err = _resolve_work_item_labels(
        body.sub_service, body.pricing_method, body.sub_service_id, body.pricing_id
    )
    if item_err:
        return item_err
    return await run_in_threadpool(
        recommend_rate,
        resolved_type,
        cat,
        sub_label,
        pm_label,
        body.entered_rate,
    )


@app.post("/api/market-rate/apply-finalized")
async def market_rate_apply_finalized(payload: Any = Body(default=None)):
    """
    Apply market_moving_averages updates from user-finalized quote payload(s) only.

    Body: one quote object, a list, or { "quotes": [...] }.
    Only entries with isFinalizeQuote / isFinalizedQuote / finalizeQuote=true are used.
    Idempotent per quote number (session key finalize:<quoteNumber>).
    """
    quotes: list = []
    if isinstance(payload, list):
        quotes = payload
    elif isinstance(payload, dict):
        raw = payload.get("quotes") or payload.get("data") or payload.get("items")
        if isinstance(raw, list):
            quotes = raw
        elif payload:
            quotes = [payload]
    if not quotes:
        return {
            "ok": False,
            "status": "error",
            "message": "POST one or more Tatva quote payloads (must include isFinalizeQuote).",
        }

    result = await run_in_threadpool(
        lambda: apply_finalized_quotes_to_market_rates(
            quotes, source="api-apply-finalized"
        )
    )
    return {"status": "success" if result.get("ok") else "partial", **result}


@app.post("/api/market-rate/sync-catalog")
async def market_rate_sync_catalog(
    request: Request,
    payload: Any = Body(default=None),
    project_id: Optional[str] = None,
    authorization: Optional[str] = Header(None),
):
    """
    Fill sub_service_id / pricing_id catalogs used by /by-category and /suggest.

    Four ways:
      A) POST ?live=1&service_id=… — fetch Tatva admin catalogs (needs TATVA_API_KEY)
      B) POST explicit maps from PM:
           { "sub_services": {"Wardrobe":"<oid>"}, "pricing_methods": {"Area (sqft)":"<oid>"} }
      C) POST Tatva project-quotes JSON (workItems with nested _id fields)
      D) POST ?project_id=... + Authorization: Bearer <jwt> (backend fetches quotes)
    """
    from services.tatva_catalog import (
        apply_catalog_maps,
        ensure_live_catalog,
        harvest_ids_from_quotes,
        payload_looks_like_catalog_maps,
    )

    query_project_id = project_id or request.query_params.get("project_id")
    auth_header = authorization or request.headers.get("authorization")
    live = (request.query_params.get("live") or "").strip().lower() in (
        "1",
        "true",
        "yes",
    )
    live_service_id = (
        request.query_params.get("service_id")
        or (payload.get("service_id") if isinstance(payload, dict) else None)
    )

    # A) Live Tatva admin catalogs
    if live:
        stats = await run_in_threadpool(
            ensure_live_catalog,
            service_id=str(live_service_id).strip() if live_service_id else None,
            force=True,
            persist=True,
        )
        ok = bool(stats.get("ok")) and (
            (stats.get("pricing_methods") or {}).get("ok")
            or (stats.get("sub_services") or {}).get("ok")
        )
        return {
            "ok": ok,
            "source": "tatva_admin_live",
            "message": (
                "Catalog refreshed from Tatva admin APIs."
                if ok
                else "Live catalog refresh failed — set TATVA_API_KEY and check paths."
            ),
            **stats,
        }

    # B) Explicit label → ObjectId maps from PM
    if payload_looks_like_catalog_maps(payload):
        stats = await run_in_threadpool(
            apply_catalog_maps,
            payload.get("sub_services") if isinstance(payload, dict) else None,
            payload.get("pricing_methods") if isinstance(payload, dict) else None,
        )
        if stats.get("registered_sub_services", 0) == 0 and stats.get(
            "registered_pricing_methods", 0
        ) == 0:
            return {
                "ok": False,
                "message": (
                    "No valid ObjectIds registered. Each value must be a 24-char hex Mongo id."
                ),
                **stats,
            }
        return {
            "ok": True,
            "source": "catalog_maps",
            "message": (
                f"Catalog updated from explicit maps "
                f"({stats.get('registered_sub_services', 0)} sub-services, "
                f"{stats.get('registered_pricing_methods', 0)} pricing methods)."
            ),
            **stats,
        }

    # B/C) Quotes payload or fetch by project_id
    harvest_input: Any = payload
    parsed = _parse_quotes_payload(payload)
    fetched_empty = False
    if not parsed and isinstance(payload, (dict, list)) and payload not in (None, {}, []):
        harvest_input = payload
    elif parsed:
        harvest_input = parsed
    elif query_project_id and auth_header:
        harvest_input = await run_in_threadpool(
            fetch_project_quotes, query_project_id, auth_header
        )
        if not harvest_input:
            fetched_empty = True
    else:
        harvest_input = []

    if not harvest_input:
        if fetched_empty:
            return {
                "ok": False,
                "message": (
                    f"Tatva quotes API returned 0 quotes for project_id={query_project_id}. "
                    "Ask PM why GET /vendor/api/vendor/quotes/project/{id}?quotationShare=true "
                    "is empty, or POST an explicit catalog map / paste quote JSON with workItems."
                ),
                "project_id": query_project_id,
                "quotes": 0,
            }
        return {
            "ok": False,
            "message": (
                "Provide one of: (1) {sub_services, pricing_methods} id maps, "
                "(2) Tatva quote JSON with workItems, "
                "(3) project_id + Authorization to fetch quotes."
            ),
        }

    stats = await run_in_threadpool(harvest_ids_from_quotes, harvest_input)
    if stats.get("quotes", 0) == 0 and stats.get("work_items", 0) == 0:
        return {
            "ok": False,
            "message": "No work items with subService/pricingMethod found in payload.",
            **stats,
        }
    return {
        "ok": True,
        "source": "quotes",
        "message": (
            f"Catalog updated from {stats.get('quotes', 0)} quotes "
            f"({stats.get('work_items', 0)} work items)."
        ),
        **stats,
    }


def _probe_supabase_tables() -> dict:
    """Sync Supabase probes — must never run on the event loop without a timeout."""
    supabase_ok = False
    sessions_ok = False
    supabase_err = None
    sessions_err = None
    try:
        get_supabase_client().table("market_moving_averages").select("id").limit(1).execute()
        supabase_ok = True
    except Exception as e:
        supabase_err = str(e)
    try:
        get_supabase_client().table("market_moving_avg_sessions").select("id").limit(1).execute()
        sessions_ok = True
    except Exception as e:
        sessions_err = str(e)
    return {
        "market_moving_averages_ok": supabase_ok,
        "market_moving_avg_sessions_ok": sessions_ok,
        "market_moving_averages_err": supabase_err,
        "market_moving_avg_sessions_err": sessions_err,
    }


@app.on_event("startup")
async def _startup_diagnostics():
    """
    Log env status immediately; probe Supabase in the background with a timeout.

    Blocking HTTP here used to hang forever when Supabase/network was slow,
    leaving port 8001 in CLOSED and curl/browser with connection refused/timeout.
    """
    diag = env_diagnostics()
    _agent_debug_log(
        "main.py:startup",
        "backend startup diagnostics (env only)",
        {**diag, "python_ok": True},
        hypothesis_id="E",
    )
    if not diag.get("supabase_configured"):
        return

    async def _bg_probe() -> None:
        try:
            probe = await asyncio.wait_for(
                run_in_threadpool(_probe_supabase_tables),
                timeout=5.0,
            )
        except asyncio.TimeoutError:
            probe = {
                "market_moving_averages_ok": False,
                "market_moving_avg_sessions_ok": False,
                "market_moving_averages_err": "timeout after 5s",
                "market_moving_avg_sessions_err": "timeout after 5s",
            }
        except Exception as e:
            probe = {
                "market_moving_averages_ok": False,
                "market_moving_avg_sessions_ok": False,
                "market_moving_averages_err": str(e),
                "market_moving_avg_sessions_err": str(e),
            }
        _agent_debug_log(
            "main.py:startup",
            "backend supabase probe",
            {**diag, **probe, "python_ok": True},
            hypothesis_id="E",
        )

    asyncio.create_task(_bg_probe())


async def _run_compare_pipeline(session_id, saved_files):
    """Background worker: extract every PDF in parallel, then compare.

    Updates the JOBS progress store at each stage so the frontend can poll for
    real, live progress instead of guessing with a timer.
    """
    total = len(saved_files)
    try:
        _set_progress(
            session_id,
            status="processing",
            stage="extracting",
            processed=0,
            total=total,
            message=f"Reading {total} vendor PDFs with Tatva Intelligence…",
        )

        async def _extract_one(file_path):
            basename = os.path.basename(file_path)
            _set_progress(
                session_id,
                message=f"Reading {basename} with Tatva Intelligence…",
            )
            await run_in_threadpool(process_single_pdf, file_path, session_id)
            job = JOBS.get(session_id, {})
            done = job.get("processed", 0) + 1
            _set_progress(
                session_id,
                processed=done,
                message=f"Extracted {done} of {total} quotes…",
            )

        await asyncio.gather(*[_extract_one(fp) for fp in saved_files])

        _set_progress(
            session_id,
            stage="comparing",
            message="Building comparison matrix…",
        )

        def _publish_matrix(matrix):
            # Called from the worker thread the moment the fast Pandas matrix is
            # ready — exposes chart + table so the UI can render before the
            # (slower) recommendation finishes.
            _set_progress(
                session_id,
                stage="recommending",
                partial=matrix,
                message="Results ready — writing the Tatva Intelligence recommendation…",
            )

        comparison_result = await run_in_threadpool(
            lambda: run_comparison(
                session_id, _publish_matrix, fast_moving_avg=True
            )
        )

        if comparison_result.get("error"):
            _set_progress(
                session_id,
                status="error",
                message=comparison_result["error"],
                error=comparison_result["error"],
            )
            return

        try:
            # Staging cleanup only — compare never writes market_moving_averages.
            await run_in_threadpool(finalize_session_market_rates, session_id, None)
        except Exception as finalize_err:
            print(f"⚠️ Compare session cleanup failed for {session_id}: {finalize_err}")

        _set_progress(
            session_id,
            status="done",
            stage="done",
            message="Analysis complete.",
            result={
                "status": "success",
                "session_id": session_id,
                "report": comparison_result.get("report", "Error generating report."),
                "chartData": comparison_result.get("chartData", []),
                "tableData": comparison_result.get("tableData", []),
                "vendors": comparison_result.get("vendors", []),
                "vendorMeta": comparison_result.get("vendorMeta", {}),
            },
        )
    except Exception as e:
        print(f"❌ Pipeline crash for {session_id}: {e}")
        _set_progress(session_id, status="error", message=str(e), error=str(e))
    finally:
        # Clean up temp files regardless of outcome.
        for file_path in saved_files:
            if os.path.exists(file_path):
                os.remove(file_path)


@app.post("/api/compare-quotes")
async def handle_customer_upload(
    files: List[UploadFile] = File(...),
    session_id: str = Form(None)
):
    """
    Receives PDFs, saves them, and kicks off the extract+compare pipeline in the
    background. Returns immediately with a session_id; the frontend polls
    /api/progress/{session_id} for live status and the final result.
    """
    if not session_id:
        session_id = f"session_{uuid.uuid4().hex[:8]}"

    if len(files) < MIN_COMPARE_QUOTES:
        return {
            "status": "error",
            "message": f"At least {MIN_COMPARE_QUOTES} quotes are required to compare.",
        }
    if len(files) > MAX_COMPARE_QUOTES:
        return {
            "status": "error",
            "message": f"You can compare at most {MAX_COMPARE_QUOTES} quotes at a time.",
        }

    print(f"\n📥 Received {len(files)} quotes for Session: {session_id}")

    saved_files = []
    for file in files:
        file_path = os.path.join(UPLOAD_DIR, file.filename)
        with open(file_path, "wb") as buffer:
            shutil.copyfileobj(file.file, buffer)
        saved_files.append(file_path)
        print(f"  -> Saved {file.filename}")

    _set_progress(
        session_id,
        status="processing",
        stage="queued",
        processed=0,
        total=len(saved_files),
        message="Queued — starting analysis…",
        result=None,
        error=None,
    )

    # Fire-and-forget: process in the background so the request returns fast.
    asyncio.create_task(_run_compare_pipeline(session_id, saved_files))

    return {
        "status": "processing",
        "session_id": session_id,
        "message": f"Received {len(files)} files. Processing started.",
    }


@app.get("/api/progress/{session_id}")
async def get_progress(session_id: str, has_partial: bool = False):
    """Poll endpoint for the async compare pipeline.

    ``has_partial`` lets the frontend say "I already have the matrix", so we
    don't re-send the (large) partial payload on every 1.5s poll — that was
    wasting ~12.9kB per request for the whole run.
    """
    job = JOBS.get(session_id)
    if not job:
        return {"status": "unknown", "message": "No job found for this session."}

    payload = {
        "status": job.get("status", "processing"),
        "stage": job.get("stage", ""),
        "message": job.get("message", ""),
        "processed": job.get("processed", 0),
        "total": job.get("total", 0),
    }
    # While still processing, expose the partial matrix (chart + table) once it's
    # ready so the frontend can render results before the recommendation finishes.
    # Send it only until the client confirms it has it (has_partial=true).
    if job.get("status") == "processing" and job.get("partial") and not has_partial:
        payload["partial"] = job.get("partial")
    # Only ship the full (large) result once, when finished.
    if job.get("status") == "done":
        payload["result"] = job.get("result")
    if job.get("status") == "error":
        payload["error"] = job.get("error")
    return payload

'''
@app.post("/api/sync-mongodb-quotes")
async def sync_mongodb_quotes(payload: Any=Body(...), session_id: str = None): # Use Any for maximum flexibility
    """
    RECEIVES: Structured JSON from MongoDB (Single Object or List)
    """
    try:
        # 1. SAFETY CHECK: Convert payload to a list if it's just one object
        if isinstance(payload, dict):
            quotes_list = [payload]
        elif isinstance(payload, list):
            quotes_list = payload
        else:
            return {"status": "error", "message": "Invalid format. Expected JSON object or list."}

        for quote_entry in quotes_list:
            # Handle the 'data' wrapper if the backend team includes it
            data = quote_entry.get("data", quote_entry)
            
            # Extract Metadata
            vendor_detail = data.get("vendorDetail", {})
            pricing_summary = data.get("pricingSummary", [])
            
            # Find the Grand Total value
            grand_total = 0
            for item in pricing_summary:
                if item.get("label") == "Total":
                    grand_total = item.get("value", 0)

            # Push to Supabase 'quotes' table
            quote_res = get_supabase_client().table("quotes").insert({
                "vendor_name": vendor_detail.get("companyName", "Unknown Vendor"),
                "grand_total": grand_total,
                "session_id": session_id,
                "source_type": "mongodb_integrated",
                "source_filename": data.get("quoteNumber", "DIRECT_SYNC")
            }).execute()
            
            quote_id = quote_res.data[0]['id']
            
            # 2. Extract Line Items
            items_to_insert = []
            work_summary = data.get("workSummary", [])
            
            for summary in work_summary:
                for service_obj in summary.get("services", []):
                    # Mapping the nested serviceId -> name
                    category_name = service_obj.get("serviceId", {}).get("name", "General")
                    
                    for work_item in service_obj.get("workItems", []):
                        from services.tatva_catalog import register_from_work_item
                        register_from_work_item(work_item)
                        # Mapping subService -> name
                        sub_service_name = work_item.get("subService", {}).get("name", work_item.get("workTitle"))
                        
                        # Pricing input extraction
                        pricing_list = work_item.get("pricingInput", [])
                        pricing = pricing_list[0] if pricing_list else {}
                        
                        items_to_insert.append(_quote_line_item(
                            quote_id,
                            service_category=category_name,
                            sub_service=sub_service_name,
                            work_title=work_item.get("workTitle", ""),
                            description=work_item.get("description", ""),
                            quantity=pricing.get("quantity", 0),
                            pricing_method=work_item.get("pricingMethod", {}).get("name", "Unit"),
                            rate=pricing.get("rate", 0),
                            amount=pricing.get("amount", 0),
                            item_name=work_item.get("workTitle", ""),
                        ))

            if items_to_insert:
                get_supabase_client().table("quote_items").insert(items_to_insert).execute()

        # 3. THE TRIGGER: Call the same comparison engine used for PDFs
        comparison_result = await run_in_threadpool(run_comparison, session_id)
        
        # Return the exact same structure as your PDF endpoint!
        return {
            
            "status": "success",
            "session_id": session_id,
            "message": f"Successfully integrated and analyzed {len(quotes_list)} MongoDB quotes.",
            "report": comparison_result.get("report"),
            "chartData": comparison_result.get("chartData"),
            "tableData": comparison_result.get("tableData"),
            "vendors": comparison_result.get("vendors")
            
        }

    except Exception as e:
        print(f"❌ Mapping Error: {str(e)}")
        return {"status": "error", "message": str(e)}
   
@app.post("/api/sync-mongodb-quotes")
async def sync_mongodb_quotes(payload: Any = Body(...), session_id: str = None):
    """
    RECEIVES: Structured JSON from MongoDB (Single Object or List)
    SAVES: To Supabase 'quotes' and 'quote_items'
    RETURNS: Unified AI Comparison for all vendors
    """
    try:
        # 1. ROBUST SAFETY CHECK: Identify the list of quotes
        if isinstance(payload, dict) and "data" in payload:
            data_content = payload["data"]
            # Case A: Nested list [data: { quotes: [...] }]
            if isinstance(data_content, dict) and "quotes" in data_content:
                quotes_list = data_content["quotes"]
            # Case B: Single object wrapper [data: { ... }]
            else:
                quotes_list = [data_content]
        # Case C: Direct list of objects [[{...}, {...}]]
        elif isinstance(payload, list):
            quotes_list = payload
        # Case D: Single raw object
        elif isinstance(payload, dict):
            quotes_list = [payload]
        else:
            return {"status": "error", "message": "Invalid format. Expected JSON object or list."}

        print(f"📦 Processing {len(quotes_list)} quotes for session: {session_id}")

        for data in quotes_list:
            # --- VENDOR DATA EXTRACTION ---
            vendor_detail = data.get("vendorDetail", {})
            pricing_summary = data.get("pricingSummary", [])
            
            # Smart search for Grand Total (handles "Total", "Grand total", "Grand Total")
            grand_total = 0
            for item in pricing_summary:
                label = str(item.get("label", "")).lower()
                if "total" in label:
                    grand_total = item.get("value", 0)

            # --- STEP 1: PUSH TO 'quotes' TABLE ---
            quote_res = get_supabase_client().table("quotes").insert({
                "vendor_name": vendor_detail.get("companyName", "Unknown Vendor"),
                "grand_total": grand_total,
                "session_id": session_id,
                "source_type": "mongodb_integrated",
                "source_filename": data.get("quoteNumber", "DIRECT_SYNC"),
                #"quote_number": data.get("quoteNumber", "DIRECT_SYNC")
            }).execute()
            
            if not quote_res.data:
                continue
                
            quote_id = quote_res.data[0]['id']
            
            # --- STEP 2: PUSH TO 'quote_items' TABLE ---
            items_to_insert = []
            work_summary = data.get("workSummary", [])
            
            for summary in work_summary:
                for service_obj in summary.get("services", []):
                    # serviceId -> name
                    category_name = service_obj.get("serviceId", {}).get("name", "General")
                    
                    for work_item in service_obj.get("workItems", []):
                        from services.tatva_catalog import register_from_work_item
                        register_from_work_item(work_item)
                        # subService -> name
                        sub_service_name = work_item.get("subService", {}).get("name", work_item.get("workTitle"))
                        
                        # pricingInput extraction
                        pricing_list = work_item.get("pricingInput", [])
                        pricing = pricing_list[0] if pricing_list else {}
                        
                        items_to_insert.append(_quote_line_item(
                            quote_id,
                            service_category=category_name,
                            sub_service=sub_service_name,
                            work_title=work_item.get("workTitle", ""),
                            description=work_item.get("description", "").replace("&nbsp;", " "),
                            quantity=pricing.get("quantity", 0),
                            pricing_method=work_item.get("pricingMethod", {}).get("name", "Unit"),
                            rate=pricing.get("rate", 0),
                            amount=pricing.get("amount", 0),
                            item_name=work_item.get("workTitle", ""),
                        ))

            if items_to_insert:
                get_supabase_client().table("quote_items").insert(items_to_insert).execute()

        # --- STEP 3: THE TRIGGER ---
        # Now that ALL 3 vendors are in Supabase, run comparison once
        comparison_result = await run_in_threadpool(run_comparison, session_id)
        
        return {
            "status": "success",
            "session_id": session_id,
            "message": f"Successfully integrated and analyzed {len(quotes_list)} MongoDB quotes.",
            "report": comparison_result.get("report"),
            "chartData": comparison_result.get("chartData"),
            "tableData": comparison_result.get("tableData"),
            "vendors": comparison_result.get("vendors")
        }

    except Exception as e:
        print(f"❌ Mapping Error: {str(e)}")
        return {"status": "error", "message": str(e)} 
'''

def _parse_quotes_payload(payload: Any) -> list:
    """Normalize Tatva/MongoDB quote payloads to a list of quote dicts."""
    if payload is None:
        return []
    if isinstance(payload, list):
        return [q for q in payload if isinstance(q, dict) and q]
    if isinstance(payload, dict):
        if not payload:
            return []
        if "quote_ids" in payload and len(payload) <= 2:
            return []
        if "quotes" in payload and isinstance(payload["quotes"], list):
            return [q for q in payload["quotes"] if isinstance(q, dict) and q]
        if any(k in payload for k in ("quoteNumber", "vendorDetail", "workSummary")):
            return [payload]
    return []


def _quote_ids_from_payload(payload: Any) -> list:
    if isinstance(payload, dict):
        raw = payload.get("quote_ids") or payload.get("quoteIds")
        if isinstance(raw, list):
            return [str(x).strip() for x in raw if str(x).strip()]
    return []


def _ingest_quotes_to_supabase(quotes_list: list, session_id: str) -> int:
    """Push quote headers + line items to Supabase. Returns quotes ingested."""
    from datetime import datetime, timezone
    from services.market_rate import normalize_service_type, quote_number_is_rate_source_already

    ingested = 0
    for quote_entry in quotes_list:
        quote_data = _unwrap_mongodb_quote(quote_entry)
        vendor_detail = quote_data.get("vendorDetail", {})
        vendor_name = vendor_detail.get("companyName", "Unknown Vendor")
        meta = _mongodb_quote_metadata(quote_data)

        # quoteType is set once per quote on the Tatva platform (essential /
        # midlevel / luxury) — every line item inherits it for compare display.
        quote_service_type = normalize_service_type(quote_data.get("quoteType"))

        grand_total = 0
        for item in quote_data.get("pricingSummary", []):
            if "grand total" in str(item.get("label", "")).lower():
                grand_total = item.get("value", 0)

        # Detect re-uploaded quote numbers for staging bookkeeping only.
        # Market MA is only written for isFinalizeQuote payloads elsewhere.
        quote_number = meta["quote_number"]
        is_rate_duplicate = quote_number_is_rate_source_already(quote_number)
        if is_rate_duplicate:
            print(
                f"  ⚠️ Quote #{quote_number} ({vendor_name}) already staged before — "
                "keeping for comparison display."
            )

        quote_res = get_supabase_client().table("quotes").insert({
            "vendor_name": vendor_name,
            "client_name": meta["client_name"],
            "quote_date": meta["quote_date"],
            "quote_number": quote_number,
            "grand_total": grand_total,
            "session_id": session_id,
            "source_type": "mongodb_integrated",
            "source_filename": meta["source_filename"],
            "market_rates_applied_at": datetime.now(timezone.utc).isoformat() if is_rate_duplicate else None,
        }).execute()

        if not quote_res.data:
            continue

        quote_id = quote_res.data[0]["id"]
        ingested += 1

        items_to_insert = []
        for section in quote_data.get("workSummary", []):
            for service_obj in section.get("services", []):
                category_name = service_obj.get("serviceId", {}).get("name", "General")
                for work_item in service_obj.get("workItems", []):
                    from services.tatva_catalog import register_from_work_item
                    register_from_work_item(work_item)
                    sub_service_name = work_item.get("subService", {}).get("name", "General Service")
                    pricing_list = work_item.get("pricingInput", [])
                    pricing = pricing_list[0] if pricing_list else {}
                    items_to_insert.append(_quote_line_item(
                        quote_id,
                        service_category=category_name,
                        sub_service=sub_service_name,
                        work_title=work_item.get("workTitle", ""),
                        description=work_item.get("description", "").replace("&nbsp;", " "),
                        quantity=pricing.get("quantity", 0),
                        pricing_method=work_item.get("pricingMethod", {}).get("name", "Unit"),
                        rate=pricing.get("rate", 0),
                        amount=pricing.get("grandTotal", 0),
                        item_name=work_item.get("workTitle", ""),
                        service_type=quote_service_type,
                    ))

        if items_to_insert:
            get_supabase_client().table("quote_items").insert(items_to_insert).execute()

    return ingested


async def _run_mongodb_sync_pipeline(session_id: str, quotes_list: list):
    """Background worker: compare in-memory from payloads, persist to Supabase after."""
    total = len(quotes_list)
    try:
        # Learn Tatva ObjectIds from quote payloads so market-rate responses include them.
        from services.tatva_catalog import harvest_ids_from_quotes

        harvested = await run_in_threadpool(harvest_ids_from_quotes, quotes_list)
        print(
            f"📇 Catalog harvest: {harvested.get('work_items', 0)} work items → "
            f"{harvested.get('sub_services', 0)} sub-services, "
            f"{harvested.get('pricing_methods', 0)} pricing methods "
            f"(+{harvested.get('new_sub_services', 0)} / +{harvested.get('new_pricing_methods', 0)} new)"
        )

        _set_progress(
            session_id,
            status="processing",
            stage="comparing",
            processed=0,
            total=total,
            message=f"Building comparison matrix for {total} quotes…",
            result=None,
            error=None,
            partial=None,
        )

        def _publish_matrix(matrix):
            _set_progress(
                session_id,
                stage="recommending",
                partial=matrix,
                message="Matrix ready — writing Tatva Intelligence recommendation…",
            )

        def _compare_from_payload():
            df = mongodb_quotes_to_dataframe(quotes_list)
            result = run_comparison(
                session_id,
                _publish_matrix,
                df=df,
                fast_moving_avg=True,
            )
            return result, df

        comparison_result, compare_df = await run_in_threadpool(_compare_from_payload)

        if comparison_result.get("error"):
            _set_progress(
                session_id,
                status="error",
                message=comparison_result["error"],
                error=comparison_result["error"],
            )
            return

        try:
            await run_in_threadpool(_ingest_quotes_to_supabase, quotes_list, session_id)
            # Compare staging cleanup only — never write MA from the full session.
            await run_in_threadpool(finalize_session_market_rates, session_id, None)
            # If any payload in this request is already the user-finalized quote,
            # merge only those into market_moving_averages (deduped by quote number).
            await run_in_threadpool(
                lambda: apply_finalized_quotes_to_market_rates(
                    quotes_list, source="compare-session-payload"
                )
            )
        except Exception as persist_err:
            print(f"⚠️ Supabase persist/cleanup/finalize-MA failed for {session_id}: {persist_err}")

        _set_progress(
            session_id,
            status="done",
            stage="done",
            processed=total,
            message="Analysis complete.",
            result={
                "status": "success",
                "session_id": session_id,
                "report": comparison_result.get("report", ""),
                "chartData": comparison_result.get("chartData", []),
                "tableData": comparison_result.get("tableData", []),
                "vendors": comparison_result.get("vendors", []),
                "vendorMeta": comparison_result.get("vendorMeta", {}),
            },
        )

    except Exception as e:
        print(f"❌ MongoDB sync pipeline crash for {session_id}: {e}")
        _set_progress(session_id, status="error", message=str(e), error=str(e))


@app.post("/api/sync-mongodb-quotes")
async def sync_mongodb_quotes(
    request: Request,
    payload: Any = Body(default=None),
    session_id: str = None,
    project_id: str = None,
    authorization: Optional[str] = Header(None),
):
    """
    RECEIVES: Tatva/MongoDB quote JSON (list or single object), OR
    project_id + Authorization to fetch quotes from Tatva API (optional quote_ids in body).
    Returns immediately with session_id; poll /api/progress/{session_id}.
    """
    quotes_list = _parse_quotes_payload(payload)
    quote_ids = _quote_ids_from_payload(payload)

    query_project_id = project_id or request.query_params.get("project_id")
    auth_header = authorization or request.headers.get("authorization")

    if len(quotes_list) < MIN_COMPARE_QUOTES and query_project_id and auth_header:
        fetched = await run_in_threadpool(
            fetch_project_quotes, query_project_id, auth_header
        )
        quotes_list = fetched
        if quote_ids:
            quotes_list = filter_quotes_by_ids(quotes_list, quote_ids)

    if len(quotes_list) < MIN_COMPARE_QUOTES:
        if query_project_id and not auth_header:
            return {
                "status": "error",
                "message": (
                    "Authorization header required when fetching quotes by project_id. "
                    "Or POST full quote payloads in the body."
                ),
            }
        if query_project_id and auth_header:
            return {
                "status": "error",
                "message": (
                    f"Could not load enough quotes for project {query_project_id}. "
                    f"Provide quote_ids in the body to select {MIN_COMPARE_QUOTES}–{MAX_COMPARE_QUOTES} quotes, "
                    "or redirect users to QuoteSense /project/{code} to pick quotes in the UI."
                ),
            }
        return {
            "status": "error",
            "message": f"At least {MIN_COMPARE_QUOTES} quotes are required to compare.",
        }
    if len(quotes_list) > MAX_COMPARE_QUOTES:
        return {
            "status": "error",
            "message": f"You can compare at most {MAX_COMPARE_QUOTES} quotes at a time.",
        }

    if not session_id:
        session_id = f"session_{uuid.uuid4().hex[:8]}"

    print(f"📦 Queuing {len(quotes_list)} MongoDB/Tatva quotes for session: {session_id}")

    _set_progress(
        session_id,
        status="processing",
        stage="queued",
        processed=0,
        total=len(quotes_list),
        message="Queued — syncing quote payloads…",
        result=None,
        error=None,
        partial=None,
    )

    asyncio.create_task(_run_mongodb_sync_pipeline(session_id, quotes_list))

    return {
        "status": "processing",
        "session_id": session_id,
        "message": f"Received {len(quotes_list)} quotes. Comparison started.",
    }


@app.get("/api/get-comparison")
async def get_existing_comparison(session_id: str):
    """
    Used by the 'Auto-Lane' to fetch results for a session 
    that was already processed via MongoDB sync.
    """
    print(f"📥 Fetching data for Session: {session_id}...")
    
    # This calls the SAME comparison engine your PDF upload uses!
    comparison_result = await run_in_threadpool(run_comparison, session_id)
    
    return {
        "status": "success",
        "session_id": session_id,
        "report": comparison_result.get("report"),
        "chartData": comparison_result.get("chartData"),
        "tableData": comparison_result.get("tableData"),
        "vendors": comparison_result.get("vendors"),
        "vendorMeta": comparison_result.get("vendorMeta", {})
    }


@app.post("/api/chat")
async def chat_with_data(request: ChatRequest):
    """
    Receives a question from the frontend, queries the LLM with the session data,
    and returns the answer.
    """
    if not request.session_id:
        return {"reply": "Error: missing session ID. Please upload quotes first."} # Fixed spelling here too!
    
    answer = handle_chat_query(request.session_id, request.message)
    return {"reply": answer}
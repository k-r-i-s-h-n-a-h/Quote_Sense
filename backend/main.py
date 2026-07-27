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
    and/or quote_type_id ObjectId mapped from env).
    """
    message = (
        "quotation type is required — send service_type or quote_type_id "
        "(vendor must select Essential / Mid-segment / Luxury first)."
    )
    if bulk:
        return {"service_type": None, "count": 0, "items": [], "message": message}
    return {"recommend": False, "message": message}


async def _resolve_lookup_category(
    service_id: Optional[str],
    service_category: Optional[str],
    category_id: Optional[str] = None,
) -> tuple[Optional[str], Optional[dict]]:
    """
    Resolve the category name for the exact-bundle-match endpoints (suggest/lookup/recommend).

    service_category (name string) wins if given. Otherwise resolves an ObjectId —
    service_id or category_id (alias, same thing) — the same way /by-category does:
    Tatva services API first, then the static backend/data/tatva_service_ids.json fallback.
    Returns (category, None) on success, or (None, error_payload) on failure.
    """
    cat = (service_category or "").strip()
    if cat:
        return cat, None
    sid = (service_id or category_id or "").strip()
    if sid:
        resolved = await run_in_threadpool(resolve_service_by_id, sid)
        if not resolved:
            return None, {"recommend": False, "message": "Unknown category_id."}
        return resolved["service_category"], None
    return None, {"recommend": False, "message": "Provide category_id or service_category."}


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
    # Quotation type: send service_type (ESSENTIAL/…) and/or quote_type_id (Tatva ObjectId).
    service_type: Optional[str] = None
    quote_type_id: Optional[str] = None  # Tatva PM quotation-type ObjectId (from env map)
    service_id: Optional[str] = None
    category_id: Optional[str] = None  # alias for service_id — Tatva PM ObjectId
    service_category: Optional[str] = None
    sub_service: str
    pricing_method: str
    entered_rate: Optional[float] = None


class MarketRateSuggestRequest(BaseModel):
    """Vendor quote form (withtatva.ai) — exact bundle match for market guidance."""
    service_type: Optional[str] = None
    quote_type_id: Optional[str] = None
    service_id: Optional[str] = None
    category_id: Optional[str] = None  # alias for service_id — Tatva PM ObjectId
    service_category: Optional[str] = None
    sub_service: str
    pricing_method: str
    entered_rate: Optional[float] = None


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
    entered_rate: Optional[float] = None,
):
    """
    Bulk market rates for one Main Service.
    Prefer category_id (Tatva PM ObjectId; service_id accepted as an alias);
    service_category name also accepted. PM calls once when the user selects
    a service, then matches locally on sub_service + pricing_method without
    further API calls.

    Quotation type is required via service_type and/or quote_type_id (ObjectId
    mapped from env) — no ESSENTIAL fallback.

    Bulk responses are HTTP-cached for 2h; rate-specific verdict responses cache 5m (private).
    """
    rate = entered_rate if entered_rate and entered_rate > 0 else None
    obj_id = (category_id or service_id or "").strip() or None

    resolved_type, type_err = _require_service_type(
        service_type, quote_type_id, bulk=True
    )
    if type_err:
        if request.method == "HEAD":
            return Response(
                status_code=200,
                headers=_market_rate_by_category_cache_control(rate, error=True),
            )
        return _market_rate_by_category_response(type_err, rate, error=True)

    list_kwargs = {
        "sub_service": sub_service,
        "pricing_method": pricing_method,
        "entered_rate": rate,
    }

    if obj_id:
        resolved = await run_in_threadpool(resolve_service_by_id, obj_id)
        if not resolved:
            payload = {
                "category_id": obj_id,
                "service_type": resolved_type,
                "count": 0,
                "items": [],
                "message": "Unknown category_id.",
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
            **list_kwargs,
        )
        result["category_id"] = resolved["service_id"]
        result["service_id"] = resolved["service_id"]  # kept for backward compatibility
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
        if request.method == "HEAD":
            return Response(
                status_code=200,
                headers=_market_rate_by_category_cache_control(rate),
            )
        return _market_rate_by_category_response(result, rate)

    payload = {
        "service_type": resolved_type,
        "count": 0,
        "items": [],
        "message": "Provide category_id or service_category.",
    }
    if request.method == "HEAD":
        return Response(
            status_code=200,
            headers=_market_rate_by_category_cache_control(rate, error=True),
        )
    return _market_rate_by_category_response(payload, rate, error=True)


@app.get("/api/market-rate/lookup")
async def market_rate_lookup(
    sub_service: str,
    pricing_method: str,
    service_type: Optional[str] = None,
    quote_type_id: Optional[str] = None,
    service_id: Optional[str] = None,
    category_id: Optional[str] = None,
    service_category: Optional[str] = None,
):
    """Return market rate when exact bundle exists; otherwise recommend=false."""
    resolved_type, type_err = _require_service_type(service_type, quote_type_id)
    if type_err:
        return type_err
    cat, error = await _resolve_lookup_category(service_id, service_category, category_id)
    if error:
        return error
    return await run_in_threadpool(
        recommend_rate,
        resolved_type,
        cat,
        sub_service,
        pricing_method,
        None,
    )


@app.get("/api/market-rate/suggest")
async def market_rate_suggest_get(
    sub_service: str,
    pricing_method: str,
    service_type: Optional[str] = None,
    quote_type_id: Optional[str] = None,
    service_id: Optional[str] = None,
    category_id: Optional[str] = None,
    service_category: Optional[str] = None,
    entered_rate: Optional[float] = None,
):
    """
    Unified vendor-form endpoint (GET) — single exact-bundle match, no bulk scan.
    Quotation type via service_type and/or quote_type_id (env-mapped ObjectId).
    Call with entered_rate on Rate blur; banner only when rate is above base.
    """
    resolved_type, type_err = _require_service_type(service_type, quote_type_id)
    if type_err:
        return type_err
    cat, error = await _resolve_lookup_category(service_id, service_category, category_id)
    if error:
        return error
    return await run_in_threadpool(
        recommend_rate,
        resolved_type,
        cat,
        sub_service,
        pricing_method,
        entered_rate if entered_rate and entered_rate > 0 else None,
    )


@app.post("/api/market-rate/suggest")
async def market_rate_suggest_post(body: MarketRateSuggestRequest):
    """
    Unified vendor-form endpoint (POST) — preferred for withtatva.ai quote form.
    Include entered_rate on Rate blur. Only recommend=true when above base rate.
    """
    resolved_type, type_err = _require_service_type(body.service_type, body.quote_type_id)
    if type_err:
        return type_err
    cat, error = await _resolve_lookup_category(
        body.service_id, body.service_category, body.category_id
    )
    if error:
        return error
    rate = body.entered_rate if body.entered_rate and body.entered_rate > 0 else None
    return await run_in_threadpool(
        recommend_rate,
        resolved_type,
        cat,
        body.sub_service,
        body.pricing_method,
        rate,
    )


@app.post("/api/market-rate/recommend")
async def market_rate_recommend(body: MarketRateRequest):
    """
    Compare entered raw rate against stored market average for the bundle.
    Quotation type via service_type and/or quote_type_id — no ESSENTIAL fallback.
    """
    resolved_type, type_err = _require_service_type(body.service_type, body.quote_type_id)
    if type_err:
        return type_err
    cat, error = await _resolve_lookup_category(
        body.service_id, body.service_category, body.category_id
    )
    if error:
        return error
    return await run_in_threadpool(
        recommend_rate,
        resolved_type,
        cat,
        body.sub_service,
        body.pricing_method,
        body.entered_rate,
    )


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
            await run_in_threadpool(finalize_session_market_rates, session_id, None)
        except Exception as finalize_err:
            print(f"⚠️ Market rate finalize failed for {session_id}: {finalize_err}")

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
        # midlevel / luxury) — every line item inherits it. Real submitted quotes
        # now feed market_moving_averages directly per their own tier, instead of
        # the old math-derived Mid-segment/Luxury rows (Essential × multiplier).
        quote_service_type = normalize_service_type(quote_data.get("quoteType"))

        grand_total = 0
        for item in quote_data.get("pricingSummary", []):
            if "grand total" in str(item.get("label", "")).lower():
                grand_total = item.get("value", 0)

        # Detect re-uploaded quotes; pre-mark to prevent double-counting in moving avg.
        quote_number = meta["quote_number"]
        is_rate_duplicate = quote_number_is_rate_source_already(quote_number)
        if is_rate_duplicate:
            print(
                f"  ⚠️ Quote #{quote_number} ({vendor_name}) already in market rates — "
                "keeping for comparison display but skipping rate re-application."
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
            # Pass None so finalize always re-fetches from DB — needed for duplicate
            # quote filtering (pre-marked market_rates_applied_at) and quote_id linkage.
            await run_in_threadpool(finalize_session_market_rates, session_id, None)
        except Exception as persist_err:
            print(f"⚠️ Supabase persist/finalize failed for {session_id}: {persist_err}")

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
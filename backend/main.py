from fastapi import FastAPI, UploadFile, File, Form, Body, Header, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.concurrency import run_in_threadpool
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

MIN_COMPARE_QUOTES = 2
MAX_COMPARE_QUOTES = 3

app = FastAPI(title="QuoteSense API")

# FIXED: We added both port 3000 and 3001 to ensure Next.js never gets blocked!
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=False,
    allow_methods=["*"],
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


@app.on_event("startup")
async def _startup_diagnostics():
    """Probe local environment once at boot — writes to debug log for diagnosis."""
    diag = env_diagnostics()
    supabase_ok = False
    sessions_ok = False
    supabase_err = None
    sessions_err = None

    if diag["supabase_configured"]:
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

    _agent_debug_log(
        "main.py:startup",
        "backend startup diagnostics",
        {
            **diag,
            "market_moving_averages_ok": supabase_ok,
            "market_moving_avg_sessions_ok": sessions_ok,
            "market_moving_averages_err": supabase_err,
            "market_moving_avg_sessions_err": sessions_err,
            "python_ok": True,
        },
        hypothesis_id="E",
    )


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

class ChatRequest(BaseModel):
    session_id: str
    message: str

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
                        
                        items_to_insert.append({
                            "quote_id": quote_id,
                            "service_category": category_name,
                            "sub_service": sub_service_name,
                            "work_title": work_item.get("workTitle", ""),
                            "description": work_item.get("description", ""),
                            "quantity": pricing.get("quantity", 0),
                            "pricing_method": work_item.get("pricingMethod", {}).get("name", "Unit"),
                            "rate": pricing.get("rate", 0),
                            "amount": pricing.get("amount", 0)
                        })

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
                        
                        items_to_insert.append({
                            "quote_id": quote_id,
                            "service_category": category_name,
                            "sub_service": sub_service_name,
                            "work_title": work_item.get("workTitle", ""),
                            "description": work_item.get("description", "").replace("&nbsp;", " "),
                            "quantity": pricing.get("quantity", 0),
                            "pricing_method": work_item.get("pricingMethod", {}).get("name", "Unit"),
                            "rate": pricing.get("rate", 0),
                            "amount": pricing.get("amount", 0),
                           # "quote_number": data.get("quoteNumber", "DIRECT_SYNC")
                        })

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
    ingested = 0
    for quote_entry in quotes_list:
        quote_data = _unwrap_mongodb_quote(quote_entry)
        vendor_detail = quote_data.get("vendorDetail", {})
        vendor_name = vendor_detail.get("companyName", "Unknown Vendor")
        meta = _mongodb_quote_metadata(quote_data)

        grand_total = 0
        for item in quote_data.get("pricingSummary", []):
            if "grand total" in str(item.get("label", "")).lower():
                grand_total = item.get("value", 0)

        quote_res = get_supabase_client().table("quotes").insert({
            "vendor_name": vendor_name,
            "client_name": meta["client_name"],
            "quote_date": meta["quote_date"],
            "quote_number": meta["quote_number"],
            "grand_total": grand_total,
            "session_id": session_id,
            "source_type": "mongodb_integrated",
            "source_filename": meta["source_filename"],
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
                    items_to_insert.append({
                        "quote_id": quote_id,
                        "service_category": category_name,
                        "sub_service": sub_service_name,
                        "work_title": work_item.get("workTitle", ""),
                        "description": work_item.get("description", "").replace("&nbsp;", " "),
                        "quantity": pricing.get("quantity", 0),
                        "pricing_method": work_item.get("pricingMethod", {}).get("name", "Unit"),
                        "rate": pricing.get("rate", 0),
                        "amount": pricing.get("grandTotal", 0),
                    })

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
            return run_comparison(
                session_id,
                _publish_matrix,
                df=df,
                fast_moving_avg=True,
            )

        comparison_result = await run_in_threadpool(_compare_from_payload)

        if comparison_result.get("error"):
            _set_progress(
                session_id,
                status="error",
                message=comparison_result["error"],
                error=comparison_result["error"],
            )
            return

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

        # Persist to Supabase in the background for chat / history (non-blocking).
        async def _persist():
            try:
                await run_in_threadpool(_ingest_quotes_to_supabase, quotes_list, session_id)
            except Exception as persist_err:
                print(f"⚠️ Background Supabase persist failed for {session_id}: {persist_err}")

        asyncio.create_task(_persist())

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
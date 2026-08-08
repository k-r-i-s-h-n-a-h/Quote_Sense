import sys
import os
import json
import time

sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), '../../')))
from backend.models.schema import ExtractedQuote

from services.env_config import get_gemini_client, get_supabase_client
from services.market_rate import DEFAULT_SERVICE_TYPE
from services.extraction_cache import get_extraction_cached_content_name
from services.taxonomy_prompt import build_extraction_system_instruction

EXTRACT_MODEL = os.getenv("GEMINI_EXTRACT_MODEL", "gemini-2.5-flash")


def process_quote_with_gemini(pdf_path, temperature=0.0, extra_instruction=""):
    from google.genai import types

    print(f"  -> Sending {os.path.basename(pdf_path)} to Tatva Intelligence ({EXTRACT_MODEL})...")

    with open(pdf_path, "rb") as f:
        pdf_bytes = f.read()

    client = get_gemini_client()
    is_retry = bool(extra_instruction and extra_instruction.strip())

    # Retries add dynamic hints — bypass cache so the hint is in-context.
    cached_content = None if is_retry else get_extraction_cached_content_name(EXTRACT_MODEL)

    if cached_content:
        contents = [
            types.Part.from_bytes(data=pdf_bytes, mime_type="application/pdf"),
            types.Part.from_text(
                text="Extract this vendor quote PDF into JSON matching the response schema."
            ),
        ]
        print("  ⚡ Using cached extraction rules + taxonomy (explicit context cache)")
    else:
        # Static prefix FIRST → Gemini 2.5 implicit cache can hit on PDF 2/3 in same batch.
        static_prefix = build_extraction_system_instruction(extra_instruction)
        contents = [
            types.Part.from_text(text=static_prefix),
            types.Part.from_bytes(data=pdf_bytes, mime_type="application/pdf"),
            types.Part.from_text(text="Extract the quote from the PDF above into JSON."),
        ]
        if is_retry:
            print("  🔁 Retry extraction with inline prompt (reconcile hint)")
        else:
            print("  📄 Inline static prefix + PDF (implicit cache friendly order)")

    response = client.models.generate_content(
        model=EXTRACT_MODEL,
        contents=contents,
        config=types.GenerateContentConfig(
            response_mime_type="application/json",
            response_schema=ExtractedQuote,
            temperature=temperature,
            cached_content=cached_content,
        ),
    )

    usage = getattr(response, "usage_metadata", None)
    if usage:
        cached_tokens = getattr(usage, "cached_content_token_count", None) or getattr(
            usage, "cachedContentTokenCount", 0
        )
        if cached_tokens:
            print(f"  📊 Cache hit: {cached_tokens} tokens from context cache")

    return json.loads(response.text)


def push_to_supabase(structured_data, filename, session_id):
    from datetime import datetime, timezone
    from services.market_rate import quote_number_is_rate_source_already

    quote_number = str(structured_data.get("quote_number", "") or "").lstrip("#").strip()

    # If this quote_number was already staged in a previous session, pre-set
    # market_rates_applied_at for cleanup bookkeeping (compare never writes MA).
    is_rate_duplicate = quote_number_is_rate_source_already(quote_number)
    if is_rate_duplicate:
        print(
            f"  ⚠️ Quote #{quote_number} already staged before — "
            "keeping for comparison display."
        )

    quote_payload = {
        "vendor_name": structured_data.get("vendor_name", "Unknown"),
        "client_name": structured_data.get("client_name", "Unknown"),
        "quote_date": structured_data.get("quote_date", ""),
        "grand_total": structured_data.get("grand_total", 0.0),
        "source_filename": filename,
        "session_id": session_id,
        "quote_number": quote_number,
        # Pre-mark duplicate quote numbers for staging lifecycle.
        "market_rates_applied_at": datetime.now(timezone.utc).isoformat() if is_rate_duplicate else None,
    }

    print(f"  -> Pushing metadata for {quote_payload['vendor_name']}...")
    try:
        quote_res = get_supabase_client().table("quotes").insert(quote_payload).execute()
    except Exception as e:
        if "quote_number" in str(e):
            print("  -> 'quote_number' column missing in Supabase; inserting without it.")
            quote_payload.pop("quote_number", None)
            quote_res = get_supabase_client().table("quotes").insert(quote_payload).execute()
        else:
            raise
    new_quote_id = quote_res.data[0]["id"]

    items_payload = []
    for service in structured_data.get("services", []):
        for item in service.get("items", []):
            items_payload.append({
                "quote_id": new_quote_id,
                "service_type": DEFAULT_SERVICE_TYPE,
                "service_category": service.get("service_category", "General"),
                "sub_service": item.get("sub_service", "Unknown"),
                "item_name": str(item.get("item_name", "") or "").strip(),
                "work_title": item.get("work_title", ""),
                "description": item.get("description", ""),
                "quantity": item.get("quantity", 0.0),
                "pricing_method": item.get("pricing_method", ""),
                "rate": item.get("rate", 0.0),
                "amount": item.get("amount", 0.0),
            })

    print(f"  -> Pushing {len(items_payload)} line items...")
    if items_payload:
        try:
            get_supabase_client().table("quote_items").insert(items_payload).execute()
        except Exception as e:
            if "item_name" in str(e):
                print("  -> 'item_name' column missing in Supabase; inserting without it.")
                for it in items_payload:
                    it.pop("item_name", None)
                get_supabase_client().table("quote_items").insert(items_payload).execute()
            else:
                raise


def validate_extraction(structured_data):
    """Reconcile line-item sum vs printed subtotal. Returns (ok, message, should_retry)."""
    line_sum = 0.0
    item_count = 0
    for service in structured_data.get("services", []):
        for item in service.get("items", []):
            item_count += 1
            try:
                line_sum += float(item.get("amount", 0) or 0)
            except (TypeError, ValueError):
                pass

    try:
        subtotal = float(structured_data.get("subtotal", 0) or 0)
    except (TypeError, ValueError):
        subtotal = 0.0

    if subtotal <= 0:
        return True, f"no subtotal to reconcile ({item_count} items, sum {line_sum:.0f})", False

    diff = abs(line_sum - subtotal)
    tolerance = max(0.02 * subtotal, 1.0)
    severe_tolerance = max(0.10 * subtotal, 1.0)
    if diff <= tolerance:
        return True, f"reconciled: {item_count} items sum {line_sum:.0f} ≈ subtotal {subtotal:.0f}", False

    should_retry = diff > severe_tolerance
    return (
        False,
        f"MISMATCH: {item_count} items sum {line_sum:.0f} vs subtotal {subtotal:.0f} "
        f"(diff {diff:.0f}){' — likely missed rows' if should_retry else ' — minor, accepting'}",
        should_retry,
    )


def process_single_pdf(file_path, session_id):
    filename = os.path.basename(file_path)
    max_reconcile_attempts = 2
    max_error_retries = 2

    error_retries = 0
    reconcile_attempt = 0
    structured_data = None

    while reconcile_attempt < max_reconcile_attempts:
        is_retry = reconcile_attempt > 0
        try:
            structured_data = process_quote_with_gemini(
                file_path,
                temperature=0.4 if is_retry else 0.0,
                extra_instruction=(
                    "PREVIOUS ATTEMPT MISSED ROWS: your extracted line items did not "
                    "sum to the printed Subtotal. Re-read the services table carefully "
                    "and include EVERY numbered row from all pages."
                    if is_retry
                    else ""
                ),
            )
        except Exception as e:
            error_retries += 1
            print(f"⚠️ Extraction error for {filename}: {e}")
            if error_retries <= max_error_retries:
                time.sleep(2)
                continue
            print(f"❌ Permanent failure for {filename} after {max_error_retries} error retries.")
            return

        print(f"\n🔥 --- RAW GEMINI JSON OUTPUT FOR {filename} --- 🔥")
        print(
            f"  -> Extracted vendor='{structured_data.get('vendor_name')}' "
            f"quote_number='{structured_data.get('quote_number')}' "
            f"quote_date='{structured_data.get('quote_date')}'"
        )

        ok, msg, should_retry = validate_extraction(structured_data)
        if ok:
            print(f"  -> ✅ Reconciliation OK — {msg}")
            break

        if not should_retry:
            print(f"  -> ⚠️ {msg}. Accepting without a retry.")
            break

        reconcile_attempt += 1
        if reconcile_attempt < max_reconcile_attempts:
            print(f"  -> ⚠️ {msg}. Re-extracting once with a stronger hint...")
        else:
            print(f"  -> ⚠️ {msg}. Saving best-effort extraction.")

    if structured_data is None:
        return

    push_to_supabase(structured_data, filename, session_id)
    print(f"✅ Successfully processed {filename}")

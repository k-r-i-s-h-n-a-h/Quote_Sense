import sys
import os
import json
import time

# import schema and taxonomy
sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), '../../')))
from backend.models.schema import ExtractedQuote
from backend.models.taxanomy import TATVAOPS_TAXONOMY

from services.env_config import get_gemini_client, get_supabase_client

def process_quote_with_gemini(pdf_path, temperature=0.0, extra_instruction=""):
    from google.genai import types

    print(f"  -> Sending {os.path.basename(pdf_path)} to Tatva Intelligence...")

    # Send the PDF inline instead of via the Files API. This avoids a separate
    # upload round-trip, the fixed processing sleep, and a delete call — three
    # network hops removed per quote. (Inline is supported for PDFs up to ~20MB.)
    with open(pdf_path, "rb") as f:
        pdf_bytes = f.read()

    schema_json = ExtractedQuote.model_json_schema()

    prompt = f"""
    You are an elite Data Extraction AI. Your ONLY job is to visually inspect this PDF quote, EXTRACT the values, and POPULATE the JSON.
    
    CRITICAL EXTRACTION RULES:
    1. STRICT EXTRACTION: Do not guess. Extract the exact numbers and names.
    2. 🎯 TABLE EXTRACTION FOCUS: The most important part of this document is the services table in the middle. It has columns like DESCRIPTION, QTY, RATE, PRICING, and AMOUNT. You MUST extract EVERY SINGLE numbered row from this table — do not skip, merge, or summarize rows. If the table spans multiple pages, include rows from all pages.
    3. 🎯 PARSING THE DESCRIPTION: The 'DESCRIPTION' column often contains things stacked on top of each other (e.g. 1. Item label, 2. Room/Location, 3. SAC Code, 4. a long scope paragraph). Separate them like this:
       - 'item_name': copy the item label VERBATIM exactly as printed (e.g. 'Granite', 'Loft', 'Wall Decor', 'Wardrobe', 'Tandem Pullouts'). DO NOT rename or normalize it.
       - 'sub_service': map that item to the closest MASTER TAXONOMY sub-service (this is allowed to differ from item_name).
       - 'work_title': the room/location (e.g. 'Kitchen', 'Master bedroom', 'Balcony', 'Overall space').
       - 'description': the long scope/material paragraph.
    4. IGNORE FLUFF: Ignore long paragraphs like "Scope of Work", "Materials & Equipment", or "Terms & Conditions". Focus ONLY on the table data.
    5. FAULT TOLERANCE: If a service is mentioned but lacks a price, extract it and set numbers to 0.0.
    6. 🎯 TOTALS: Also extract the 'Subtotal' (sum of all line-item amounts, BEFORE TatvaOps service charges and taxes) into 'subtotal', and the final 'GRAND TOTAL' into 'grand_total'.

    🔥 THE MASTER TAXONOMY (YOUR WORD BANK):
    When assigning a 'service_category' or 'sub_service', you MUST choose the exact matching string from this dictionary.
    {json.dumps(TATVAOPS_TAXONOMY, indent=2)}

    DICTIONARY (JSON Structure Rules):
    {json.dumps(schema_json, indent=2)}

    Output ONLY valid JSON exactly matching the schema above.
    {extra_instruction}
    """

    response = get_gemini_client().models.generate_content(
        model='gemini-3.5-flash',
        contents=[
            types.Part.from_bytes(data=pdf_bytes, mime_type='application/pdf'),
            prompt,
        ],
        config=types.GenerateContentConfig(
            response_mime_type="application/json",
            temperature=temperature,
        ),
    )

    return json.loads(response.text)

def push_to_supabase(structured_data, filename, session_id):
    quote_number = str(structured_data.get("quote_number", "") or "").lstrip("#").strip()

    quote_payload = {
        "vendor_name": structured_data.get("vendor_name", "Unknown"),
        "client_name": structured_data.get("client_name", "Unknown"),
        "quote_date": structured_data.get("quote_date", ""),
        "grand_total": structured_data.get("grand_total", 0.0),
        "source_filename": filename,
        "session_id": session_id,
        "quote_number": quote_number,
    }

    print(f"  -> Pushing metadata for {quote_payload['vendor_name']}...")
    try:
        quote_res = get_supabase_client().table("quotes").insert(quote_payload).execute()
    except Exception as e:
        # The 'quote_number' column may not exist yet — fall back without it so the
        # pipeline keeps working. Add the column in Supabase to enable it (see notes).
        if "quote_number" in str(e):
            print("  -> 'quote_number' column missing in Supabase; inserting without it.")
            quote_payload.pop("quote_number", None)
            quote_res = get_supabase_client().table("quotes").insert(quote_payload).execute()
        else:
            raise
    new_quote_id = quote_res.data[0]['id']
    
    items_payload = []
    for service in structured_data.get("services", []):
        for item in service.get("items", []):
            items_payload.append({
                "quote_id": new_quote_id,
                "service_category": service.get("service_category", "General"),
                "sub_service": item.get("sub_service", "Unknown"),
                "item_name": str(item.get("item_name", "") or "").strip(),
                "work_title": item.get("work_title", ""),
                "description": item.get("description", ""),
                "quantity": item.get("quantity", 0.0),
                "pricing_method": item.get("pricing_method", ""),
                "rate": item.get("rate", 0.0),
                "amount": item.get("amount", 0.0)
            })
            
    print(f"  -> Pushing {len(items_payload)} line items...")
    if items_payload:
        try:
            get_supabase_client().table("quote_items").insert(items_payload).execute()
        except Exception as e:
            # 'item_name' column may not exist yet — retry without it so the
            # pipeline keeps working. Add the column to enable it (see notes).
            if "item_name" in str(e):
                print("  -> 'item_name' column missing in Supabase; inserting without it.")
                for it in items_payload:
                    it.pop("item_name", None)
                get_supabase_client().table("quote_items").insert(items_payload).execute()
            else:
                raise

def validate_extraction(structured_data):
    """Reconcile the sum of extracted line items against the quote's subtotal.

    Returns (ok: bool, message: str, should_retry: bool).
      - ok:           within 2% — extraction is trustworthy.
      - should_retry: off by more than 10% — likely whole rows missed, so a
                      re-extraction is worth the extra Gemini call.
      - in between (2-10%): accept best-effort WITHOUT a retry. A small gap is
                      usually rounding/taxes, not missing rows, so paying for a
                      second full extraction there just doubles the time for no
                      real gain.
    """
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
    tolerance = max(0.02 * subtotal, 1.0)        # within 2% = good
    severe_tolerance = max(0.10 * subtotal, 1.0)  # off >10% = likely missed rows
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
    # Reconciliation re-extraction is capped at ONE retry: the first pass is
    # deterministic (temperature 0); the retry raises the temperature and adds an
    # explicit "you missed rows" hint so it can actually produce a different (better)
    # result. Re-running an identical deterministic prompt only reproduces the gap.
    max_reconcile_attempts = 2
    # Independent budget for hard failures (network/JSON errors), worth a quick retry.
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
                    if is_retry else ""
                ),
            )
        except Exception as e:
            error_retries += 1
            print(f"⚠️ Extraction error for {filename}: {e}")
            if error_retries <= max_error_retries:
                time.sleep(2)
                continue  # transient failure: retry without spending a reconcile attempt
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

        # Only spend a second (expensive) extraction when the gap is large enough
        # to suggest whole rows were missed. Minor gaps are accepted as-is.
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
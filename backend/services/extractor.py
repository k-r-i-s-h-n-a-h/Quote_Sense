import sys
import os
import json
import time 
from dotenv import load_dotenv
from supabase import Client, create_client

# 1. NEW GOOGLE SDK IMPORTS
from google import genai
from google.genai import types

# import schema and taxonomy
sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), '../../')))
from backend.models.schema import ExtractedQuote
from backend.models.taxanomy import TATVAOPS_TAXONOMY

load_dotenv()

# 2. NEW GEMINI CLIENT INITIALIZATION
gemini_client = genai.Client(api_key=os.getenv("GEMINI_API_KEY"))

supabase: Client = create_client(
    os.getenv("SUPABASE_URL"),
    os.getenv("SUPABASE_SERVICE_ROLE_KEY")
)

def process_quote_with_gemini(pdf_path):
    print(f"  -> Uploading {os.path.basename(pdf_path)} to Gemini Vision API...")

    # 3. NEW UPLOAD SYNTAX
    pdf_file = gemini_client.files.upload(file=pdf_path, config={'mime_type': 'application/pdf'})
    
    # Give Google a brief second to process the document
    time.sleep(2)

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
    """

    # 4. NEW GENERATE CONTENT SYNTAX (Using 2.5 Flash!)
    response = gemini_client.models.generate_content(
        model='gemini-2.5-flash',
        contents=[pdf_file, prompt],
        config=types.GenerateContentConfig(
            response_mime_type="application/json",
            temperature=0.0,
        ),
    )

    # 5. NEW DELETE SYNTAX
    gemini_client.files.delete(name=pdf_file.name)
    
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
        quote_res = supabase.table("quotes").insert(quote_payload).execute()
    except Exception as e:
        # The 'quote_number' column may not exist yet — fall back without it so the
        # pipeline keeps working. Add the column in Supabase to enable it (see notes).
        if "quote_number" in str(e):
            print("  -> 'quote_number' column missing in Supabase; inserting without it.")
            quote_payload.pop("quote_number", None)
            quote_res = supabase.table("quotes").insert(quote_payload).execute()
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
            supabase.table("quote_items").insert(items_payload).execute()
        except Exception as e:
            # 'item_name' column may not exist yet — retry without it so the
            # pipeline keeps working. Add the column to enable it (see notes).
            if "item_name" in str(e):
                print("  -> 'item_name' column missing in Supabase; inserting without it.")
                for it in items_payload:
                    it.pop("item_name", None)
                supabase.table("quote_items").insert(items_payload).execute()
            else:
                raise

def validate_extraction(structured_data):
    """Reconcile the sum of extracted line items against the quote's subtotal.

    Returns (ok: bool, message: str). When the model misses rows, the line-item
    sum falls short of the printed subtotal, which we use to trigger a re-try.
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
        return True, f"no subtotal to reconcile ({item_count} items, sum {line_sum:.0f})"

    diff = abs(line_sum - subtotal)
    tolerance = max(0.02 * subtotal, 1.0)  # allow 2% for rounding
    if diff <= tolerance:
        return True, f"reconciled: {item_count} items sum {line_sum:.0f} ≈ subtotal {subtotal:.0f}"
    return (
        False,
        f"MISMATCH: {item_count} items sum {line_sum:.0f} vs subtotal {subtotal:.0f} "
        f"(diff {diff:.0f}) — likely missed rows",
    )


def process_single_pdf(file_path, session_id):
    filename = os.path.basename(file_path)
    max_retries = 3
    retry_count = 0
    
    while retry_count < max_retries:
        try:
            structured_data = process_quote_with_gemini(file_path)
            
            print(f"\n🔥 --- RAW GEMINI JSON OUTPUT FOR {filename} --- 🔥")
            print(
                f"  -> Extracted vendor='{structured_data.get('vendor_name')}' "
                f"quote_number='{structured_data.get('quote_number')}' "
                f"quote_date='{structured_data.get('quote_date')}'"
            )

            ok, msg = validate_extraction(structured_data)
            is_last_attempt = retry_count >= max_retries - 1
            if ok:
                print(f"  -> ✅ Reconciliation OK — {msg}")
            elif not is_last_attempt:
                # Numbers don't add up: re-extract to try to recover missed rows.
                print(f"  -> ⚠️ {msg}. Re-extracting (attempt {retry_count + 1}/{max_retries})...")
                retry_count += 1
                time.sleep(5)
                continue
            else:
                # Last attempt: push anyway, but flag the gap loudly.
                print(f"  -> ⚠️ {msg}. Out of retries — saving best-effort extraction.")

            push_to_supabase(structured_data, filename, session_id)
            print(f"✅ Successfully processed {filename} on attempt {retry_count + 1}")
            return # Exit function on success
            
        except Exception as e:
            retry_count += 1
            print(f"⚠️ Attempt {retry_count} failed for {filename}: {e}")
            if retry_count < max_retries:
                time.sleep(5) # Wait 5 seconds before retrying
            else:
                print(f"❌ Permanent Failure for {filename} after {max_retries} attempts.")
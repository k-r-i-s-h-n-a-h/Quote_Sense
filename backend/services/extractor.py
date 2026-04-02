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
    2. 🎯 TABLE EXTRACTION FOCUS: The most important part of this document is the services table in the middle. It has columns like DESCRIPTION, QTY, RATE, PRICING, and AMOUNT. You MUST extract every single row from this table.
    3. 🎯 PARSING THE DESCRIPTION: The 'DESCRIPTION' column often contains three things stacked on top of each other (1. Sub-Service Name, 2. Work Title, 3. SAC Code). Read carefully and separate these into the correct JSON fields.
    4. IGNORE FLUFF: Ignore long paragraphs like "Scope of Work", "Materials & Equipment", or "Terms & Conditions". Focus ONLY on the table data.
    5. FAULT TOLERANCE: If a service is mentioned but lacks a price, extract it and set numbers to 0.0.

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
    quote_payload = {
        "vendor_name": structured_data.get("vendor_name", "Unknown"),
        "client_name": structured_data.get("client_name", "Unknown"),
        "quote_date": structured_data.get("quote_date", ""),
        "grand_total": structured_data.get("grand_total", 0.0),
        "source_filename": filename,
        "session_id": session_id ,
        "quote_number":structured_data.get("vendor_name", "Unknown"),
      
    }
    
    print(f"  -> Pushing metadata for {quote_payload['vendor_name']}...")
    quote_res = supabase.table("quotes").insert(quote_payload).execute()
    new_quote_id = quote_res.data[0]['id']
    
    items_payload = []
    for service in structured_data.get("services", []):
        for item in service.get("items", []):
            items_payload.append({
                "quote_id": new_quote_id,
                "service_category": service.get("service_category", "General"),
                "sub_service": item.get("sub_service", "Unknown"),
                "work_title": item.get("work_title", ""),
                "description": item.get("description", ""),
                "quantity": item.get("quantity", 0.0),
                "pricing_method": item.get("pricing_method", ""),
                "rate": item.get("rate", 0.0),
                "amount": item.get("amount", 0.0)
            })
            
    print(f"  -> Pushing {len(items_payload)} line items...")
    if items_payload:
        supabase.table("quote_items").insert(items_payload).execute()

def process_single_pdf(file_path, session_id):
    filename = os.path.basename(file_path)
    max_retries = 3
    retry_count = 0
    
    while retry_count < max_retries:
        try:
            structured_data = process_quote_with_gemini(file_path)
            
            print(f"\n🔥 --- RAW GEMINI JSON OUTPUT FOR {filename} --- 🔥")
            # (Optional: limit print size if JSON is huge)
            
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
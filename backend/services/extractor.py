import sys
import os
import json

sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), '../../')))

from dotenv import load_dotenv
from supabase import create_client, Client
from backend.models.schema import ExtractedQuote
from groq import Groq
import fitz

load_dotenv()

groq_client = Groq(api_key=os.getenv("GROQ_API_KEY"))
supabase: Client = create_client(
    os.getenv("SUPABASE_URL"),
    os.getenv("SUPABASE_SERVICE_ROLE_KEY")
)

def extract_text_from_pdf(pdf_path):
    doc = fitz.open(pdf_path)
    text = ""
    for page in doc:
        text += page.get_text()
    return text

def process_quote_with_llm(text):
    schema_json = ExtractedQuote.model_json_schema()
    prompt = f"""
    You are an expert data extraction AI for interior design quotes.
    Extract the vendor details, client details, and all line items from the following quote text.
    Normalize the line items strictly according to this JSON schema:
    {json.dumps(schema_json, indent=2)}

    Return ONLY valid JSON matching this exact schema. Do not include markdown formatting like ```json.
    
    Quote Text:
    {text}
    """
    response = groq_client.chat.completions.create(
        model="llama-3.3-70b-versatile",
        messages=[{"role": "user", "content": prompt}],
        temperature=0, 
        response_format={"type": "json_object"}
    )
    return json.loads(response.choices[0].message.content)

def push_to_supabase(structured_data, filename, session_id):
    quote_payload = {
        "vendor_name": structured_data["vendor_name"],
        "client_name": structured_data["client_name"],
        "quote_date": structured_data["quote_date"],
        "grand_total": structured_data["grand_total"],
        "source_filename": filename,
        "session_id": session_id  # This links the file to the specific web upload!
    }
    
    print(f"  -> Pushing metadata for {quote_payload['vendor_name']}...")
    quote_res = supabase.table("quotes").insert(quote_payload).execute()
    new_quote_id = quote_res.data[0]['id']
    
    items_payload = []
    for item in structured_data["items"]:
        item["quote_id"] = new_quote_id 
        items_payload.append(item)
        
    print(f"  -> Pushing {len(items_payload)} line items...")
    supabase.table("quote_items").insert(items_payload).execute()

def process_single_pdf(file_path, session_id):
    """This is the function FastAPI was looking for!"""
    filename = os.path.basename(file_path)
    try:
        raw_text = extract_text_from_pdf(file_path)
        print(f"  -> Extracting structured data via LLM for {filename}...")
        structured_data = process_quote_with_llm(raw_text)
        push_to_supabase(structured_data, filename, session_id)
        print(f" Successfully processed {filename}")
    except Exception as e:
        print(f" Failed to process {filename}: {e}")

# (We can remove the old main() function since FastAPI is now the boss)
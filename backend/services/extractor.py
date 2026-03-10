import sys
import os
import json

# Ensure Python can find the 'backend' folder when running this script directly
sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), '../../')))

from dotenv import load_dotenv
from supabase import create_client, Client
from backend.models.schema import ExtractedQuote
from groq import Groq
import fitz

# Load environment variables
load_dotenv()

# Initialize Clients - FIXED TYPO: 'api_key' instead of 'api_keys'
groq_client = Groq(api_key=os.getenv("GROQ_API_KEY"))

supabase: Client = create_client(
    os.getenv("SUPABASE_URL"),
    os.getenv("SUPABASE_SERVICE_ROLE_KEY")
)

def extract_text_from_pdf(pdf_path):
    """Reads all text from a given PDF file."""
    doc = fitz.open(pdf_path)
    text = ""
    for page in doc:
        text += page.get_text()
    return text

def process_quote_with_llm(text):
    """Sends the raw text to Groq and forces it to return JSON matching our schema."""
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

def push_to_supabase(structured_data , filename):
    """Pushes the LLM JSON output into the Supabase relational tables."""
    # 1. Insert the main quote metadata
    quote_payload = {
        "vendor_name": structured_data["vendor_name"],
        "client_name": structured_data["client_name"],
        "quote_date": structured_data["quote_date"],
        "grand_total": structured_data["grand_total"],
        "source_filename": filename
    }
    
    print(f"  -> Pushing metadata for {quote_payload['vendor_name']}...")
    quote_res = supabase.table("quotes").insert(quote_payload).execute()
    new_quote_id = quote_res.data[0]['id']
    
    # 2. Insert all the line items linked to that quote ID
    items_payload = []
    for item in structured_data["items"]:
        item["quote_id"] = new_quote_id 
        items_payload.append(item)
        
    print(f"  -> Pushing {len(items_payload)} line items...")
    supabase.table("quote_items").insert(items_payload).execute()

def main():
    # Safely locate the tatva_quotes folder in the root directory
    base_dir = os.getcwd()
    folder_path = os.path.join(base_dir, "backend","tatva_quotes")
    
    if not os.path.exists(folder_path):
        print(f" Could not find folder: {folder_path}")
        return

    for filename in os.listdir(folder_path):
        if filename.endswith(".pdf"):
            print(f"\n Processing: {filename}...")
            pdf_path = os.path.join(folder_path, filename)
            
            # ANTI-DUPLICATE CHECK --- 
            existing_record = supabase.table("quotes").select("id").eq("source_filename", filename).execute()
            if len(existing_record.data) > 0:
                print(f"skipping:{filename} is already in the dataset!")
                continue
            #-------------------

            pdf_path = os.path.json(folder_path , filename)
            
            try:
                # 1. Read PDF
                raw_text = extract_text_from_pdf(pdf_path)
                
                # 2. Extract Data
                print("  -> Extracting structured data via LLM...")
                structured_data = process_quote_with_llm(raw_text)
                
                # 3. Push to Database
                push_to_supabase(structured_data , filename)
                
                print(f" Successfully processed {filename}")
            except Exception as e:
                print(f" Failed to process {filename}: {e}")

if __name__ == "__main__":
    main()
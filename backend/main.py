from fastapi import FastAPI, UploadFile, File, Form, Body
from fastapi.middleware.cors import CORSMiddleware
from fastapi.concurrency import run_in_threadpool
from pydantic import BaseModel
from typing import List,Any,Optional
import os
import shutil
import uuid
import asyncio

# Import your extractor and comparator functions!
from services.extractor import process_single_pdf
from services.comparator import run_comparison, handle_chat_query
from supabase import create_client, Client 

app = FastAPI(title="QuoteSense API")

# FIXED: We added both port 3000 and 3001 to ensure Next.js never gets blocked!
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=False,
    allow_methods=["*"],
    allow_headers=["*"],
)

BASE_DIR = os.path.dirname(os.path.abspath(__file__))
UPLOAD_DIR = os.path.join(BASE_DIR, "temp_uploads")
os.makedirs(UPLOAD_DIR, exist_ok=True)

supabase: Client = create_client(
    os.getenv("SUPABASE_URL"),
    os.getenv("SUPABASE_SERVICE_ROLE_KEY")
)

@app.get("/")
def read_root():
    return {"status": "QuoteSense Backend is running perfectly! 🚀"}

@app.post("/api/compare-quotes")
async def handle_customer_upload(
    files: List[UploadFile] = File(...),
    session_id: str = Form(None)
):
    """
    This endpoint receives PDFs from the Next.js frontend, extracts them,
    compares them, and returns the AI recommendation.
    """
    # 1. Generate a unique session ID for this customer if they didn't provide one
    if not session_id:
        session_id = f"session_{uuid.uuid4().hex[:8]}"
        
    print(f"\n📥 Received {len(files)} quotes for Session: {session_id}")
    
    saved_files = []
    
    # 2. Save the uploaded files temporarily
    for file in files:
        file_path = os.path.join(UPLOAD_DIR, file.filename)
        with open(file_path, "wb") as buffer:
            shutil.copyfileobj(file.file, buffer)
        saved_files.append(file_path)
        print(f"  -> Saved {file.filename}")

    # 3. Process the files using your extractor
    print(f"parallel extraction for {len(saved_files)} files")

    tasks = [
        run_in_threadpool(process_single_pdf, file_path,session_id)
        for file_path in saved_files
    ]
    await asyncio.gather(*tasks)

    # 4. Run the comparison using your comparator
    comparison_result = await run_in_threadpool(run_comparison, session_id)
    
    # 5. Clean up the temporary files so we don't waste storage
    for file_path in saved_files:
        if os.path.exists(file_path):
            os.remove(file_path)

    # 6. FIXED: Pass the tableData and vendors to the frontend!
    return {
        "status": "success",
        "session_id": session_id,
        "message": f"Successfully received and analyzed {len(files)} files.",
        "report": comparison_result.get("report", "Error generating report."),
        "chartData": comparison_result.get("chartData", []), 
        "tableData": comparison_result.get("tableData", []), # <-- Added this!
        "vendors": comparison_result.get("vendors", [])      # <-- Added this!
    }

class ChatRequest(BaseModel):
    session_id: str
    message: str


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
            quote_res = supabase.table("quotes").insert({
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
                supabase.table("quote_items").insert(items_to_insert).execute()

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
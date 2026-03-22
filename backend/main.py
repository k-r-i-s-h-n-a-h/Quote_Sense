from fastapi import FastAPI, UploadFile, File, Form
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel
import os
import shutil
import uuid

# Import your extractor and comparator functions!
from services.extractor import process_single_pdf
from services.comparator import run_comparison, handle_chat_query

app = FastAPI(title="QuoteSense API")

# FIXED: We added both port 3000 and 3001 to ensure Next.js never gets blocked!
app.add_middleware(
    CORSMiddleware,
    allow_origins=[
        "http://localhost:3000",
        "https://quote-comparator.vercel.app",
        "https://quote-comparator-iedl.vercel.app", # <--- ADD THIS ONE
        "http://127.0.0.1:3000",
    ],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

BASE_DIR = os.path.dirname(os.path.abspath(__file__))
UPLOAD_DIR = os.path.join(BASE_DIR, "temp_uploads")
os.makedirs(UPLOAD_DIR, exist_ok=True)

@app.get("/")
def read_root():
    return {"status": "QuoteSense Backend is running perfectly! 🚀"}

@app.post("/api/compare-quotes")
async def handle_customer_upload(
    files: list[UploadFile] = File(...),
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
    for file_path in saved_files:
        process_single_pdf(file_path, session_id)
    
    # 4. Run the comparison using your comparator
    comparison_result = run_comparison(session_id)
    
    # 5. Clean up the temporary files so we don't waste storage
    for file_path in saved_files:
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
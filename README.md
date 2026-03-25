# QuoteSense Comparator 🏠📊

An AI-powered full-stack application designed to extract, normalize, and compare interior design quotes for TatvaOps. Built with FastAPI backend and Next.js frontend, leveraging Google Gemini AI for intelligent PDF extraction and Supabase for data management.

## 📋 Table of Contents
- [Overview](#overview)
- [Features](#features)
- [Tech Stack](#tech-stack)
- [Prerequisites](#prerequisites)
- [Project Structure](#project-structure)
- [Installation & Setup](#installation--setup)
- [Environment Configuration](#environment-configuration)
- [Running the Application](#running-the-application)
- [API Endpoints](#api-endpoints)
- [Frontend Features](#frontend-features)
- [Troubleshooting](#troubleshooting)

## 📖 Overview

QuoteSense Comparator is a sophisticated quote management system that:
- **Extracts data** from vendor PDF quotes using Google Gemini Vision API
- **Structures information** into normalized JSON using predefined taxonomies
- **Stores data** in Supabase PostgreSQL database
- **Analyzes comparisons** using Pandas for cost analysis
- **Provides insights** through an interactive Next.js dashboard

Perfect for interior design firms, construction companies, and procurement teams managing multiple vendor quotes.

## 🚀 Features

* **🤖 AI-Powered PDF Extraction:**
  - Uses Google Gemini 2.5 Flash Vision API to analyze PDF documents
  - Extracts vendor names, costs, dates, and service line-items
  - Intelligent table recognition for quote structures
  - High accuracy with predefined taxonomy matching

* **💾 Database Integration:**
  - Supabase PostgreSQL relational database
  - Automatic storage of extracted quotes and line items
  - Session-based organization for batch processing
  - Real-time data synchronization

* **📊 Cost Analysis & Comparison:**
  - Pandas-powered matrix analysis across vendors
  - Service-category breakdown with cost totals
  - Vendor performance comparison charts
  - Statistical baseline calculations

* **🎨 Interactive Dashboard:**
  - Next.js frontend with Tailwind CSS styling
  - Real-time comparison charts using Recharts
  - Tabular data visualization
  - Session management and history

* **⚡ RESTful API:**
  - FastAPI with comprehensive CORS support
  - Async/await for concurrent PDF processing
  - Structured JSON responses
  - Full error handling and status tracking

## 🛠️ Tech Stack

### Backend
* **Python 3.10+** - Core runtime
* **FastAPI** - Modern async web framework
* **Google Genai SDK** - AI-powered PDF extraction (Gemini 2.5 Flash)
* **Supabase** - PostgreSQL database with Python client
* **Pandas** - Data analysis and matrix operations
* **Pydantic** - Data validation and schema definition
* **Uvicorn** - ASGI server
* **Python-dotenv** - Environment variable management

### Frontend
* **Next.js 16.1.6** - React meta-framework
* **React 19.2.3** - UI library
* **TypeScript** - Type-safe JavaScript
* **Tailwind CSS 4** - Utility-first styling
* **Recharts** - React charting library for data visualization
* **ESLint** - Code quality

### Database & APIs
* **Supabase** - PostgreSQL database platform
* **Google Gemini API** - Advanced vision and language model

## 📋 Prerequisites

Before you begin, ensure you have installed:

- **Python 3.10 or higher** - [Download Python](https://www.python.org/downloads/)
- **Node.js 18+ and npm** - [Download Node.js](https://nodejs.org/)
- **Git** - [Download Git](https://git-scm.com/)
- **A code editor** (VS Code recommended)

### Required API Keys & Credentials

You will need to obtain the following credentials:

1. **Google Gemini API Key**
   - Visit [Google AI Studio](https://aistudio.google.com/app/apikey)
   - Create a new API key
   - Enable the Generative Language API

2. **Supabase Credentials**
   - Create account at [supabase.com](https://supabase.com)
   - Create a new project
   - Get your `SUPABASE_URL` and `SUPABASE_SERVICE_ROLE_KEY` from project settings

## 📁 Project Structure

```
quote_comparator/
├── backend/                          # FastAPI backend
│   ├── main.py                       # FastAPI app initialization
│   ├── requirements.txt              # Python dependencies
│   ├── api/
│   │   └── routes.py                 # Additional API routes
│   ├── models/
│   │   ├── schema.py                 # Pydantic data models
│   │   └── taxanomy.py               # Service taxonomy definitions
│   ├── services/
│   │   ├── extractor.py              # PDF extraction logic (Gemini)
│   │   └── comparator.py             # Quote comparison logic (Pandas)
│   ├── tatva_quotes/                 # Sample quote data
│   └── temp_uploads/                 # Temporary PDF storage
│
├── frontend/                         # Next.js frontend
│   ├── app/
│   │   ├── layout.tsx                # Root layout
│   │   ├── page.tsx                  # Home page
│   │   └── globals.css               # Global styles
│   ├── public/                       # Static assets
│   ├── package.json                  # Node dependencies
│   ├── tsconfig.json                 # TypeScript config
│   ├── next.config.ts                # Next.js configuration
│   └── postcss.config.mjs            # Tailwind/PostCSS config
│
├── .env                              # Environment variables (CREATE THIS)
├── .git/                             # Git repository
└── README.md                         # This file
```

## 🚀 Installation & Setup

### Step 1: Clone the Repository

```bash
# Clone the project from GitHub
git clone https://github.com/Hkrish098/Quote_comparator.git

# Navigate into the project directory
cd Quote_comparator
```

### Step 2: Set Up Python Virtual Environment

Create an isolated Python environment for backend dependencies:

```bash
# Create a virtual environment named .venv
python3 -m venv .venv

# Activate the virtual environment
# On macOS/Linux:
source .venv/bin/activate

# On Windows (PowerShell):
.venv\Scripts\Activate.ps1

# On Windows (Command Prompt):
.venv\Scripts\activate.bat
```

You should see `(.venv)` prefix in your terminal, indicating the environment is active.

### Step 3: Install Python Dependencies

```bash
# Ensure you're in the project root directory with .venv activated
pip install --upgrade pip

# Install all backend requirements
pip install -r backend/requirements.txt
```

### Step 4: Install Frontend Dependencies

```bash
# Navigate to the frontend directory
cd frontend

# Install Node.js dependencies using npm
npm install

# Return to project root
cd ..
```

### Step 5: Create Environment Configuration File

Create a `.env` file in the project root directory:

```bash
# Create the .env file (from project root)
touch .env

# On Windows, use:
# type nul > .env
```

## 🔐 Environment Configuration

Edit the `.env` file you created and add your API credentials:

```env
# ============================================
# GOOGLE GEMINI API CONFIGURATION
# ============================================
GEMINI_API_KEY="your_google_gemini_api_key_here"

# ============================================
# SUPABASE DATABASE CONFIGURATION
# ============================================
SUPABASE_URL="https://your-project-id.supabase.co"
SUPABASE_SERVICE_ROLE_KEY="your_supabase_service_role_key_here"

# ============================================
# OPTIONAL: FRONTEND API CONFIGURATION
# ============================================
# If your frontend needs to call the API
NEXT_PUBLIC_API_URL="http://localhost:8001"
```

## ▶️ Running the Application

The application consists of two parts that must be run in separate terminals:

### Terminal 1: Start the Backend Server

```bash
# Navigate to project root if not already there
cd /path/to/Quote_comparator

# Ensure virtual environment is activated
source .venv/bin/activate

# Start the FastAPI server using Uvicorn
# Default: runs on http://localhost:8001
uvicorn backend.main:app --port8001 --reload

# Custom port (if you need a different port):
# uvicorn backend.main:app --reload --port 8001

# To run with multiple workers (production):
# uvicorn backend.main:app --host 0.0.0.0 --port 8001--workers 4
```

The backend server should display:
```
INFO:     Uvicorn running on http://127.0.0.1:8001 (Press CTRL+C to quit)
INFO:     Application startup complete
```

### Terminal 2: Start the Frontend Development Server

```bash
# Open new terminal in project root directory
cd /path/to/Quote_comparator

# Navigate to frontend directory
cd frontend

# Start Next.js development server
# Default: runs on http://localhost:3000
npm run dev

# For production build and start:
# npm run build
# npm start
```

The frontend server should display:
```
▲ Next.js 16.1.6
- Local:        http://localhost:3000
- Environments: .env.local
```

### Both Servers Running

Once both servers are active:
- **Backend API**: http://localhost:8001
- **Frontend App**: http://localhost:3000
- **API Documentation**: http://localhost:8001/docs (Swagger UI)
- **Alternative API Docs**: http://localhost:8001/redoc (ReDoc)

## 📡 API Endpoints

### Root Endpoint

**GET** `/`
```bash
curl http://localhost:8001/
```

**Response:**
```json
{
  "status": "QuoteSense Backend is running perfectly! 🚀"
}
```

---

### Compare Quotes Endpoint

**POST** `/api/compare-quotes`

Extract, analyze, and compare multiple quote PDFs in one request.

**Request:**
```bash
curl -X POST http://localhost:8000/api/compare-quotes \
  -F "files=@quote1.pdf" \
  -F "files=@quote2.pdf" \
  -F "files=@quote3.pdf" \
  -F "session_id=my_session_123"
```

**Parameters:**
- `files` (required): Array of PDF files to analyze
- `session_id` (optional): Unique session identifier. Auto-generated if not provided.

**Response:**
```json
{
  "status": "success",
  "session_id": "session_a1b2c3d4",
  "message": "Successfully received and analyzed 3 files.",
  "report": "Detailed analysis report text...",
  "chartData": [
    {
      "vendor": "Vendor A (quote1.pdf)",
      "total": 15000.00
    },
    {
      "vendor": "Vendor B (quote2.pdf)",
      "total": 16500.00
    }
  ],
  "tableData": [
    {
      "service_category": "Interior Design",
      "sub_service": "Space Planning",
      "vendor1": 2000,
      "vendor2": 2200
    }
  ],
  "vendors": [
    {
      "name": "Vendor A",
      "total": 15000.00,
      "file": "quote1.pdf"
    }
  ]
}
```

**Error Response:**
```json
{
  "detail": "No files provided or processing failed"
}
```

---

### Data Models

#### WorkItem
Represents a single line item in a quote.

```json
{
  "sub_service": "Space Planning",
  "work_title": "Living Room Design",
  "description": "Complete interior design consultation",
  "quantity": 1.0,
  "pricing_method": "Square Feet",
  "rate": 250.0,
  "amount": 5000.0
}
```

#### MainService
Groups multiple work items under a service category.

```json
{
  "service_category": "Interior Design",
  "items": [
    { ...work_item_1 },
    { ...work_item_2 }
  ]
}
```

#### ExtractedQuote
Complete quote structure returned from extraction.

```json
{
  "vendor_name": "Premier Designs",
  "client_name": "ABC Corporation",
  "quote_date": "2025-03-20",
  "grand_total": 25000.00,
  "services": [
    { ...main_service_1 },
    { ...main_service_2 }
  ]
}
```

---

## 🎨 Frontend Features

### Dashboard Overview
The Next.js frontend provides:

1. **Quote Upload Interface**
   - Drag-and-drop PDF upload
   - Multiple file support
   - Progress tracking

2. **Comparison Visualizations**
   - Bar chart showing total costs per vendor
   - Line charts for price trends
   - Heat maps for category comparisons

3. **Detailed Analysis Tables**
   - Service breakdown by vendor
   - Cost per item comparison
   - Vendor ranking

4. **Session Management**
   - Save comparison sessions
   - View comparison history
   - Export reports

### Key Pages

- **`app/page.tsx`** - Main dashboard with upload and results
- **`app/layout.tsx`** - Root layout with navigation
- **`app/globals.css`** - Global styling and theme

---

## 🔍 Usage Examples

### Example 1: Compare Three Vendor Quotes

```bash
# Terminal 1: Backend running
source .venv/bin/activate
uvicorn backend.main:app --reload

# Terminal 2: Frontend running
cd frontend
npm run dev

# Terminal 3: Test API
curl -X POST http://localhost:8001/api/compare-quotes \
  -F "files=@vendor_a_quote.pdf" \
  -F "files=@vendor_b_quote.pdf" \
  -F "files=@vendor_c_quote.pdf" \
  -F "session_id=project_xyz"
```

### Example 2: Verify Backend is Running

```bash
# Check API health
curl http://localhost:8001/

# View interactive API documentation
# Open in browser: http://localhost:8000/docs
```

### Example 3: Check Python Environment

```bash
# Verify Python version
python --version

# List installed packages
pip list

# Check specific package version
pip show fastapi
```

---

## 🐛 Troubleshooting

### Issue: "ModuleNotFoundError: No module named 'fastapi'"

**Solution:**
```bash
# Ensure virtual environment is activated
source .venv/bin/activate

# Reinstall dependencies
pip install -r backend/requirements.txt
```

---

### Issue: "SUPABASE_URL not found" or "GEMINI_API_KEY not found"

**Solution:**
```bash
# Verify .env file exists in project root
ls -la .env

# Verify .env contains correct keys with proper format
cat .env

# The file should contain:
# GEMINI_API_KEY="your_key"
# SUPABASE_URL="your_url"
# SUPABASE_SERVICE_ROLE_KEY="your_key"
```

---

### Issue: Backend running but frontend can't connect

**Solution:**
```bash
# Check if backend is accessible
curl http://localhost:8001/

# Update NEXT_PUBLIC_API_URL in .env
NEXT_PUBLIC_API_URL="http://localhost:8001"

# Restart frontend development server
# Press Ctrl+C in frontend terminal and run:
npm run dev
```

---

### Issue: "Address already in use" on port 8000 or 3000

**Solution:**
```bash
# Find process using port 8000
lsof -i :8000

# Kill the process
kill -9 <PID>

# Or use a different port
uvicorn backend.main:app --reload --port 8001
```

---

### Issue: PDF extraction fails or returns empty results

**Solution:**
1. Verify Google Gemini API key is valid
2. Check PDF file is readable and not corrupted
3. Ensure Supabase connection is active
4. Check backend logs for detailed error messages

```bash
# Test Gemini API directly with Python
python -c "
import os
from dotenv import load_dotenv
load_dotenv()
from google import genai
client = genai.Client(api_key=os.getenv('GEMINI_API_KEY'))
print('✓ Gemini API Connection Successful')
"
```

---

### Issue: NextJS Build Errors

**Solution:**
```bash
# Clear Next.js cache
cd frontend
rm -rf .next

# Clear node_modules and reinstall
rm -rf node_modules
npm install

# Rebuild
npm run build
npm run dev
```

---

## 📦 Dependencies Summary

### Python Backend Dependencies
```
fastapi              # Web framework
uvicorn              # ASGI server
pydantic             # Data validation
python-dotenv        # Environment variables
google-genai         # Google Gemini API
supabase             # Database client
pandas               # Data analysis
python-multipart     # File upload handling
tabulate             # Table formatting
```

To check all installed versions:
```bash
pip list | grep -E "fastapi|pydantic|google|supabase|pandas"
```

### Node.js Frontend Dependencies
```
next                 # React framework
react                # UI library
react-dom            # DOM rendering
recharts             # Charting library
tailwindcss          # CSS framework
typescript           # Type safety
eslint               # Code quality
```

To check all installed versions:
```bash
cd frontend
npm list
```

---

## 🚀 Deployment

### Deploying Backend (FastAPI)

**Option 1: Heroku**
```bash
# Install Heroku CLI and login
heroku login

# Create Procfile in project root
echo "web: uvicorn backend.main:app --host 0.0.0.0 --port $PORT" > Procfile

# Deploy
git push heroku main
```

**Option 2: Railway or Render**
- Follow their documentation for Python FastAPI apps
- Set environment variables in dashboard
- Deploy from GitHub repository

### Deploying Frontend (Next.js)

**Option 1: Vercel (Recommended)**
```bash
# Install Vercel CLI
npm i -g vercel

# Deploy
vercel

# Set environment variables in Vercel dashboard
# Redeploy with: vercel --prod
```

**Option 2: Netlify**
```bash
# Install Netlify CLI
npm i -g netlify-cli

# Deploy
netlify deploy --prod
```

---

## 📞 Support & Contributing

For issues, questions, or contributions:
- GitHub: [Quote_comparator](https://github.com/Hkrish098/Quote_comparator)
- Create issues for bug reports
- Submit pull requests for improvements

---

## 📝 License

This project is proprietary to TatvaOps. All rights reserved.

---

## ✅ Quick Reference: Complete Setup Checklist

- [ ] Python 3.10+ installed
- [ ] Node.js 18+ installed
- [ ] GitHub account and local git configured
- [ ] Repository cloned locally
- [ ] `.venv` created and activated
- [ ] `pip install -r backend/requirements.txt` completed
- [ ] `npm install` completed in `/frontend`
- [ ] `.env` file created with credentials
- [ ] GEMINI_API_KEY configured
- [ ] SUPABASE_URL and SUPABASE_SERVICE_ROLE_KEY configured
- [ ] Backend runs with `uvicorn backend.main:app --reload`
- [ ] Frontend runs with `npm run dev` (from frontend directory)
- [ ] Access http://localhost:3000 in browser
- [ ] Backend API docs available at http://localhost:8000/docs
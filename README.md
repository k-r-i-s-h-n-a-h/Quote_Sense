# QuoteSense Comparator 🏠📊

An AI-powered backend engine designed to extract, normalize, and compare interior design quotes for TatvaOps.

## 🚀 Features
* **AI Data Extraction:** Uses `PyMuPDF` and the `Groq` LLM (Llama 3.3 70B) to read messy vendor PDFs and convert them into structured JSON.
* **Database Integration:** Automatically pushes extracted line-items into a relational `Supabase` PostgreSQL database.
* **Unbiased Market Math:** Uses `Pandas` to calculate a true market baseline by averaging item costs across multiple vendors.
* **AI Quantity Surveyor:** Analyzes the Pandas math to generate an objective summary identifying cost-effective vendors and tactical pricing outliers.

## 🛠️ Tech Stack
* **Python 3** (Backend processing)
* **FastAPI** (API architecture - *in progress*)
* **Next.js** (Frontend UI - *in progress*)
* **Supabase** (Database)
* **Groq** (LLM Inference)

## 🔧 Setup & Configuration

To run this project locally, you must create a `.env` file in the root directory containing the following API keys and database credentials:

```env
# Groq LLM API Key
GROQ_API_KEY="your_groq_api_key_here"

# Supabase Database Credentials
SUPABASE_URL="[https://your-project-id.supabase.co](https://your-project-id.supabase.co)"
SUPABASE_SERVICE_ROLE_KEY="your_supabase_service_role_key_here"
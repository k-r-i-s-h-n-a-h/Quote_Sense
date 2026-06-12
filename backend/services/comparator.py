import sys
import os
import math
import pandas as pd
from dotenv import load_dotenv
from supabase import create_client, Client
import traceback
import json

from google import genai
from google.genai import types

sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), '../../')))
load_dotenv()

gemini_client = genai.Client(api_key=os.getenv("GEMINI_API_KEY"))

supabase: Client = create_client(
    os.getenv("SUPABASE_URL"),
    os.getenv("SUPABASE_SERVICE_ROLE_KEY")
)


def sanitize_for_json(obj):
    """Convert NaN/Inf floats to 0 without corrupting string fields in JSON."""
    if isinstance(obj, dict):
        return {k: sanitize_for_json(v) for k, v in obj.items()}
    if isinstance(obj, list):
        return [sanitize_for_json(v) for v in obj]
    if isinstance(obj, float):
        if math.isnan(obj) or math.isinf(obj):
            return 0.0
        return obj
    if isinstance(obj, (pd.Series, pd.DataFrame)):
        return sanitize_for_json(obj.to_dict())
    # pandas / numpy scalar types
    if hasattr(obj, "item") and callable(obj.item):
        try:
            return sanitize_for_json(obj.item())
        except (ValueError, TypeError):
            pass
    return obj


def fetch_data(session_id):
    print(f"📥 Fetching data for Session: {session_id}...")
    # select("*") so optional columns (e.g. quote_number) don't error if absent.
    quotes_response = supabase.table("quotes").select("*").eq("session_id", session_id).execute()
    
    if not quotes_response.data:
        raise ValueError("No quotes found in the database for this session!")
        
    quotes_df = pd.DataFrame(quotes_response.data)
    quote_ids = quotes_df['id'].tolist()
    
    # Order by id so line items come back in the sequence they were inserted,
    # which mirrors the quote's original top-to-bottom flow.
    try:
        items_response = (
            supabase.table("quote_items")
            .select("*")
            .in_("quote_id", quote_ids)
            .order("id")
            .execute()
        )
    except Exception:
        items_response = supabase.table("quote_items").select("*").in_("quote_id", quote_ids).execute()
    
    if not items_response.data:
        raise ValueError("I found the quotes, but there are no line items attached to them! The PDF extraction likely failed.")

    items_df = pd.DataFrame(items_response.data)
    
    df = pd.merge(items_df, quotes_df, left_on="quote_id", right_on="id", suffixes=('_item', '_quote'))
    # Keep the original company name, then build the unique vendor key used everywhere.
    df['company'] = df['vendor_name']
    df['vendor_name'] = df['vendor_name'] + " (" + df['source_filename'] + ")"
    
    return df

def run_comparison(session_id, on_matrix_ready=None):
    """Build the comparison matrix, then generate the recommendation.

    If ``on_matrix_ready`` is provided, it's invoked with the matrix payload
    (chart + table + vendors, no report) the moment the fast Pandas step finishes
    — before the slower Gemini recommendation call. This lets the frontend render
    results immediately while the recommendation is still being written.
    """
    try:
        df = fetch_data(session_id)
        print("🧮 Running Pandas matrix analysis for detailed frontend checklist...")

        # Sum of the extracted line items per vendor (used as a fallback for the chart)
        line_item_totals = df.groupby('vendor_name')['amount'].sum().to_dict()

        # 1. Prepare Chart Data — use the PDF grand_total, fall back to line-item sum
        quotes_df = df[['vendor_name', 'grand_total']].drop_duplicates()
        chart_data = []
        for index, row in quotes_df.iterrows():
            grand = float(row['grand_total']) if pd.notna(row['grand_total']) else 0.0
            total_val = grand if grand > 0 else float(line_item_totals.get(row['vendor_name'], 0.0))
            chart_data.append({"vendor": row['vendor_name'], "total": total_val})

        chart_data = sorted(chart_data, key=lambda x: x['total'])

        # 1b. Per-vendor metadata so the frontend can build professional labels
        #     (company name + quote number + quote date) for the chart and table.
        has_quote_number = 'quote_number' in df.columns
        has_quote_date = 'quote_date' in df.columns
        vendor_meta = {}
        for _, r in df.drop_duplicates('vendor_name').iterrows():
            key = r['vendor_name']
            vendor_meta[key] = {
                "company": str(r.get('company', '') or '').strip(),
                "filename": str(r.get('source_filename', '') or '').strip(),
                "quote_number": (str(r.get('quote_number', '') or '').strip() if has_quote_number else ''),
                "quote_date": (str(r.get('quote_date', '') or '').strip() if has_quote_date else ''),
            }

        # 2. Prepare Tabular Data & THE NOTEBOOK MEAN CALCULATION
        # Three-level hierarchy that mirrors the quote flow:
        #   service_category  ->  sub_service (normalized taxonomy)  ->  item_name (room)
        # The row label is the vendor's ORIGINAL item wording (item_name), with the
        # room shown as secondary. We "stop the diffusion" (clubbing) at this level.
        # Some optional columns (item_name, work_title) may be missing entirely if
        # the Supabase schema lacks them. Create them before normalizing so we never
        # call .fillna on a plain string (which raises AttributeError).
        for col in ('work_title', 'item_name', 'sub_service', 'service_category'):
            if col not in df.columns:
                df[col] = ''
            df[col] = df[col].fillna('').astype(str).str.strip()

        def _is_blank(value):
            return (not value) or value.lower() in ('', 'nan', 'none', 'null')

        df['service_category'] = df['service_category'].apply(
            lambda v: v if not _is_blank(v) else 'Other'
        )
        df['sub_service'] = df['sub_service'].apply(
            lambda v: v if not _is_blank(v) else 'General'
        )

        # Row label = original item name; fall back to room, then sub-service.
        def _item_label(r):
            if not _is_blank(r['item_name']):
                return r['item_name']
            if not _is_blank(r['work_title']):
                return r['work_title']
            return r['sub_service'] or 'Unspecified Item'

        df['item_label'] = df.apply(_item_label, axis=1)
        df['room'] = df['work_title'].apply(lambda v: v if not _is_blank(v) else '')
        # Backward-compat alias used by some callers.
        df['work_item'] = df['item_label']

        # First-appearance ordering so rows follow the quote's natural top-to-bottom flow.
        df = df.reset_index(drop=True)
        df['__seq'] = range(len(df))
        cat_order = df.groupby('service_category')['__seq'].min().to_dict()
        sub_order = df.groupby(['service_category', 'sub_service'])['__seq'].min().to_dict()
        item_order = (
            df.groupby(
                ['service_category', 'sub_service', 'item_label', 'room']
            )['__seq'].min().to_dict()
        )

        detailed_totals = (
            df.groupby(
                ['service_category', 'sub_service', 'item_label', 'room', 'vendor_name']
            )['amount']
            .sum()
            .reset_index()
        )
        pivot_df = detailed_totals.pivot(
            index=['service_category', 'sub_service', 'item_label', 'room'],
            columns='vendor_name',
            values='amount',
        ).fillna(0.0)

        vendors = pivot_df.columns.tolist()
        table_data = [] # Renamed for React frontend!

        for index, row in pivot_df.iterrows():
            category, sub_service_name, item_label, room = index
            # Calculate the Mean (Baseline) ONLY using vendors who actually provided the service (>0)
            vendor_prices = [float(row[v]) for v in vendors if float(row[v]) > 0]
            market_avg = sum(vendor_prices) / len(vendor_prices) if vendor_prices else 0.0

            row_dict = {
                "category": str(category),             # level 1: service category group
                "sub_service": str(sub_service_name),  # level 2: normalized TatvaOps sub-service
                "item_name": str(item_label),          # level 3: vendor's original item wording
                "room": str(room),                     # location shown as secondary text
                "work_item": str(item_label),          # kept for backward-compat
                "taxonomy": str(sub_service_name),     # kept for backward-compat
                "market_average": round(market_avg, 2),  # kept for AI; hidden in UI
                "_cat_order": float(cat_order.get(category, 1e9)),
                "_sub_order": float(sub_order.get((category, sub_service_name), 1e9)),
                "_item_order": float(
                    item_order.get((category, sub_service_name, item_label, room), 1e9)
                ),
            }
            for v in vendors:
                row_dict[v] = float(row[v])
            table_data.append(row_dict)

        # Sort to follow the quote flow: category, then sub-service, then item.
        table_data.sort(key=lambda r: (r["_cat_order"], r["_sub_order"], r["_item_order"]))
        for r in table_data:
            r.pop("_cat_order", None)
            r.pop("_sub_order", None)
            r.pop("_item_order", None)

        print(f"📊 Built comparison matrix with {len(table_data)} line items across {len(vendors)} quotes.")

        # Publish the fast matrix result before the slow recommendation call so the
        # frontend can render the chart + table right away.
        matrix_payload = sanitize_for_json({
            "chartData": chart_data,
            "tableData": table_data,
            "vendors": vendors,
            "vendorMeta": vendor_meta,
            "session_id": session_id,
        })
        if on_matrix_ready is not None:
            try:
                on_matrix_ready(matrix_payload)
            except Exception as cb_err:
                print(f"⚠️ on_matrix_ready callback failed: {cb_err}")

        # 3. Generate Expert Recommendation using Tatva Intelligence (Gemini 2.5 Flash)
        print("🧠 Generating Expert Recommendation with Tatva Intelligence...")
        summary_prompt = f"""
        You are 'QuoteSense', an expert procurement analyst for TatvaOps.
        Analyze these quotes based strictly on the provided data.
        
        Data Matrix (Includes the 'market_average' mean for each sub-service):
        {table_data}
        Overall Totals: {chart_data}
        
        Write the analysis as SHORT, POINT-WISE bullets — NOT a paragraph.

        FORMAT RULES (follow exactly):
        - Output 4 to 6 bullet points, each on its own line starting with "- ".
        - Begin every bullet with a short bold label using double asterisks, then a colon,
          then one concise sentence. Example: "- **Best Overall Value:** Vendor X ...".
        - Keep each bullet to a single, plain, professional sentence anyone can understand.
        - Do NOT write any intro or closing paragraph; output only the bullets.

        COVER THESE POINTS (one bullet each):
        - **Lowest Total:** which quote is cheapest overall and by roughly how much.
        - **Price vs Market:** who tends to price above or below the market average on common work.
        - **Scope Difference:** call out apples-to-oranges — a lower total may just mean fewer
          services/items, so name what is missing or extra.
        - **Strength:** which vendor is the better choice for a key service category and why.
        - **Recommendation:** a clear, practical suggestion on which to pick or what to confirm.
        """

        summary_response = gemini_client.models.generate_content(
            model='gemini-2.5-flash',
            contents=summary_prompt,
            config=types.GenerateContentConfig(temperature=0.2)
        )
        
        ai_report = summary_response.text

        # Reuse the already-sanitized matrix and just attach the report.
        final_output = {**matrix_payload, "report": ai_report}

        return sanitize_for_json(final_output)
        
    except Exception as e:
        error_details = traceback.format_exc()
        print(f"❌ Backend Crash Details:\n{error_details}")
        return {"error": f"Error during comparison: {str(e)}"}
    
def handle_chat_query(session_id, user_message):
    print(f"💬 Processing chat query for Session: {session_id}...")
    try:
        df = fetch_data(session_id)
        quotes_df = df[['vendor_name', 'grand_total']].drop_duplicates()
        vendor_totals = quotes_df.to_dict(orient='records')
        
        top_items = df['sub_service'].value_counts().head(20).index
        item_spreads = df[df['sub_service'].isin(top_items)].groupby(['sub_service', 'vendor_name'])['rate'].mean().reset_index().to_dict(orient='records')
        item_specs = df[df['sub_service'].isin(top_items)][['sub_service', 'vendor_name', 'description']].drop_duplicates().to_dict(orient='records')

        prompt = f"""
        You are 'QuoteSense', an expert AI assistant.
        The user uploaded vendor quotes. Here is the mathematical data:
        
        Vendor Totals: {vendor_totals}
        Key Item Rates: {item_spreads}
        Descriptions/Specs: {item_specs}

        User Question: "{user_message}"

        CRITICAL RULES:
        1. Answer based ONLY on the provided data. 
        2. Be concise, professional, and helpful. 
        3. Do not guess. If the data doesn't contain the answer, politely say you don't have that detail.
        """

        chat_response = gemini_client.models.generate_content(
            model='gemini-2.5-flash',
            contents=prompt,
            config=types.GenerateContentConfig(temperature=0.2)
        )
        
        return chat_response.text

    except Exception as e:
        return f"❌ Sorry, I encountered an error while accessing your data: {e}"
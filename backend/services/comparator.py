import sys
import os
import math
import concurrent.futures
import traceback
import json

# Hard ceiling for the recommendation LLM call. If Gemini takes longer than this
# (huge prompt, slow upstream, or a hang), we stop waiting and return a
# data-driven fallback so the run always finishes with a report.
RECOMMENDATION_TIMEOUT_SEC = 45


class _PandasLazy:
    """Defer pandas import so uvicorn starts instantly (pandas can take 30s+ on first load)."""
    _mod = None

    def __getattr__(self, name):
        if self._mod is None:
            import pandas as _mod
            self._mod = _mod
        return getattr(self._mod, name)


pd = _PandasLazy()

sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), '../../')))

from services.env_config import get_gemini_client, get_supabase_client
from services.market_rate import (
    DEFAULT_SERVICE_TYPE,
    lookup_market_rate,
    normalize_pricing_method,
    normalize_service_type,
    update_rates_from_dataframe,
)

DEBUG_LOG_PATH = os.path.abspath(
    os.path.join(os.path.dirname(__file__), "../../.cursor/debug-b7c34a.log")
)
_SESSIONS_TABLE_AVAILABLE: bool | None = None


def _agent_debug_log(location, message, data=None, hypothesis_id=None, run_id="pre-fix"):
    # region agent log
    try:
        import time
        import json as _json
        os.makedirs(os.path.dirname(DEBUG_LOG_PATH), exist_ok=True)
        with open(DEBUG_LOG_PATH, "a") as f:
            f.write(_json.dumps({
                "sessionId": "b7c34a",
                "timestamp": int(time.time() * 1000),
                "location": location,
                "message": message,
                "data": data or {},
                "hypothesisId": hypothesis_id,
                "runId": run_id,
            }) + "\n")
    except Exception:
        pass
    # endregion


def _sessions_table_available() -> bool:
    """Return False once if market_moving_avg_sessions is missing in Supabase."""
    global _SESSIONS_TABLE_AVAILABLE
    if _SESSIONS_TABLE_AVAILABLE is not None:
        return _SESSIONS_TABLE_AVAILABLE
    try:
        from services.env_config import env_diagnostics
        if not env_diagnostics()["supabase_configured"]:
            _SESSIONS_TABLE_AVAILABLE = False
            return False
        get_supabase_client().table("market_moving_avg_sessions").select("id").limit(1).execute()
        _SESSIONS_TABLE_AVAILABLE = True
    except Exception as e:
        err = str(e)
        if "market_moving_avg_sessions" in err or "PGRST205" in err:
            _SESSIONS_TABLE_AVAILABLE = False
            print(
                "ℹ️ market_moving_avg_sessions table not found — session dedup disabled. "
                "Run supabase/migrations/001_market_moving_avg_sessions.sql in Supabase SQL editor."
            )
            _agent_debug_log(
                "comparator.py:_sessions_table_available",
                "sessions table missing",
                {"error": err},
                hypothesis_id="A",
            )
        else:
            _SESSIONS_TABLE_AVAILABLE = True
    return _SESSIONS_TABLE_AVAILABLE


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
    quotes_response = get_supabase_client().table("quotes").select("*").eq("session_id", session_id).execute()
    
    if not quotes_response.data:
        raise ValueError("No quotes found in the database for this session!")
        
    quotes_df = pd.DataFrame(quotes_response.data)
    quote_ids = quotes_df['id'].tolist()
    
    # Order by id so line items come back in the sequence they were inserted,
    # which mirrors the quote's original top-to-bottom flow.
    try:
        items_response = (
            get_supabase_client().table("quote_items")
            .select("*")
            .in_("quote_id", quote_ids)
            .order("id")
            .execute()
        )
    except Exception:
        items_response = get_supabase_client().table("quote_items").select("*").in_("quote_id", quote_ids).execute()
    
    if not items_response.data:
        raise ValueError("I found the quotes, but there are no line items attached to them! The PDF extraction likely failed.")

    items_df = pd.DataFrame(items_response.data)
    
    df = pd.merge(items_df, quotes_df, left_on="quote_id", right_on="id", suffixes=('_item', '_quote'))
    # Keep the original company name, then build the unique vendor key used everywhere.
    df['company'] = df['vendor_name']
    df['vendor_name'] = df['vendor_name'] + " (" + df['source_filename'] + ")"
    
    return df

    return df


def _line_item_key(item_label: str, room: str) -> str:
    """Stable Supabase item_key for one comparison-matrix row."""
    label = (item_label or "").strip()
    loc = (room or "").strip()
    if loc and loc.lower() not in ("", "nan", "none") and loc != label:
        return f"{label}::{loc}"
    return label or loc or "Unspecified"


def _build_fallback_report(chart_data):
    """A deterministic, no-AI recommendation built straight from the totals.

    Used when the Gemini recommendation call times out or errors, so the user
    still gets a usable summary alongside the comparison table.
    """
    if not chart_data:
        return (
            "- **Recommendation:** Comparison table is ready above; the AI summary "
            "could not be generated this time — please re-run to retry."
        )
    ranked = sorted(chart_data, key=lambda x: x.get("total", 0))
    cheapest = ranked[0]
    priciest = ranked[-1]
    lines = [
        f"- **Lowest Total:** {cheapest['vendor']} is the cheapest overall at "
        f"₹{cheapest['total']:,.0f}."
    ]
    if len(ranked) > 1 and priciest.get("total", 0) > 0:
        diff_pct = (priciest["total"] - cheapest["total"]) / priciest["total"] * 100
        lines.append(
            f"- **Spread:** {priciest['vendor']} is the highest at "
            f"₹{priciest['total']:,.0f} (~{diff_pct:.0f}% more than the lowest)."
        )
    lines.append(
        "- **Scope Check:** A lower total may just mean a smaller scope — compare the "
        "line items in the table before deciding."
    )
    lines.append(
        "- **Recommendation:** This is an automatic summary (the detailed AI write-up "
        "timed out). Re-run the comparison to retry the full analysis."
    )
    return "\n".join(lines)


def _generate_recommendation(summary_prompt, chart_data):
    """Run the recommendation LLM call with a hard timeout + graceful fallback.

    The Gemini call runs in a worker thread so we can abandon it after
    RECOMMENDATION_TIMEOUT_SEC instead of letting a slow/hung request block the
    whole job forever. We don't wait on the orphaned thread (shutdown wait=False).
    """
    ex = concurrent.futures.ThreadPoolExecutor(max_workers=1)
    try:
        from google.genai import types

        future = ex.submit(
            lambda: get_gemini_client().models.generate_content(
                model='gemini-2.5-flash',
                contents=summary_prompt,
                config=types.GenerateContentConfig(temperature=0.2),
            )
        )
        summary_response = future.result(timeout=RECOMMENDATION_TIMEOUT_SEC)
        return summary_response.text
    except concurrent.futures.TimeoutError:
        print(
            f"⚠️ Recommendation timed out after {RECOMMENDATION_TIMEOUT_SEC}s — "
            "returning data-driven fallback summary."
        )
        return _build_fallback_report(chart_data)
    except Exception as e:
        print(f"⚠️ Recommendation generation failed: {e} — using fallback summary.")
        return _build_fallback_report(chart_data)
    finally:
        ex.shutdown(wait=False)


def run_comparison(session_id, on_matrix_ready=None, df=None, fast_moving_avg=True):
    """Build the comparison matrix, then generate the recommendation.

    If ``df`` is provided (MongoDB/Tatva payload lane), skip the Supabase fetch.
    ``fast_moving_avg`` (default True) uses in-session / seed lookups only —
    no market_moving_averages writes. MA updates only run from finalized quotes.
    """
    try:
        if df is None:
            df = fetch_data(session_id)
        else:
            df = df.copy()
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
        # Three-level hierarchy:
        #   service_category -> sub_service -> line items (item_name + room).
        # Line items stay visible; the UI sums amounts on the sub_service header row.
        for col in ('work_title', 'item_name', 'sub_service', 'service_category', 'pricing_method', 'service_type', 'rate'):
            if col not in df.columns:
                df[col] = '' if col != 'rate' else 0.0
            if col == 'rate':
                df[col] = pd.to_numeric(df[col], errors='coerce').fillna(0.0)
            else:
                df[col] = df[col].fillna('').astype(str).str.strip()

        if 'service_type' not in df.columns or df['service_type'].eq('').all():
            df['service_type'] = DEFAULT_SERVICE_TYPE

        # Display-only rates for this compare matrix — never persist MA here.
        # Market averages update only from isFinalizeQuote via apply_finalized_*.
        bundle_rate_map = update_rates_from_dataframe(df, session_id, fast=True)

        def _is_blank(value):
            return (not value) or value.lower() in ('', 'nan', 'none', 'null')

        df['service_category'] = df['service_category'].apply(
            lambda v: v if not _is_blank(v) else 'Other'
        )
        df['sub_service'] = df['sub_service'].apply(
            lambda v: v if not _is_blank(v) else 'General'
        )

        def _item_label(r):
            if not _is_blank(r['item_name']):
                return r['item_name']
            if not _is_blank(r['work_title']):
                return r['work_title']
            return r['sub_service'] or 'Unspecified Item'

        df['item_label'] = df.apply(_item_label, axis=1)
        df['room'] = df['work_title'].apply(lambda v: v if not _is_blank(v) else '')
        df['work_item'] = df['item_label']

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
        table_data = []

        for index, row in pivot_df.iterrows():
            category, sub_service_name, item_label, room = index

            line_mask = (
                (df['service_category'] == category)
                & (df['sub_service'] == sub_service_name)
                & (df['item_label'] == item_label)
                & (df['room'] == room)
            )
            line_slice = df.loc[line_mask]
            service_type = normalize_service_type(
                line_slice['service_type'].iloc[0] if len(line_slice) else DEFAULT_SERVICE_TYPE
            )
            pricing_method = normalize_pricing_method(
                line_slice['pricing_method'].iloc[0] if len(line_slice) else 'Unit'
            )
            bundle = (service_type, str(category), str(sub_service_name), pricing_method)

            if bundle in bundle_rate_map:
                moving_avg, moving_weight = bundle_rate_map[bundle]
            else:
                lookup = lookup_market_rate(
                    service_type, str(category), str(sub_service_name), pricing_method
                )
                moving_avg = lookup["market_rate"] if lookup else 0.0
                moving_weight = lookup["weight"] if lookup else 0

            # Compute average quantity across vendors for this specific line item so
            # we can show market_estimate = rate_per_unit × avg_qty in the Moving Avg
            # column — making it directly comparable to vendor total amounts.
            avg_qty = 1.0
            if moving_avg > 0 and 'quantity' in line_slice.columns:
                valid_qtys = line_slice['quantity'].dropna()
                valid_qtys = valid_qtys[valid_qtys > 0]
                if len(valid_qtys) > 0:
                    avg_qty = float(valid_qtys.mean())

            market_estimate = round(moving_avg * avg_qty) if moving_avg > 0 else 0

            row_dict = {
                "category": str(category),
                "sub_service": str(sub_service_name),
                "item_name": str(item_label),
                "room": str(room),
                "work_item": str(item_label),
                "taxonomy": str(sub_service_name),
                "service_type": service_type,
                "pricing_method": pricing_method,
                # market_estimate = per-unit rate × avg qty → same unit as vendor amounts
                "moving_average": market_estimate,
                "moving_weight": moving_weight,
                "market_average": market_estimate,
                # raw per-unit rate kept for the UI to show as a sub-label (e.g. "₹1,166/sqft")
                "market_rate_per_unit": round(moving_avg, 2),
                "_cat_order": float(cat_order.get(category, 1e9)),
                "_sub_order": float(sub_order.get((category, sub_service_name), 1e9)),
                "_item_order": float(
                    item_order.get((category, sub_service_name, item_label, room), 1e9)
                ),
            }
            for v in vendors:
                amt = float(row[v])
                row_dict[v] = round(amt) if amt > 0 else 0
            table_data.append(row_dict)

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

        # Send a COMPACT view of the matrix to the LLM — only the fields it needs
        # to reason about price (item, sub-service, category, market avg, and each
        # vendor's amount). This drops duplicate/UI-only keys (room, work_item,
        # taxonomy) and roughly halves the prompt size, making the call faster and
        # far less likely to hang on large quotes.
        compact_matrix = [
            {
                "item": r["item_name"],
                "sub_service": r["sub_service"],
                "category": r["category"],
                "moving_avg": r["moving_average"],
                "moving_weight": r["moving_weight"],
                **{v: int(r.get(v, 0) or 0) for v in vendors},
            }
            for r in table_data
        ]

        summary_prompt = f"""
        You are 'QuoteSense', an expert procurement analyst for TatvaOps.
        Analyze these quotes based strictly on the provided data.
        
        Data Matrix (Includes the historical 'moving_avg' baseline and 'moving_weight'
        — the number of past quotes used to build that baseline):
        {compact_matrix}
        Overall Totals: {chart_data}
        
        Write the analysis as SHORT, POINT-WISE bullets — NOT a paragraph.

        FORMAT RULES (follow exactly):
        - Output 4 to 6 bullet points, each on its own line starting with "- ".
        - Begin every bullet with a short bold label using double asterisks, then a colon,
          then one concise sentence. Example: "- **Best Overall Value:** Vendor X ...".
        - Do NOT show arithmetic breakdowns (e.g. do not write amounts as "X + Y" or "(A + B)").
        - Quote whole rupee totals only — no decimal paise.

        COVER THESE POINTS (one bullet each):
        - **Lowest Total:** which quote is cheapest overall and by roughly how much.
        - **Price vs Baseline:** who tends to price above or below the moving average baseline on common work.
        - **Scope Difference:** call out apples-to-oranges — a lower total may just mean fewer
          services/items, so name what is missing or extra.
        - **Strength:** which vendor is the better choice for a key service category and why.
        - **Recommendation:** a clear, practical suggestion on which to pick or what to confirm.
        """

        ai_report = _generate_recommendation(summary_prompt, chart_data)

        # Reuse the already-sanitized matrix and just attach the report.
        final_output = {**matrix_payload, "report": ai_report}

        return sanitize_for_json(final_output)
        
    except Exception as e:
        error_details = traceback.format_exc()
        print(f"❌ Backend Crash Details:\n{error_details}")
        return {"error": f"Error during comparison: {str(e)}"}


def _unwrap_quote_payload(quote_entry: dict) -> dict:
    if not isinstance(quote_entry, dict):
        return quote_entry
    inner = quote_entry.get("data")
    if isinstance(inner, dict) and (
        "quoteNumber" in inner or "vendorDetail" in inner or "workSummary" in inner
    ):
        return inner
    return quote_entry


def mongodb_quotes_to_dataframe(quotes_list: list):
    """Build a comparison DataFrame directly from Tatva/MongoDB quote JSON."""
    rows = []
    for quote_entry in quotes_list:
        quote_data = _unwrap_quote_payload(quote_entry)
        vendor_detail = quote_data.get("vendorDetail") or {}
        company = str(vendor_detail.get("companyName") or "Unknown Vendor")
        quote_number = str(quote_data.get("quoteNumber") or "").lstrip("#").strip()
        source_filename = quote_number or "DIRECT_SYNC"
        client_detail = quote_data.get("clientDetail") or {}
        quote_date = str(quote_data.get("quoteDate") or quote_data.get("createdAt") or "")

        grand_total = 0.0
        for item in quote_data.get("pricingSummary") or []:
            if "grand total" in str(item.get("label", "")).lower():
                grand_total = float(item.get("value") or 0)

        vendor_key = f"{company} ({source_filename})"

        # quoteType is set once per quote on the Tatva platform (essential /
        # midlevel / luxury) — every line item in this quote shares it for compare.
        # Market averages update only from isFinalizeQuote via apply_finalized_*.
        quote_service_type = normalize_service_type(quote_data.get("quoteType"))

        for section in quote_data.get("workSummary") or []:
            for service_obj in section.get("services") or []:
                category_name = (
                    (service_obj.get("serviceId") or {}).get("name") or "General"
                )
                for work_item in service_obj.get("workItems") or []:
                    sub_service_name = (
                        (work_item.get("subService") or {}).get("name")
                        or work_item.get("workTitle")
                        or "General Service"
                    )
                    pricing_list = work_item.get("pricingInput") or []
                    pricing = pricing_list[0] if pricing_list else {}
                    amount = float(pricing.get("grandTotal") or pricing.get("amount") or 0)
                    pricing_method = (
                        (work_item.get("pricingMethod") or {}).get("name") or "Unit"
                    )
                    rows.append({
                        "vendor_name": vendor_key,
                        "company": company,
                        "source_filename": source_filename,
                        "quote_number": quote_number,
                        "quote_date": quote_date[:10] if len(quote_date) >= 10 else quote_date,
                        "grand_total": grand_total,
                        "client_name": client_detail.get("clientName") or "",
                        "service_type": quote_service_type,
                        "service_category": category_name,
                        "sub_service": sub_service_name,
                        "work_title": work_item.get("workTitle") or "",
                        "item_name": work_item.get("workTitle") or "",
                        "description": str(work_item.get("description") or "").replace("&nbsp;", " "),
                        "quantity": pricing.get("quantity") or 0,
                        "pricing_method": pricing_method,
                        "rate": pricing.get("rate") or 0,
                        "amount": amount,
                    })

    if not rows:
        raise ValueError("No line items found in quote payloads.")
    return pd.DataFrame(rows)
    
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

        from google.genai import types

        chat_response = get_gemini_client().models.generate_content(
            model='gemini-2.5-flash',
            contents=prompt,
            config=types.GenerateContentConfig(temperature=0.2)
        )
        
        return chat_response.text

    except Exception as e:
        return f"❌ Sorry, I encountered an error while accessing your data: {e}"
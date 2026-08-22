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
    normalize_pricing_method,
    normalize_service_type,
)
from services.space_clusters import apply_space_clusters
from services.work_rollup import apply_work_rollup

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
        "- **Scope Check:** A lower total may just mean a smaller scope — compare rooms "
        "in the matrix before deciding."
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
    """Build the space-first comparison matrix, then generate the recommendation.

    If ``df`` is provided (MongoDB/Tatva payload lane), skip the Supabase fetch.
    Compare does not look up or send market moving averages.
    ``fast_moving_avg`` is kept for call-site compatibility and ignored.
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

        # 2. Space-first matrix: cluster rooms, roll up lighting lumpsum vs itemized.
        for col in ('work_title', 'item_name', 'sub_service', 'service_category', 'pricing_method', 'service_type', 'rate', 'space_raw', 'description'):
            if col not in df.columns:
                df[col] = '' if col != 'rate' else 0.0
            if col == 'rate':
                df[col] = pd.to_numeric(df[col], errors='coerce').fillna(0.0)
            else:
                df[col] = df[col].fillna('').astype(str).str.strip()

        if 'service_type' not in df.columns or df['service_type'].eq('').all():
            df['service_type'] = DEFAULT_SERVICE_TYPE

        if "space_raw" not in df.columns or df["space_raw"].eq("").all():
            df["space_raw"] = df["work_title"]

        def _is_blank(value):
            return (not value) or str(value).lower() in ('', 'nan', 'none', 'null')

        df['service_category'] = df['service_category'].apply(
            lambda v: v if not _is_blank(v) else 'Other'
        )
        df['sub_service'] = df['sub_service'].apply(
            lambda v: v if not _is_blank(v) else 'General'
        )

        df = _bind_catalog_ids_from_cache(df)
        df = apply_space_clusters(df)
        df = apply_work_rollup(df)

        def _item_label(r):
            if not _is_blank(r['item_name']):
                return r['item_name']
            if not _is_blank(r['sub_service']):
                return r['sub_service']
            return r['work_title'] or 'Unspecified Item'

        df['item_label'] = df.apply(_item_label, axis=1)
        df['room'] = df['space']
        df['work_item'] = df['item_label']
        if "sub_service_id" not in df.columns:
            df["sub_service_id"] = ""
        df["sub_service_id"] = df["sub_service_id"].fillna("").astype(str).str.strip()
        df["sub_key"] = df.apply(
            lambda r: r["sub_service_id"] if r["sub_service_id"] else r["sub_service"],
            axis=1,
        )

        df = df.reset_index(drop=True)
        df['__seq'] = range(len(df))
        space_order = df.groupby('space')['__seq'].min().to_dict()
        sub_order = df.groupby(['space', 'sub_key'])['__seq'].min().to_dict()

        detailed_totals = (
            df.groupby(
                ['space', 'sub_key', 'vendor_name']
            )['amount']
            .sum()
            .reset_index()
        )
        pivot_df = detailed_totals.pivot(
            index=['space', 'sub_key'],
            columns='vendor_name',
            values='amount',
        ).fillna(0.0)

        vendors = pivot_df.columns.tolist()
        table_data = []

        for index, row in pivot_df.iterrows():
            space_name, sub_key = index

            line_mask = (df['space'] == space_name) & (df['sub_key'] == sub_key)
            line_slice = df.loc[line_mask]
            sub_service_name = str(
                line_slice['sub_service'].mode().iloc[0]
                if len(line_slice) and not line_slice['sub_service'].mode().empty
                else sub_key
            )
            category = str(
                line_slice['service_category'].iloc[0] if len(line_slice) else "Other"
            )
            service_type = normalize_service_type(
                line_slice['service_type'].iloc[0] if len(line_slice) else DEFAULT_SERVICE_TYPE
            )
            pricing_method = normalize_pricing_method(
                line_slice['pricing_method'].iloc[0] if len(line_slice) else 'Unit'
            )
            space_raws = sorted({
                str(v).strip() for v in line_slice.get('space_raw', pd.Series(dtype=str)).tolist()
                if str(v).strip()
            })
            breakdown = []
            if len(line_slice) > 1:
                for _, child in line_slice.iterrows():
                    breakdown.append({
                        "vendor": str(child.get("vendor_name") or ""),
                        "item": str(child.get("item_label") or child.get("item_name") or ""),
                        "amount": round(float(child.get("amount") or 0)),
                    })

            row_dict = {
                "category": category,
                "space": str(space_name),
                "space_raw": " · ".join(space_raws),
                "sub_service": str(sub_service_name),
                "sub_service_id": str(line_slice['sub_service_id'].iloc[0] if len(line_slice) else ""),
                "item_name": str(sub_service_name),
                "room": str(space_name),
                "work_item": str(sub_service_name),
                "taxonomy": str(sub_service_name),
                "service_type": service_type,
                "pricing_method": pricing_method,
                "breakdown": breakdown,
                "_space_order": float(space_order.get(space_name, 1e9)),
                "_sub_order": float(sub_order.get((space_name, sub_key), 1e9)),
            }
            for v in vendors:
                amt = float(row[v])
                row_dict[v] = round(amt) if amt > 0 else 0
            table_data.append(row_dict)

        table_data.sort(key=lambda r: (r["_space_order"], r["_sub_order"]))
        for r in table_data:
            r.pop("_space_order", None)
            r.pop("_sub_order", None)

        print(f"📊 Built space-first comparison matrix with {len(table_data)} rows across {len(vendors)} quotes.")

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
                "space": r.get("space") or r.get("room"),
                "sub_service": r["sub_service"],
                "pricing_method": r.get("pricing_method"),
                **{v: int(r.get(v, 0) or 0) for v in vendors},
            }
            for r in table_data
        ]

        summary_prompt = f"""
        You are 'QuoteSense', an expert procurement analyst for TatvaOps.
        Analyze these quotes based strictly on the provided data.
        Rows are grouped by SPACE (room) then sub-service. N/A or 0 means that
        vendor did not quote that work in that space.

        Data Matrix:
        {compact_matrix}
        Overall Totals: {chart_data}

        Write the analysis as SHORT, POINT-WISE bullets — NOT a paragraph.

        FORMAT RULES (follow exactly):
        - Output 4 to 6 bullet points, each on its own line starting with "- ".
        - Begin every bullet with a short bold label using double asterisks, then a colon,
          then one concise sentence. Example: "- **Best Overall Value:** Vendor X ...".
        - Do NOT show arithmetic breakdowns (e.g. do not write amounts as "X + Y" or "(A + B)").
        - Quote whole rupee totals only — no decimal paise.
        - Do NOT mention market averages, moving averages, or historical baselines.

        COVER THESE POINTS (one bullet each):
        - **Lowest Total:** which quote is cheapest overall and by roughly how much.
        - **By Space:** name 1-2 rooms where one vendor is clearly cheaper (use space labels like GF-Bedroom1).
        - **Scope Difference:** apples-to-oranges — lumpsum vs itemized (e.g. electrical lighting), or rooms/items only one vendor quoted.
        - **Strength:** which vendor is stronger for a key space and why.
        - **Recommendation:** a clear, practical suggestion on which to pick or what to confirm with vendors.
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


def _nested_oid(obj) -> str:
    if not isinstance(obj, dict):
        return ""
    raw = obj.get("_id") or obj.get("id") or ""
    if isinstance(raw, dict):
        raw = raw.get("$oid") or raw.get("_id") or ""
    return str(raw or "").strip()


def _nested_name(obj, fallback: str = "") -> str:
    if isinstance(obj, dict):
        return str(obj.get("name") or fallback or "").strip()
    return fallback


def _bind_catalog_ids_from_cache(df):
    """Resolve missing ObjectIds from cached JSON maps — no live Tatva HTTP."""
    try:
        from services.tatva_catalog import (
            resolve_pricing_method_id,
            resolve_sub_service_id,
        )
    except Exception:
        return df

    if "sub_service_id" not in df.columns:
        df["sub_service_id"] = ""
    if "pricing_method_id" not in df.columns:
        df["pricing_method_id"] = ""

    def _fill_sub(row):
        existing = str(row.get("sub_service_id") or "").strip()
        if existing:
            return existing
        return resolve_sub_service_id(row.get("sub_service")) or ""

    def _fill_pm(row):
        existing = str(row.get("pricing_method_id") or "").strip()
        if existing:
            return existing
        return resolve_pricing_method_id(row.get("pricing_method")) or ""

    df["sub_service_id"] = df.apply(_fill_sub, axis=1)
    df["pricing_method_id"] = df.apply(_fill_pm, axis=1)
    return df


def mongodb_quotes_to_dataframe(quotes_list: list):
    """Build a comparison DataFrame directly from Tatva/MongoDB quote JSON."""
    try:
        from services.tatva_catalog import register_from_work_item
    except Exception as exc:
        print(f"ℹ️ Catalog harvest skipped: {exc}")
        register_from_work_item = None

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
                service_ref = service_obj.get("serviceId") or {}
                category_name = _nested_name(service_ref, "General")
                service_id = _nested_oid(service_ref)
                for work_item in service_obj.get("workItems") or []:
                    if register_from_work_item:
                        try:
                            register_from_work_item(work_item, persist=False)
                        except Exception:
                            pass
                    sub_ref = work_item.get("subService") or {}
                    sub_service_name = (
                        _nested_name(sub_ref)
                        or work_item.get("workTitle")
                        or "General Service"
                    )
                    space_raw = str(work_item.get("workTitle") or "").strip()
                    pricing_list = work_item.get("pricingInput") or []
                    pricing = pricing_list[0] if pricing_list else {}
                    amount = float(pricing.get("grandTotal") or pricing.get("amount") or 0)
                    pm_ref = work_item.get("pricingMethod") or {}
                    pricing_method = _nested_name(pm_ref, "Unit")
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
                        "service_id": service_id,
                        "sub_service": sub_service_name,
                        "sub_service_id": _nested_oid(sub_ref),
                        "work_title": space_raw,
                        "space_raw": space_raw,
                        "item_name": sub_service_name,
                        "description": str(work_item.get("description") or "").replace("&nbsp;", " "),
                        "quantity": pricing.get("quantity") or 0,
                        "pricing_method": pricing_method,
                        "pricing_method_id": _nested_oid(pm_ref),
                        "rate": pricing.get("rate") or 0,
                        "amount": amount,
                    })

    if not rows:
        raise ValueError("No line items found in quote payloads.")
    df = pd.DataFrame(rows)
    return _bind_catalog_ids_from_cache(df)
    
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
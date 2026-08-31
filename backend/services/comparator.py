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

from services.env_config import (
    gemini_compare_model,
    gemini_generate_config,
    get_gemini_client,
    get_supabase_client,
)
from services.market_rate import (
    DEFAULT_SERVICE_TYPE,
    normalize_pricing_method,
    normalize_service_type,
)
from services.bundles import (
    apply_bundles,
    bundle_comparison_rows,
    bundled_families_by_vendor,
    bundled_space_ids,
)
from services.space_clusters import apply_space_clusters, containment_parent
from services.work_catalog import apply_work_catalog
from services.comparison_summary import row_comparison_summary

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


def _build_fallback_report(chart_data, bundle_tier=None):
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
    # With bundles detected we can say something specific instead of repeating
    # the generic scope caveat above.
    for bundle in bundle_tier or []:
        takeaway = bundle.get("takeaway") or {}
        text = takeaway.get("text") if isinstance(takeaway, dict) else None
        if text:
            lines.append(f"- **Package vs itemised:** {text}")
            break
        basis = bundle.get("basis") or {}
        bundlers = [v for v, b in basis.items() if b == "bundle"]
        if not bundlers:
            continue
        lines.append(
            f"- **Bundled Scope:** {bundlers[0]} priced "
            f"\"{bundle.get('bundle_label')}\" as a single lump sum, so that row is "
            "not a like-for-like comparison — confirm what it covers."
        )
        break
    lines.append(
        "- **Recommendation:** This is an automatic summary (the detailed AI write-up "
        "timed out). Re-run the comparison to retry the full analysis."
    )
    return "\n".join(lines)


def _build_recommendation_prompt(
    space_tier, bundle_tier, project_tier, coverage, vendors, chart_data
):
    """Project the tiered matrix into a prompt that states what a zero means.

    The previous prompt asserted "N/A or 0 means that vendor did not quote that
    work". After S4 that is false for any work a vendor bundled, and the model
    would confidently report a bundled scope as a missing one. Coverage status
    and pricing basis are now passed through explicitly.
    """
    def _amounts(row):
        return {v: int(row.get(v, 0) or 0) for v in vendors}

    by_space = [
        {
            "space": row.get("space"),
            "work": row.get("sub_service"),
            "pricing_method": row.get("pricing_method"),
            "coverage": row.get("coverage") or {},
            **_amounts(row),
        }
        # Drop all-zero rows: they carry no signal and inflate the prompt.
        for row in space_tier
        if any(_amounts(row).values())
    ]
    bundles = [
        {
            "scope": row.get("bundle_label"),
            "covers_spaces": row.get("covered_spaces"),
            "covers_items": row.get("covered_items"),
            "basis": row.get("basis"),
            "possible_double_count": row.get("overlap_flags"),
            "takeaway": (row.get("takeaway") or {}).get("text")
            if isinstance(row.get("takeaway"), dict)
            else None,
            **_amounts(row),
        }
        for row in bundle_tier
    ]
    project = [
        {"work": row.get("sub_service"), **_amounts(row)}
        for row in project_tier
        if any(_amounts(row).values())
    ]
    not_comparable = sorted({
        entry["space"] for entry in coverage if not entry.get("comparable", True)
    })

    return f"""
        You are 'QuoteSense', an expert procurement analyst for TatvaOps.
        Analyze these quotes based strictly on the provided data.

        HOW TO READ THE DATA (important):
        - BY SPACE rows are one work item in one room. Each row has a "coverage"
          map per vendor:
            "quoted"          = that vendor priced this work in this room.
            "incl_in_bundle:X" = that vendor's price for this work is inside its
                                 bundle X. It is NOT a missing item. NEVER say
                                 this vendor did not quote it.
            "not_quoted"      = a genuine gap in that vendor's scope.
        - BUNDLED SCOPES rows compare a single lumpsum against the other vendor's
          itemised lines for the same family. The "basis" map says how each figure
          was arrived at: "bundle" is one lump price, "itemized" is the sum of
          several lines, "none" means nothing quoted. A lumpsum and an itemised
          sum are NOT the same kind of number — if they differ, call it a scope
          difference, not simply a cheaper price.
        - "possible_double_count" lists work the bundle description names that the
          same vendor also bills separately. Treat it as a question for the
          vendor, not a proven error.
        - SPACES NOT DIRECTLY COMPARABLE have a bundle overlapping them, so their
          room totals are not like-for-like.

        BY SPACE:
        {by_space}

        BUNDLED SCOPES:
        {bundles}

        PROJECT-LEVEL (no room):
        {project}

        SPACES NOT DIRECTLY COMPARABLE: {not_comparable}
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
        - **By Space:** name 1-2 rooms where one vendor is clearly cheaper. Only use
          rooms that are NOT in the not-comparable list.
        - **Package vs itemised:** if a bundled-scope row has a "takeaway" string,
          copy that text verbatim. Do not rephrase the amounts. Omit this bullet
          if no takeaway is present. Never write this for a recap where both
          sides are itemised.
        - **Scope Difference:** other bundled-scope or not_quoted gaps, kept distinct
          from the package-vs-itemised takeaway.
        - **Watch Out:** any possible_double_count, or omit this bullet if there is none.
        - **Recommendation:** a clear, practical suggestion on which to pick or what to confirm with vendors.
        """


def _generate_recommendation(summary_prompt, chart_data, bundle_tier=None):
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
                model=gemini_compare_model(),
                contents=summary_prompt,
                config=gemini_generate_config(
                    types,
                    model=gemini_compare_model(),
                    temperature=0.2,
                ),
            )
        )
        summary_response = future.result(timeout=RECOMMENDATION_TIMEOUT_SEC)
        return summary_response.text
    except concurrent.futures.TimeoutError:
        print(
            f"⚠️ Recommendation timed out after {RECOMMENDATION_TIMEOUT_SEC}s — "
            "returning data-driven fallback summary."
        )
        return _build_fallback_report(chart_data, bundle_tier)
    except Exception as e:
        print(f"⚠️ Recommendation generation failed: {e} — using fallback summary.")
        return _build_fallback_report(chart_data, bundle_tier)
    finally:
        ex.shutdown(wait=False)


def _vendor_measures(line_slice, vendor: str) -> dict:
    if "vendor_name" not in line_slice.columns:
        return {"quantity": 0.0, "rate": 0.0, "pricing_method": "", "description": ""}
    slice_ = line_slice[line_slice["vendor_name"] == vendor]
    if len(slice_) == 0:
        return {"quantity": 0.0, "rate": 0.0, "pricing_method": "", "description": ""}
    qty = 0.0
    if "quantity" in slice_.columns:
        qty = float(pd.to_numeric(slice_["quantity"], errors="coerce").fillna(0).sum())
    amount = float(pd.to_numeric(slice_["amount"], errors="coerce").fillna(0).sum())
    rate = 0.0
    if "rate" in slice_.columns:
        rates = pd.to_numeric(slice_["rate"], errors="coerce").fillna(0)
        if len(slice_) == 1:
            rate = float(rates.iloc[0] or 0)
        elif qty > 0:
            rate = amount / qty
        elif len(rates):
            rate = float(rates.mean())
    elif qty > 0:
        rate = amount / qty
    method = ""
    if "pricing_method" in slice_.columns:
        mode = slice_["pricing_method"].mode()
        if not mode.empty:
            method = normalize_pricing_method(str(mode.iloc[0] or "Unit"))
    desc = ""
    if "description" in slice_.columns:
        seen: set[str] = set()
        parts: list[str] = []
        for raw in slice_["description"].tolist():
            text = str(raw or "").strip()
            key = text.casefold()
            if not text or key in seen:
                continue
            seen.add(key)
            parts.append(text)
        desc = " · ".join(parts)[:280]
    return {
        "quantity": round(qty, 4),
        "rate": round(rate, 2),
        "pricing_method": method,
        "description": desc,
    }


def _parent_id_for_slice(line_slice, space_id: str, present: set[str]) -> str:
    if "contained_in" in line_slice.columns:
        raw = str(line_slice["contained_in"].iloc[0] or "").strip()
        if raw:
            return raw
    return containment_parent(str(space_id), present)


def _build_space_rows(subset, vendors, bundled_families=None):
    """Pivot rows into one entry per (space_id, work_key).

    Both halves of the key are canonical, which is what makes `Side table` and
    `Side Table`, or `Bedroom 1` and `GF Bedroom 1`, land on a single row. The
    displayed label comes from the modal work label among the contributing lines
    so the row still reads in human words.
    """
    if subset is None or len(subset) == 0:
        return []

    space_order = subset.groupby('space_id')['__seq'].min().to_dict()
    work_order = subset.groupby(['space_id', 'work_key'])['__seq'].min().to_dict()

    totals = (
        subset.groupby(['space_id', 'work_key', 'vendor_name'])['amount']
        .sum()
        .reset_index()
    )
    pivot_df = totals.pivot(
        index=['space_id', 'work_key'],
        columns='vendor_name',
        values='amount',
    ).fillna(0.0)

    rows = []
    for index, amounts in pivot_df.iterrows():
        space_id, work_key = index
        line_slice = subset.loc[
            (subset['space_id'] == space_id) & (subset['work_key'] == work_key)
        ]
        if len(line_slice) == 0:
            continue

        def _modal(column, fallback=""):
            if column not in line_slice.columns:
                return fallback
            mode = line_slice[column].mode()
            if mode.empty:
                return fallback
            return str(mode.iloc[0])

        label = _modal('work_label') or _modal('sub_service') or str(work_key)
        space_label = _modal('space', 'Project-level')
        space_raws = sorted({
            str(v).strip()
            for v in line_slice.get('space_raw', pd.Series(dtype=str)).tolist()
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
            "category": _modal('service_category', 'Other'),
            "space_id": str(space_id),
            "space": space_label,
            "space_raw": " · ".join(space_raws),
            "work_key": str(work_key),
            "sub_service": label,
            "sub_service_id": _modal('sub_service_id'),
            "work_confidence": float(line_slice['work_confidence'].min())
            if 'work_confidence' in line_slice.columns else 1.0,
            "space_confidence": float(line_slice['space_confidence'].min())
            if 'space_confidence' in line_slice.columns else 1.0,
            # Retained for existing consumers that read the flat shape.
            "item_name": label,
            "room": space_label,
            "work_item": label,
            "taxonomy": label,
            "service_type": normalize_service_type(
                _modal('service_type', DEFAULT_SERVICE_TYPE)
            ),
            "pricing_method": normalize_pricing_method(_modal('pricing_method', 'Unit')),
            "breakdown": breakdown,
            "_space_order": float(space_order.get(space_id, 1e9)),
            "_work_order": float(work_order.get((space_id, work_key), 1e9)),
        }
        # Cell-level coverage. A zero is only "not quoted" when the vendor has
        # not bundled this work's family somewhere else, and not priced the
        # same work_key in a parent space (nested room).
        family = str(_modal('bundle_family'))
        if family.casefold() in ("nan", "none", "null"):
            family = ""
        row_dict["bundle_family"] = family
        present_ids = {str(v) for v in subset["space_id"].tolist()}
        parent_id = _parent_id_for_slice(line_slice, str(space_id), present_ids)
        parent_label = ""
        if parent_id:
            parent_rows = subset[subset["space_id"].astype(str) == parent_id]
            if len(parent_rows):
                parent_label = str(parent_rows["space"].iloc[0] or parent_id)
        row_dict["contained_in"] = parent_id
        measures = {vendor: _vendor_measures(line_slice, vendor) for vendor in vendors}
        row_dict["measures"] = measures
        cell_coverage = {}
        for vendor in vendors:
            amount = float(amounts[vendor]) if vendor in amounts.index else 0.0
            row_dict[vendor] = round(amount) if amount > 0 else 0
            if amount > 0:
                cell_coverage[vendor] = "quoted"
                continue
            bundle_label = (bundled_families or {}).get(vendor, {}).get(family)
            if bundle_label:
                cell_coverage[vendor] = f"incl_in_bundle:{bundle_label}"
                continue
            parent_hit = False
            if parent_id:
                parent_work = subset[
                    (subset["space_id"].astype(str) == parent_id)
                    & (subset["work_key"] == work_key)
                    & (subset["vendor_name"] == vendor)
                ]
                parent_amt = (
                    float(pd.to_numeric(parent_work["amount"], errors="coerce").fillna(0).sum())
                    if len(parent_work)
                    else 0.0
                )
                if parent_amt > 0:
                    cell_coverage[vendor] = f"incl_in_parent:{parent_label or parent_id}"
                    parent_hit = True
            if not parent_hit:
                cell_coverage[vendor] = "not_quoted"
        row_dict["coverage"] = cell_coverage
        row_dict["summary"] = row_comparison_summary(row_dict, vendors)
        rows.append(row_dict)

    rows.sort(key=lambda r: (r["_space_order"], r["_work_order"]))
    for row in rows:
        row.pop("_space_order", None)
        row.pop("_work_order", None)
    return rows


def _build_coverage(df, vendors):
    """Per (space, vendor) status so the UI stops calling everything N/A.

    A zero used to be rendered as "did not quote" in every case. After S4 it can
    equally mean the amount sits inside a bundle, which is a completely different
    conclusion for a buyer.
    """
    if df is None or len(df) == 0:
        return []

    space_rows = df[df['scope'] == 'space']
    if len(space_rows) == 0:
        return []

    affected = bundled_space_ids(df)
    ordered = (
        space_rows.groupby(['space_id'])['__seq'].min().sort_values().index.tolist()
    )
    present_ids = {str(s) for s in ordered}

    bundle_label_by_vendor = {}
    for _, row in df[df['scope'] == 'bundle'].iterrows():
        vendor = str(row.get('vendor_name') or '')
        bundle_label_by_vendor.setdefault(vendor, []).append(
            (str(row.get('bundle_id') or ''), str(row.get('bundle_label') or 'bundle'))
        )

    entries = []
    for space_id in ordered:
        slice_ = space_rows[space_rows['space_id'] == space_id]
        space_label = str(slice_['space'].iloc[0]) if len(slice_) else str(space_id)
        quoted_vendors = set(slice_['vendor_name'].tolist())
        bundled_here = {
            vendor for vendor, spaces in affected.items() if str(space_id) in spaces
        }
        parent_id = ""
        if "contained_in" in slice_.columns:
            parent_id = str(slice_["contained_in"].iloc[0] or "").strip()
        if not parent_id:
            parent_id = containment_parent(str(space_id), present_ids)
        parent_label = ""
        parent_quoted: set[str] = set()
        if parent_id:
            parent_slice = space_rows[space_rows["space_id"].astype(str) == parent_id]
            if len(parent_slice):
                parent_label = str(parent_slice["space"].iloc[0] or parent_id)
                parent_quoted = set(str(v) for v in parent_slice["vendor_name"].tolist())

        per_vendor: list[tuple[str, str, str]] = []
        has_parent_gap = False
        for vendor in vendors:
            if vendor in quoted_vendors:
                per_vendor.append((vendor, "quoted", ""))
            elif vendor in bundled_here:
                per_vendor.append((vendor, "incl_in_bundle", (bundle_label_by_vendor.get(vendor) or [("", "")])[0][0]))
            elif vendor in parent_quoted:
                per_vendor.append((vendor, "incl_in_parent", parent_id))
                has_parent_gap = True
            else:
                per_vendor.append((vendor, "not_quoted", ""))
        comparable = len(bundled_here) == 0 and not has_parent_gap

        for vendor, status, extra_id in per_vendor:
            entry = {
                "space_id": str(space_id),
                "space": space_label,
                "vendor": vendor,
                "status": status,
                "comparable": comparable,
            }
            if status == "incl_in_bundle" and extra_id:
                entry["bundle_id"] = extra_id
                entry["bundle_label"] = (
                    bundle_label_by_vendor.get(vendor) or [("", "")]
                )[0][1]
            if status == "incl_in_parent":
                entry["parent_space_id"] = parent_id
                entry["parent_space"] = parent_label or parent_id
            entries.append(entry)
    return entries


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
        has_gst_mode = 'gst_mode' in df.columns
        vendor_meta = {}
        for _, r in df.drop_duplicates('vendor_name').iterrows():
            key = r['vendor_name']
            vendor_meta[key] = {
                "company": str(r.get('company', '') or '').strip(),
                "filename": str(r.get('source_filename', '') or '').strip(),
                "quote_number": (str(r.get('quote_number', '') or '').strip() if has_quote_number else ''),
                "quote_date": (str(r.get('quote_date', '') or '').strip() if has_quote_date else ''),
                "gst_mode": (str(r.get('gst_mode', '') or '').strip() if has_gst_mode else ''),
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

        if "sub_service_id" not in df.columns:
            df["sub_service_id"] = ""
        df["sub_service_id"] = df["sub_service_id"].fillna("").astype(str).str.strip()

        # Stage order is fixed and documented in backend/docs/plan/. Each stage
        # only adds fields, so a failure in one is isolated from the others.
        df = _bind_catalog_ids_from_cache(df)   # S2a — Tatva ObjectIds
        df = apply_work_catalog(df)             # S2b — work_key
        df = apply_space_clusters(df)           # S3  — space_id
        df = apply_bundles(df)                  # S4  — scope

        def _item_label(r):
            if not _is_blank(r['item_name']):
                return r['item_name']
            if not _is_blank(r['sub_service']):
                return r['sub_service']
            return r['work_title'] or 'Unspecified Item'

        df['item_label'] = df.apply(_item_label, axis=1)
        df['room'] = df['space']
        df['work_item'] = df['item_label']

        df = df.reset_index(drop=True)
        df['__seq'] = range(len(df))
        vendors = sorted(df['vendor_name'].unique().tolist())

        # Three tiers keyed by scope, so every rupee lands in exactly one of them.
        # A bundle spans several rooms, so it cannot sit in the space tier without
        # either distorting a room total or vanishing from all of them.
        bundled_families = bundled_families_by_vendor(df)
        space_tier = _build_space_rows(
            df[df['scope'] == 'space'], vendors, bundled_families
        )
        project_tier = _build_space_rows(
            df[df['scope'] == 'project'], vendors, bundled_families
        )
        bundle_tier = bundle_comparison_rows(df, vendors)
        coverage = _build_coverage(df, vendors)

        table_data = space_tier + project_tier

        print(
            f"📊 Built matrix: {len(space_tier)} space rows, {len(bundle_tier)} bundle rows, "
            f"{len(project_tier)} project rows across {len(vendors)} quotes."
        )

        # Publish the fast matrix result before the slow recommendation call so the
        # frontend can render the chart + table right away.
        matrix_payload = sanitize_for_json({
            "contract_version": "MatrixV1",
            "chartData": chart_data,
            "spaceTier": space_tier,
            "bundleTier": bundle_tier,
            "projectTier": project_tier,
            "coverage": coverage,
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

        summary_prompt = _build_recommendation_prompt(
            space_tier, bundle_tier, project_tier, coverage, vendors, chart_data
        )
        ai_report = _generate_recommendation(summary_prompt, chart_data, bundle_tier)

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


def gst_mode_from_quote(quote_data: dict) -> str:
    """Read Tatva workSummary GST flags.

    Vendors choose exclusive (prices before GST) or inclusive (prices already
    include GST). Returns ``exclusive``, ``inclusive``, ``mixed``, or ``""``.
    """
    modes: set[str] = set()
    for section in quote_data.get("workSummary") or []:
        if not isinstance(section, dict):
            continue
        exclusive = bool(section.get("exclusiveGst"))
        inclusive = bool(section.get("inclusiveGst"))
        if exclusive and not inclusive:
            modes.add("exclusive")
        elif inclusive and not exclusive:
            modes.add("inclusive")
        elif exclusive and inclusive:
            modes.add("mixed")
    if not modes:
        return ""
    if modes == {"exclusive"}:
        return "exclusive"
    if modes == {"inclusive"}:
        return "inclusive"
    return "mixed"


def _qty_rate_from_pricing(pricing_list) -> tuple[float, float]:
    """Copy qty/rate as written. Do not invent area from amount when qty is 0."""
    qty = 0.0
    rate = 0.0
    if not isinstance(pricing_list, list):
        return 0.0, 0.0
    for raw in pricing_list:
        if not isinstance(raw, dict):
            continue
        q = raw.get("quantity", raw.get("qty", raw.get("area")))
        try:
            qty += float(q or 0)
        except (TypeError, ValueError):
            pass
        if rate <= 0:
            r = raw.get("rate", raw.get("unitRate"))
            try:
                rate = float(r or 0)
            except (TypeError, ValueError):
                pass
    return qty, rate


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
        gst_mode = gst_mode_from_quote(quote_data)

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
                    qty, rate = _qty_rate_from_pricing(pricing_list)
                    rows.append({
                        "vendor_name": vendor_key,
                        "company": company,
                        "source_filename": source_filename,
                        "quote_number": quote_number,
                        "quote_date": quote_date[:10] if len(quote_date) >= 10 else quote_date,
                        "gst_mode": gst_mode,
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
                        "quantity": qty,
                        "pricing_method": pricing_method,
                        "pricing_method_id": _nested_oid(pm_ref),
                        "rate": rate,
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
            model=gemini_compare_model(),
            contents=prompt,
            config=gemini_generate_config(
                types,
                model=gemini_compare_model(),
                temperature=0.2,
            ),
        )
        
        return chat_response.text

    except Exception as e:
        return f"❌ Sorry, I encountered an error while accessing your data: {e}"
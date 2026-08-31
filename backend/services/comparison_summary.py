"""Deterministic row-wise comparison summary (S5).

Explains why one vendor's figure is higher using payload quantity, rate,
pricing method, and coverage. Does not reallocate rupees or invent area.
"""

from __future__ import annotations

from typing import Any


def _who(vendor: str) -> str:
    return (vendor.split(" (")[0] or vendor).strip() or vendor


def _qty_unit(pricing_method: str) -> str:
    pm = (pricing_method or "").casefold()
    if "sq ft" in pm or "sqft" in pm or "sq.ft" in pm:
        return "sqft"
    if "sq m" in pm or "sqm" in pm:
        return "sqm"
    if "rft" in pm or "running" in pm:
        return "rft"
    return "units"


def _inr(amount: float) -> str:
    n = int(round(float(amount) or 0))
    return f"₹{n:,}"


def _coverage_place(raw: str, prefix: str) -> str:
    if ":" in raw:
        return raw.split(":", 1)[1].strip() or prefix
    return prefix


def _measure(row: dict[str, Any], vendor: str) -> dict[str, Any]:
    measures = row.get("measures") or {}
    raw = measures.get(vendor) if isinstance(measures, dict) else None
    if not isinstance(raw, dict):
        return {"quantity": 0.0, "rate": 0.0, "pricing_method": ""}
    try:
        qty = float(raw.get("quantity") or 0)
    except (TypeError, ValueError):
        qty = 0.0
    try:
        rate = float(raw.get("rate") or 0)
    except (TypeError, ValueError):
        rate = 0.0
    return {
        "quantity": qty,
        "rate": rate,
        "pricing_method": str(raw.get("pricing_method") or ""),
    }


def _amount_clause(amt_a: float, amt_b: float, a: str, b: str) -> str:
    if abs(amt_a - amt_b) < 1:
        return "Same amount"
    higher = a if amt_a > amt_b else b
    return f"{_who(higher)} is {_inr(abs(amt_a - amt_b))} higher"


def row_comparison_summary(row: dict[str, Any], vendors: list[str]) -> str:
    """One sentence for a work (or space) row. Empty when there is nothing to say."""
    if len(vendors) < 2:
        return ""

    coverage = row.get("coverage") or {}
    amounts: dict[str, float] = {}
    for vendor in vendors:
        try:
            amounts[vendor] = float(row.get(vendor) or 0)
        except (TypeError, ValueError):
            amounts[vendor] = 0.0

    elsewhere: list[str] = []
    gaps: list[str] = []
    quoted: list[str] = []
    for vendor in vendors:
        status = str(coverage.get(vendor) or "")
        if status.startswith("incl_in_parent"):
            place = _coverage_place(status, "another space")
            elsewhere.append(f"{_who(vendor)}'s figure is inside {place}")
        elif status.startswith("incl_in_bundle"):
            place = _coverage_place(status, "a package")
            elsewhere.append(f"{_who(vendor)}'s figure is inside {place}")
        elif amounts[vendor] > 0 or status == "quoted":
            quoted.append(vendor)
        else:
            gaps.append(vendor)

    if elsewhere:
        return "; ".join(elsewhere)

    if len(quoted) == 1 and gaps:
        return f"{_who(gaps[0])} did not quote this line"

    if len(quoted) < 2:
        return ""

    a, b = quoted[0], quoted[1]
    amt_a, amt_b = amounts[a], amounts[b]
    ma, mb = _measure(row, a), _measure(row, b)
    qty_a, qty_b = ma["quantity"], mb["quantity"]
    rate_a, rate_b = ma["rate"], mb["rate"]
    unit = _qty_unit(ma["pricing_method"] or mb["pricing_method"])

    amount = _amount_clause(amt_a, amt_b, a, b)
    if qty_a > 0 and qty_b > 0:
        mid = (qty_a + qty_b) / 2.0
        qty_gap = abs(qty_a - qty_b) / mid if mid else 0.0
        if qty_gap >= 0.10:
            return f"{amount} — {qty_a:g} {unit} vs {qty_b:g} {unit} (billed more area)"
        if rate_a > 0 and rate_b > 0:
            rmid = (rate_a + rate_b) / 2.0
            if rmid and abs(rate_a - rate_b) / rmid >= 0.10:
                higher = a if rate_a > rate_b else b
                return f"{amount} — same area, {_who(higher)}'s rate is higher"

    return amount


def _item_count_reason(
    totals: dict[str, float],
    vendors: list[str],
    item_counts: dict[str, int] | None,
) -> str:
    if not item_counts or len(vendors) < 2:
        return ""
    quoted = [v for v in vendors if (totals.get(v) or 0) > 0]
    if len(quoted) < 2:
        return ""
    a, b = quoted[0], quoted[1]
    n_a = int(item_counts.get(a) or 0)
    n_b = int(item_counts.get(b) or 0)
    if n_a == n_b or (n_a == 0 and n_b == 0):
        return ""
    amt_a = float(totals.get(a) or 0)
    amt_b = float(totals.get(b) or 0)
    higher = a if amt_a >= amt_b else b
    higher_n = n_a if higher == a else n_b
    other_n = n_b if higher == a else n_a
    text = f"{n_a} items vs {n_b}"
    if higher_n < other_n:
        text += f" — {_who(higher)} charged more for fewer lines"
    return text


def space_header_summary(
    totals: dict[str, float],
    vendors: list[str],
    *,
    comparable: bool = True,
    coverage_notes: list[str] | None = None,
    item_counts: dict[str, int] | None = None,
    exclusive_labels: dict[str, list[str]] | None = None,
    package_vs_itemised: bool = False,
) -> str:
    """Space-header sentence from totals. Does not change the addition."""
    notes = [n for n in (coverage_notes or []) if n]
    skip_gap = bool(notes)

    quoted = [v for v in vendors if (totals.get(v) or 0) > 0]
    gaps = [v for v in vendors if (totals.get(v) or 0) <= 0]
    amount = ""
    if len(quoted) == 1 and gaps and not skip_gap:
        amount = f"{_who(gaps[0])} did not quote this line"
    elif len(quoted) >= 2:
        a, b = quoted[0], quoted[1]
        amount = _amount_clause(
            float(totals.get(a) or 0), float(totals.get(b) or 0), a, b
        )

    parts: list[str] = []
    if amount:
        parts.append(amount)
    if not comparable:
        parts.append(
            "scopes differ (package vs itemised)"
            if package_vs_itemised
            else "scopes differ"
        )
    counts = _item_count_reason(totals, vendors, item_counts)
    if counts:
        parts.append(counts)
    if exclusive_labels:
        for vendor in vendors:
            labels = [lab for lab in (exclusive_labels.get(vendor) or []) if lab][:3]
            if labels:
                parts.append(f"{_who(vendor)} also quoted {', '.join(labels)}")
    parts.extend(notes)
    return " · ".join(parts)

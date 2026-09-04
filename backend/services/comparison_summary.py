"""Deterministic row-wise comparison summary (S5).

Explains why one vendor's figure is higher using payload quantity, rate,
pricing method, coverage, and named finishes in description. Does not
reallocate rupees or invent area or materials.
"""

from __future__ import annotations

import re
from typing import Any

# Phrases the vendor must have written. Not a work list (ACTION.md §2).
_SPEC_TERMS: tuple[tuple[str, str], ...] = (
    ("hi-gloss", "hi-gloss"),
    ("hi gloss", "hi-gloss"),
    ("high gloss", "hi-gloss"),
    ("hdhmr", "HDHMR"),
    ("greenply", "Greenply"),
    ("century", "Century"),
    ("merino", "Merino"),
    ("hettich", "Hettich"),
    ("hafele", "Hafele"),
    ("laminates", "laminates"),
    ("laminate", "laminate"),
    ("louvers", "louvers"),
    ("louver", "louver"),
    ("louvres", "louvers"),
    ("louvre", "louver"),
    ("plywood", "plywood"),
    ("beeding", "beeding"),
    ("beading", "beading"),
    ("membrane", "membrane"),
    ("veneer", "veneer"),
    ("acrylic", "acrylic"),
    ("premium", "premium"),
    ("mirror", "mirror"),
    ("glass", "glass"),
    ("walnut", "walnut"),
    ("blum", "Blum"),
    ("matt", "matt"),
    ("matte", "matte"),
    ("teak", "teak"),
    ("oak", "oak"),
    ("pvc", "PVC"),
    ("mdf", "MDF"),
    ("pu finish", "PU finish"),
)


def _who(vendor: str) -> str:
    return (vendor.split(" (")[0] or vendor).strip() or vendor


def _vendor_refs(vendors: list[str]) -> dict[str, str]:
    """Readable labels; duplicate company names become Vendor Q1 / Vendor Q2."""
    base = {vendor: _who(vendor) for vendor in vendors}
    counts: dict[str, int] = {}
    for name in base.values():
        key = name.casefold()
        counts[key] = counts.get(key, 0) + 1
    return {
        vendor: (
            f"{name} Q{index + 1}"
            if counts.get(name.casefold(), 0) > 1
            else name
        )
        for index, (vendor, name) in enumerate(base.items())
    }


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
        return {"quantity": 0.0, "rate": 0.0, "pricing_method": "", "description": ""}
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
        "description": str(raw.get("description") or ""),
    }


def _spec_tokens(description: str) -> list[str]:
    text = re.sub(r"<[^>]+>", " ", description or "")
    text = re.sub(r"\s+", " ", text).strip()
    if not text:
        return []
    folded = text.casefold()
    found: list[str] = []
    seen: set[str] = set()
    for term, label in _SPEC_TERMS:
        if label.casefold() in seen:
            continue
        if not re.search(rf"(?<![a-z0-9]){re.escape(term)}(?![a-z0-9])", folded):
            continue
        found.append(label)
        seen.add(label.casefold())
        if len(found) >= 4:
            break
    return found


def _spec_clause(ma: dict[str, Any], mb: dict[str, Any], a: str, b: str) -> str:
    ta = _spec_tokens(str(ma.get("description") or ""))
    tb = _spec_tokens(str(mb.get("description") or ""))
    if not ta and not tb:
        return ""
    if ta and tb and set(x.casefold() for x in ta) == set(x.casefold() for x in tb):
        return ""
    bits: list[str] = []
    if ta:
        bits.append(f"{_who(a)} specified {', '.join(ta)}")
    if tb:
        bits.append(f"{_who(b)} specified {', '.join(tb)}")
    return "; ".join(bits)


def _amount_clause(amt_a: float, amt_b: float, a: str, b: str) -> str:
    if abs(amt_a - amt_b) < 1:
        return "Same amount"
    higher = a if amt_a > amt_b else b
    return f"{_who(higher)} is {_inr(abs(amt_a - amt_b))} higher"


def _qty_rate_parts(
    qty_a: float,
    qty_b: float,
    rate_a: float,
    rate_b: float,
    unit: str,
    a: str,
    b: str,
) -> list[str]:
    parts: list[str] = []
    qty_gap = False
    if qty_a > 0 and qty_b > 0:
        mid = (qty_a + qty_b) / 2.0
        qty_gap = bool(mid and abs(qty_a - qty_b) / mid >= 0.10)
        if qty_gap:
            more = a if qty_a > qty_b else b
            parts.append(
                f"{_who(a)}: {qty_a:g} {unit}; {_who(b)}: {qty_b:g} {unit} "
                f"({_who(more)} billed more area)"
            )
    if rate_a > 0 and rate_b > 0:
        rmid = (rate_a + rate_b) / 2.0
        if rmid and abs(rate_a - rate_b) / rmid >= 0.10:
            higher = a if rate_a > rate_b else b
            rates = (
                f"{_who(a)}: {_inr(rate_a)}/{unit}; "
                f"{_who(b)}: {_inr(rate_b)}/{unit}"
            )
            if qty_gap:
                parts.append(rates)
            elif qty_a > 0 and qty_b > 0:
                parts.append(f"same area, {_who(higher)}'s rate is higher ({rates})")
            else:
                parts.append(f"{_who(higher)}'s rate is higher ({rates})")
    return parts


def row_comparison_summary(row: dict[str, Any], vendors: list[str]) -> str:
    """One sentence for a work (or space) row. Empty when there is nothing to say."""
    if len(vendors) < 2:
        return ""

    refs = _vendor_refs(vendors)
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
            elsewhere.append(f"{refs[vendor]}'s figure is inside {place}")
        elif status.startswith("incl_in_bundle"):
            place = _coverage_place(status, "a package")
            elsewhere.append(f"{refs[vendor]}'s figure is inside {place}")
        elif amounts[vendor] > 0 or status == "quoted":
            quoted.append(vendor)
        else:
            gaps.append(vendor)

    if elsewhere:
        return "; ".join(elsewhere)

    if len(quoted) == 1 and gaps:
        return f"{refs[gaps[0]]} did not quote this line"

    if len(quoted) < 2:
        return ""

    a, b = quoted[0], quoted[1]
    amt_a, amt_b = amounts[a], amounts[b]
    ma, mb = _measure(row, a), _measure(row, b)
    qty_a, qty_b = ma["quantity"], mb["quantity"]
    rate_a, rate_b = ma["rate"], mb["rate"]
    unit = _qty_unit(ma["pricing_method"] or mb["pricing_method"])

    amount = _amount_clause(amt_a, amt_b, refs[a], refs[b])
    reasons = _qty_rate_parts(
        qty_a, qty_b, rate_a, rate_b, unit, refs[a], refs[b]
    )
    spec = _spec_clause(ma, mb, refs[a], refs[b])
    if spec:
        reasons.append(spec)
    if not reasons:
        return amount
    return f"{amount} — " + " · ".join(reasons)


def _item_count_reason(
    totals: dict[str, float],
    vendors: list[str],
    item_counts: dict[str, int] | None,
    refs: dict[str, str],
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
        text += f" — {refs[higher]} charged more for fewer lines"
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
    refs = _vendor_refs(vendors)
    notes = [n for n in (coverage_notes or []) if n]
    skip_gap = bool(notes)

    quoted = [v for v in vendors if (totals.get(v) or 0) > 0]
    gaps = [v for v in vendors if (totals.get(v) or 0) <= 0]
    amount = ""
    if len(quoted) == 1 and gaps and not skip_gap:
        amount = f"{refs[gaps[0]]} did not quote this line"
    elif len(quoted) >= 2:
        a, b = quoted[0], quoted[1]
        amount = _amount_clause(
            float(totals.get(a) or 0),
            float(totals.get(b) or 0),
            refs[a],
            refs[b],
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
    counts = _item_count_reason(totals, vendors, item_counts, refs)
    if counts:
        parts.append(counts)
    if exclusive_labels:
        for vendor in vendors:
            labels = [lab for lab in (exclusive_labels.get(vendor) or []) if lab][:3]
            if labels:
                parts.append(f"{refs[vendor]} also quoted {', '.join(labels)}")
    parts.extend(notes)
    return " · ".join(parts)

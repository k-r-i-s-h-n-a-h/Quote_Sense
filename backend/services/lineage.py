"""S1 lineage + the pre-render reconciliation gate.

Every comparison row must be traceable back to the vendor lines it was built
from, and every source line must land in exactly one row. Without that, a line
can vanish from the matrix and nothing notices: a real client comparison lost
`Soft closing hinges` (Rs 29,146) entirely, and two unrelated lines collided
under one relabelled row, because no stage owned the question "did all the
money arrive?".

`line_id` is the anchor. It is assigned once, in S1, and never rewritten.
Downstream rows carry `source_line_ids` (flat, every contributing line) and
`line_ids` (per vendor), which is what the gate below sums.

Out of scope for the gate, by design: GST, discount, and TatvaOps
service-charge lines. Those are quote footer arithmetic, not scope, and the
matrix deliberately does not paint them.

See backend/docs/plan/01-extract.md and 05-matrix.md.
"""

from __future__ import annotations

import re
from typing import Any, Iterable

LINE_ID_COLUMN = "line_id"

# Per-row rounding of paise amounts is allowed to drift by a rupee or so.
# Anything larger is a lost or double-counted line, not rounding.
RECONCILE_TOLERANCE_INR = 5.0

# Quote footer arithmetic. Not scope, never a comparison row.
OUT_OF_SCOPE_PATTERN = re.compile(
    r"\b(?:gst|cgst|sgst|igst|tax(?:es|able)?|discount|round\s*off|"
    r"tatvaops\s+service|service\s+charges?|grand\s+total|sub\s*total)\b",
    re.I,
)

OUT_OF_SCOPE_NOTE = (
    "GST, discount, and TatvaOps service-charge lines are excluded from the "
    "reconciliation baseline — they are quote footer arithmetic, not scope."
)


class ReconciliationError(RuntimeError):
    """Raised when a vendor's rows do not add up to that vendor's quote lines."""


def _slug(text: str) -> str:
    return re.sub(r"[^A-Za-z0-9]+", "_", str(text or "").strip()).strip("_")


def _quote_tag(row: Any) -> str:
    for column in ("quote_number", "source_filename", "vendor_name"):
        value = _slug(row.get(column) if hasattr(row, "get") else "")
        if value:
            return value[:32]
    return "quote"


def ensure_line_ids(df):
    """Give every source line a stable `line_id`. Idempotent.

    Ids the payload already supplied (the Supabase lane has `quote_items.id`)
    are kept verbatim; only blanks are minted, numbered per quote in the order
    the lines were extracted.
    """
    if df is None or len(df) == 0:
        return df

    existing = (
        df[LINE_ID_COLUMN].fillna("").astype(str).str.strip().tolist()
        if LINE_ID_COLUMN in df.columns
        else [""] * len(df)
    )

    counters: dict[str, int] = {}
    seen: set[str] = set()
    ids: list[str] = []
    for (_, row), current in zip(df.iterrows(), existing):
        candidate = current
        if not candidate or candidate.lower() in ("nan", "none", "null"):
            tag = _quote_tag(row)
            counters[tag] = counters.get(tag, 0) + 1
            candidate = f"{tag}:L{counters[tag]:03d}"
        # Two lanes could hand us the same id; a collision here would silently
        # merge two lines' lineage.
        while candidate in seen:
            candidate = f"{candidate}+"
        seen.add(candidate)
        ids.append(candidate)

    df[LINE_ID_COLUMN] = ids
    return df


def is_out_of_scope_line(row: Any) -> bool:
    """True for a GST / discount / service-charge line."""
    get = row.get if hasattr(row, "get") else (lambda _k, _d=None: None)
    blob = " ".join(
        str(get(column, "") or "")
        for column in ("sub_service", "item_name", "work_title", "work_label")
    )
    return bool(OUT_OF_SCOPE_PATTERN.search(blob))


def source_line_index(df) -> dict[str, dict[str, Any]]:
    """`line_id` -> {vendor, amount, label, out_of_scope} for the gate."""
    if df is None or len(df) == 0:
        return {}
    df = ensure_line_ids(df)
    index: dict[str, dict[str, Any]] = {}
    for _, row in df.iterrows():
        try:
            amount = float(row.get("amount") or 0)
        except (TypeError, ValueError):
            amount = 0.0
        index[str(row.get(LINE_ID_COLUMN) or "")] = {
            "vendor": str(row.get("vendor_name") or ""),
            "amount": amount,
            "label": str(row.get("item_name") or row.get("sub_service") or ""),
            "space": str(row.get("space") or ""),
            "out_of_scope": is_out_of_scope_line(row),
        }
    return index


def _row_line_ids(row: dict[str, Any], vendor: str) -> list[str]:
    """Line ids this row attributes to one vendor."""
    per_vendor = row.get("line_ids")
    if isinstance(per_vendor, dict):
        return [str(v) for v in (per_vendor.get(vendor) or []) if str(v)]
    return []


def _rows_for_vendor(
    vendor: str,
    space_tier: Iterable[dict[str, Any]],
    project_tier: Iterable[dict[str, Any]],
    bundle_tier: Iterable[dict[str, Any]],
) -> list[dict[str, Any]]:
    """Rows whose rupees are that vendor's, counted once.

    A bundle row with `basis == "itemized"` is a comparison view of lines that
    already sit in the space or project tier, so counting it again would double
    the money. Only a real lumpsum (`basis == "bundle"`) is extra.
    """
    rows = list(space_tier) + list(project_tier)
    for row in bundle_tier:
        if (row.get("basis") or {}).get(vendor) == "bundle":
            rows.append(row)
    return rows


def reconcile_vendor_totals(
    df,
    vendors: list[str],
    space_tier: list[dict[str, Any]],
    project_tier: list[dict[str, Any]],
    bundle_tier: list[dict[str, Any]],
    *,
    tolerance: float = RECONCILE_TOLERANCE_INR,
) -> dict[str, Any]:
    """Per vendor: do the rendered rows add up to that vendor's quoted lines?

    Returns a report, never raises. `ok is False` blocks PDF generation and
    names the unaccounted `line_id`s so the loss is findable instead of
    invisible.
    """
    index = source_line_index(df)
    report: dict[str, Any] = {
        "ok": True,
        "tolerance_inr": tolerance,
        "out_of_scope_note": OUT_OF_SCOPE_NOTE,
        "vendors": {},
    }

    for vendor in vendors:
        expected_ids = {
            line_id
            for line_id, meta in index.items()
            if meta["vendor"] == vendor and not meta["out_of_scope"]
        }
        expected_total = sum(index[line_id]["amount"] for line_id in expected_ids)

        rows = _rows_for_vendor(vendor, space_tier, project_tier, bundle_tier)
        covered: set[str] = set()
        rows_total = 0.0
        row_count = 0
        for row in rows:
            try:
                amount = float(row.get(vendor) or 0)
            except (TypeError, ValueError):
                amount = 0.0
            ids = _row_line_ids(row, vendor)
            if amount <= 0 and not ids:
                continue
            rows_total += amount
            row_count += 1
            covered.update(ids)

        missing = expected_ids - covered
        # A zero-rupee line cannot hide money, so it is reported but does not
        # block the artefact. Anything with rupees on it does.
        unaccounted = sorted(
            line_id for line_id in missing if index[line_id]["amount"] > 0
        )
        unaccounted_zero = sorted(
            line_id for line_id in missing if index[line_id]["amount"] <= 0
        )
        unexpected = sorted(
            line_id
            for line_id in covered - expected_ids
            if not index.get(line_id, {}).get("out_of_scope")
        )
        delta = round(rows_total, 2) - round(expected_total, 2)
        vendor_ok = abs(delta) <= tolerance and not unaccounted and not unexpected
        if not vendor_ok:
            report["ok"] = False
        report["vendors"][vendor] = {
            "source_total": round(expected_total, 2),
            "rows_total": round(rows_total, 2),
            "delta": round(delta, 2),
            "row_count": row_count,
            "line_count": len(expected_ids),
            "ok": vendor_ok,
            "unaccounted_line_ids": unaccounted,
            "unaccounted": [
                {
                    "line_id": line_id,
                    "label": index.get(line_id, {}).get("label", ""),
                    "space": index.get(line_id, {}).get("space", ""),
                    "amount": round(float(index.get(line_id, {}).get("amount") or 0)),
                }
                for line_id in unaccounted
            ],
            "unaccounted_zero_line_ids": unaccounted_zero,
            "unexpected_line_ids": unexpected,
        }
    return report


def reconciliation_message(report: dict[str, Any]) -> str:
    """One-line human summary. Empty when the gate is green."""
    if report.get("ok"):
        return ""
    bits: list[str] = []
    for vendor, entry in (report.get("vendors") or {}).items():
        if entry.get("ok"):
            continue
        who = vendor.split(" (")[0].strip() or vendor
        missing = entry.get("unaccounted") or []
        names = ", ".join(
            f"{item['label'] or item['line_id']} (Rs {item['amount']:,})"
            for item in missing[:3]
        )
        detail = f"{len(missing)} line(s) unaccounted: {names}" if missing else ""
        if not detail:
            detail = f"row total is Rs {entry.get('delta') or 0:,.0f} off the quoted lines"
        bits.append(f"{who}: {detail}")
    return "; ".join(bits)


def assert_reconciled(report: dict[str, Any]) -> None:
    """Raise when the gate is red. For CI and scripted runs."""
    if report.get("ok"):
        return
    raise ReconciliationError(
        reconciliation_message(report) or "reconciliation failed"
    )

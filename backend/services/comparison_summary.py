"""Deterministic row-wise comparison summary (S5).

Explains why one vendor's figure is higher using payload quantity, rate,
pricing method, coverage, and named finishes in description. Does not
reallocate rupees or invent area or materials.
"""

from __future__ import annotations

import re
from typing import Any

from services.work_catalog import ancillary_intents_in

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


_CIVIL_LUMP_RE = re.compile(
    r"\b(?:civil|other services|miscellaneous|misc\.?)\b", re.I
)
_INCLUDES_RE = re.compile(r"\binclud(?:e|es|ing)\b", re.I)
_FAMILY_STOP = frozenset(
    {
        "after",
        "also",
        "and",
        "area",
        "charge",
        "charges",
        "civil",
        "cost",
        "costs",
        "deep",
        "existing",
        "for",
        "from",
        "full",
        "home",
        "includes",
        "including",
        "item",
        "labour",
        "line",
        "other",
        "over",
        "room",
        "service",
        "services",
        "that",
        "the",
        "this",
        "unit",
        "units",
        "used",
        "with",
        "work",
        "works",
        "dismantle",
        "dismantling",
        "demolish",
        "demolition",
        "cleaning",
        "cleanup",
        "shifting",
        "relocate",
        "relocation",
        "removal",
        "remove",
        "moving",
    }
)


def _plain_text(value: str) -> str:
    text = re.sub(r"<[^>]+>", " ", value or "")
    return re.sub(r"\s+", " ", text).strip()


def _intent_from_work_key(work_key: str) -> str:
    key = str(work_key or "")
    if "::intent:" not in key:
        return ""
    return key.rsplit("::intent:", 1)[-1].strip()


def _family_tokens(*texts: str) -> set[str]:
    blob = _plain_text(" ".join(str(t or "") for t in texts)).casefold()
    blob = re.sub(r"[^a-z0-9]+", " ", blob)
    return {
        token
        for token in blob.split()
        if len(token) >= 4 and token not in _FAMILY_STOP
    }


def _is_cover_lump(label: str, description: str, intents: list[str]) -> bool:
    if not intents:
        return False
    if len(intents) >= 2:
        return True
    hay = f"{label} {description}"
    return bool(_CIVIL_LUMP_RE.search(hay) or _INCLUDES_RE.search(description))


def apply_description_covers(rows: list[dict[str, Any]], vendors: list[str]) -> None:
    """Link itemised ancillary gaps to another vendor's covering description.

    Mutates rows in place. Does not change amounts or coverage status.
    """
    if len(vendors) < 2 or not rows:
        return

    covers: list[dict[str, Any]] = []
    for row in rows:
        for vendor in vendors:
            try:
                amount = float(row.get(vendor) or 0)
            except (TypeError, ValueError):
                amount = 0.0
            if amount <= 0:
                continue
            measure = _measure(row, vendor)
            desc = _plain_text(str(measure.get("description") or ""))
            intents = ancillary_intents_in(desc)
            label = str(row.get("sub_service") or "")
            if not _is_cover_lump(label, desc, intents):
                continue
            covers.append(
                {
                    "vendor": vendor,
                    "label": label or "Civil services",
                    "amount": amount,
                    "space": str(row.get("space") or "").strip(),
                    "intents": intents,
                    "tokens": _family_tokens(label, desc),
                }
            )

    if not covers:
        return

    for row in rows:
        named: dict[str, dict[str, Any]] = {}
        intent = _intent_from_work_key(str(row.get("work_key") or ""))
        if not intent:
            intent = (ancillary_intents_in(str(row.get("sub_service") or "")) or [""])[0]
        if not intent:
            continue
        quoted_desc = ""
        for vendor in vendors:
            try:
                amount = float(row.get(vendor) or 0)
            except (TypeError, ValueError):
                amount = 0.0
            if amount > 0:
                quoted_desc = _plain_text(
                    str(_measure(row, vendor).get("description") or "")
                )
                break
        item_tokens = _family_tokens(str(row.get("sub_service") or ""), quoted_desc)
        for vendor in vendors:
            status = str((row.get("coverage") or {}).get(vendor) or "")
            try:
                amount = float(row.get(vendor) or 0)
            except (TypeError, ValueError):
                amount = 0.0
            if amount > 0 or status.startswith("incl_in_"):
                continue
            if status and status != "not_quoted":
                continue
            for cover in covers:
                if cover["vendor"] != vendor:
                    continue
                if intent not in cover["intents"]:
                    continue
                if item_tokens and not (item_tokens & cover["tokens"]):
                    continue
                if not item_tokens and not _CIVIL_LUMP_RE.search(cover["label"]):
                    continue
                also = [slug for slug in cover["intents"] if slug != intent]
                named[vendor] = {
                    "label": cover["label"],
                    "amount": cover["amount"],
                    "space": cover["space"],
                    "intent": intent,
                    "also_names": also,
                }
                break
        if not named:
            continue
        row["named_in"] = named
        row["summary"] = row_comparison_summary(row, vendors)


def _lineage_prefix(
    row: dict[str, Any], vendors: list[str], refs: dict[str, str]
) -> str:
    """"combines: A, B" when one display row merged several of a vendor's lines.

    A silent relabel is what let `Profile lights` + `Strip lights` render as a
    single `Lighting points` row that traced back to nothing.
    """
    combines = row.get("combines")
    if not isinstance(combines, dict) or not combines:
        return ""
    named: list[str] = []
    for vendor in vendors:
        labels = [str(v).strip() for v in (combines.get(vendor) or []) if str(v).strip()]
        if len(labels) < 2:
            continue
        who = refs.get(vendor, _who(vendor))
        joined = ", ".join(labels)
        named.append(
            f"combines: {joined}" if len(combines) == 1 else f"{who} combines: {joined}"
        )
    return " · ".join(named)


def _with_notes(row: dict[str, Any], prefix: str, body: str) -> str:
    """Assemble the cell sentence: lineage, then the reason, then the flags."""
    parts = [text for text in (prefix, body) if text]
    for key in ("space_note", "qty_scope_note"):
        note = str(row.get(key) or "").strip()
        if note and note.casefold() != "nan":
            parts.append(note)
    if row.get("match_tier") == "BUNDLE_NOT_DECOMPOSABLE":
        parts.append("bundled zone — compare at zone level only")
    return " · ".join(parts)


def apply_cross_scope_notes(
    rows: list[dict[str, Any]],
    candidates: list[dict[str, Any]],
    vendors: list[str],
) -> None:
    """Replace "did not quote this line" on a flagged possible match.

    The row is still not a merge — the rupees stay where the vendor put them —
    but the sentence must stop asserting an omission that S4b has already
    found a candidate for.
    """
    if not rows or not candidates:
        return

    refs = _vendor_refs(vendors)
    by_line: dict[str, dict[str, Any]] = {}
    for candidate in candidates:
        for line_id in candidate.get("source_line_ids") or []:
            by_line[str(line_id)] = candidate

    for row in rows:
        candidate = next(
            (
                by_line[line_id]
                for line_id in (row.get("source_line_ids") or [])
                if str(line_id) in by_line
            ),
            None,
        )
        if candidate is None:
            continue
        quoting = [v for v in vendors if float(row.get(v) or 0) > 0]
        gaps = [
            v
            for v in vendors
            if v not in quoting and (candidate.get("vendors") or {}).get(v)
        ]
        if len(quoting) != 1 or not gaps:
            continue
        row["match_tier"] = "POSSIBLE_CROSS_SCOPE_MATCH"
        other = gaps[0]
        where = str((candidate["vendors"][other] or {}).get("space") or "").strip()
        place = f"'s {where}" if where else ""
        row["cross_scope_note"] = (
            f"Possible match with {refs[other]}{place} — confirm with vendor. "
            "Not counted twice."
        )
        row["summary"] = _with_notes(
            row, _lineage_prefix(row, vendors, refs), row["cross_scope_note"]
        )


# Two different source lines must never render under an identical label in the
# same quote. `Spot lights` and a merged `Profile lights + Strip lights` row
# both resolve to the work label `Lighting points`; without a disambiguator the
# reader sees the same name twice and cannot tell which is which.
def disambiguate_display_labels(
    rows: list[dict[str, Any]], vendors: list[str]
) -> None:
    """Append a space (or description) disambiguator to colliding labels.

    Mutates rows in place. Runs after `apply_description_covers` because it
    needs `source_line_ids` to know the rows are genuinely different lines.
    """
    if not rows:
        return

    by_label: dict[str, list[dict[str, Any]]] = {}
    for row in rows:
        label = str(row.get("sub_service") or "").strip()
        if not label:
            continue
        by_label.setdefault(label.casefold(), []).append(row)

    for group in by_label.values():
        if len(group) < 2:
            continue
        # Only a collision inside one quote is confusing; the same label in two
        # quotes is exactly what the matrix is for.
        colliding: list[dict[str, Any]] = []
        for vendor in vendors:
            quoting = [
                row for row in group if (row.get("line_ids") or {}).get(vendor)
            ]
            if len(quoting) > 1:
                colliding = quoting
                break
        if not colliding:
            continue

        # `Wall decor` in the foyer and `Wall decor` in the living room is one
        # work in two rooms, and the space heading already tells them apart.
        # Two cases do mislead: the same label twice inside one space, and a
        # merged row whose new heading now clashes with an unrelated line
        # (`Profile lights` + `Strip lights` -> `Lighting points`, next to a
        # `Spot lights` row that also resolved to `Lighting points`).
        same_space = len({str(row.get("space_id") or "") for row in colliding}) < len(
            colliding
        )
        merged = any(row.get("combined_from") for row in colliding)
        if not same_space and not merged:
            continue

        # Rename only the rows of the quote that collides. The other vendor's
        # row keeps the plain label: nothing is ambiguous inside its quote.
        used: set[str] = set()
        for row in colliding:
            for candidate in _disambiguators(row):
                if candidate and candidate.casefold() not in used:
                    used.add(candidate.casefold())
                    row["sub_service"] = (
                        f"{row.get('sub_service')} ({candidate})"
                    )
                    row["item_name"] = row["sub_service"]
                    row["work_item"] = row["sub_service"]
                    break


def _disambiguators(row: dict[str, Any]) -> list[str]:
    """Candidate suffixes, most meaningful first."""
    out: list[str] = []
    space = str(row.get("space") or "").strip()
    if space and space.casefold() not in str(row.get("sub_service") or "").casefold():
        out.append(space)
    measures = row.get("measures") or {}
    if isinstance(measures, dict):
        for measure in measures.values():
            labels = (measure or {}).get("labels") or []
            for label in labels:
                text = _plain_text(str(label))[:32].strip()
                if text and text.casefold() != str(row.get("sub_service") or "").casefold():
                    out.append(text)
                    break
            if out and len(out) > 1:
                break
    ids = [str(v) for v in (row.get("source_line_ids") or []) if str(v)]
    if ids:
        out.append(ids[0].split(":")[-1])
    return out


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


def _quantity_basis(pricing_method: str) -> str:
    """Coarse physical unit of a pricing-method LABEL, not its catalog id.

    `Area – Direct Entry (sq ft)` and `Area – Length × Breadth (sq ft)` are
    different catalog ids that both mean square feet. Comparing ids would
    suppress a real area comparison; comparing units would not. `"other"` means
    we do not know — the caller then falls back to ids / labels.
    """
    pm = (pricing_method or "").casefold().strip()
    if not pm:
        return "other"
    if re.search(r"lump|fixed\s*amount|per\s*project|whole\s*project", pm):
        return "lump"
    # Cubic before plain area so "cubic feet" never collapses into sq ft.
    if re.search(r"cubic\s*(ft|feet|foot)|cu\.?\s*ft|\bcft\b", pm):
        return "cubic_ft"
    if re.search(r"sq\.?\s*m\b|sqm|square\s*me?t(?:er|re)s?", pm):
        return "area_sqm"
    if re.search(r"sq\.?\s*ft|sqft|square\s*fe?e?t", pm):
        return "area_sqft"
    if re.search(r"\brft\b|running\s*(ft|feet|foot|length)|linear\s*(ft|feet|foot)", pm):
        return "rft"
    if re.search(r"\bmt\b|metric\s*tonn|\btonne\b|\bton\b|\bweight\b", pm):
        return "weight"
    if re.search(r"per\s*unit|per\s*each|unit\s*/\s*each|/\s*each\b", pm):
        return "unit"
    return "other"


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
        return {
            "quantity": 0.0,
            "rate": 0.0,
            "pricing_method": "",
            "pricing_method_id": "",
            "description": "",
        }
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
        "pricing_method_id": str(raw.get("pricing_method_id") or ""),
        "description": str(raw.get("description") or ""),
    }


def pricing_methods_differ(ma: dict[str, Any], mb: dict[str, Any]) -> bool:
    """True when quantity language would compare unlike physical units.

    Physical basis first: Direct Entry and Length × Breadth are different
    catalog ids that both mean square feet, so they stay comparable. Unit-count
    vs area still differ. Only when a side's basis is unknown do we fall back
    to `pricing_method_id`, then the raw label — same order as before. This
    gate only decides wording; IDs-first matching elsewhere is untouched.
    """
    basis_a = _quantity_basis(str(ma.get("pricing_method") or ""))
    basis_b = _quantity_basis(str(mb.get("pricing_method") or ""))
    if basis_a != "other" and basis_b != "other":
        return basis_a != basis_b
    id_a = str(ma.get("pricing_method_id") or "").strip()
    id_b = str(mb.get("pricing_method_id") or "").strip()
    if id_a and id_b:
        return id_a != id_b
    label_a = str(ma.get("pricing_method") or "").strip().casefold()
    label_b = str(mb.get("pricing_method") or "").strip().casefold()
    if label_a and label_b:
        return label_a != label_b
    return False


def _method_name(measure: dict[str, Any]) -> str:
    return str(measure.get("pricing_method") or "").strip() or "an unstated method"


def pricing_method_clause(
    ma: dict[str, Any],
    mb: dict[str, Any],
    a: str,
    b: str,
) -> str:
    """Replacement for quantity language when the pricing methods differ.

    "1 units vs 8 units" implied one vendor quoted eight shutters when it had
    in fact priced 8 sq ft. A quantity is only comparable inside one pricing
    method, so we name the methods and compare rates only.
    """
    rate_a = float(ma.get("rate") or 0)
    rate_b = float(mb.get("rate") or 0)
    text = (
        f"{a} and {b} use different pricing methods "
        f"({_method_name(ma)} vs {_method_name(mb)}) for this item — "
        "not directly comparable by quantity"
    )
    if rate_a > 0 and rate_b > 0:
        text += f". Rate difference only: {_inr(rate_a)} vs {_inr(rate_b)}"
    return text


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

    prefix = _lineage_prefix(row, vendors, refs)
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
        return _with_notes(row, prefix, "; ".join(elsewhere))

    if len(quoted) == 1 and gaps:
        named = row.get("named_in") if isinstance(row.get("named_in"), dict) else {}
        cover = named.get(gaps[0]) if isinstance(named, dict) else None
        if isinstance(cover, dict) and cover.get("label"):
            space = str(cover.get("space") or "").strip()
            place = f", {space}" if space else ""
            intent = str(cover.get("intent") or "this work")
            also = [
                slug for slug in (cover.get("also_names") or []) if slug
            ]
            extra = (
                f" That lumpsum also names {', '.join(also)}." if also else ""
            )
            try:
                item_amt = float(amounts[quoted[0]] or 0)
            except (TypeError, ValueError):
                item_amt = 0.0
            try:
                cover_amt = float(cover.get("amount") or 0)
            except (TypeError, ValueError):
                cover_amt = 0.0
            return _with_notes(
                row,
                prefix,
                f"{refs[gaps[0]]} did not itemise this line; their "
                f"{cover['label']} ({_inr(cover_amt)}{place}) names {intent} "
                f"in the description.{extra} Not a like-for-like rate against "
                f"this {_inr(item_amt)} line.",
            )
        return _with_notes(
            row, prefix, f"{refs[gaps[0]]} did not quote this line"
        )

    if len(quoted) < 2:
        return _with_notes(row, prefix, "")

    a, b = quoted[0], quoted[1]
    amt_a, amt_b = amounts[a], amounts[b]
    ma, mb = _measure(row, a), _measure(row, b)
    qty_a, qty_b = ma["quantity"], mb["quantity"]
    rate_a, rate_b = ma["rate"], mb["rate"]
    unit = _qty_unit(ma["pricing_method"] or mb["pricing_method"])

    amount = _amount_clause(amt_a, amt_b, refs[a], refs[b])
    if pricing_methods_differ(ma, mb):
        # No quantity language at all in this branch: a sq-ft figure and a
        # per-unit figure are not two quantities of the same thing.
        reasons = [pricing_method_clause(ma, mb, refs[a], refs[b])]
    else:
        reasons = _qty_rate_parts(
            qty_a, qty_b, rate_a, rate_b, unit, refs[a], refs[b]
        )
    spec = _spec_clause(ma, mb, refs[a], refs[b])
    if spec:
        reasons.append(spec)
    if not reasons:
        return _with_notes(row, prefix, amount)
    return _with_notes(row, prefix, f"{amount} — " + " · ".join(reasons))


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

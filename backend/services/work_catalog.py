"""S2 — work identity. Decide WHAT work each line item is.

The comparison join key used to be the raw vendor string, so `Side table` and
`Side Table` landed on different matrix rows. This module produces `work_key`,
a canonical identifier that is stable across vendors.

Resolution ladder (first hit wins, recorded in `work_source`):
  1. Curated cross-vendor alias             -> alias:<slug>
  2. Exact TATVAOPS_TAXONOMY match          -> tax:<slug>
  3. Description contradicts sub_service    -> as resolved, confidence dropped
  4. Tatva ObjectId already on the row      -> tatva:<oid>
  5. Gemini pass over the leftovers         -> alias:<slug>
  6. Normalised vendor string               -> norm:<slug>

Rung 6 always succeeds, so `work_key` is never blank. Heuristic runs first and
always; the LLM only groups labels that reached rung 6, and any failure falls
back to the deterministic result.

The ObjectId sits BELOW the shared vocabulary on purpose. An ObjectId identifies
one catalog entry, and two vendors picking different catalog entries for the same
work is precisely the problem this module exists to solve — in the golden
comparison, `False Ceiling` carried an id while `False ceiling with painting` did
not, so keying on the id split a row that the alias table joins correctly. An
ObjectId is only a better key than a normalised string, not better than a
deliberate cross-vendor alias.

See backend/docs/plan/02-bind.md.
"""

from __future__ import annotations

import json
import os
import re
from typing import Any

WORK_LLM_TIMEOUT_SEC = 8

# Words that never distinguish one work item from another. Deliberately short:
# every addition risks merging two genuinely different works, which is far worse
# than failing to merge two identical ones.
_FILLER = {
    "area",
    "areas",
    "zone",
    "space",
    "unit",
    "units",
    "provision",
    "provisions",
    "required",
    "work",
    "works",
    "with",
    "type",
    "the",
    "for",
}

# Normalised vendor label -> canonical slug. Many-to-one is the point: mapping
# several vendor labels to one slug is what makes the matrix compare them.
WORK_ALIASES = {
    # False ceiling: one vendor bundles painting into the label.
    "false ceiling": "false_ceiling",
    "false ceiling painting": "false_ceiling",
    "ceiling": "false_ceiling",
    # Loft variants, including the loft-plus-door-type phrasing.
    "loft": "loft",
    "loft and door": "loft",
    "loft and door frame": "loft",
    # Crockery: one vendor quotes a single line, the other splits base and wall.
    "crockery": "crockery_units",
    "crockery base": "crockery_units",
    "crockery wall": "crockery_units",
    # Study table, including the folding variant.
    "study table": "study_table",
    "folding study table": "study_table",
    "study": "study_table",
    # Used-cloth storage. Vendor b prefixes it with the room.
    "used cloth storage": "used_cloth_storage",
    "used cloth": "used_cloth_storage",
    "mbr used cloth": "used_cloth_storage",
    # Wardrobe and its sliding mechanism are priced separately by one vendor.
    "wardrobe": "wardrobe",
    "hinged wardrobe": "wardrobe",
    # Wall treatments.
    "wall decor": "wall_decor",
    "wall decor pvc beeding": "wall_decor",
    "dining wall decor": "wall_decor",
    "wall panels": "wall_panels",
    "wall panelling": "wall_panels",
    # Kitchen carcass units. base and wall stay distinct on purpose.
    "base": "base_unit",
    "wall": "wall_unit",
    "tall": "tall_unit",
    "janitor": "janitor_unit",
    "rolling shutter": "rolling_shutter",
    "additional storage": "additional_storage",
    # Bedroom furniture.
    "king size bed": "king_size_bed",
    "side table": "side_table",
    "dressing": "dressing_unit",
    # Mirrors are quoted as a line of their own but often carry the sub_service
    # of whatever they hang above, which is why they need their own key.
    "mirror": "mirror",
    "dressing mirror": "mirror",
    "normal mirror": "mirror",
    "vanity mirror": "mirror",
    "console": "console_unit",
    "tv": "tv_units",
    "bench seating": "bench_seating",
    # A seater unit mis-filed under crockery is its own work, not bench seating
    # and not a crockery wall.
    "seater": "seating_unit",
    "seater unit": "seating_unit",
    "sofa": "sofa",
    "chimney": "chimney",
    "sink": "sink",
    "electrical": "electrical_points",
    "2d flooring": "2d_floor_planning",
    "material assistence": "material_selection_assistance",
    "material assistance": "material_selection_assistance",
    "vanity": "vanity_units",
    # Wet areas. A shower cubicle and a bathroom glass partition are the same
    # scope quoted two ways.
    "shower cubic": "shower_enclosure",
    "shower cubicle": "shower_enclosure",
    "bathroom glass partitions": "shower_enclosure",
    "glass partitions": "shower_enclosure",
    # Lighting and electrical.
    "co light": "lighting_points",
    "strip light": "lighting_points",
    "spot lights": "lighting_points",
    "decorative lights": "lighting_points",
    "profile lights": "lighting_points",
    "electrical point creations": "electrical_points",
    "electrical point": "electrical_points",
    "adaptors": "adaptors",
    # Hardware and kitchen accessories.
    "hardwares": "hardware",
    "hardware": "hardware",
    "tandem drawers": "tandem_drawers",
    "bottle pullouts": "bottle_pullouts",
    "pvc cutlery tray": "cutlery_tray",
    "cutlery tray": "cutlery_tray",
    "soft closing hinges": "soft_closing_hinges",
    "soft closing channels": "soft_closing_channels",
    "sliding mechanism": "sliding_mechanism",
    "foldable mechanism": "foldable_mechanism",
    # Misc.
    "ledges": "ledges",
    "window blinds": "window_blinds",
    "tissue paper holder": "tissue_paper_holder",
}

# Display labels for canonical slugs. Falls back to a title-cased slug.
WORK_LABELS = {
    "false_ceiling": "False ceiling",
    "loft": "Loft",
    "crockery_units": "Crockery units",
    "study_table": "Study table",
    "used_cloth_storage": "Used cloth storage",
    "wardrobe": "Wardrobe",
    "wall_decor": "Wall decor",
    "wall_panels": "Wall panels",
    "base_unit": "Base unit",
    "wall_unit": "Wall unit",
    "tall_unit": "Tall unit",
    "janitor_unit": "Janitor unit",
    "rolling_shutter": "Rolling shutter",
    "additional_storage": "Additional storage",
    "king_size_bed": "King size bed",
    "side_table": "Side table",
    "dressing_unit": "Dressing unit",
    "mirror": "Mirror",
    "console_unit": "Console unit",
    "tv_units": "TV units",
    "bench_seating": "Bench seating",
    "seating_unit": "Seater unit",
    "sofa": "Sofa",
    "chimney": "Chimney",
    "sink": "Sink",
    "2d_floor_planning": "2D floor planning",
    "material_selection_assistance": "Material selection assistance",
    "vanity_units": "Vanity units",
    "shower_enclosure": "Shower / glass partition",
    "lighting_points": "Lighting points",
    "electrical_points": "Electrical points",
    "adaptors": "Adaptors",
    "hardware": "Hardware & accessories",
    "tandem_drawers": "Tandem drawers",
    "bottle_pullouts": "Bottle pullouts",
    "cutlery_tray": "Cutlery tray",
    "soft_closing_hinges": "Soft closing hinges",
    "soft_closing_channels": "Soft closing channels",
    "sliding_mechanism": "Sliding mechanism",
    "foldable_mechanism": "Foldable mechanism",
    "ledges": "Ledges",
    "window_blinds": "Window blinds",
    "tissue_paper_holder": "Tissue paper holder",
}

# Ancillary intent changes what is being bought even when the catalog title is
# the same. Keep this deliberately conservative: a plain "Wardrobe" remains
# fabrication/installation, while an explicit "dismantle wardrobe" line gets a
# separate key and cannot inflate the wardrobe's billed area or dilute its rate.
_ANCILLARY_INTENTS: tuple[tuple[str, str, re.Pattern[str]], ...] = (
    (
        "dismantling",
        "dismantling",
        re.compile(
            r"\b(?:dismantl(?:e|ed|ing|ement)|demolish(?:ed|ing)?|demolition|"
            r"strip[\s-]?out|remov(?:e|ing)\s+(?:the\s+)?(?:existing|old)|"
            r"removal\s+(?:of\s+)?(?:the\s+)?(?:existing|old))\b",
            re.I,
        ),
    ),
    (
        "cleaning",
        "cleaning",
        re.compile(
            r"\b(?:cleaning|clean[\s-]?up|debris\s+(?:clearance|removal)|"
            r"site\s+clearance)\b",
            re.I,
        ),
    ),
    (
        "shifting",
        "shifting",
        re.compile(
            r"\b(?:shifting|relocat(?:e|ed|ing|ion)|moving)\b",
            re.I,
        ),
    ),
)


def ancillary_intents_in(*source_texts: str) -> list[str]:
    """Every explicit ancillary intent in the text, in matcher order."""
    text = " ".join(str(value or "") for value in source_texts)
    return [slug for slug, _label, pattern in _ANCILLARY_INTENTS if pattern.search(text)]


def _with_ancillary_intent(
    resolved: dict[str, Any], *source_texts: str
) -> dict[str, Any]:
    """Split explicit dismantling/cleaning/shifting from the base work row."""
    text = " ".join(str(value or "") for value in source_texts)
    for slug, label, pattern in _ANCILLARY_INTENTS:
        if not pattern.search(text):
            continue
        result = dict(resolved)
        result["work_key"] = f"{resolved['work_key']}::intent:{slug}"
        base_label = str(resolved.get("work_label") or "").strip()
        result["work_label"] = (
            base_label
            if pattern.search(base_label)
            else f"{base_label or 'Work'} — {label}"
        )
        return result
    return resolved


def _singularize(token: str) -> str:
    """Crude but safe: only strip a trailing plural s."""
    if len(token) > 3 and token.endswith("ies"):
        return token[:-3] + "y"
    if len(token) > 3 and token.endswith("ses"):
        return token[:-2]
    if len(token) > 3 and token.endswith("s") and not token.endswith("ss"):
        return token[:-1]
    return token


def normalize_work_label(raw: str) -> str:
    """Casefold, strip punctuation, singularise, drop filler words.

    This alone collapses `Side table` / `Side Table` and
    `Rolling Shutter` / `Rolling shutters` with no alias entry.
    """
    text = (raw or "").casefold()
    text = text.replace("&", " and ")
    text = re.sub(r"[^a-z0-9]+", " ", text)
    tokens = [t for t in text.split() if t]
    kept = []
    for token in tokens:
        singular = _singularize(token)
        if singular in _FILLER or token in _FILLER:
            continue
        kept.append(singular)
    if not kept:
        # The label was nothing but filler ("Units", "Provision"). Keep the
        # normalised original so it still compares against itself.
        return " ".join(_singularize(t) for t in tokens)
    return " ".join(kept)


def _slugify(text: str) -> str:
    return re.sub(r"[^a-z0-9]+", "_", (text or "").casefold()).strip("_") or "unspecified"


_TAX_INDEX: dict[str, str] | None = None


def _taxonomy_index() -> dict[str, str]:
    """Normalised taxonomy sub-service name -> slug. Built once."""
    global _TAX_INDEX
    if _TAX_INDEX is not None:
        return _TAX_INDEX
    index: dict[str, str] = {}
    try:
        from models.taxanomy import TATVAOPS_TAXONOMY
    except Exception:
        try:
            from backend.models.taxanomy import TATVAOPS_TAXONOMY  # type: ignore
        except Exception:
            _TAX_INDEX = {}
            return _TAX_INDEX
    for subs in TATVAOPS_TAXONOMY.values():
        for name in subs:
            index.setdefault(normalize_work_label(name), _slugify(name))
    _TAX_INDEX = index
    return index


def work_label_for(slug: str, sample_raw: str = "") -> str:
    if slug in WORK_LABELS:
        return WORK_LABELS[slug]
    cleaned = re.sub(r"\s+", " ", (sample_raw or "").strip())
    if cleaned:
        return cleaned
    return slug.replace("_", " ").strip().capitalize() or "Unspecified"


_ALIAS_INDEX: dict[str, str] | None = None


def _alias_index() -> dict[str, str]:
    """WORK_ALIASES with its keys pushed through the normaliser.

    Keys are written in readable form above; normalising them here means a key
    spelled `"bathroom glass partitions"` still matches after singularisation.
    """
    global _ALIAS_INDEX
    if _ALIAS_INDEX is None:
        _ALIAS_INDEX = {
            normalize_work_label(key): slug for key, slug in WORK_ALIASES.items()
        }
    return _ALIAS_INDEX


def _resolve_label(raw: str) -> tuple[str, str, float] | None:
    """Deterministic label resolution. Returns (key, source, confidence)."""
    normalized = normalize_work_label(raw)
    if not normalized:
        return None
    aliases = _alias_index()
    if normalized in aliases:
        return f"alias:{aliases[normalized]}", "alias", 0.9
    tax = _taxonomy_index().get(normalized)
    if tax:
        return f"tax:{tax}", "taxonomy", 0.85
    return None


def _is_specific(text: str) -> bool:
    """A short, concrete description we can trust over a contradicting label."""
    cleaned = re.sub(r"\s+", " ", (text or "").strip())
    if not cleaned or len(cleaned) > 60:
        return False
    # Boilerplate spec text is long and full of brand names; a real item name
    # is a couple of words.
    return 1 <= len(cleaned.split()) <= 5


def _specific_overrides(description: str, item_name: str, sub_service: str) -> list[str]:
    """Short labels that may contradict the catalog sub_service.

    Vendors often write `Seater unit - Matt / Hi Glossy Laminates ...`: the
    real item name is the prefix, and the rest is finish boilerplate that
    would fail `_is_specific` on word count.
    """
    seen: list[str] = []
    sub_fold = (sub_service or "").strip().casefold()

    def add(text: str) -> None:
        cleaned = re.sub(r"\s+", " ", (text or "").strip())
        if not cleaned or not _is_specific(cleaned):
            return
        if cleaned.casefold() == sub_fold:
            return
        if cleaned not in seen:
            seen.append(cleaned)

    add(description)
    for sep in (" - ", " – ", " — "):
        if sep in (description or ""):
            add(description.split(sep, 1)[0])
            break
    add(item_name)
    return seen


def resolve_work(row: dict[str, Any]) -> dict[str, Any]:
    """Resolve one row's work identity. Deterministic; no I/O."""
    sub_service = str(row.get("sub_service") or "").strip()
    item_name = str(row.get("item_name") or "").strip()
    description = str(row.get("description") or "").strip()

    primary = _resolve_label(sub_service) or _resolve_label(item_name)

    # Description-wins: fires only on contradiction. A vendor occasionally puts
    # the wrong sub_service on a line (a dressing mirror labelled as used-cloth
    # storage); taking the label at face value files it under the wrong work.
    for candidate in _specific_overrides(description, item_name, sub_service):
        from_desc = _resolve_label(candidate)
        if from_desc and (primary is None or from_desc[0] != primary[0]):
            key, _source, _conf = from_desc
            slug = key.split(":", 1)[1]
            return _with_ancillary_intent(
                {
                    "work_key": key,
                    "work_label": work_label_for(slug, candidate),
                    "work_confidence": 0.6,
                    "work_source": "description",
                },
                sub_service,
                item_name,
                description,
            )

    if primary:
        key, source, confidence = primary
        slug = key.split(":", 1)[1]
        return _with_ancillary_intent(
            {
                "work_key": key,
                "work_label": work_label_for(slug, sub_service or item_name),
                "work_confidence": confidence,
                "work_source": source,
            },
            sub_service,
            item_name,
            description,
        )

    label = sub_service or item_name or "Unspecified"

    # No shared vocabulary matched. A catalog ObjectId is still a better key than
    # a raw string, because two vendors picking the same catalog entry do mean
    # the same work.
    oid = str(row.get("sub_service_id") or "").strip()
    if oid:
        return _with_ancillary_intent(
            {
                "work_key": f"tatva:{oid}",
                "work_label": work_label_for("", label),
                "work_confidence": 0.8,
                "work_source": "tatva",
            },
            sub_service,
            item_name,
            description,
        )

    normalized = normalize_work_label(label)
    return _with_ancillary_intent(
        {
            "work_key": f"norm:{_slugify(normalized or label)}",
            "work_label": work_label_for("", label),
            "work_confidence": 0.3,
            "work_source": "normalized",
        },
        sub_service,
        item_name,
        description,
    )


def _llm_enabled() -> bool:
    flag = (os.getenv("GEMINI_WORK_LLM") or "1").strip().lower()
    if flag in ("0", "false", "no", "off"):
        return False
    api_key = (os.getenv("GEMINI_API_KEY") or "").strip()
    return bool(api_key) and not api_key.lower().startswith("your_")


def _try_gemini_merge(
    leftovers: dict[str, list[str]]
) -> dict[str, str]:
    """Group unresolved labels into equivalence classes.

    `leftovers` maps a vendor label to sample descriptions. Returns a mapping of
    label -> shared slug for labels the model considers the same work. Any
    failure returns {} so the deterministic result stands.
    """
    if len(leftovers) < 2 or not _llm_enabled():
        return {}

    try:
        from google.genai import types
        from services.env_config import (
            gemini_generate_config,
            gemini_work_model,
            get_gemini_client,
        )
    except Exception:
        return {}

    model = gemini_work_model()
    payload = [
        {"label": label, "context": ctx[:3]} for label, ctx in leftovers.items()
    ]
    prompt = (
        "You group construction/interior quote line-item labels that describe the "
        "SAME work quoted by different vendors.\n"
        "DEFAULT: each label is its own group. Only group labels when they are the "
        "same work with different wording.\n"
        "Read each label's context descriptions carefully. Verbs and scope in the "
        "description decide the work: dismantling/demolition, cleaning, shifting, "
        "and new installation are different purchases even when the catalog title "
        "is the same (Wardrobe vs Wardrobe dismantle).\n"
        "NEVER group a Civil / Other-services lumpsum with a named install or "
        "ancillary line. A description that lists several jobs (tiling dismantle, "
        "cleaning, bench seating) is a cover note, not a synonym for any one of "
        "those jobs.\n"
        "NEVER group a base unit with a wall unit, or a wardrobe with a bed. "
        "Different materials or different furniture are different work.\n"
        "Grouping a lighting item with a hardware item is always wrong.\n"
        "Only return groups with two or more members; skip singletons.\n\n"
        f"Labels:\n{json.dumps(payload, ensure_ascii=False)}\n\n"
        'Return JSON: {"groups": [{"canonical": "short name", "members": ["...", "..."]}]}'
    )

    try:
        import concurrent.futures

        client = get_gemini_client()
        config = gemini_generate_config(
            types,
            model=model,
            temperature=0.0,
            response_mime_type="application/json",
        )
        ex = concurrent.futures.ThreadPoolExecutor(max_workers=1)
        try:
            future = ex.submit(
                lambda: client.models.generate_content(
                    model=model, contents=prompt, config=config
                )
            )
            response = future.result(timeout=WORK_LLM_TIMEOUT_SEC)
        finally:
            ex.shutdown(wait=False)

        data = json.loads(response.text or "{}")
        groups = data.get("groups") if isinstance(data, dict) else None
        if not isinstance(groups, list):
            return {}

        merged: dict[str, str] = {}
        for group in groups:
            if not isinstance(group, dict):
                continue
            members = [
                str(m).strip() for m in (group.get("members") or []) if str(m).strip()
            ]
            # A single-member group cannot merge anything; ignore it rather than
            # letting the model relabel a lone item.
            if len(members) < 2:
                continue
            canonical = str(group.get("canonical") or members[0]).strip()
            slug = _slugify(normalize_work_label(canonical) or canonical)
            for member in members:
                if member in leftovers:
                    merged[member] = slug
        return merged
    except Exception as exc:
        print(f"ℹ️ Work catalog LLM skipped ({exc}) — using deterministic keys.")
        return {}


def apply_work_catalog(df):
    """Add work_key / work_label / work_confidence / work_source columns."""
    if df is None or len(df) == 0:
        return df

    resolved = [resolve_work(row) for _, row in df.iterrows()]
    df["work_key"] = [r["work_key"] for r in resolved]
    df["work_label"] = [r["work_label"] for r in resolved]
    df["work_confidence"] = [r["work_confidence"] for r in resolved]
    df["work_source"] = [r["work_source"] for r in resolved]

    # Rung 5: hand only the unresolved labels to the LLM, and only when more than
    # one vendor is involved — there is nothing to reconcile in a single quote.
    vendor_count = df["vendor_name"].nunique() if "vendor_name" in df.columns else 1
    if vendor_count < 2:
        return df

    unresolved = df[
        (df["work_source"] == "normalized")
        & ~df["work_key"].astype(str).str.contains("::intent:", regex=False)
    ]
    if len(unresolved) < 2:
        return df

    leftovers: dict[str, list[str]] = {}
    for _, row in unresolved.iterrows():
        label = str(row.get("sub_service") or row.get("item_name") or "").strip()
        if not label:
            continue
        leftovers.setdefault(label, [])
        desc = str(row.get("description") or "").strip()
        if desc and len(leftovers[label]) < 3:
            leftovers[label].append(desc[:120])

    merged = _try_gemini_merge(leftovers)
    if not merged:
        return df

    def _remap(row):
        if row["work_source"] != "normalized":
            return row["work_key"], row["work_label"], row["work_confidence"], row["work_source"]
        label = str(row.get("sub_service") or row.get("item_name") or "").strip()
        slug = merged.get(label)
        if not slug:
            return row["work_key"], row["work_label"], row["work_confidence"], row["work_source"]
        return f"alias:{slug}", work_label_for(slug, label), 0.5, "llm"

    remapped = [_remap(row) for _, row in df.iterrows()]
    df["work_key"] = [r[0] for r in remapped]
    df["work_label"] = [r[1] for r in remapped]
    df["work_confidence"] = [r[2] for r in remapped]
    df["work_source"] = [r[3] for r in remapped]
    return df


def is_known_work_label(raw: str) -> bool:
    """True when a string names a work item rather than a room.

    S3 uses this so that an item name in the Space/Zone column does not become a
    fake room. Because it defers to the alias table and the taxonomy, adding a
    sub-service automatically stops it becoming a phantom space.
    """
    return _resolve_label(raw) is not None


def work_slug_for(raw: str) -> str | None:
    """Canonical slug for a work-item phrase, or None when the catalog misses.

    S4 uses this so a lumpsum description is enumerated against the same
    vocabulary as S2: adding a sub-service to the taxonomy teaches the bundle
    detector the new word automatically, instead of extending a second token
    list.
    """
    hit = _resolve_label(raw)
    if hit is None:
        return None
    return hit[0].split(":", 1)[1]

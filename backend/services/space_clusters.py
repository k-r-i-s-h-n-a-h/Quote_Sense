"""Constrained space clustering for compare — same physical room only.

Default: one unique Space/Zone string = one cluster.
Merge only high-confidence same-floor + same-room aliases (Bedroom 1 ≈ GF Bedroom 1).
Item-as-space labels (Spot lights, Adaptors) map to Project-level, not a fake room.

Heuristic always runs (no network). Optional Gemini overlay can refine leftovers
when GEMINI_API_KEY is set; failures fall back to heuristic.
"""

from __future__ import annotations

import json
import os
import re
from typing import Any, Literal

Kind = Literal["space", "not_a_space", "project_level"]

_NOT_A_SPACE = {
    "spot lights",
    "spot lights for false ceiling",
    "adaptors",
    "profile lights",
    "strip lights",
    "transportation",
    "debris disposal",
    "deep cleaning",
    "loading",
    "loading & unloading",
    "loading and unloading",
    "soft closing",
    "soft closing hinges",
    "hardwares",
    "hardware",
    "electrical",
    "electrical works",
    "electrical works shifting points",
    "electrical work required",
    "electrical work required areas",
    "adaptors required",
    "adaptors required areas",
    "profile lights required",
    "profile lights required areas",
    "window blinds",
    "tissue paper holder",
    "plumbing",
    "cleaning",
    "complete home painting",
    "asian full home painting",
    "ss",
    "quartz",
}

_CLUSTER_LABELS = {
    "kitchen": "Kitchen",
    "living": "Living",
    "dining": "Dining",
    "foyer": "Foyer",
    "utility": "Utility",
    "pooja": "Pooja",
    "common_washroom": "Common-Washroom",
    "kids_bedroom": "Kids-Bedroom",
    "gf_bedroom1": "GF-Bedroom1",
    "gf_bedroom2": "GF-Bedroom2",
    "1f_walkin": "1F-Walk-in",
    "mbr": "Master-Bedroom",
    "1f_bathroom": "1F-Bathroom",
    "gf_bathroom": "GF-Bathroom",
    "project_level": "Project-level",
}


def _norm(raw: str) -> str:
    text = (raw or "").casefold()
    text = text.replace("&", " and ")
    text = re.sub(r"^:+", " ", text)
    text = re.sub(r"[^a-z0-9]+", " ", text)
    return re.sub(r"\s+", " ", text).strip()


def _core(raw: str) -> str:
    """Drop vendor fluff (area / zone / space) so Dining ≈ Dining area."""
    n = _norm(raw)
    n = re.sub(r"\b(area|zone|space)\b", " ", n)
    return re.sub(r"\s+", " ", n).strip()


def _fingerprint(raw: str) -> str:
    n = _core(raw)
    if not n or n in _NOT_A_SPACE or _norm(raw) in _NOT_A_SPACE:
        return "project_level"

    if "kitchen" in n:
        return "kitchen"
    if "dining" in n:
        return "dining"
    if "foyer" in n or n in ("entrance", "entry"):
        return "foyer"
    if "living" in n:
        return "living"
    if "utility" in n or "janitor" in n:
        return "utility"
    if "pooja" in n:
        return "pooja"

    if "walkin" in n or "walk in" in n:
        return "1f_walkin"
    if re.search(r"\bmbr\b", n) or "master" in n:
        return "mbr"
    if "kid" in n or "children" in n:
        return "kids_bedroom"

    if "washroom" in n or "bathroom" in n or "wash room" in n or (
        "vanity" in n and "common" in n
    ):
        if "common" in n or "vanity" in n:
            return "common_washroom"
        if "first" in n or "1st" in n or re.search(r"\b1f\b", n):
            return "1f_bathroom"
        if "ground" in n or re.search(r"\bgf\b", n):
            return "gf_bathroom"
        return "common_washroom"

    bedroom = "bedroom" in n or re.search(r"\bbr\b", n)
    if bedroom:
        num = "2" if re.search(r"\b(2|two)\b", n) else "1"
        floor = "gf"
        if "first" in n or "1st" in n or re.search(r"\b1f\b", n):
            floor = "1f"
        if num == "2":
            return "gf_bedroom2" if floor == "gf" else f"{floor}_bedroom2"
        return "gf_bedroom1" if floor == "gf" else f"{floor}_bedroom1"

    return f"unique:{n}"


def _canonical(fp: str, sample_raw: str) -> str:
    if fp in _CLUSTER_LABELS:
        return _CLUSTER_LABELS[fp]
    if fp.startswith("unique:"):
        return _title_space(sample_raw)
    return _title_space(sample_raw)


def _title_space(raw: str) -> str:
    text = re.sub(r"\s+", " ", (raw or "").strip())
    return text or "Project-level"


def cluster_spaces_heuristic(space_raws: list[str]) -> dict[str, dict[str, Any]]:
    """Map each raw space string → cluster dict. Deterministic, no I/O."""
    mapping: dict[str, dict[str, Any]] = {}
    buckets: dict[str, list[str]] = {}
    for raw in space_raws:
        key = (raw or "").strip()
        if not key:
            key = "Project-level"
        fp = _fingerprint(key)
        buckets.setdefault(fp, []).append(key)

    for fp, members in buckets.items():
        unique_members = list(dict.fromkeys(members))
        kind: Kind = "project_level" if fp == "project_level" else "space"
        if fp == "project_level":
            kind = "not_a_space"
        canonical = _canonical(fp, unique_members[0])
        cluster = {
            "cluster_id": fp,
            "canonical": canonical,
            "aliases": unique_members,
            "members": unique_members,
            "kind": kind,
        }
        for member in unique_members:
            mapping[member] = cluster
    return mapping


SPACE_CLUSTER_TIMEOUT_SEC = 8


def _try_gemini_overlay(space_raws: list[str], heuristic: dict[str, dict[str, Any]]) -> dict[str, dict[str, Any]]:
    unique = list(dict.fromkeys((s or "").strip() or "Project-level" for s in space_raws))
    if len(unique) < 2:
        return heuristic
    api_key = (os.getenv("GEMINI_API_KEY") or "").strip()
    if not api_key or api_key.lower().startswith("your_"):
        return heuristic
    flag = (os.getenv("GEMINI_SPACE_LLM") or "1").strip().lower()
    if flag in ("0", "false", "no", "off"):
        return heuristic

    try:
        from google.genai import types
        from services.env_config import get_gemini_client
    except Exception:
        return heuristic

    model = os.getenv("GEMINI_EXTRACT_MODEL") or os.getenv("GEMINI_SPACE_MODEL") or "gemini-2.5-flash"
    prompt = (
        "You cluster vendor Space/Zone labels from ONE quote comparison.\n"
        "DEFAULT: each string is its own cluster. Merge ONLY when two labels are the "
        "same physical room with different wording (Ground Floor Bedroom 1 = Bedroom 1).\n"
        "NEVER merge Kitchen with Bedroom, or Common Washroom with Walk-in closet.\n"
        "If a label is an item not a room (Spot lights, Adaptors, Transportation, Electrical), "
        "kind=not_a_space and canonical=Project-level.\n"
        "Uncertain MBR vs walk-in closet: keep TWO clusters.\n"
        "Canonical labels like GF-Bedroom1, Kitchen, Common-Washroom, 1F-Walk-in.\n\n"
        f"Labels:\n{json.dumps(unique)}\n\n"
        "Return JSON: {\"clusters\": [{\"canonical\": \"GF-Bedroom1\", \"members\": [\"...\"], "
        "\"kind\": \"space\"}]}"
    )

    try:
        import concurrent.futures

        client = get_gemini_client()
        config = types.GenerateContentConfig(
            response_mime_type="application/json",
            temperature=0.0,
        )
        ex = concurrent.futures.ThreadPoolExecutor(max_workers=1)
        try:
            future = ex.submit(
                lambda: client.models.generate_content(
                    model=model,
                    contents=prompt,
                    config=config,
                )
            )
            response = future.result(timeout=SPACE_CLUSTER_TIMEOUT_SEC)
        finally:
            ex.shutdown(wait=False)
        payload = json.loads(response.text or "{}")
        clusters = payload.get("clusters") if isinstance(payload, dict) else None
        if not isinstance(clusters, list) or not clusters:
            return heuristic

        overlay: dict[str, dict[str, Any]] = {}
        for i, cluster in enumerate(clusters):
            if not isinstance(cluster, dict):
                continue
            members = [str(m).strip() for m in (cluster.get("members") or []) if str(m).strip()]
            if not members:
                continue
            kind = cluster.get("kind") or "space"
            if kind not in ("space", "not_a_space", "project_level"):
                kind = "space"
            canonical = str(cluster.get("canonical") or members[0]).strip()
            if kind in ("not_a_space", "project_level"):
                canonical = "Project-level"
                kind = "not_a_space"
            info = {
                "cluster_id": f"llm_{i}",
                "canonical": canonical,
                "aliases": members,
                "members": members,
                "kind": kind,
            }
            for member in members:
                overlay[member] = info
        for raw in unique:
            if raw not in overlay:
                overlay[raw] = heuristic.get(raw) or {
                    "cluster_id": f"unique:{_norm(raw)}",
                    "canonical": _title_space(raw),
                    "aliases": [raw],
                    "members": [raw],
                    "kind": "space",
                }
        return overlay
    except Exception as exc:
        print(f"ℹ️ Space cluster LLM skipped ({exc}) — using heuristic.")
        return heuristic


def cluster_spaces(space_raws: list[str]) -> dict[str, dict[str, Any]]:
    heuristic = cluster_spaces_heuristic(space_raws)
    return _try_gemini_overlay(space_raws, heuristic)


def apply_space_clusters(df, *, raw_col: str = "space_raw", out_col: str = "space"):
    """Add canonical `space` column from Space/Zone strings."""
    raws = []
    if raw_col in df.columns:
        raws = [str(v).strip() for v in df[raw_col].fillna("").tolist()]
    mapping = cluster_spaces(raws)

    def _lookup(raw: str) -> str:
        key = (raw or "").strip() or "Project-level"
        info = mapping.get(key) or mapping.get(raw) or {}
        canonical = info.get("canonical") or key or "Project-level"
        kind = info.get("kind")
        if kind in ("not_a_space", "project_level"):
            return "Project-level"
        return canonical

    df[out_col] = df[raw_col].fillna("").astype(str).map(_lookup) if raw_col in df.columns else "Project-level"
    return df

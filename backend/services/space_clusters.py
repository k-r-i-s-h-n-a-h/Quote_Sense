"""S3 — room identity. Decide WHICH ROOM each line item belongs to.

Two failures this replaces:

1. `_NOT_A_SPACE` was a hardcoded set of literal strings, so a label only
   avoided becoming a fake room if it was already listed or if a room name
   happened to be a substring. `MBR Dressing unit` folded correctly by luck of
   the prefix; `Used cloth unit` did not, and became its own phantom space.

2. Only `space_raw` was ever inspected. The room is frequently stated in the
   line's own description — `Used cloth unit` has the description
   "MBR Used cloth storages" — so reading the whole row fixes the phantom
   without needing a new literal.

Resolution ladder (first hit wins, recorded in `space_source`):
  1. room name in space_raw        -> 0.95
  2. space_raw is an item, room in description -> 0.70
  3. space_raw is an item, room in item_name  -> 0.60
  4. Gemini overlay grouped it     -> 0.50
  5. no room anywhere              -> Project-level, 0.40

Default merge policy stays conservative: one raw string is one cluster unless two
labels are clearly the same physical room. A wrong merge silently sums two rooms'
costs and is far harder to spot than a missing merge.

See backend/docs/plan/03-spaces.md.
"""

from __future__ import annotations

import json
import os
import re
from typing import Any, Literal

Kind = Literal["space", "not_a_space", "project_level"]

PROJECT_LEVEL_ID = "project_level"
PROJECT_LEVEL_LABEL = "Project-level"

# Labels that are project-wide services rather than rooms. Kept small: the
# is-this-a-room predicate below generalises, so this only holds things that are
# neither a room nor a catalogued work item.
_PROJECT_WIDE = {
    "transportation",
    "debris disposal",
    "deep cleaning",
    "loading",
    "loading and unloading",
    "cleaning",
    "plumbing",
    "complete home painting",
    "asian full home painting",
    "ss",
    "quartz",
}

# Phrases that mark a label as describing an item or a scope, not a room.
_ITEMISH_RE = re.compile(
    r"\b(required|provision|accessor|mechanism|holder|partition|pullout|"
    r"shutter|hinge|channel|tray|blind|adaptor|adapter|light|electrical)\b",
    re.I,
)

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
    "1f_bedroom1": "1F-Bedroom1",
    "1f_bedroom2": "1F-Bedroom2",
    "1f_walkin": "1F-Walk-in",
    "mbr": "Master-Bedroom",
    "1f_bathroom": "1F-Bathroom",
    "gf_bathroom": "GF-Bathroom",
    PROJECT_LEVEL_ID: PROJECT_LEVEL_LABEL,
}


def _norm(raw: str) -> str:
    text = (raw or "").casefold()
    text = text.replace("&", " and ")
    text = re.sub(r"^:+", " ", text)
    text = re.sub(r"[^a-z0-9]+", " ", text)
    return re.sub(r"\s+", " ", text).strip()


def _core(raw: str) -> str:
    """Drop vendor fluff (area / zone / space) so Dining is Dining area."""
    n = _norm(raw)
    n = re.sub(r"\b(area|zone|space)\b", " ", n)
    return re.sub(r"\s+", " ", n).strip()


def _room_token(text: str) -> str | None:
    """Find a room in free text. Returns a cluster id, or None."""
    n = _core(text)
    if not n:
        return None

    if "kitchen" in n:
        return "kitchen"
    if "dining" in n:
        return "dining"
    if "foyer" in n or n in ("entrance", "entry") or "entrance" in n:
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

    if "bedroom" in n or re.search(r"\bbr\b", n):
        num = "2" if re.search(r"\b(2|two|second)\b", n) else "1"
        floor = "gf"
        if "first" in n or "1st" in n or re.search(r"\b1f\b", n):
            floor = "1f"
        return f"{floor}_bedroom{num}"

    return None


def is_room_label(space_raw: str, item_name: str = "") -> bool:
    """True when a Space/Zone string really names a room.

    Replaces the old literal blocklist. A label is NOT a room when it names a
    catalogued work item, repeats the line's own item name, or reads like an
    item/scope phrase. Because the first check defers to S2, adding a
    sub-service to the taxonomy automatically stops it becoming a phantom room.
    """
    raw = (space_raw or "").strip()
    if not raw:
        return False

    normalized = _norm(raw)
    if not normalized or normalized in _PROJECT_WIDE or _core(raw) in _PROJECT_WIDE:
        return False

    # An explicit room word wins outright: a label like "Kitchen Accessories"
    # still tells us the room, even though it also names items.
    if _room_token(raw) is not None:
        return True

    if item_name and _norm(item_name) == normalized:
        return False

    try:
        from services.work_catalog import is_known_work_label

        if is_known_work_label(raw):
            return False
    except Exception:
        pass

    if _ITEMISH_RE.search(raw):
        return False

    return True


def _title_space(raw: str) -> str:
    text = re.sub(r"\s+", " ", (raw or "").strip())
    return text or PROJECT_LEVEL_LABEL


def resolve_space(row: dict[str, Any]) -> dict[str, Any]:
    """Resolve one row's room. Deterministic; no I/O."""
    space_raw = str(row.get("space_raw") or row.get("work_title") or "").strip()
    item_name = str(row.get("item_name") or "").strip()
    description = str(row.get("description") or "").strip()

    if is_room_label(space_raw, item_name):
        token = _room_token(space_raw)
        if token:
            return {
                "space_id": token,
                "space": _CLUSTER_LABELS.get(token, _title_space(space_raw)),
                "space_confidence": 0.95,
                "space_source": "space_raw",
            }
        # A room we do not have a token for (a study, a balcony). Keep it as its
        # own cluster keyed on the normalised string rather than guessing.
        return {
            "space_id": f"unique:{_core(space_raw)}",
            "space": _title_space(space_raw),
            "space_confidence": 0.8,
            "space_source": "space_raw",
        }

    # space_raw is an item name or a scope phrase. The room is often in the
    # description of the same line.
    for source, text, confidence in (
        ("description", description, 0.7),
        ("item_name", item_name, 0.6),
    ):
        token = _room_token(text)
        if token:
            return {
                "space_id": token,
                "space": _CLUSTER_LABELS.get(token, PROJECT_LEVEL_LABEL),
                "space_confidence": confidence,
                "space_source": source,
            }

    return {
        "space_id": PROJECT_LEVEL_ID,
        "space": PROJECT_LEVEL_LABEL,
        "space_confidence": 0.4,
        "space_source": PROJECT_LEVEL_ID,
    }


def cluster_spaces_heuristic(space_raws: list[str]) -> dict[str, dict[str, Any]]:
    """Map each raw space string to a cluster dict. Deterministic, no I/O.

    Label-only entry point, kept for callers that have no row context. Prefer
    `resolve_space` when a full row is available, since the description is what
    rescues item-as-space labels.
    """
    mapping: dict[str, dict[str, Any]] = {}
    buckets: dict[str, list[str]] = {}
    for raw in space_raws:
        key = (raw or "").strip() or PROJECT_LEVEL_LABEL
        info = resolve_space({"space_raw": key})
        buckets.setdefault(info["space_id"], []).append(key)

    for cluster_id, members in buckets.items():
        unique_members = list(dict.fromkeys(members))
        kind: Kind = "not_a_space" if cluster_id == PROJECT_LEVEL_ID else "space"
        canonical = _CLUSTER_LABELS.get(cluster_id) or _title_space(unique_members[0])
        cluster = {
            "cluster_id": cluster_id,
            "canonical": canonical,
            "aliases": unique_members,
            "members": unique_members,
            "kind": kind,
        }
        for member in unique_members:
            mapping[member] = cluster
    return mapping


SPACE_CLUSTER_TIMEOUT_SEC = 8


def _llm_enabled() -> bool:
    api_key = (os.getenv("GEMINI_API_KEY") or "").strip()
    if not api_key or api_key.lower().startswith("your_"):
        return False
    flag = (os.getenv("GEMINI_SPACE_LLM") or "1").strip().lower()
    return flag not in ("0", "false", "no", "off")


def _try_gemini_overlay(
    contexts: dict[str, dict[str, Any]],
    heuristic: dict[str, dict[str, Any]],
) -> dict[str, dict[str, Any]]:
    """Refine leftover clusters using row context.

    `contexts` maps a raw label to sample item names and descriptions. Passing
    that context (rather than bare labels, as before) is what lets the model see
    that `Used cloth unit` is a master-bedroom item.
    """
    unique = list(contexts.keys())
    if len(unique) < 2 or not _llm_enabled():
        return heuristic

    try:
        from google.genai import types
        from services.env_config import get_gemini_client
    except Exception:
        return heuristic

    model = (
        os.getenv("GEMINI_SPACE_MODEL")
        or os.getenv("GEMINI_EXTRACT_MODEL")
        or "gemini-2.5-flash"
    )
    payload = [
        {
            "label": label,
            "items": ctx.get("items", [])[:3],
            "notes": ctx.get("notes", [])[:2],
        }
        for label, ctx in contexts.items()
    ]
    prompt = (
        "You cluster vendor Space/Zone labels from ONE quote comparison.\n"
        "DEFAULT: each label is its own cluster. Merge ONLY when two labels are the "
        "same physical room with different wording (Ground Floor Bedroom 1 = Bedroom 1).\n"
        "NEVER merge Kitchen with Bedroom, or Common Washroom with Walk-in closet.\n"
        "Use the item names and notes to place a label that is an ITEM rather than a "
        "room: a label whose notes mention MBR belongs to the master bedroom.\n"
        "If a label is an item with no room anywhere in its context (Transportation, "
        "Window blinds), set kind=not_a_space and canonical=Project-level.\n"
        "Uncertain MBR vs walk-in closet: keep TWO clusters.\n"
        "Canonical labels like GF-Bedroom1, Kitchen, Common-Washroom, Master-Bedroom.\n\n"
        f"Labels:\n{json.dumps(payload, ensure_ascii=False)}\n\n"
        'Return JSON: {"clusters": [{"canonical": "GF-Bedroom1", "members": ["..."], '
        '"kind": "space"}]}'
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
                    model=model, contents=prompt, config=config
                )
            )
            response = future.result(timeout=SPACE_CLUSTER_TIMEOUT_SEC)
        finally:
            ex.shutdown(wait=False)

        payload_out = json.loads(response.text or "{}")
        clusters = payload_out.get("clusters") if isinstance(payload_out, dict) else None
        if not isinstance(clusters, list) or not clusters:
            return heuristic

        overlay: dict[str, dict[str, Any]] = {}
        for i, cluster in enumerate(clusters):
            if not isinstance(cluster, dict):
                continue
            members = [
                str(m).strip() for m in (cluster.get("members") or []) if str(m).strip()
            ]
            if not members:
                continue
            kind = cluster.get("kind") or "space"
            if kind not in ("space", "not_a_space", "project_level"):
                kind = "space"
            canonical = str(cluster.get("canonical") or members[0]).strip()
            cluster_id = f"llm_{i}"
            if kind in ("not_a_space", "project_level"):
                canonical = PROJECT_LEVEL_LABEL
                kind = "not_a_space"
                cluster_id = PROJECT_LEVEL_ID
            info = {
                "cluster_id": cluster_id,
                "canonical": canonical,
                "aliases": members,
                "members": members,
                "kind": kind,
                "source": "llm",
            }
            for member in members:
                overlay[member] = info

        for raw in unique:
            if raw not in overlay:
                overlay[raw] = heuristic.get(raw) or {
                    "cluster_id": f"unique:{_core(raw)}",
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
    contexts = {
        (raw or "").strip() or PROJECT_LEVEL_LABEL: {"items": [], "notes": []}
        for raw in space_raws
    }
    return _try_gemini_overlay(contexts, heuristic)


def apply_space_clusters(df, *, raw_col: str = "space_raw", out_col: str = "space"):
    """Add space_id / space / space_confidence / space_source columns."""
    if df is None or len(df) == 0:
        return df

    if raw_col not in df.columns:
        df[out_col] = PROJECT_LEVEL_LABEL
        df["space_id"] = PROJECT_LEVEL_ID
        df["space_confidence"] = 0.4
        df["space_source"] = PROJECT_LEVEL_ID
        return df

    resolved = [resolve_space(row) for _, row in df.iterrows()]
    df["space_id"] = [r["space_id"] for r in resolved]
    df[out_col] = [r["space"] for r in resolved]
    df["space_confidence"] = [r["space_confidence"] for r in resolved]
    df["space_source"] = [r["space_source"] for r in resolved]

    # The overlay only sees labels the heuristic could not place in a room, and
    # it receives their row context so it can do better than the label alone.
    if not _llm_enabled():
        return df

    unresolved = df[df["space_source"] == PROJECT_LEVEL_ID]
    labels = [
        str(v).strip()
        for v in unresolved[raw_col].fillna("").tolist()
        if str(v).strip()
    ]
    if len(set(labels)) < 2:
        return df

    contexts: dict[str, dict[str, Any]] = {}
    for _, row in unresolved.iterrows():
        label = str(row.get(raw_col) or "").strip()
        if not label:
            continue
        ctx = contexts.setdefault(label, {"items": [], "notes": []})
        item = str(row.get("item_name") or "").strip()
        note = str(row.get("description") or "").strip()
        if item and item not in ctx["items"]:
            ctx["items"].append(item)
        if note and len(ctx["notes"]) < 2:
            ctx["notes"].append(note[:160])

    heuristic = {
        label: {
            "cluster_id": PROJECT_LEVEL_ID,
            "canonical": PROJECT_LEVEL_LABEL,
            "aliases": [label],
            "members": [label],
            "kind": "not_a_space",
        }
        for label in contexts
    }
    overlay = _try_gemini_overlay(contexts, heuristic)

    def _apply(row):
        if row["space_source"] != PROJECT_LEVEL_ID:
            return row["space_id"], row[out_col], row["space_confidence"], row["space_source"]
        label = str(row.get(raw_col) or "").strip()
        info = overlay.get(label)
        if not info or info.get("source") != "llm":
            return row["space_id"], row[out_col], row["space_confidence"], row["space_source"]
        if info.get("kind") != "space":
            return PROJECT_LEVEL_ID, PROJECT_LEVEL_LABEL, 0.4, PROJECT_LEVEL_ID
        return info["cluster_id"], info["canonical"], 0.5, "llm"

    applied = [_apply(row) for _, row in df.iterrows()]
    df["space_id"] = [a[0] for a in applied]
    df[out_col] = [a[1] for a in applied]
    df["space_confidence"] = [a[2] for a in applied]
    df["space_source"] = [a[3] for a in applied]
    return df

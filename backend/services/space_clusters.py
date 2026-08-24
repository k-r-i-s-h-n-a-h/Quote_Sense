"""S3 — room identity. Decide WHICH ROOM each line item belongs to.

Grouping and naming are two separate decisions here, and conflating them was a
bug of its own. `space_id` is the grouping key and may carry a floor qualifier;
`space` is only the heading, and it is chosen from the vendors' own wording for
the cluster by `choose_space_label`. That is why the matrix no longer heads a row
`GF-Bedroom1` for two quotes that never mention a floor: a floor the vendors did
not state cannot reach the heading, and the LLM overlay no longer names anything.

Failures this replaces:

1. `_NOT_A_SPACE` was a hardcoded set of literal strings, so a label only
   avoided becoming a fake room if it was already listed or if a room name
   happened to be a substring. `MBR Dressing unit` folded correctly by luck of
   the prefix; `Used cloth unit` did not, and became its own phantom space.

2. Only `space_raw` was ever inspected. The room is frequently stated in the
   line's own description — `Used cloth unit` has the description
   "MBR Used cloth storages" — so reading the whole row fixes the phantom
   without needing a new literal.

3. Vendor abbreviations (`L R`, `LVR`, `LIV`) matched no room token, so each
   spelling became its own `unique:` cluster and one living room was listed once
   per vendor. The overlay could not rescue them either, because it was only
   shown `project_level` rows — never the `unique:` ones.

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

# Fallback display names, used ONLY when a cluster has no vendor-supplied room
# string to borrow (every member is an item name). Never a first choice: the
# display label normally comes from the vendors' own wording via
# `choose_space_label`, so the matrix cannot show a floor or a room name that
# nobody actually quoted.
_CLUSTER_LABELS = {
    "kitchen": "Kitchen",
    "living": "Living",
    "dining": "Dining",
    "foyer": "Foyer",
    "utility": "Utility",
    "pooja": "Pooja",
    "common_washroom": "Common Washroom",
    "kids_bedroom": "Kids Bedroom",
    "bedroom1": "Bedroom 1",
    "bedroom2": "Bedroom 2",
    "gf_bedroom1": "GF Bedroom 1",
    "gf_bedroom2": "GF Bedroom 2",
    "1f_bedroom1": "1F Bedroom 1",
    "1f_bedroom2": "1F Bedroom 2",
    "1f_walkin": "Walk-in Closet",
    "mbr": "Master Bedroom",
    "1f_bathroom": "1F Bathroom",
    "gf_bathroom": "GF Bathroom",
    PROJECT_LEVEL_ID: PROJECT_LEVEL_LABEL,
}

# Room words, used to score which vendor label reads most like a room name.
# Spelled-out words beat abbreviations, so "Living Room" wins over "L R".
_ROOM_WORDS = {
    "living", "hall", "lounge", "drawing", "room", "dining", "kitchen",
    "modular", "bedroom", "master", "kids", "children", "guest", "foyer",
    "entrance", "lobby", "passage", "utility", "janitor", "pooja", "puja",
    "washroom", "bathroom", "toilet", "powder", "vanity", "common", "walk",
    "walkin", "closet", "balcony", "study", "office", "terrace",
    "garden", "laundry", "staircase", "ground", "first", "floor", "second",
}

# Nouns that give a label away as furniture or a scope. A label can name a room
# and an item at once ("MBR Study unit", "Kitchen Accessories"): good enough to
# place the row, too specific to head the column.
_ITEM_NOUN_RE = re.compile(
    r"\b(unit|units|table|desk|storage|storages|mirror|accessor\w*|panel\w*|"
    r"shutter\w*|loft|counter|cabinet\w*|drawer\w*|blind\w*|ceiling|light\w*|"
    r"work|works|wardrobe|dressing|false)\b",
    re.I,
)


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


# Vendors abbreviate room names on the Space/Zone column (L R, LVR, DNR). Without
# these the abbreviations fall through to `unique:` clusters and the same room is
# listed once per vendor spelling.
_ROOM_ABBREVIATIONS: tuple[tuple[str, str], ...] = (
    (r"\bl\s*v?\s*r\b", "living"),
    (r"\bl\s+room\b", "living"),
    (r"\bliv\b", "living"),
    (r"\bd\s*n?\s*r\b", "dining"),
    (r"\bdin\b", "dining"),
    (r"\bkit\b", "kitchen"),
    (r"\bktn\b", "kitchen"),
)


def _room_token(text: str) -> str | None:
    """Find a room in free text. Returns a cluster id, or None.

    Floor prefixes are only emitted when a floor is actually stated. An
    unqualified "Bedroom 1" resolves to `bedroom1`, not `gf_bedroom1`, so the
    ground floor is never invented; `_merge_floor_variants` reunites it with a
    floor-qualified twin afterwards when there is exactly one candidate.
    """
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
        if "first" in n or "1st" in n or re.search(r"\b1f\b", n):
            return f"1f_bedroom{num}"
        if "ground" in n or re.search(r"\bgf\b", n):
            return f"gf_bedroom{num}"
        return f"bedroom{num}"

    for pattern, token in _ROOM_ABBREVIATIONS:
        if re.search(pattern, n):
            return token

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
    text = re.sub(r"^:+\s*", "", (raw or "").strip())
    text = re.sub(r"\s+", " ", text).strip()
    return text or PROJECT_LEVEL_LABEL


def _label_score(label: str) -> int:
    """How much this string reads like a room name, in spelled-out room words."""
    return sum(1 for token in _core(label).split() if token in _ROOM_WORDS)


def choose_space_label(members: list[str], space_id: str = "") -> str:
    """Pick the row heading for a cluster from the vendors' own wording.

    The heading must be a string some vendor actually typed, so the matrix never
    shows a floor or a room name nobody quoted. Among the members we prefer the
    one with the most spelled-out room words ("Living Room" over "L R"), then the
    shortest ("Dining" over "Dining area"), then alphabetical for determinism.

    `_CLUSTER_LABELS` is the fallback for a cluster with nothing readable to
    borrow — every member is an abbreviation ("L R") or a room-prefixed item
    ("MBR Dressing unit"), neither of which makes a usable heading.
    """
    candidates: list[str] = []
    seen: set[str] = set()
    for member in members:
        label = _title_space(member)
        if label == PROJECT_LEVEL_LABEL or not is_room_label(label):
            continue
        if label not in seen:
            seen.add(label)
            candidates.append(label)

    order = sorted(candidates, key=lambda s: (-_label_score(s), len(s), s))
    readable = [
        s for s in order if _label_score(s) > 0 and not _ITEM_NOUN_RE.search(s)
    ]
    if readable:
        return readable[0]
    return _CLUSTER_LABELS.get(space_id) or (order[0] if order else PROJECT_LEVEL_LABEL)


def _is_anchor(space_id: str) -> bool:
    """True for a cluster the deterministic rules named with confidence.

    Anchors are immutable during the LLM pass: the model may attach a loose
    label to one, but never move a row out of one.
    """
    return bool(space_id) and space_id != PROJECT_LEVEL_ID and space_id in _CLUSTER_LABELS


_FLOOR_PREFIXES = ("gf_", "1f_")


def _merge_floor_variants(space_ids: list[str]) -> dict[str, str]:
    """Fold an unqualified bedroom into its floor-qualified twin.

    One vendor writes "Bedroom 1", another "Ground Floor Bedroom 1": the same
    room. We only merge when exactly one floor is in play for that bedroom
    number — if both a GF and a 1F Bedroom 1 exist, the unqualified label is
    genuinely ambiguous and stays its own cluster rather than being guessed into
    one of them.
    """
    present = set(space_ids)
    remap: dict[str, str] = {}
    for space_id in present:
        match = re.fullmatch(r"bedroom(\d+)", space_id or "")
        if not match:
            continue
        qualified = [
            f"{prefix}bedroom{match.group(1)}"
            for prefix in _FLOOR_PREFIXES
            if f"{prefix}bedroom{match.group(1)}" in present
        ]
        if len(qualified) == 1:
            remap[space_id] = qualified[0]
    return remap


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
                # The vendor's own wording, not a canonical invention. The final
                # heading is re-chosen across the whole cluster later.
                "space": _title_space(space_raw),
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

    remap = _merge_floor_variants(list(buckets.keys()))
    if remap:
        merged: dict[str, list[str]] = {}
        for cluster_id, members in buckets.items():
            merged.setdefault(remap.get(cluster_id, cluster_id), []).extend(members)
        buckets = merged

    for cluster_id, members in buckets.items():
        unique_members = list(dict.fromkeys(members))
        kind: Kind = "not_a_space" if cluster_id == PROJECT_LEVEL_ID else "space"
        canonical = (
            PROJECT_LEVEL_LABEL
            if cluster_id == PROJECT_LEVEL_ID
            else choose_space_label(unique_members, cluster_id)
        )
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
            "group": ctx.get("group") or "",
            "items": ctx.get("items", [])[:3],
            "notes": ctx.get("notes", [])[:2],
        }
        for label, ctx in contexts.items()
    ]
    prompt = (
        "You group vendor Space/Zone labels from ONE quote comparison.\n"
        "Each label may already carry a group id. Those are FIXED — never move a "
        "label out of a group it already has, and never merge two different "
        "existing groups.\n"
        "Your only job: for every label whose group is empty, decide whether it is "
        "the same physical room as another label. Vendors abbreviate and rename the "
        "same room (L R / LVR / Living Room; Ground Floor Bedroom 1 / Bedroom 1) — "
        "put those in one cluster.\n"
        "NEVER merge Kitchen with Bedroom, or Common Washroom with Walk-in closet.\n"
        "Use the item names and notes to place a label that is an ITEM rather than a "
        "room: a label whose notes mention MBR belongs to the master bedroom.\n"
        "If a label is an item with no room anywhere in its context (Transportation, "
        "Window blinds), set kind=not_a_space.\n"
        "Uncertain MBR vs walk-in closet: keep TWO clusters.\n"
        "Do NOT name the clusters. Return the labels verbatim; the display name is "
        "chosen from the vendors' own wording, not by you. Never introduce a floor "
        "or a room word that is absent from the labels.\n\n"
        f"Labels:\n{json.dumps(payload, ensure_ascii=False)}\n\n"
        'Return JSON: {"clusters": [{"members": ["Living Room", "L R"], '
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
        for cluster in clusters:
            if not isinstance(cluster, dict):
                continue
            members = [
                str(m).strip()
                for m in (cluster.get("members") or [])
                if str(m).strip() in contexts
            ]
            if not members:
                continue
            kind = cluster.get("kind") or "space"
            if kind not in ("space", "not_a_space", "project_level"):
                kind = "space"

            if kind != "space":
                for member in members:
                    if not _is_anchor(str(contexts[member].get("group") or "")):
                        overlay[member] = {
                            "cluster_id": PROJECT_LEVEL_ID,
                            "canonical": PROJECT_LEVEL_LABEL,
                            "aliases": [member],
                            "members": [member],
                            "kind": "not_a_space",
                            "source": "llm",
                        }
                continue

            # The cluster id comes from an anchor if the model attached loose
            # labels to a room we already named; otherwise it is minted from the
            # labels themselves so the id still traces back to vendor wording.
            anchors = [
                str(contexts[m].get("group") or "")
                for m in members
                if _is_anchor(str(contexts[m].get("group") or ""))
            ]
            movable = [
                m for m in members if not _is_anchor(str(contexts[m].get("group") or ""))
            ]
            if not movable:
                continue
            if len(set(anchors)) == 1:
                cluster_id = anchors[0]
            elif anchors:
                # Two named rooms in one cluster: the model is trying to merge
                # groups we consider settled. Ignore it.
                continue
            elif len(movable) < 2:
                continue
            else:
                cluster_id = f"unique:{_core(choose_space_label(movable) or movable[0])}"

            info = {
                "cluster_id": cluster_id,
                "canonical": choose_space_label(members, cluster_id),
                "aliases": members,
                "members": members,
                "kind": "space",
                "source": "llm",
            }
            for member in movable:
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
    contexts = {}
    for raw in space_raws:
        label = (raw or "").strip() or PROJECT_LEVEL_LABEL
        group = str((heuristic.get(label) or {}).get("cluster_id") or "")
        contexts[label] = {
            "items": [],
            "notes": [],
            "group": group if _is_anchor(group) else "",
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

    _run_space_overlay(df, raw_col=raw_col, out_col=out_col)
    _finalize_space_labels(df, raw_col=raw_col, out_col=out_col)
    return df


def _run_space_overlay(df, *, raw_col: str, out_col: str) -> None:
    """Let Gemini attach labels the deterministic rules could not place.

    Movable rows are the ones with no named room: Project-level rows and
    `unique:` rows. Restricting this to Project-level (as it first did) meant an
    unrecognised room spelling like "L R" was already parked in its own
    `unique:` cluster and never offered for merging, which is exactly how one
    living room ended up listed once per vendor.
    """
    if not _llm_enabled():
        return

    movable_mask = (df["space_source"] == PROJECT_LEVEL_ID) | df["space_id"].astype(
        str
    ).str.startswith("unique:")
    if not movable_mask.any():
        return

    contexts: dict[str, dict[str, Any]] = {}
    for _, row in df.iterrows():
        label = str(row.get(raw_col) or "").strip()
        if not label:
            continue
        space_id = str(row.get("space_id") or "")
        ctx = contexts.setdefault(
            label,
            {"items": [], "notes": [], "group": space_id if _is_anchor(space_id) else ""},
        )
        item = str(row.get("item_name") or "").strip()
        note = str(row.get("description") or "").strip()
        if item and item not in ctx["items"] and len(ctx["items"]) < 3:
            ctx["items"].append(item)
        if note and len(ctx["notes"]) < 2:
            ctx["notes"].append(note[:160])

    if len(contexts) < 2 or not any(not ctx["group"] for ctx in contexts.values()):
        return

    heuristic = {
        label: {
            "cluster_id": ctx["group"] or PROJECT_LEVEL_ID,
            "canonical": _title_space(label),
            "aliases": [label],
            "members": [label],
            "kind": "space" if ctx["group"] else "not_a_space",
        }
        for label, ctx in contexts.items()
    }
    overlay = _try_gemini_overlay(contexts, heuristic)

    def _apply(row):
        current = (
            row["space_id"],
            row[out_col],
            row["space_confidence"],
            row["space_source"],
        )
        if _is_anchor(str(row["space_id"])):
            return current
        info = overlay.get(str(row.get(raw_col) or "").strip())
        if not info or info.get("source") != "llm":
            return current
        if info.get("kind") != "space":
            return PROJECT_LEVEL_ID, PROJECT_LEVEL_LABEL, 0.4, PROJECT_LEVEL_ID
        return info["cluster_id"], info["canonical"], 0.5, "llm"

    applied = [_apply(row) for _, row in df.iterrows()]
    df["space_id"] = [a[0] for a in applied]
    df[out_col] = [a[1] for a in applied]
    df["space_confidence"] = [a[2] for a in applied]
    df["space_source"] = [a[3] for a in applied]


def _finalize_space_labels(df, *, raw_col: str, out_col: str) -> None:
    """Fold floor variants, then name every cluster from its members.

    Naming happens once, here, over the whole cluster rather than per row. That
    is what keeps the heading in the vendors' language: a row placed by its
    description borrows the room string its siblings supplied, and a cluster
    whose members never mention a floor cannot acquire one.
    """
    remap = _merge_floor_variants([str(v) for v in df["space_id"].tolist()])
    if remap:
        df["space_id"] = [remap.get(str(v), str(v)) for v in df["space_id"].tolist()]

    members: dict[str, list[str]] = {}
    for space_id, label in zip(df["space_id"].tolist(), df[raw_col].fillna("").tolist()):
        members.setdefault(str(space_id), []).append(str(label).strip())

    labels = {
        space_id: (
            PROJECT_LEVEL_LABEL
            if space_id == PROJECT_LEVEL_ID
            else choose_space_label(raws, space_id)
        )
        for space_id, raws in members.items()
    }
    df[out_col] = [labels.get(str(v), PROJECT_LEVEL_LABEL) for v in df["space_id"].tolist()]

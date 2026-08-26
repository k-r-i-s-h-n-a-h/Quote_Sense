# ACTION.md — invariants agents must not reverse

This file is the lock on comparison behaviour that customers already agreed.
If a later change looks like an improvement but violates one of these rules,
**do not ship it**. Update a stage implementation to honour the rule; do not
weaken the rule to make a model or a heuristic easier.

The pipeline plan stays in [PLAN.md](PLAN.md). This file is the "why we must
not undo that work" list.

---

## 1. One physical space, one customer total (S3)

Vendors name the same room in different words. The matrix must **combine**
those spellings into one space so the customer sees spend per room, not per
vendor nickname.

These are the **same living space** and must be one section:

`Living` · `LIVING` · `Living Room` · `Living area` · `L R` · `LR` · `LVR` ·
`L ROOM` · `Lroom` · `Liv`

The same rule applies to every room type: `DNR` / `Dining` / `Dining area`;
`KIT` / `Kitchen`; `MBR` / `Master Bedroom`; lounge spellings on one floor.

**What the customer must see:** every sub-service the vendors quoted in that
space, under one heading, with one space total.

**What they must not see:** a separate block for each spelling (`LIVING`, then
`L R`, then `LVR`, then `L ROOM`). That is a decomposition by words, not by
rooms, and it hides the living-area total.

How S3 is allowed to do this:

1. Deterministic room tokens and compact abbreviations first
   (`backend/services/space_clusters.py`).
2. LLM overlay only for leftovers the tokens missed — and the prompt must
   treat the living/dining abbreviations above as **mandatory merges**.
3. Display heading comes from the vendors' own wording (prefer the spelled-out
   name). Never invent a floor (`GF-`) nobody wrote.

The frontend **must not** re-split by the heading. It groups on `space_id`.

Do **not** "fix" this by showing every vendor string as its own space. That
was the bug.

---

## 2. Expired session → login popup, not an inline button

When the user's Tatva session has expired, tell them with a **modal**.

- Do not put a small "Sign in again" button inside the My projects card.
- The popup states that the session expired and the primary action is
  **Sign in again**.
- Standalone PDF compare may remain available after they dismiss the popup.

Module: `frontend/components/SessionExpiredModal.tsx`, shown from
`ProjectDashboard` on a 401/403 while a stale user is still in memory.

---

## 3. Change protocol

If a matrix looks wrongly grouped, fix **S3** (or S2 for work items, S4 for
lumpsums). Do not invent a new grouping layer on the frontend. Do not drop
abbreviation rules because a new model "will understand it" — keep the
deterministic merge; the LLM is a backup, not a replacement.

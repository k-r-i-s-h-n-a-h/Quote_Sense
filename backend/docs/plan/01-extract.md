# S1 — Extract

Turn a vendor quote (PDF or Tatva/Mongo JSON) into `LineItemV1` rows.

**Input:** PDF bytes, or a Tatva quote payload.
**Output:** `LineItemV1` — see [00-contracts.md](00-contracts.md).

**Modules**

- `services/extractor.py` — PDF lane. Gemini structured extraction against
  `models/schema.py`, then `push_to_supabase`.
- `services/comparator.py::mongodb_quotes_to_dataframe` — Tatva payload lane.
- `services/taxonomy_prompt.py` — static prompt carrying `TATVAOPS_TAXONOMY`.
- `services/extraction_cache.py` — Gemini explicit context cache for that prompt.

---

## Responsibility boundary

S1 owns **reading**, not interpreting. It records what the vendor wrote and does
not attempt to decide what work it is or which room it belongs to. Those are S2
and S3.

Specifically, S1 must **not**:

- normalise or canonicalise `sub_service` (S2's job),
- guess a room when `space_raw` is an item name (S3's job),
- decide whether a line is a lumpsum (S4's job).

The reason is the change protocol: extraction models change often. Keeping
interpretation out of S1 means a model swap cannot corrupt grouping.

---

## Rules

1. `space_raw` is recorded **verbatim**, including the vendor's oddities:
   `": Foyer area"`, `"Kitchen Accessories"`, `"MBR Dressing Mirror"`. Do not
   clean it here — S3 needs the raw string to judge confidence.
2. `description` is preserved in full. It is the highest-value field in the
   pipeline: it carries room hints (`"MBR Used cloth storages"`) and bundle
   contents (`"5 tandem, 1 bottle unit, Rolling shutter, Gola handles..."`).
   Truncating it breaks S3 and S4.
3. `pricing_method` is recorded verbatim. S4 keys bundle detection off it.
4. One quote's `grand_total` is repeated on every row of that quote.
5. `vendor_name` is `"{company} ({source_filename})"` so two quotes from the
   same company remain distinct matrix columns.
6. Tatva `workSummary` GST flags become `gst_mode` (`exclusive` / `inclusive`).
   Line `amount` is the billed `grandTotal` so excl. and incl. quotes compare
   on the same GST-inclusive basis. Do not mix a pre-GST `amount` with a
   GST-inclusive total, and do not apply a homemade GST rate.

## Validation

`validate_extraction` reconciles the sum of line-item amounts against the PDF
subtotal and triggers a retry when the gap is severe. A mismatch below tolerance
is accepted with a warning — the matrix stays usable, but per-vendor totals
prefer the printed `grand_total` over the line-item sum.

## Kill switches

| Env var | Default | Effect |
| --- | --- | --- |
| `GEMINI_EXTRACT_MODEL` | `gemini-3.5-flash` | Override the extraction model. |
| `GEMINI_EXPLICIT_CACHE` | — | Disable prompt caching. |
| `GEMINI_CACHE_TTL` | — | Cache lifetime. |

Gemini 3.x often 400s on explicit `temperature` (including `0`).
`gemini_generate_config` in `services/env_config.py` omits sampling overrides
on 3.x and keeps them for 2.5.

## Tests

- `tests/test_space_compare.py::test_mongodb_keeps_nested_object_ids` — ObjectIds
  and `space_raw` survive the Tatva lane.
- `tests/fixtures/quote_*.json` — the two golden quotes, already in
  `LineItemV1` shape, so S2–S6 can be tested without touching a PDF or Gemini.

---

## What to change if this stage breaks

**Symptom: a new extraction model returns a different JSON shape.**
Change only the adapter — `process_quote_with_gemini` for the PDF lane, or
`mongodb_quotes_to_dataframe` for the payload lane. Both must still emit every
required `LineItemV1` field. Nothing downstream should need an edit; if it does,
the adapter is not honouring the contract.

**Symptom: rows are missing fields downstream.**
Run with `QUOTESENSE_VALIDATE_CONTRACTS=1`. `validate_line_items(df, "S1")`
names the missing field. Add it in the adapter with a sensible empty default
(`""` for strings, `0.0` for numbers) — never `None`.

**Symptom: totals do not reconcile.**
That is `validate_extraction`, not the matrix. Check the tolerance logic before
suspecting S5.

**Do not** fix a grouping problem here. If two vendors' equivalent lines are not
comparing, the fix belongs in S2 (work identity) or S3 (space identity), even
when the root cause looks like messy vendor text.

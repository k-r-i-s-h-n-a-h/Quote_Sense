# Golden fixtures

Two quotes captured from the test environment, already in `LineItemV1` shape,
plus the assertions that pin the grouping behaviour they exposed. The vendor
names are the placeholder companies from that environment, not real suppliers.

| File | Contents |
| --- | --- |
| `quote_a_Q2OE1CX.json` | 30 line items, grand total 11,50,444.54 |
| `quote_b_QGT3A1I.json` | 47 line items, grand total 10,31,710.27 |
| `expected_matrix.json` | The grouping outcomes that must hold |

These two quotes are the regression net for the whole pipeline. They were chosen
because between them they contain every failure mode the redesign addresses:

- casing and plural splits (`Side table` / `Side Table`, `Rolling Shutter` /
  `Rolling shutters`),
- cross-vendor synonyms (`False Ceiling` / `False ceiling with painting`,
  `Loft` / `Loft unit`),
- one-to-many work mapping (`Crockery Units` against `Crockery Base unit` +
  `Crockery Wall unit`),
- item names in the Space/Zone column, both with a room prefix
  (`MBR Dressing unit`) and without (`Used cloth unit`),
- a vendor mislabelling a line (`MBR Used cloth units` on a dressing mirror),
- a real lumpsum against real itemised lines (`Hardwares` vs five accessories),
- a lumpsum whose description overlaps a separately billed line
  (`Hardwares` names a rolling shutter; the same vendor also bills one).

Because the fixtures start at `LineItemV1`, every stage from S2 onward can be
tested without a PDF, without Gemini and without Supabase.

## Using them

```python
from tests.fixtures import load_golden_df
df = load_golden_df()          # both quotes, one DataFrame
```

Tests set `GEMINI_WORK_LLM=0` and `GEMINI_SPACE_LLM=0`, so results are
deterministic.

## Changing them

If a code change alters the golden output, that is either a bug or a deliberate
improvement. In the second case update `expected_matrix.json` in the **same
commit** as the code, with the reason in the commit message. Never update the
fixture separately to make a red test go green.

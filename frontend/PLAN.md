# Frontend — comparison UI stage index

Start at [../PLAN.md](../PLAN.md) for the pipeline contract chain and change
protocol. This file is the frontend-side index.

| Stage | Doc | Module |
| --- | --- | --- |
| F0 contracts | [docs/plan/00-contracts.md](docs/plan/00-contracts.md) | `lib/compare-types.ts` |
| F1 fetch | [docs/plan/01-fetch.md](docs/plan/01-fetch.md) | `lib/compare-progress.ts`, `lib/compare-sync.ts`, `app/api/**` |
| F2 grouping | [docs/plan/02-grouping.md](docs/plan/02-grouping.md) | `lib/compare-matrix.ts` |
| F3 matrix UI | [docs/plan/03-matrix-ui.md](docs/plan/03-matrix-ui.md) | `components/compare/ComparisonMatrix.tsx` |
| F4 export | [docs/plan/04-export.md](docs/plan/04-export.md) | `lib/download-comparison-pdf.ts`, `lib/pdf-unicode-font.ts` |

## Where the backend boundary sits

The backend owns all interpretation. The frontend does **no** canonicalisation:
it does not decide which rows are the same work, which room a line belongs to, or
whether a price is a bundle. Those are `work_key`, `space_id` and `scope`,
computed in the backend and shipped in `MatrixV1`.

The frontend's only grouping job is presentation nesting — category, then space,
then work row — keyed on identifiers the backend already resolved.

Customer copy says **space**, not room. Recap notes name the quote (company if
they differ, quote number if they are the same company) and say whether a figure
is already in the spaces above or is a whole-home amount in this quote. GST
entry chips come from `vendorMeta.gst_mode`. The matrix does not paint a Quote
total row; grand totals stay on the chart.

This split matters for the change protocol: a backend model change must never
require a frontend edit, and a UI change must never alter a number.

## Rendering rule

Never invent or recompute a comparison figure. Vendor amounts arrive
pre-aggregated per row; the UI sums them for header rows and nothing more. In
particular, a zero is not automatically `N/A` — check the coverage status first,
because a zero can mean the amount lives inside a bundle.

## Backward compatibility

`MatrixV1` still carries `tableData` (equal to `spaceTier + projectTier`), so
every component keeps working before it is migrated. Components read
`contract_version` and fall back to the flat shape when the tiers are absent.

## Running

```bash
cd frontend && npm run dev
npm test           # vitest
npx tsc --noEmit   # type check
```

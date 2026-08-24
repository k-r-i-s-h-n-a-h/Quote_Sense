# Backend — comparison pipeline stage index

Start at [../PLAN.md](../PLAN.md) for the contract chain and change protocol.
This file is the backend-side index: what each stage owns, which module
implements it, and where to look when it misbehaves.

| Stage | Doc | Module |
| --- | --- | --- |
| S0 contracts | [docs/plan/00-contracts.md](docs/plan/00-contracts.md) | `services/contracts.py` |
| S1 extract | [docs/plan/01-extract.md](docs/plan/01-extract.md) | `services/extractor.py`, `comparator.mongodb_quotes_to_dataframe` |
| S2 bind | [docs/plan/02-bind.md](docs/plan/02-bind.md) | `services/work_catalog.py`, `services/tatva_catalog.py` |
| S3 spaces | [docs/plan/03-spaces.md](docs/plan/03-spaces.md) | `services/space_clusters.py` |
| S4 bundles | [docs/plan/04-bundles.md](docs/plan/04-bundles.md) | `services/bundles.py` |
| S5 matrix | [docs/plan/05-matrix.md](docs/plan/05-matrix.md) | `services/comparator.py` |
| S6 recommend | [docs/plan/06-recommend.md](docs/plan/06-recommend.md) | `services/comparator.py` |

## Orchestration

`run_comparison` in `services/comparator.py` is the only place the stages are
wired together, in this fixed order:

```python
df = _bind_catalog_ids_from_cache(df)   # S2a — Tatva ObjectIds
df = apply_work_catalog(df)             # S2b — work_key
df = apply_space_clusters(df)           # S3  — space_id
df = apply_bundles(df)                  # S4  — scope
# S5 — pivot into spaceTier / bundleTier / projectTier
# S6 — recommendation
```

Entry points that reach this: `POST /api/compare-quotes`,
`POST /api/sync-mongodb-quotes`, `GET /api/get-comparison` (all in `main.py`).

## Running the tests

```bash
cd backend && python -m pytest tests/ -q
```

Tests force `GEMINI_SPACE_LLM=0` and `GEMINI_WORK_LLM=0`, so the suite is fully
deterministic and never makes a network call.

## Debugging a bad matrix

1. `python -m pytest tests/test_matrix_contract.py -q` — validates the row
   contract between stages and names the first stage that produced a bad row.
2. Set `QUOTESENSE_VALIDATE_CONTRACTS=1` on a real run to get the same check
   in production paths.
3. Go to that stage's doc and read its "What to change if this stage breaks"
   section.

Symptom-to-stage shortcut:

| Symptom | Stage |
| --- | --- |
| Same work split across two rows | S2 |
| Item name showing up as a room | S3 |
| Room total looks too low | S3 or S4 |
| Lumpsum shown as `N/A` against an itemising vendor | S4 |
| Amounts right, layout wrong | S5 or frontend |
| Narrative contradicts the table | S6 |

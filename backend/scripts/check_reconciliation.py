#!/usr/bin/env python
"""Fail the build if a comparison loses a vendor's money.

Runs the comparison over the golden quotes (or a live session id) and exits
non-zero when any vendor's rows do not add back up to that vendor's quoted
lines. Same gate the API applies before a PDF; here it blocks a merge.

    python scripts/check_reconciliation.py            # golden fixtures
    python scripts/check_reconciliation.py <session>  # a real session
"""

from __future__ import annotations

import os
import sys

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

os.environ.setdefault("GEMINI_WORK_LLM", "0")
os.environ.setdefault("GEMINI_SPACE_LLM", "0")


def main(argv: list[str]) -> int:
    import services.comparator as comparator
    from services.lineage import ReconciliationError, assert_reconciled

    session = argv[1] if len(argv) > 1 else None
    if session:
        payload = comparator.run_comparison(session)
    else:
        from tests.fixtures import load_golden_df

        comparator._generate_recommendation = lambda *a, **k: ""
        payload = comparator.run_comparison("reconciliation-check", df=load_golden_df())

    report = payload.get("reconciliation") or {}
    try:
        assert_reconciled(report)
    except ReconciliationError as exc:
        print(f"reconciliation FAILED: {exc}", file=sys.stderr)
        return 1

    for vendor, entry in (report.get("vendors") or {}).items():
        print(f"  {vendor}: delta {entry.get('delta', 0):.2f}")
    print("reconciliation OK")
    return 0


if __name__ == "__main__":
    raise SystemExit(main(sys.argv))

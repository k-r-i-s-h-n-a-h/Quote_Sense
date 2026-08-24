"""Golden fixture loaders — two real quotes in LineItemV1 shape.

See README.md in this directory for why these two quotes are the regression net.
"""

from __future__ import annotations

import json
import os

FIXTURE_DIR = os.path.dirname(os.path.abspath(__file__))

QUOTE_A = "quote_a_Q2OE1CX.json"
QUOTE_B = "quote_b_QGT3A1I.json"

VENDOR_A = "INFOSYS LIMITED (Q2OE1CX)"
VENDOR_B = "TATA CONSULTANCY SERVICES LIMITED (QGT3A1I)"


def load_quote(filename: str) -> dict:
    with open(os.path.join(FIXTURE_DIR, filename), encoding="utf-8") as fh:
        return json.load(fh)


def load_expected() -> dict:
    return load_quote("expected_matrix.json")


def quote_to_rows(quote: dict) -> list[dict]:
    """Flatten one fixture quote into LineItemV1 rows."""
    header = {
        "vendor_name": quote["vendor_name"],
        "company": quote["company"],
        "source_filename": quote["source_filename"],
        "quote_number": quote["quote_number"],
        "quote_date": quote["quote_date"],
        "grand_total": quote["grand_total"],
        "service_category": quote["service_category"],
        "service_type": quote["service_type"],
    }
    rows = []
    for item in quote["items"]:
        row = dict(header)
        row.update(item)
        # work_title mirrors space_raw on the PDF lane, matching the real pipeline.
        row["work_title"] = item["space_raw"]
        row["sub_service_id"] = ""
        row["pricing_method_id"] = ""
        rows.append(row)
    return rows


def load_golden_rows() -> list[dict]:
    """Both quotes as a single list of LineItemV1 rows."""
    return quote_to_rows(load_quote(QUOTE_A)) + quote_to_rows(load_quote(QUOTE_B))


def load_golden_df():
    import pandas as pd

    return pd.DataFrame(load_golden_rows())

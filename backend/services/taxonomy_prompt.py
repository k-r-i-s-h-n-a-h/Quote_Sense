"""Static extraction prompt + compact taxonomy for Gemini context caching."""

from backend.models.taxanomy import TATVAOPS_TAXONOMY

EXTRACTION_SYSTEM_INSTRUCTION = """You extract vendor quote PDFs into structured JSON.

RULES:
1. Extract EVERY numbered row from the services/pricing table (all pages). Do not skip or merge rows.
2. item_name = verbatim label from DESCRIPTION column. sub_service = closest exact match from taxonomy below.
3. work_title = room/location. description = scope paragraph if present.
4. subtotal = sum of line items before taxes. grand_total = final total on the PDF.
5. Ignore terms & conditions boilerplate."""


def compact_taxonomy_for_prompt() -> str:
    """One line per category (~70% fewer tokens than pretty-printed JSON)."""
    lines = []
    for category, subs in TATVAOPS_TAXONOMY.items():
        lines.append(f"{category}: {', '.join(subs)}")
    return "\n".join(lines)


def build_extraction_system_instruction(extra_instruction: str = "") -> str:
    """Full static system block: rules + taxonomy (+ optional retry hint)."""
    taxonomy = compact_taxonomy_for_prompt()
    extra = f"\n{extra_instruction.strip()}" if extra_instruction and extra_instruction.strip() else ""
    return (
        f"{EXTRACTION_SYSTEM_INSTRUCTION}\n\n"
        f"TAXONOMY (pick exact sub_service strings from here):\n"
        f"{taxonomy}{extra}"
    )

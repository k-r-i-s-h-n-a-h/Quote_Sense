"""Send one Ask-the-vendors checklist through an approved MSG91 template.

WhatsApp forbids newlines inside a variable. Line breaks belong in the
template body; each question gets its own placeholder.

v2 template (MSG91_ASK_VENDOR_TEMPLATE=tatvaops_quotesense_ask_vendor_v2_en):
  {{1}} vendor name
  {{2}} quote number
  {{3}} question count
  {{4}} question 1
  {{5}} question 2 (or —)
  {{6}} question 3, plus any extras packed with " | "
  {{7}} notes, or — when the box is empty

The original 5-variable template still works until v2 is approved.
"""

from __future__ import annotations

import os
import re
from typing import Any

import httpx

TEMPLATE_NAME = "tatvaops_quotesense_ask_vendor_en"
TEMPLATE_V2_NAME = "tatvaops_quotesense_ask_vendor_v2_en"
TEMPLATE_LANG = "en"
MSG91_URL = "https://api.msg91.com/api/v5/whatsapp/whatsapp-outbound-message/bulk/"

QUESTIONS_MAX = 400
QUESTION_SLOT_MAX = 220
NOTES_MAX = 200
NAME_MAX = 80
EMPTY_SLOT = "—"


class WhatsAppSendError(Exception):
    def __init__(self, message: str, *, status_code: int = 502):
        super().__init__(message)
        self.status_code = status_code


def clip_var(text: Any, limit: int) -> str:
    compact = " ".join(str(text or "").split())
    if not compact:
        return ""
    if len(compact) <= limit:
        return compact
    return compact[: max(1, limit - 1)].rstrip() + "…"


def template_name() -> str:
    return (os.getenv("MSG91_ASK_VENDOR_TEMPLATE") or TEMPLATE_NAME).strip()


def ask_vendor_layout() -> str:
    explicit = (os.getenv("MSG91_ASK_VENDOR_LAYOUT") or "").strip().lower()
    if explicit in {"lines", "packed"}:
        return explicit
    return "lines" if "_v2" in template_name() else "packed"


def notes_or_dash(notes: str) -> str:
    """Empty free-text is a valid send: the template still needs a notes slot."""
    clipped = clip_var(notes, NOTES_MAX)
    return clipped or EMPTY_SLOT


def format_questions(questions: list[str]) -> str:
    """Packed layout: WhatsApp strips newlines, so separate items with ' | '."""
    parts = []
    for i, item in enumerate(questions, start=1):
        text = clip_var(item, 180)
        if text:
            parts.append(f"{i}) {text}")
    return clip_var(" | ".join(parts), QUESTIONS_MAX) or EMPTY_SLOT


def question_slots(questions: list[str]) -> tuple[str, str, str]:
    """Three body slots. Extra questions append to the last slot."""
    cleaned = [clip_var(q, QUESTION_SLOT_MAX) for q in questions]
    cleaned = [q for q in cleaned if q]
    first = cleaned[0] if cleaned else EMPTY_SLOT
    second = cleaned[1] if len(cleaned) > 1 else EMPTY_SLOT
    rest = cleaned[2:]
    if not rest:
        third = EMPTY_SLOT
    elif len(rest) == 1:
        third = rest[0]
    else:
        packed = [rest[0]]
        packed.extend(f"{i}) {text}" for i, text in enumerate(rest[1:], start=4))
        third = clip_var(" | ".join(packed), QUESTION_SLOT_MAX)
    return first, second, third


def default_country_code() -> str:
    digits = re.sub(r"\D", "", os.getenv("MSG91_DEFAULT_COUNTRY_CODE") or "91")
    return digits or "91"


def india_whatsapp_number(raw: str) -> str:
    digits = re.sub(r"\D", "", str(raw or ""))
    cc = default_country_code()
    if digits.startswith("0") and len(digits) == 11:
        digits = digits[1:]
    if len(digits) == 10:
        return cc + digits
    if digits.startswith(cc) and len(digits) >= 10 + len(cc):
        return digits[: 10 + len(cc)]
    return ""


def build_template_vars(
    *,
    vendor_name: str,
    quote_number: str,
    questions: list[str],
    notes: str,
) -> dict[str, str]:
    listed = [q for q in questions if str(q or "").strip()]
    count = str(len(listed) or 1)
    name = clip_var(vendor_name, NAME_MAX) or "Vendor"
    quote = clip_var(quote_number, 24) or EMPTY_SLOT
    if ask_vendor_layout() == "lines":
        q1, q2, q3 = question_slots(listed)
        return {
            "body_1": name,
            "body_2": quote,
            "body_3": count,
            "body_4": q1,
            "body_5": q2,
            "body_6": q3,
            "body_7": notes_or_dash(notes),
        }
    return {
        "body_1": name,
        "body_2": quote,
        "body_3": count,
        "body_4": format_questions(listed),
        "body_5": notes_or_dash(notes),
    }


def send_ask_vendor(
    *,
    phone: str,
    vendor_name: str,
    quote_number: str,
    questions: list[str],
    notes: str = "",
) -> dict[str, Any]:
    to = india_whatsapp_number(phone)
    if not to:
        raise WhatsAppSendError(
            "No usable vendor phone on this quote. Extract a number first.",
            status_code=400,
        )
    listed = [q for q in questions if str(q or "").strip()]
    if not listed:
        raise WhatsAppSendError(
            "Tick at least one question before sending.",
            status_code=400,
        )

    authkey = (os.getenv("MSG91_AUTH_KEY") or "").strip()
    integrated = re.sub(r"\D", "", os.getenv("MSG91_WHATSAPP_NUMBER") or "916383065482")
    if not authkey:
        raise WhatsAppSendError(
            "MSG91_AUTH_KEY is not set on the backend. Add it to backend/.env.",
            status_code=503,
        )

    variables = build_template_vars(
        vendor_name=vendor_name,
        quote_number=quote_number,
        questions=listed,
        notes=notes,
    )
    components = {
        key: {"type": "text", "value": value} for key, value in variables.items()
    }

    template: dict[str, Any] = {
        "name": template_name(),
        "language": {
            "code": (os.getenv("MSG91_ASK_VENDOR_LANG") or TEMPLATE_LANG).strip(),
            "policy": "deterministic",
        },
        "to_and_components": [{"to": [to], "components": components}],
    }
    namespace = (os.getenv("MSG91_WHATSAPP_NAMESPACE") or "").strip()
    if namespace:
        template["namespace"] = namespace

    body = {
        "integrated_number": integrated,
        "content_type": "template",
        "payload": {
            "messaging_product": "whatsapp",
            "type": "template",
            "template": template,
        },
    }

    try:
        response = httpx.post(
            MSG91_URL,
            headers={"authkey": authkey, "Content-Type": "application/json"},
            json=body,
            timeout=20.0,
        )
    except httpx.HTTPError as exc:
        raise WhatsAppSendError(f"Could not reach MSG91: {exc}") from exc

    try:
        payload = response.json()
    except ValueError:
        payload = {"raw": response.text[:300]}

    if response.status_code >= 400 or str(payload.get("status") or "").lower() in {
        "error",
        "fail",
        "failed",
    }:
        detail = (
            payload.get("message")
            or payload.get("error")
            or payload.get("type")
            or response.text[:200]
        )
        raise WhatsAppSendError(f"MSG91 refused the send: {detail}")

    return {
        "ok": True,
        "to": to,
        "template": template["name"],
        "variables": variables,
        "msg91": payload,
    }

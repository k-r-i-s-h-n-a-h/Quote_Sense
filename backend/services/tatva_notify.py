"""Send one vendor-private clarification brief through Tatva PM notification.

POST {TATVA_API_BASE}/notification/api/notifications/send
PM Nodemailer sends as info@withtatva.ai — QuoteSense does not set From.
WhatsApp stays on MSG91. Do not use MSG91 Email (Hostinger DNS clash).
"""

from __future__ import annotations

import html
import os
from typing import Any

import httpx

from services.vendor_contact import normalize_vendor_email

SEND_PATH = "/notification/api/notifications/send"
DEFAULT_API_BASE = "https://devopsapi.withtatva.ai"


class EmailSendError(Exception):
    def __init__(self, message: str, *, status_code: int = 502):
        super().__init__(message)
        self.status_code = status_code


def notification_send_url() -> str:
    explicit = (os.getenv("TATVA_NOTIFICATION_SEND_URL") or "").strip()
    if explicit:
        return explicit.rstrip("/")
    base = (os.getenv("TATVA_API_BASE") or DEFAULT_API_BASE).strip().rstrip("/")
    return f"{base}{SEND_PATH}"


def outbound_quote_number(raw: str) -> str:
    """One quote id for the vendor email — never a joined pair."""
    text = " ".join(str(raw or "").replace("#", " ").split())
    first = text.split(",")[0].strip()
    return first or "—"


def build_clarification_html(
    *,
    vendor_name: str,
    quote_number: str,
    questions: list[str],
    notes: str = "",
) -> str:
    name = html.escape(vendor_name or "Vendor")
    quote = html.escape(quote_number)
    items = "".join(f"<li>{html.escape(question)}</li>" for question in questions)
    notes_text = str(notes or "").strip()
    notes_block = ""
    if notes_text:
        notes_html = html.escape(notes_text).replace("\n", "<br>")
        notes_block = f"<p><strong>Notes:</strong><br>{notes_html}</p>"
    return (
        f"<p>Hi {name},</p>"
        f"<p>Please confirm the following for quote <strong>{quote}</strong>:</p>"
        f"<ol>{items}</ol>"
        f"{notes_block}"
        f"<p>Thanks,<br>Tatva Ops</p>"
    )


def build_clarification_text(
    *,
    vendor_name: str,
    quote_number: str,
    questions: list[str],
    notes: str = "",
) -> str:
    lines = [
        f"Hi {vendor_name or 'Vendor'},",
        "",
        f"Please confirm the following for quote {quote_number}:",
        "",
    ]
    lines.extend(f"{index}. {question}" for index, question in enumerate(questions, start=1))
    notes_text = str(notes or "").strip()
    if notes_text:
        lines.extend(["", "Notes:", notes_text])
    lines.extend(["", "Thanks,", "Tatva Ops"])
    return "\n".join(lines)


def build_notification_body(
    *,
    email: str,
    vendor_name: str,
    quote_number: str,
    questions: list[str],
    notes: str = "",
) -> dict[str, Any]:
    to = normalize_vendor_email(email)
    if not to:
        raise EmailSendError(
            "No usable vendor email on this quote. Extract an email first.",
            status_code=400,
        )
    listed = [str(question or "").strip() for question in questions]
    listed = [question for question in listed if question]
    if not listed:
        raise EmailSendError(
            "Tick at least one question before sending.",
            status_code=400,
        )
    name = str(vendor_name or "").strip() or "Vendor"
    quote = outbound_quote_number(quote_number)
    notes_text = str(notes or "").strip()
    return {
        "type": "generic",
        "to": to,
        "data": {
            "subject": f"Clarifications for quote {quote}",
            "message": build_clarification_text(
                vendor_name=name,
                quote_number=quote,
                questions=listed,
                notes=notes_text,
            ),
            "html": build_clarification_html(
                vendor_name=name,
                quote_number=quote,
                questions=listed,
                notes=notes_text,
            ),
        },
    }


def send_ask_vendor_email(
    *,
    email: str,
    vendor_name: str,
    quote_number: str,
    questions: list[str],
    notes: str = "",
) -> dict[str, Any]:
    body = build_notification_body(
        email=email,
        vendor_name=vendor_name,
        quote_number=quote_number,
        questions=questions,
        notes=notes,
    )
    url = notification_send_url()
    headers = {
        "Accept": "application/json",
        "Content-Type": "application/json",
    }
    api_key = (os.getenv("TATVA_API_KEY") or "").strip()
    if api_key:
        headers["x-api-key"] = api_key

    try:
        response = httpx.post(url, headers=headers, json=body, timeout=20.0)
    except httpx.HTTPError as exc:
        raise EmailSendError(f"Could not reach Tatva notification: {exc}") from exc

    try:
        payload = response.json()
    except ValueError:
        payload = {"raw": response.text[:300]}

    ok = response.status_code < 400 and payload.get("success") is True
    if not ok:
        detail = payload.get("message") or payload.get("errors") or response.text[:200]
        raise EmailSendError(f"Tatva notification refused the email: {detail}")

    return {
        "ok": True,
        "to": body["to"],
        "quote_number": outbound_quote_number(quote_number),
        "tatva": payload,
    }

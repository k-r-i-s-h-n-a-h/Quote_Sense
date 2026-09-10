"""Send one vendor-private clarification checklist through MSG91 Email.

MSG91 template variables (Handlebars):

  {{vendor_name}} {{quote_number}} {{question_count}}
  {{#each questions}}{{number}}. {{text}}{{/each}}
  {{#if has_notes}}{{notes}}{{/if}}

From: info@mail.withtatva.ai on domain mail.withtatva.ai.
Reply-To: contact@withtatva.ai.
"""

from __future__ import annotations

import os
from typing import Any

import httpx

from services.vendor_contact import normalize_vendor_email

MSG91_EMAIL_URL = "https://control.msg91.com/api/v5/email/send"
DEFAULT_DOMAIN = "mail.withtatva.ai"
DEFAULT_FROM_EMAIL = "info@mail.withtatva.ai"
DEFAULT_FROM_NAME = "TatvaOps QuoteSense"
DEFAULT_REPLY_TO = "contact@withtatva.ai"


class EmailSendError(Exception):
    def __init__(self, message: str, *, status_code: int = 502):
        super().__init__(message)
        self.status_code = status_code


def email_settings() -> dict[str, str]:
    return {
        "authkey": (os.getenv("MSG91_AUTH_KEY") or "").strip(),
        "template_id": (
            os.getenv("MSG91_ASK_VENDOR_EMAIL_TEMPLATE")
            or "tatvaops_quotesense_vendor_clarifications"
        ).strip(),
        "domain": (
            os.getenv("MSG91_EMAIL_DOMAIN") or DEFAULT_DOMAIN
        ).strip().lower(),
        "from_email": (
            os.getenv("MSG91_EMAIL_FROM") or DEFAULT_FROM_EMAIL
        ).strip().lower(),
        "from_name": (
            os.getenv("MSG91_EMAIL_FROM_NAME") or DEFAULT_FROM_NAME
        ).strip(),
        "reply_to": (
            os.getenv("MSG91_EMAIL_REPLY_TO") or DEFAULT_REPLY_TO
        ).strip().lower(),
    }


def build_email_body(
    *,
    email: str,
    vendor_name: str,
    quote_number: str,
    questions: list[str],
    notes: str = "",
) -> dict[str, Any]:
    settings = email_settings()
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
    notes_text = str(notes or "").strip()
    if not settings["authkey"]:
        raise EmailSendError(
            "MSG91_AUTH_KEY is not set on the backend.",
            status_code=503,
        )
    if not settings["template_id"]:
        raise EmailSendError(
            "The MSG91 vendor email template is not configured yet.",
            status_code=503,
        )

    variables: dict[str, Any] = {
        "vendor_name": str(vendor_name or "").strip() or "Vendor",
        "quote_number": str(quote_number or "").strip() or "—",
        "question_count": len(listed),
        "questions": [
            {"number": index, "text": question}
            for index, question in enumerate(listed, start=1)
        ],
        "notes": notes_text,
        "has_notes": bool(notes_text),
    }
    body: dict[str, Any] = {
        "recipients": [
            {
                "to": [{"name": variables["vendor_name"], "email": to}],
                "variables": variables,
            }
        ],
        "from": {
            "name": settings["from_name"],
            "email": settings["from_email"],
        },
        "domain": settings["domain"],
        "template_id": settings["template_id"],
    }
    reply_to = normalize_vendor_email(settings["reply_to"])
    if reply_to:
        body["reply_to"] = [{"email": reply_to}]
    return body


def send_ask_vendor_email(
    *,
    email: str,
    vendor_name: str,
    quote_number: str,
    questions: list[str],
    notes: str = "",
) -> dict[str, Any]:
    settings = email_settings()
    body = build_email_body(
        email=email,
        vendor_name=vendor_name,
        quote_number=quote_number,
        questions=questions,
        notes=notes,
    )
    try:
        response = httpx.post(
            MSG91_EMAIL_URL,
            headers={
                "accept": "application/json",
                "authkey": settings["authkey"],
                "Content-Type": "application/json",
            },
            json=body,
            timeout=20.0,
        )
    except httpx.HTTPError as exc:
        raise EmailSendError(f"Could not reach MSG91: {exc}") from exc

    try:
        payload = response.json()
    except ValueError:
        payload = {"raw": response.text[:300]}

    failed = (
        response.status_code >= 400
        or bool(payload.get("hasError"))
        or str(payload.get("status") or "").lower() in {"error", "fail", "failed"}
    )
    if failed:
        detail = (
            payload.get("message")
            or payload.get("errors")
            or payload.get("error")
            or response.text[:200]
        )
        raise EmailSendError(f"MSG91 refused the email: {detail}")

    return {
        "ok": True,
        "to": body["recipients"][0]["to"][0]["email"],
        "template": body["template_id"],
        "msg91": payload,
    }

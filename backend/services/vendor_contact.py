"""Vendor contact fields pulled from a quote payload.

Tatva `vendorDetail` does not use one field name. We try the common keys and
keep digits (with a leading + if the vendor wrote a country code). Empty
means the payload had no number — WhatsApp send must not invent one.
"""

from __future__ import annotations

import re
from typing import Any

_PHONE_KEYS = (
    "phoneNumber",
    "phone",
    "mobile",
    "mobileNumber",
    "contactNumber",
    "whatsappNumber",
    "companyPhone",
    "phoneNo",
    "phone_number",
)


def normalize_vendor_phone(raw: Any) -> str:
    text = str(raw or "").strip()
    if not text:
        return ""
    plus = text.startswith("+")
    digits = re.sub(r"\D", "", text)
    if len(digits) < 10:
        return ""
    return f"+{digits}" if plus else digits


def vendor_phone_from_detail(vendor_detail: Any) -> str:
    if not isinstance(vendor_detail, dict):
        return ""
    for key in _PHONE_KEYS:
        phone = normalize_vendor_phone(vendor_detail.get(key))
        if phone:
            return phone
    for nested_key in ("contact", "user", "profile"):
        nested = vendor_detail.get(nested_key)
        phone = vendor_phone_from_detail(nested) if isinstance(nested, dict) else ""
        if phone:
            return phone
    return ""

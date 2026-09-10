"""Vendor contact fields pulled from a quote payload.

Tatva does not use one field name. Phone/email may sit on `vendorDetail`,
a populated `vendorId` object, or a nested contact/profile. Empty means the
payload had no usable contact — vendor outreach must not invent one.

Never read `clientDetail`; that is the customer's address, not the vendor's.
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
    "company_phone",
)

_EMAIL_KEYS = (
    "email",
    "emailAddress",
    "emailId",
    "email_id",
    "vendorEmail",
    "vendor_email",
    "companyEmail",
    "company_email",
    "officialEmail",
    "contactEmail",
    "userEmail",
    "workEmail",
    "primaryEmail",
)

_VENDOR_BLOBS = ("vendorDetail", "vendorId", "vendor")
_NESTED_BLOBS = ("contact", "user", "profile", "company")

_EMAIL_RE = re.compile(
    r"^[A-Z0-9.!#$%&'*+/=?^_`{|}~-]+@[A-Z0-9](?:[A-Z0-9-]{0,61}[A-Z0-9])?"
    r"(?:\.[A-Z0-9](?:[A-Z0-9-]{0,61}[A-Z0-9])?)+$",
    re.I,
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


def normalize_vendor_email(raw: Any) -> str:
    email = str(raw or "").strip().lower()
    if not email or len(email) > 254 or not _EMAIL_RE.fullmatch(email):
        return ""
    return email


def vendor_phone_from_detail(vendor_detail: Any) -> str:
    return _first_from_mapping(vendor_detail, normalize_vendor_phone, _PHONE_KEYS)


def vendor_email_from_detail(vendor_detail: Any) -> str:
    email = _first_from_mapping(vendor_detail, normalize_vendor_email, _EMAIL_KEYS)
    if email:
        return email
    if not isinstance(vendor_detail, dict):
        return ""
    for key, value in vendor_detail.items():
        if "email" not in str(key).lower():
            continue
        email = normalize_vendor_email(value)
        if email:
            return email
    return ""


def vendor_phone_from_quote(quote_data: Any) -> str:
    for blob in _vendor_blobs(quote_data):
        phone = vendor_phone_from_detail(blob)
        if phone:
            return phone
    return ""


def vendor_email_from_quote(quote_data: Any) -> str:
    for blob in _vendor_blobs(quote_data):
        email = vendor_email_from_detail(blob)
        if email:
            return email
    return ""


def _vendor_blobs(quote_data: Any) -> list[dict]:
    if not isinstance(quote_data, dict):
        return []
    blobs: list[dict] = []
    seen: set[int] = set()
    for key in _VENDOR_BLOBS:
        value = quote_data.get(key)
        if isinstance(value, dict) and id(value) not in seen:
            seen.add(id(value))
            blobs.append(value)
    return blobs


def _first_from_mapping(obj: Any, normalize, keys: tuple[str, ...], depth: int = 0) -> str:
    if not isinstance(obj, dict) or depth > 4:
        return ""
    for key in keys:
        found = normalize(obj.get(key))
        if found:
            return found
    for nested_key in _NESTED_BLOBS:
        nested = obj.get(nested_key)
        found = _first_from_mapping(nested, normalize, keys, depth + 1)
        if found:
            return found
    return ""

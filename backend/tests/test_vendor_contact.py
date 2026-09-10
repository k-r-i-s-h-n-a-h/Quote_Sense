from services.vendor_contact import (
    normalize_vendor_email,
    normalize_vendor_phone,
    vendor_email_from_detail,
    vendor_email_from_quote,
    vendor_phone_from_detail,
    vendor_phone_from_quote,
)


def test_normalize_keeps_ten_digit_numbers():
    assert normalize_vendor_phone("98765 43210") == "9876543210"
    assert normalize_vendor_phone("+91 98765-43210") == "+919876543210"
    assert normalize_vendor_phone("123") == ""
    assert normalize_vendor_phone("") == ""


def test_reads_common_tatva_keys():
    assert vendor_phone_from_detail({"phoneNumber": "9876543210"}) == "9876543210"
    assert vendor_phone_from_detail({"mobile": "9876543210"}) == "9876543210"
    assert vendor_phone_from_detail({"contact": {"whatsappNumber": "9876543210"}}) == (
        "9876543210"
    )
    assert vendor_phone_from_detail({"companyName": "Acme"}) == ""


def test_normalize_vendor_email():
    assert normalize_vendor_email(" Sales@Example.COM ") == "sales@example.com"
    assert normalize_vendor_email("not-an-email") == ""
    assert normalize_vendor_email("") == ""


def test_reads_vendor_email_from_common_and_nested_keys():
    assert vendor_email_from_detail({"email": "sales@example.com"}) == (
        "sales@example.com"
    )
    assert vendor_email_from_detail(
        {"contact": {"emailAddress": "quotes@example.com"}}
    ) == "quotes@example.com"
    assert vendor_email_from_detail({"companyName": "Acme"}) == ""


def test_reads_contact_from_populated_vendor_id():
    quote = {
        "vendorDetail": {"companyName": "INFOSYS LIMITED", "phoneNumber": "9513158197"},
        "vendorId": {
            "_id": "abc",
            "companyEmail": "Vidya.M@tatvaops.com",
            "companyPhone": "9513158197",
        },
        "clientDetail": {"email": "customer@example.com"},
    }
    assert vendor_email_from_quote(quote) == "vidya.m@tatvaops.com"
    assert vendor_phone_from_quote(quote) == "9513158197"


def test_does_not_use_client_email():
    quote = {
        "vendorDetail": {"companyName": "INFOSYS LIMITED"},
        "clientDetail": {"email": "customer@example.com"},
    }
    assert vendor_email_from_quote(quote) == ""

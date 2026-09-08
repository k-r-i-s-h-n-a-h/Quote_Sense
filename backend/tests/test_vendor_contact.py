from services.vendor_contact import normalize_vendor_phone, vendor_phone_from_detail


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

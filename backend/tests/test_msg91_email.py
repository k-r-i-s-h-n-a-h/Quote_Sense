import pytest

from services.msg91_email import EmailSendError, build_email_body


def configure_email(monkeypatch):
    monkeypatch.setenv("MSG91_AUTH_KEY", "test-auth-key")
    monkeypatch.setenv(
        "MSG91_ASK_VENDOR_EMAIL_TEMPLATE",
        "tatvaops_quotesense_vendor_clarifications",
    )
    monkeypatch.setenv("MSG91_EMAIL_DOMAIN", "mail.withtatva.ai")
    monkeypatch.setenv("MSG91_EMAIL_FROM", "info@mail.withtatva.ai")
    monkeypatch.setenv("MSG91_EMAIL_FROM_NAME", "TatvaOps QuoteSense")
    monkeypatch.setenv("MSG91_EMAIL_REPLY_TO", "contact@withtatva.ai")


def test_build_email_body_keeps_variable_length_checklist(monkeypatch):
    configure_email(monkeypatch)
    body = build_email_body(
        email=" Quotes@Vendor.COM ",
        vendor_name="Example Vendor",
        quote_number="Q-123",
        questions=["Confirm GST.", "List package contents.", "Confirm warranty."],
        notes="Please reply by Friday.",
    )

    recipient = body["recipients"][0]
    assert recipient["to"] == [
        {"name": "Example Vendor", "email": "quotes@vendor.com"}
    ]
    assert recipient["variables"]["questions"] == [
        {"number": 1, "text": "Confirm GST."},
        {"number": 2, "text": "List package contents."},
        {"number": 3, "text": "Confirm warranty."},
    ]
    assert recipient["variables"]["question_count"] == 3
    assert recipient["variables"]["notes"] == "Please reply by Friday."
    assert recipient["variables"]["has_notes"] is True
    assert body["from"]["email"] == "info@mail.withtatva.ai"
    assert body["reply_to"] == [{"email": "contact@withtatva.ai"}]
    assert body["template_id"] == "tatvaops_quotesense_vendor_clarifications"


def test_empty_notes_are_valid(monkeypatch):
    configure_email(monkeypatch)
    body = build_email_body(
        email="quotes@vendor.com",
        vendor_name="Vendor",
        quote_number="Q-1",
        questions=["Confirm GST."],
    )
    variables = body["recipients"][0]["variables"]
    assert variables["notes"] == ""
    assert variables["has_notes"] is False
    assert variables["questions"] == [{"number": 1, "text": "Confirm GST."}]


def test_rejects_invalid_recipient(monkeypatch):
    configure_email(monkeypatch)
    with pytest.raises(EmailSendError, match="No usable vendor email"):
        build_email_body(
            email="not-an-email",
            vendor_name="Vendor",
            quote_number="Q-1",
            questions=["Confirm GST."],
        )


def test_defaults_to_approved_quotesense_template(monkeypatch):
    configure_email(monkeypatch)
    monkeypatch.delenv("MSG91_ASK_VENDOR_EMAIL_TEMPLATE")
    body = build_email_body(
        email="quotes@vendor.com",
        vendor_name="Vendor",
        quote_number="Q-1",
        questions=["Confirm GST."],
    )
    assert body["template_id"] == "tatvaops_quotesense_vendor_clarifications"
